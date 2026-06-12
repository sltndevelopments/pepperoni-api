#!/usr/bin/env python3
"""Fetch behaviour & conversion data from Yandex Metrika — Fable's "eyes" on
what people actually DO on the site (not just search impressions).

Metrika is already installed on the site (counter 107064141) with goals:
  • click_phone  — tel: click  (a B2B lead signal)
  • click_email  — mailto: click (a B2B lead signal)
  • play_video   — engagement

This pulls a compact daily snapshot the brain reads each cycle:
  • visits / users / bounce / depth / avg time (last 30 days)
  • traffic sources split (search / direct / referral / social / ads)
  • top landing pages by visits (where people actually enter)
  • goal completions = LEADS (phone/email clicks) and which pages drive them

Auth: Yandex OAuth token with `metrika:read` scope. Tries
YANDEX_METRIKA_TOKEN first, then falls back to YANDEX_WM_TOKEN (same OAuth
system — often issued with broad scope). Counter id from YANDEX_METRIKA_COUNTER
(default 107064141).

Output: data/metrika.json  (read by seo_brain.py digest + the Telegram chat).
Never raises fatally — on any error it writes a stub with an "error" field so
the brain knows analytics is temporarily unavailable rather than crashing.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
OUT = DATA / "metrika.json"

COUNTER = os.environ.get("YANDEX_METRIKA_COUNTER", "107064141")
DAYS_BACK = int(os.environ.get("METRIKA_DAYS_BACK", "30"))
API = "https://api-metrika.yandex.net/stat/v1/data"

# Goal names → IDs are resolved at runtime; we match by the goal NAME the site
# uses so a goal-id change in Metrika never breaks this.
LEAD_GOAL_NAMES = {"click_phone", "click_email"}


def _token() -> str:
    for var in ("YANDEX_METRIKA_TOKEN", "YANDEX_WM_TOKEN"):
        t = os.environ.get(var, "").strip()
        if t:
            return t
    return ""


def _api(token: str, params: dict) -> dict:
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url, headers={"Authorization": f"OAuth {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _date_range() -> tuple[str, str]:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=DAYS_BACK)
    return start.isoformat(), end.isoformat()


def _totals(token: str, d1: str, d2: str) -> dict:
    data = _api(token, {
        "ids": COUNTER, "date1": d1, "date2": d2,
        "metrics": "ym:s:visits,ym:s:users,ym:s:bounceRate,"
                   "ym:s:pageDepth,ym:s:avgVisitDurationSeconds",
        "accuracy": "full",
    })
    # Metrika returns top-level "totals" as a FLAT list of numbers.
    t = data.get("totals") or [0, 0, 0, 0, 0]
    return {
        "visits": int(t[0]), "users": int(t[1]),
        "bounce_rate_pct": round(t[2], 1), "page_depth": round(t[3], 2),
        "avg_visit_sec": int(t[4]),
    }


def _sources(token: str, d1: str, d2: str) -> list:
    data = _api(token, {
        "ids": COUNTER, "date1": d1, "date2": d2,
        "metrics": "ym:s:visits", "dimensions": "ym:s:trafficSource",
        "sort": "-ym:s:visits", "limit": 10, "accuracy": "full",
    })
    out = []
    for row in data.get("data", []):
        name = (row["dimensions"][0].get("name") or "—")
        out.append({"source": name, "visits": int(row["metrics"][0])})
    return out


def _top_landing(token: str, d1: str, d2: str) -> list:
    data = _api(token, {
        "ids": COUNTER, "date1": d1, "date2": d2,
        "metrics": "ym:s:visits,ym:s:bounceRate",
        "dimensions": "ym:s:startURLPath",
        "sort": "-ym:s:visits", "limit": 15, "accuracy": "full",
    })
    out = []
    for row in data.get("data", []):
        out.append({"path": row["dimensions"][0].get("name") or "/",
                    "visits": int(row["metrics"][0]),
                    "bounce_pct": round(row["metrics"][1], 1)})
    return out


def _leads(token: str, d1: str, d2: str) -> dict:
    """Goal reaches = leads. Sum the lead-type goals; also break down by page."""
    # All goals with reaches.
    try:
        data = _api(token, {
            "ids": COUNTER, "date1": d1, "date2": d2,
            "metrics": "ym:s:goalReaches" if False else "ym:s:sumGoalReachesAny",
            "dimensions": "ym:s:goal",
            "sort": "-ym:s:sumGoalReachesAny", "limit": 30, "accuracy": "full",
        })
    except Exception:
        data = {}
    by_goal = {}
    total_leads = 0
    for row in data.get("data", []):
        name = (row["dimensions"][0].get("name") or "").strip()
        reaches = int(row["metrics"][0])
        by_goal[name] = reaches
        if any(k in name.lower() for k in ("phone", "тел", "email", "почт", "mail")):
            total_leads += reaches
    return {"total_leads": total_leads, "by_goal": by_goal}


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    token = _token()
    snapshot: dict = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "counter": COUNTER, "days": DAYS_BACK,
    }
    if not token:
        snapshot["error"] = "no YANDEX_METRIKA_TOKEN / YANDEX_WM_TOKEN"
        OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1))
        print("⚠️  Metrika: no token — wrote stub", file=sys.stderr)
        return 0

    d1, d2 = _date_range()
    try:
        snapshot["totals"] = _totals(token, d1, d2)
        snapshot["sources"] = _sources(token, d1, d2)
        snapshot["top_landing"] = _top_landing(token, d1, d2)
        snapshot["leads"] = _leads(token, d1, d2)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        snapshot["error"] = f"HTTP {e.code}: {body}"
        OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1))
        print(f"⚠️  Metrika API {e.code}: {body}", file=sys.stderr)
        # 403 usually means the token lacks metrika:read scope.
        return 0
    except Exception as e:
        snapshot["error"] = f"{e.__class__.__name__}: {e}"
        OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1))
        print(f"⚠️  Metrika error: {e}", file=sys.stderr)
        return 0

    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1))
    t = snapshot["totals"]
    leads = snapshot["leads"]["total_leads"]
    print(f"✅ Metrika: {t['visits']} визитов, {t['users']} польз., "
          f"отказы {t['bounce_rate_pct']}%, лидов (тел/почта) {leads} за {DAYS_BACK}д")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
