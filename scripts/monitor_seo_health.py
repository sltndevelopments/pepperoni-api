#!/usr/bin/env python3
"""
SEO health monitor — runs daily, finds structured-data / rich-result problems
and sends a summary to the Telegram bot (all authorized chats).

Two layers:
  1) LOCAL validator — scans every generated HTML page's JSON-LD for problems
     (invalid GTIN, broken JSON, missing required Product/Offer fields, etc.).
     Catches issues BEFORE Google sees them. Free, no quota.
  2) URL Inspection API — inspects a small sample of key pages and reads
     Google's own richResultsResult verdict. Reflects what Google actually sees.

Writes a snapshot to data/seo_health.json and (unless --no-telegram) sends a
digest to Telegram. Designed to be cron-friendly and dependency-light.

Env: GSC_SERVICE_ACCOUNT_KEY (or _B64), TELEGRAM_BOT_TOKEN
Usage:
    python3 scripts/monitor_seo_health.py            # full run + telegram
    python3 scripts/monitor_seo_health.py --no-telegram
    python3 scripts/monitor_seo_health.py --no-gsc   # local validator only
"""

import json
import os
import re
import sys
import glob
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"
DATA = ROOT / "data"
SNAPSHOT = DATA / "seo_health.json"
SITE = "https://pepperoni.tatar"
SITE_URL_GSC = "sc-domain:pepperoni.tatar"

# How many key pages to inspect via the (quota-limited) URL Inspection API.
GSC_SAMPLE = int(os.environ.get("SEO_GSC_SAMPLE", "12"))


# ── Layer 1: local JSON-LD validator ─────────────────────────────────────────────
def _gtin_ok(s: str) -> bool:
    s = str(s or "").strip()
    if not s or not s.isdigit() or len(s) not in (8, 12, 13, 14):
        return False
    digits = [int(c) for c in s]
    body = digits[:-1][::-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(body))
    return (10 - (total % 10)) % 10 == digits[-1]


JSONLD_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
    re.S | re.I,
)


def _iter_jsonld(html: str):
    for m in JSONLD_RE.finditer(html):
        raw = m.group(1).strip()
        try:
            yield json.loads(raw), None
        except Exception as e:
            yield None, f"{type(e).__name__}: {e}"


def validate_page(path: Path) -> list:
    """Return a list of problem strings for one HTML file."""
    problems = []
    try:
        html = path.read_text(errors="ignore")
    except Exception as e:
        return [f"unreadable: {e}"]

    for obj, err in _iter_jsonld(html):
        if err:
            problems.append(f"broken JSON-LD ({err})")
            continue
        nodes = obj if isinstance(obj, list) else [obj]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("@type") == "Product":
                gtin = node.get("gtin13") or node.get("gtin") or node.get("gtin12") or node.get("gtin14")
                if "gtin13" in node and not _gtin_ok(node.get("gtin13")):
                    problems.append(f"invalid GTIN '{node.get('gtin13')}'")
                if not node.get("name"):
                    problems.append("Product missing name")
                offers = node.get("offers")
                if isinstance(offers, dict):
                    if not offers.get("price"):
                        problems.append("Offer missing price")
                    if not offers.get("priceCurrency"):
                        problems.append("Offer missing priceCurrency")
    return problems


def run_local_validator() -> dict:
    targets = []
    for pat in ("products/*.html", "en/products/*.html",
                "*.html", "en/*.html"):
        targets += glob.glob(str(PUBLIC / pat))
    targets = sorted(set(targets))

    issues = {}          # issue message -> count
    pages_with_issues = []
    for fp in targets:
        probs = validate_page(Path(fp))
        if probs:
            rel = os.path.relpath(fp, PUBLIC)
            pages_with_issues.append({"page": rel, "problems": probs})
            for p in probs:
                key = re.sub(r"'[^']*'", "'…'", p)  # normalize values for grouping
                issues[key] = issues.get(key, 0) + 1
    return {
        "scanned": len(targets),
        "pages_with_issues": pages_with_issues,
        "issue_counts": issues,
    }


# ── Layer 2: GSC URL Inspection API ──────────────────────────────────────────────
def _sample_urls() -> list:
    urls = [
        f"{SITE}/", f"{SITE}/en/", f"{SITE}/halal", f"{SITE}/export",
        f"{SITE}/about", f"{SITE}/pepperoni",
    ]
    prod = sorted(glob.glob(str(PUBLIC / "products" / "kd-*.html")))
    for fp in prod[: max(0, GSC_SAMPLE - len(urls))]:
        slug = Path(fp).stem
        urls.append(f"{SITE}/products/{slug}")
    return urls[:GSC_SAMPLE]


