#!/usr/bin/env python3
"""Core Web Vitals monitor — lab (PSI/Lighthouse) + field (CrUX via PSI).

Samples ONE URL per template (not the whole site). Prefers PageSpeed Insights
API when PAGESPEED_API_KEY is set (needed for CrUX field metrics + higher
quota). Falls back to local `npx lighthouse` for lab-only when PSI is missing
or rate-limited.

Self-gated: skips unless data/cwv.json is older than CWV_REFRESH_DAYS (7),
unless --force. Writes data/cwv.json for the brain digest.

Usage:
  python3 scripts/core_web_vitals.py [--force] [--setup-key]
Env:
  PAGESPEED_API_KEY   Google Cloud API key with PageSpeed Insights API enabled
  CWV_REFRESH_DAYS    default 7
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
OUT = DATA / "cwv.json"
BASE = "https://pepperoni.tatar"
PSI_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
REFRESH_DAYS = int(os.environ.get("CWV_REFRESH_DAYS", "7"))
API_KEY = os.environ.get("PAGESPEED_API_KEY", "").strip()

# Post geo-cleanup samples (2026-07-23). Paths must exist on prod.
SAMPLES = {
    "home": "/",
    "catalog": "/pepperoni",
    "product": "/products/kd-001",
    "commercial": "/private-label/kotlety-dlya-burgerov-optom",
    "blog": "/blog/kazylyk-chto-eto-takoe",
    "geo_keep": "/geo/kazylyk-premium-kazan",
    "export": "/export/uae",
    "oem": "/dlya-distributorov",
    "experiment_x": "/x",
}

# Google "good" thresholds (field / lab).
THRESH = {"LCP": 2500, "CLS": 0.1, "INP": 200}

SETUP_KEY_HELP = """
=== Setup PAGESPEED_API_KEY (2 min, once) ===
1. Open https://console.cloud.google.com/apis/credentials?project=pepperoni-seo
2. Enable APIs:
   - PageSpeed Insights API
   - Chrome UX Report API  (optional; PSI already embeds CrUX field)
3. Create credentials → API key → restrict to those APIs (HTTP referrer optional).
4. On VPS:
   echo 'PAGESPEED_API_KEY=AIza...' >> /var/www/pepperoni/seo-agent.env
5. Re-run:  cd /var/www/pepperoni/repo && set -a; . /var/www/pepperoni/seo-agent.env; set +a
            python3 scripts/core_web_vitals.py --force
