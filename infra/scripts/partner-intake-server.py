#!/usr/bin/env python3
"""
Partner Intake Server for pepperoni.tatar/china
================================================
Receives form submissions from the /china page, writes to Google Sheets,
translates Chinese descriptions to Russian via Claude API (fallback: DeepSeek).

Run:  python3 partner-intake-server.py
Port: 5001 (proxied by nginx at /partner-submit)

Environment (set in /var/www/pepperoni/.env):
  GOOGLE_SHEET_ID          — existing sheet ID (optional — auto-detected)
  GOOGLE_SHEET_NAME        — sheet name to auto-create if no ID given
  GOOGLE_SERVICE_ACCOUNT   — path to service-account JSON key file
  CLAUDE_API_KEY           — Anthropic Claude API key (primary translation)
  DEEPSEEK_API_KEY         — DeepSeek API key (optional fallback)
"""

import os
import json
import logging
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, request, redirect
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "data" / "partner-catalogs"))
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".jpg", ".jpeg", ".png", ".zip"}
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_TOTAL_SIZE = 30 * 1024 * 1024

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Pepperoni Partners")
GOOGLE_SA_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT", str(BASE_DIR / "google-sa.json"))

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

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
# Google Sheets helpers (lazy init + auto-create)
# ---------------------------------------------------------------------------
_sheet = None

def _get_sheet():
    """Return the worksheet for partner data. Creates sheet/tab if needed."""
    global _sheet
    if _sheet is not None:
        return _sheet

    if not Path(GOOGLE_SA_PATH).exists():
        log.warning("Service account file not found: %s — Sheets disabled", GOOGLE_SA_PATH)
        return None

    try:
        import gspread
        gc = gspread.service_account(filename=GOOGLE_SA_PATH)

        if GOOGLE_SHEET_ID:
            # Use explicitly configured sheet
            sh = gc.open_by_key(GOOGLE_SHEET_ID)
        else:
            # Auto-find or create sheet by name
            try:
                sh = gc.open(GOOGLE_SHEET_NAME)
                log.info("Found existing sheet: %s", GOOGLE_SHEET_NAME)
            except gspread.SpreadsheetNotFound:
                sh = gc.create(GOOGLE_SHEET_NAME)
                log.info("Created new sheet: %s (ID: %s)", GOOGLE_SHEET_NAME, sh.id)
                # Share with yourself (the owner of the SA) — optional
                # The SA is the owner since it created the sheet

        # Use first worksheet (or specifically named one)
        try:
            _sheet = sh.worksheet("Submissions")
        except gspread.WorksheetNotFound:
            _sheet = sh.sheet1
            _sheet.update_title("Submissions")
            # Write header row if sheet is empty
            if not _sheet.get_all_values():
                _sheet.append_row([
                    "Timestamp", "Company Name", "Website", "Contact Person",
                    "Position", "WeChat ID", "Email", "Phone", "Category",
                    "Description (Original)", "Description (Russian)",
                    "Notes", "Catalog Files"
                ])

        log.info("Connected: sheet=%s tab=%s", sh.title, _sheet.title)
        return _sheet
    except Exception as exc:
        log.error("Google Sheets error: %s", exc)
        return None


def _append_row(data: list):
    """Append a row to the sheet. Returns True on success."""
    sheet = _get_sheet()
    if sheet is None:
        log.warning("Sheet unavailable; row NOT saved.")
        return False
    try:
        sheet.append_row(data, value_input_option="USER_ENTERED")
        log.info("Row appended to sheet.")
        return True
    except Exception as exc:
        log.error("Sheet append failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Translation (Claude primary, DeepSeek fallback)
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

def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf" for ch in text)


def _translate_via_claude(text: str) -> str:
    """Translate using Anthropic Claude API."""
    from anthropic import Anthropic
    client = Anthropic(api_key=CLAUDE_API_KEY)
    prompt = TRANSLATION_PROMPT.format(text=text[:4000])
    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def _translate_via_deepseek(text: str) -> str:
    """Translate using DeepSeek API (OpenAI-compatible)."""
    from openai import OpenAI
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")
    prompt = TRANSLATION_PROMPT.format(text=text[:4000])
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=2000,
    )
    return resp.choices[0].message.content.strip()


def translate_text(text: str) -> str:
    """Translate Chinese → Russian. Tries Claude, then DeepSeek."""
    if not text or not text.strip():
        return text
    if not _has_cjk(text):
        log.info("No CJK characters; skipping translation.")
        return text

    # Try Claude first
    if CLAUDE_API_KEY:
        try:
            result = _translate_via_claude(text)
            log.info("Translated via Claude (%d → %d chars)", len(text), len(result))
            return result
        except Exception as exc:
            log.warning("Claude translation failed: %s", exc)

    # Fallback to DeepSeek
    if DEEPSEEK_API_KEY:
        try:
            result = _translate_via_deepseek(text)
            log.info("Translated via DeepSeek (%d → %d chars)", len(text), len(result))
            return result
        except Exception as exc:
            log.warning("DeepSeek translation failed: %s", exc)

    log.warning("No translation API keys configured — returning original.")
    return text


# ---------------------------------------------------------------------------
# File handling
# ---------------------------------------------------------------------------
def _safe_filename(original: str) -> str:
    name = secure_filename(original)
    if not name:
        name = "catalog"
    stem, ext = os.path.splitext(name)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short_hash = hashlib.md5(f"{original}{time.time()}".encode()).hexdigest()[:6]
    return f"{stem}_{ts}_{short_hash}{ext}"


def _save_files(files) -> list:
    saved = []
    total_size = 0
    if not files:
        return saved
    uploaded = request.files.getlist("catalog")
    for f in uploaded:
        if not f or not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0)
        if size > MAX_FILE_SIZE or total_size + size > MAX_TOTAL_SIZE:
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

    file_paths = _save_files(request.files)
    file_links = "\n".join(file_paths) if file_paths else ""

    translated = translate_text(description) if description else ""

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    row = [
        now_utc, company, website, contact, position,
        wechat, email, phone, category,
        description, translated, notes, file_links,
    ]
    _append_row(row)

    return redirect("https://pepperoni.tatar/china?thanks=1", code=302)


@app.route("/partner-submit", methods=["GET", "HEAD"])
def partner_submit_get():
    return "Partner intake endpoint is live. Please POST your form here.", 200


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    log.info("Starting partner-intake server on port %d", port)
    log.info("Upload dir: %s", UPLOAD_DIR)
    log.info("Sheets:     %s", GOOGLE_SHEET_ID or f"auto (name: {GOOGLE_SHEET_NAME})")
    log.info("Claude:     %s", "enabled" if CLAUDE_API_KEY else "(not set)")
    log.info("DeepSeek:   %s", "enabled" if DEEPSEEK_API_KEY else "(not set)")
    app.run(host="127.0.0.1", port=port, debug=False)
