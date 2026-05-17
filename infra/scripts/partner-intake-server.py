#!/usr/bin/env python3
"""
Partner Intake Server for pepperoni.tatar/china
================================================
Receives form submissions from the /china page, writes to Google Sheets,
translates Chinese descriptions to Russian via DeepSeek API, stores uploaded
catalog files.

Run:  python3 partner-intake-server.py
Port: 5001 (proxied by nginx at /partner-submit)

Environment variables (set in /opt/pepperoni-api/.env):
  GOOGLE_SHEET_ID          — Google Sheet ID (from sheet URL)
  GOOGLE_SERVICE_ACCOUNT   — path to service-account JSON key file
  DEEPSEEK_API_KEY         — DeepSeek API key
  UPLOAD_DIR               — directory for uploaded files (default: ./uploads)
"""

import os
import json
import logging
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, request, redirect
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Config (from environment or defaults)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent  # /opt/pepperoni-api/infra/..
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "data" / "partner-catalogs"))
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".jpg", ".jpeg", ".png", ".zip"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file
MAX_TOTAL_SIZE = 30 * 1024 * 1024  # 30 MB total per submission

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Google Sheets config
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_SA_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT", str(BASE_DIR / "google-sa.json"))

# DeepSeek API config
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("partner-intake")

# ---------------------------------------------------------------------------
# Google Sheets helpers (lazy init)
# ---------------------------------------------------------------------------
_sheet = None

def _get_sheet():
    """Return the first worksheet of the configured Google Sheet."""
    global _sheet
    if _sheet is not None:
        return _sheet

    if not GOOGLE_SHEET_ID:
        log.warning("GOOGLE_SHEET_ID not set — Sheets integration disabled")
        return None

    try:
        import gspread
        gc = gspread.service_account(filename=GOOGLE_SA_PATH)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        _sheet = sh.sheet1
        log.info("Connected to Google Sheet: %s", _sheet.title)
        return _sheet
    except Exception as exc:
        log.error("Failed to connect to Google Sheets: %s", exc)
        return None


def _append_row(data: list):
    """Append a row to the sheet. Silently skip if Sheets is unavailable."""
    sheet = _get_sheet()
    if sheet is None:
        log.warning("Sheet not available; row NOT saved.")
        return False
    try:
        sheet.append_row(data, value_input_option="USER_ENTERED")
        log.info("Row appended to sheet.")
        return True
    except Exception as exc:
        log.error("Sheet append failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# DeepSeek translation helper
# ---------------------------------------------------------------------------
TRANSLATION_PROMPT = """You are a professional translator for a Russian halal meat manufacturer (Kazan Delicacies).
Translate the following text from Chinese to Russian. Follow these rules:
1. Preserve all product names, technical terms, and numbers exactly.
2. If the text appears to be a company or product description, translate it naturally.
3. If the text is mixed Chinese/English, keep English terms but translate Chinese.
4. Return ONLY the Russian translation, no explanations, no notes.
5. If the input is empty or contains no Chinese, return it unchanged.

Text to translate:
---
{text}
---
"""

def translate_text(text: str) -> str:
    """Translate Chinese text to Russian via DeepSeek API."""
    if not text or not text.strip():
        return text
    if not DEEPSEEK_API_KEY:
        log.warning("DEEPSEEK_API_KEY not set — translation skipped")
        return text

    # Quick check: if no CJK characters, skip
    has_cjk = any("\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf" for ch in text)
    if not has_cjk:
        log.info("No CJK characters detected; skipping translation.")
        return text

    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

        prompt = TRANSLATION_PROMPT.format(text=text[:4000])  # limit to avoid huge requests

        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2000,
        )
        translated = resp.choices[0].message.content.strip()
        log.info("Translation successful (%d → %d chars)", len(text), len(translated))
        return translated
    except Exception as exc:
        log.error("Translation failed: %s", exc)
        return text  # fallback: return original