def run_gsc_inspection() -> dict:
    try:
        from fetch_gsc_queries import _load_gsc_key, get_access_token
    except Exception as e:
        return {"error": f"cannot import GSC auth: {e}"}
    sa_raw = _load_gsc_key()
    if not sa_raw:
        return {"error": "GSC key not set"}
    try:
        token = get_access_token(json.loads(sa_raw))
    except Exception as e:
        return {"error": f"auth failed: {e}"}

    findings = []
    checked = 0
    for url in _sample_urls():
        body = json.dumps({
            "inspectionUrl": url,
            "siteUrl": SITE_URL_GSC,
        }).encode()
        req = urllib.request.Request(
            "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
            data=body,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.loads(r.read())
            checked += 1
        except urllib.error.HTTPError as e:
            findings.append({"url": url, "error": f"HTTP {e.code}"})
            continue
        except Exception as e:
            findings.append({"url": url, "error": str(e)})
            continue

        rr = (res.get("inspectionResult", {}) or {}).get("richResultsResult", {})
        for det in rr.get("detectedItems", []) or []:
            rtype = det.get("richResultType", "?")
            for item in det.get("items", []) or []:
                for iss in item.get("issues", []) or []:
                    if iss.get("severity") in ("ERROR", "WARNING"):
                        findings.append({
                            "url": url,
                            "type": rtype,
                            "severity": iss.get("severity"),
                            "message": iss.get("issueMessage", ""),
                        })
    return {"checked": checked, "findings": findings}


# ── Reporting ────────────────────────────────────────────────────────────────────
def build_report(local: dict, gsc: dict) -> str:
    lines = ["<b>🩺 SEO health — структурированные данные</b>"]

    lic = local.get("issue_counts", {})
    if lic:
        lines.append(f"\n<b>Локальная проверка</b> ({local['scanned']} стр.):")
        for msg, n in sorted(lic.items(), key=lambda x: -x[1]):
            lines.append(f"  ⚠️ {msg} — <b>{n}</b> стр.")
    else:
        lines.append(f"\n✅ Локально чисто ({local['scanned']} стр.)")

    if "error" in gsc:
        lines.append(f"\n<b>Google (URL Inspection):</b> ⏭ {gsc['error']}")
    else:
        gf = gsc.get("findings", [])
        real = [f for f in gf if "message" in f]
        if real:
            lines.append(f"\n<b>Google видит</b> ({gsc.get('checked',0)} стр.):")
            seen = {}
            for f in real:
                k = f"{f['severity']}: {f['message']} [{f['type']}]"
                seen[k] = seen.get(k, 0) + 1
            for k, n in sorted(seen.items(), key=lambda x: -x[1])[:10]:
                icon = "🔴" if k.startswith("ERROR") else "🟡"
                lines.append(f"  {icon} {k} — {n}")
        else:
            lines.append(f"\n✅ Google: проблем не видит ({gsc.get('checked',0)} стр.)")

    lines.append("\n<i>Если есть проблемы шаблона — напиши «почини schema», "
                 "мозг проанализирует и исправит генератор.</i>")
    return "\n".join(lines)


def send_to_telegram(text: str) -> None:
    try:
        from telegram_notify import notify
        notify(text)
    except Exception as e:
        print(f"⏭ telegram unavailable: {e}", file=sys.stderr)


def main():
    args = set(sys.argv[1:])
    local = run_local_validator()
    gsc = {} if "--no-gsc" in args else run_gsc_inspection()

    snapshot = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "local": local,
        "gsc": gsc,
    }
    try:
        DATA.mkdir(exist_ok=True)
        SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1))
    except Exception as e:
        print(f"⚠️ snapshot write failed: {e}", file=sys.stderr)

    report = build_report(local, gsc if gsc else {"error": "skipped"})
    if "--raw-report" in args:
        # Emit HTML-formatted report for the Telegram bot to forward verbatim.
        print(report)
    else:
        print(report.replace("<b>", "").replace("</b>", "")
                    .replace("<i>", "").replace("</i>", ""))

    if "--no-telegram" not in args:
        # Only ping Telegram if there is something worth reporting, OR always on
        # explicit request. Default: send only when issues exist to avoid noise.
        has_issues = bool(local.get("issue_counts")) or bool(
            [f for f in gsc.get("findings", []) if "message" in f]
        )
        if has_issues or "--always" in args:
            send_to_telegram(report)
        else:
            print("✅ no issues — telegram digest skipped (use --always to force)")


if __name__ == "__main__":
    main()