Field CrUX (ranking signal) only appears when the API key works.
"""


def _stale() -> bool:
    try:
        age_days = (datetime.now(timezone.utc).timestamp() - OUT.stat().st_mtime) / 86400
        return age_days >= REFRESH_DAYS
    except OSError:
        return True


def _field_block(experience: dict | None) -> dict | None:
    if not experience:
        return None
    metrics = experience.get("metrics") or {}
    if not metrics:
        return None

    def one(key: str) -> dict | None:
        m = metrics.get(key) or {}
        if not m:
            return None
        return {"p75": m.get("percentile"), "category": m.get("category")}

    return {
        "overall": experience.get("overall_category"),
        "LCP": one("LARGEST_CONTENTFUL_PAINT_MS"),
        "INP": one("INTERACTION_TO_NEXT_PAINT"),
        "CLS": one("CUMULATIVE_LAYOUT_SHIFT_SCORE"),
        "FCP": one("FIRST_CONTENTFUL_PAINT_MS"),
    }


def _flags(lcp, cls, inp) -> list[str]:
    flags = []
    if lcp is not None and lcp > THRESH["LCP"]:
        flags.append("slow_LCP")
    if cls is not None and cls > THRESH["CLS"]:
        flags.append("layout_shift")
    if inp is not None and inp > THRESH["INP"]:
        flags.append("slow_INP")
    return flags


def _probe_psi(path: str) -> dict:
    url = BASE + path
    params = {"url": url, "strategy": "mobile", "category": "performance"}
    if API_KEY:
        params["key"] = API_KEY
    full = f"{PSI_API}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(full, headers={"User-Agent": "pepperoni-cwv/2"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read()[:160].decode("utf-8", "replace")
        return {"url": url, "source": "psi", "error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"url": url, "source": "psi", "error": str(e)[:160]}

    lr = data.get("lighthouseResult") or {}
    audits = lr.get("audits") or {}
    perf = (lr.get("categories", {}).get("performance") or {}).get("score")

    def num(aid: str):
        return (audits.get(aid) or {}).get("numericValue")

    lcp = num("largest-contentful-paint")
    cls = num("cumulative-layout-shift")
    inp = num("interaction-to-next-paint") or num("experimental-interaction-to-next-paint")
    unsized = (audits.get("unsized-images") or {}).get("score")

    return {
        "url": url,
        "source": "psi",
        "perf_score": round(perf * 100) if perf is not None else None,
        "LCP_ms": round(lcp) if lcp is not None else None,
        "CLS": round(cls, 3) if cls is not None else None,
        "INP_ms": round(inp) if inp is not None else None,
        "unsized_images_ok": unsized == 1 if unsized is not None else None,
        "flags": _flags(lcp, cls, inp),
        "field_url": _field_block(data.get("loadingExperience")),
        "field_origin": _field_block(data.get("originLoadingExperience")),
    }


def _probe_lighthouse(path: str) -> dict:
    """Lab-only fallback when PSI key missing / 429."""
    url = BASE + path
    npx = shutil.which("npx")
    if not npx:
        return {"url": url, "source": "lighthouse", "error": "npx not available"}
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out_path = tmp.name
    try:
        cmd = [
            npx, "--yes", "lighthouse@12.2.1", url,
            "--only-categories=performance",
            "--form-factor=mobile",
            "--chrome-flags=--headless --no-sandbox --disable-gpu",
            "--quiet",
            "--output=json",
            f"--output-path={out_path}",
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
        data = json.loads(Path(out_path).read_text(encoding="utf-8"))
    except Exception as e:
        return {"url": url, "source": "lighthouse", "error": str(e)[:160]}
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass

    audits = data.get("audits") or {}
    perf = (data.get("categories", {}).get("performance") or {}).get("score")

    def num(aid: str):
        return (audits.get(aid) or {}).get("numericValue")

    lcp = num("largest-contentful-paint")
    cls = num("cumulative-layout-shift")
    inp = num("interaction-to-next-paint")
    unsized = (audits.get("unsized-images") or {}).get("score")
    return {
        "url": url,
        "source": "lighthouse",
        "perf_score": round(perf * 100) if perf is not None else None,
        "LCP_ms": round(lcp) if lcp is not None else None,
        "CLS": round(cls, 3) if cls is not None else None,
        "INP_ms": round(inp) if inp is not None else None,
        "unsized_images_ok": unsized == 1 if unsized is not None else None,
        "flags": _flags(lcp, cls, inp),
        "field_url": None,
        "field_origin": None,
    }


def _probe(path: str) -> dict:
    if API_KEY:
        r = _probe_psi(path)
        if not r.get("error"):
            return r
        # fall through to lighthouse on quota / transient errors
        print(f"    psi miss → lighthouse ({r.get('error', '')[:60]})")
    elif not API_KEY:
        # Try PSI without key once; on 429 use lighthouse
        r = _probe_psi(path)
        if not r.get("error"):
            return r
        if "429" in (r.get("error") or "") or "403" in (r.get("error") or ""):
            return _probe_lighthouse(path)
        return r
    return _probe_lighthouse(path)


def brain_summary() -> dict:
    """Compact view for seo_brain digest."""
    try:
        r = json.loads(OUT.read_text(encoding="utf-8"))
        tmpl = r.get("templates", {})
        slow = {k: v for k, v in tmpl.items() if v.get("flags")}
        scores = [v["perf_score"] for v in tmpl.values() if v.get("perf_score") is not None]
        origin = None
        for v in tmpl.values():
            if v.get("field_origin"):
                origin = v["field_origin"]
                break
        return {
            "checked_at": r.get("generated_at", "")[:10],
            "source": r.get("source_mode"),
            "avg_perf_score": round(sum(scores) / len(scores)) if scores else None,
            "slow_templates": {k: v.get("flags") for k, v in slow.items()},
            "field_origin_overall": (origin or {}).get("overall"),
            "worst": min(
                tmpl.items(),
                key=lambda kv: kv[1].get("perf_score") or 101,
                default=(None, {}),
            )[0],
        }
    except Exception:
        return {}


def main() -> int:
    if "--setup-key" in sys.argv:
        print(SETUP_KEY_HELP)
        return 0

    force = "--force" in sys.argv
    if not force and not _stale():
        print(f"cwv: свежо (< {REFRESH_DAYS}д), пропуск")
        return 0

    mode = "psi+key" if API_KEY else "psi-anon|lighthouse-fallback"
    if not API_KEY:
        print("cwv: PAGESPEED_API_KEY не задан → lab via Lighthouse; field CrUX недоступен")
        print("     python3 scripts/core_web_vitals.py --setup-key")

    results = {}
    origin_field = None
    for name, path in SAMPLES.items():
        print(f"  probing {name} ({path}) …", flush=True)
        results[name] = _probe(path)
        row = results[name]
        if row.get("field_origin") and not origin_field:
            origin_field = row["field_origin"]
        print(
            f"  {name:<12} score={row.get('perf_score', '?')} "
            f"LCP={row.get('LCP_ms')} CLS={row.get('CLS')} "
            f"src={row.get('source')} {row.get('flags') or row.get('error') or 'ok'}",
            flush=True,
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_mode": mode,
        "has_api_key": bool(API_KEY),
        "field_origin": origin_field,
        "templates": results,
        "thresholds": THRESH,
    }
    DATA.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    slow = sum(1 for v in results.values() if v.get("flags"))
    errors = sum(1 for v in results.values() if v.get("error"))
    print(f"⚡ CWV: {len(results)} templates, slow={slow}, errors={errors}, wrote {OUT}")
    if origin_field:
        print(f"   field origin overall={origin_field.get('overall')} "
              f"LCP_p75={((origin_field.get('LCP') or {}).get('p75'))} "
              f"INP_p75={((origin_field.get('INP') or {}).get('p75'))}")
    elif not API_KEY:
        print("   field: нет (нужен PAGESPEED_API_KEY) — см. --setup-key")
    return 0 if errors < len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