# ---------------------------------------------------------------------------
# File handling
# ---------------------------------------------------------------------------
def _safe_filename(original: str) -> str:
    """Generate a safe, unique filename."""
    name = secure_filename(original)
    if not name:
        name = "catalog"
    stem, ext = os.path.splitext(name)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short_hash = hashlib.md5(f"{original}{time.time()}".encode()).hexdigest()[:6]
    return f"{stem}_{ts}_{short_hash}{ext}"


def _save_files(files) -> list:
    """Save uploaded files, return list of relative paths."""
    saved = []
    total_size = 0

    if not files:
        return saved

    # Group by field name; Formspree sends as 'catalog' (single or multiple)
    uploaded = request.files.getlist("catalog")

    for f in uploaded:
        if not f or not f.filename:
            continue

        # Validate extension
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            log.warning("Rejected file type: %s", f.filename)
            continue

        # Validate size (read into memory to measure)
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0)

        if size > MAX_FILE_SIZE:
            log.warning("File too large (%d bytes): %s", size, f.filename)
            continue
        if total_size + size > MAX_TOTAL_SIZE:
            log.warning("Total upload size exceeded; skipping %s", f.filename)
            continue

        filename = _safe_filename(f.filename)
        dest = UPLOAD_DIR / filename
        f.save(str(dest))
        total_size += size
        saved.append(str(dest))
        log.info("Saved: %s (%d bytes)", filename, size)

    return saved


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)

@app.route("/partner-submit", methods=["POST"])
def partner_submit():
    log.info("=" * 50)
    log.info("New submission from %s", request.remote_addr)

    # --- 1. Gather form fields ---
    company     = (request.form.get("company") or "").strip()
    website     = (request.form.get("website") or "").strip()
    contact     = (request.form.get("contact_name") or "").strip()
    position    = (request.form.get("position") or "").strip()
    wechat      = (request.form.get("wechat") or "").strip()
    email       = (request.form.get("email") or "").strip()
    phone       = (request.form.get("phone") or "").strip()
    category    = (request.form.get("category") or "").strip()
    description = (request.form.get("description") or "").strip()
    notes       = (request.form.get("notes") or "").strip()

    log.info("Company: %s | WeChat: %s | Category: %s", company, wechat, category)

    # --- 2. Save uploaded files ---
    file_paths = _save_files(request.files)
    file_links = "\n".join(file_paths) if file_paths else ""

    # --- 3. Translate description ---
    translated = ""
    if description:
        log.info("Translating description (%d chars)...", len(description))
        translated = translate_text(description)
    else:
        translated = ""

    # --- 4. Write to Google Sheets ---
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    row = [
        now_utc,       # A: Timestamp
        company,       # B: Company Name
        website,       # C: Website
        contact,       # D: Contact Person
        position,      # E: Position
        wechat,        # F: WeChat ID
        email,         # G: Email
        phone,         # H: Phone
        category,      # I: Category
        description,   # J: Description (original)
        translated,    # K: Description (Russian translation)
        notes,         # L: Notes / How we met
        file_links,    # M: Catalog file paths
    ]
    _append_row(row)

    # --- 5. Redirect to success page ---
    thanks_url = "https://pepperoni.tatar/china?thanks=1"
    log.info("Redirecting to %s", thanks_url)
    return redirect(thanks_url, code=302)


@app.route("/partner-submit", methods=["GET", "HEAD"])
def partner_submit_get():
    """Health-check / friendly message for GET requests."""
    return "Partner intake endpoint is live. Please POST your form here.", 200


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    log.info("Starting partner-intake server on port %d", port)
    log.info("Upload dir: %s", UPLOAD_DIR)
    log.info("Sheets ID: %s", GOOGLE_SHEET_ID or "(not set)")
    log.info("DeepSeek:  %s", "enabled" if DEEPSEEK_API_KEY else "(not set)")
    app.run(host="127.0.0.1", port=port, debug=False)
