#!/usr/bin/env python3
"""Core Web Vitals monitor — the brain's eye on page speed (a Google ranking factor).

Calls Google PageSpeed Insights API for ONE representative URL per page template
(home, product, blog, geo, export, OEM) — not all 4000+ pages — so the brain sees
whether each section is fast or slow without burning quota. Works without an API
key (lower rate limit); set PAGESPEED_API_KEY for higher limits.

Self-gated: exits early unless data/cwv.json is older than CWV_REFRESH_DAYS (7),
so it costs almost nothing day-to-day. Writes data/cwv.json for the brain digest.

Usage: python3 scripts/core_web_vitals.py [--force]
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
OUT = DATA / "cwv.json"
BASE = "https://pepperoni.tatar"
API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
REFRESH_DAYS = int(os.environ.get("CWV_REFRESH_DAYS", "7"))
API_KEY = os.environ.get("PAGESPEED_API_KEY", "").strip()

# One representative URL per template. Edit paths if structure changes.
SAMPLES = {
    "home": "/",
    "product": "/products/kd-001",
    "blog": "/blog/kazylyk-chto-eto-takoe",
    "geo": "/geo/sosiki-dlya-hotdog-moskva",
    "export": "/export/uae",
    "oem": "/dlya-distributorov.html",
}
# Core Web Vitals thresholds (Google "good"): LCP<2.5s, CLS<0.1, INP<200ms.
THRESH = {"LCP": 2500, "CLS": 0.1, "INP": 200}


def _stale() -> bool:
    try:
        age_days = (datetime.now(timezone.utc).timestamp() - OUT.stat().st_mtime) / 86400
        return age_days >= REFRESH_DAYS
    except OSError:
        return True


def _probe(path: str) -> dict:
    url = BASE + path
    params = {"url": url, "strategy": "mobile",
              "category": "performance"}
    if API_KEY:
        params["key"] = API_KEY
    full = f"{API}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(full, headers={"User-Agent": "pepperoni-cwv/1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return {"url": url, "error": str(e)[:120]}
    lr = data.get("lighthouseResult", {})
    audits = lr.get("audits", {})
    perf = (lr.get("categories", {}).get("performance", {}) or {}).get("score")

    def _num(audit_id):
        return (audits.get(audit_id, {}) or {}).get("numericValue")

    lcp = _num("largest-contentful-paint")
    cls = _num("cumulative-layout-shift")
    inp = _num("interaction-to-next-paint") or _num("experimental-interaction-to-next-paint")
    flags = []
    if lcp and lcp > THRESH["LCP"]:
        flags.append("slow_LCP")
    if cls and cls > THRESH["CLS"]:
        flags.append("layout_shift")
    if inp and inp > THRESH["INP"]:
        flags.append("slow_INP")
    return {
        "url": url,
        "perf_score": round(perf * 100) if perf is not None else None,
        "LCP_ms": round(lcp) if lcp else None,
        "CLS": round(cls, 3) if cls is not None else None,
        "INP_ms": round(inp) if inp else None,
        "flags": flags,
    }


def brain_summary() -> dict:
    """Compact view for seo_brain digest."""
    try:
        r = json.loads(OUT.read_text())
        tmpl = r.get("templates", {})
        slow = {k: v for k, v in tmpl.items() if v.get("flags")}
        scores = [v["perf_score"] for v in tmpl.values() if v.get("perf_score") is not None]
        return {
            "checked_at": r.get("generated_at", "")[:10],
            "avg_perf_score": round(sum(scores) / len(scores)) if scores else None,
            "slow_templates": {k: v.get("flags") for k, v in slow.items()},
            "worst": min(tmpl.items(), key=lambda kv: kv[1].get("perf_score") or 101,
                         default=(None, {}))[0],
        }
    except Exception:
        return {}


def main() -> int:
    force = "--force" in sys.argv
    if not force and not _stale():
        print(f"cwv: свежо (< {REFRESH_DAYS}д), пропуск")
        return 0
    results = {}
    for name, path in SAMPLES.items():
        results[name] = _probe(path)
        print(f"  {name:<8} {results[name].get('perf_score','?')}  "
              f"{results[name].get('flags') or 'ok'}")
    report = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "templates": results}
    DATA.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    slow = sum(1 for v in results.values() if v.get("flags"))
    print(f"⚡ CWV: проверено {len(results)} шаблонов, медленных {slow}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
