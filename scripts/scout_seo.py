#!/usr/bin/env python3
"""
SCOUT — the discovery agent of the meta-agent (runs every ~6h).

Watches the search landscape and surfaces opportunities the optimizer/brain
should act on, WITHOUT generating anything itself (discovery only):

  • NEW queries     — queries we now appear for that we had not seen before,
                      with real impressions and no strong landing page.
  • RISING queries  — impressions grew materially vs the last baseline.
  • COVERAGE gaps   — meaningful query whose best page is the homepage / weak.

Durability: the DB (data/seo_data.db) is rebuilt each run and not committed, so
Scout keeps its own git-tracked baseline at data/scout_state.json (per-query best
impressions + first_seen). The diff against that baseline is what detects "new"
and "rising". Findings are written to data/scout_findings.json (git-tracked) and,
when there is something notable, a digest is sent to Telegram.

The brain (seo_brain.py) reads scout_findings.json to decide new pages/topics.

Env: (GSC fetched upstream by fetch_gsc_queries.py); TELEGRAM_BOT_TOKEN for digest.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from seo_db import get_conn, init_db

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
STATE_PATH    = DATA / "scout_state.json"
FINDINGS_PATH = DATA / "scout_findings.json"
# Memory of what was already pushed to Telegram, so the same coverage gap is not
# re-announced every run. {query: {"pos": <last reported pos>, "at": <iso>}}
SENT_PATH     = DATA / "scout_sent.json"

# Re-announce an already-reported signal only if it has been quiet this long…
SCOUT_RESEND_DAYS = float(os.environ.get("SCOUT_RESEND_DAYS", "7"))
# …or if its position changed by at least this much (real movement worth a ping).
SCOUT_RESEND_POS_DELTA = float(os.environ.get("SCOUT_RESEND_POS_DELTA", "5"))

# Thresholds (env-tunable)
SCOUT_MIN_IMPR     = int(os.environ.get("SCOUT_MIN_IMPR", "10"))     # min impressions to care
SCOUT_RISE_FACTOR  = float(os.environ.get("SCOUT_RISE_FACTOR", "2.0"))  # 2x growth = rising
SCOUT_RISE_MIN     = int(os.environ.get("SCOUT_RISE_MIN", "20"))     # and >= this many impr now
SCOUT_MAX_FINDINGS = int(os.environ.get("SCOUT_MAX_FINDINGS", "25"))
SCOUT_WINDOW_DAYS  = int(os.environ.get("SCOUT_WINDOW_DAYS", "30"))

# A page is "weak" for a query if the only thing ranking is the homepage or an
# obviously generic page — i.e. we have demand but no dedicated landing.
WEAK_PAGE_MARKERS = ("pepperoni.tatar/", "pepperoni.tatar/en/")


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def is_brand_query(q: str) -> bool:
    ql = (q or "").lower()
    return any(b in ql for b in ("pepperoni.tatar", "pepperoni tatar",
                                 "казанские деликатес", "kazandelikates", "пепперони татар"))


def current_query_stats(conn) -> dict:
    """Aggregate the freshest GSC window into {query: {impr, clk, wpos, best_page}}."""
    rows = conn.execute(f"""
        SELECT query, page,
               SUM(impressions) AS impr,
               SUM(clicks)      AS clk,
               SUM(position * impressions) AS pw
        FROM gsc_queries
        WHERE date >= date('now', '-' || ? || ' days')
          AND query != ''
        GROUP BY query, page
    """, (SCOUT_WINDOW_DAYS,)).fetchall()

    agg: dict[str, dict] = {}
    for r in rows:
        q = r["query"]
        a = agg.setdefault(q, {"impr": 0, "clk": 0, "pw": 0.0, "best_page": "", "best_page_impr": 0})
        a["impr"] += r["impr"] or 0
        a["clk"] += r["clk"] or 0
        a["pw"] += r["pw"] or 0
        if (r["impr"] or 0) > a["best_page_impr"]:
            a["best_page_impr"] = r["impr"] or 0
            a["best_page"] = r["page"] or ""
    for q, a in agg.items():
        a["wpos"] = (a["pw"] / a["impr"]) if a["impr"] else 0.0
    return agg


def page_is_weak(page: str) -> bool:
    p = (page or "").rstrip("/")
    return p in ("https://pepperoni.tatar", "https://pepperoni.tatar/en") or page == ""


def run_scout(send_tg: bool = True) -> dict:
    init_db()
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    stats = current_query_stats(conn)
    conn.close()

    baseline = load_json(STATE_PATH, {})   # {query: {best_impr, first_seen, last_seen}}
    new_q, rising_q, gap_q = [], [], []

    for q, a in stats.items():
        if is_brand_query(q) or a["impr"] < SCOUT_MIN_IMPR:
            continue
        prev = baseline.get(q)
        entry = {
            "query": q, "impr": a["impr"], "clk": a["clk"],
            "pos": round(a["wpos"], 1), "page": a["best_page"],
        }
        if prev is None:
            new_q.append(entry)
        else:
            prev_impr = prev.get("best_impr", 0)
            if a["impr"] >= SCOUT_RISE_MIN and prev_impr > 0 and a["impr"] >= prev_impr * SCOUT_RISE_FACTOR:
                entry["from_impr"] = prev_impr
                rising_q.append(entry)
        # coverage gap: demand exists but only the homepage ranks
        if a["impr"] >= SCOUT_RISE_MIN and page_is_weak(a["best_page"]):
            gap_q.append(entry)

    # Update baseline (best-ever impressions + first/last seen).
    for q, a in stats.items():
        b = baseline.get(q, {"first_seen": now})
        b["best_impr"] = max(b.get("best_impr", 0), a["impr"])
        b["last_seen"] = now
        baseline[q] = b
    save_json(STATE_PATH, baseline)

    # Rank by impressions, cap.
    for lst in (new_q, rising_q, gap_q):
        lst.sort(key=lambda x: -x["impr"])

    # Strong coverage gaps (lots of demand, only homepage ranks) are worth a
    # dedicated landing page — a high-value action. Queue them for the owner's
    # approval so the brain/hands build them deliberately, not on a guess.
    _queue_strong_gaps(gap_q)
    findings = {
        "generated_at": now,
        "new_queries":   new_q[:SCOUT_MAX_FINDINGS],
        "rising_queries": rising_q[:SCOUT_MAX_FINDINGS],
        "coverage_gaps":  gap_q[:SCOUT_MAX_FINDINGS],
    }
    save_json(FINDINGS_PATH, findings)

    print(f"🛰  Scout: {len(new_q)} new, {len(rising_q)} rising, {len(gap_q)} coverage gaps "
          f"(baseline now {len(baseline)} queries)")
    for label, lst in (("NEW", new_q), ("RISING", rising_q), ("GAP", gap_q)):
        for e in lst[:5]:
            print(f"   {label:6s} «{e['query'][:34]:34}» impr{e['impr']:>4} pos{e['pos']:.0f} {e['page'].replace('https://pepperoni.tatar','') or '—'}")

    if send_tg:
        _maybe_send_digest(findings)
    return findings


SCOUT_GAP_APPROVAL_IMPR = int(os.environ.get("SCOUT_GAP_APPROVAL_IMPR", "120"))


def _queue_strong_gaps(gap_q: list) -> None:
    """Ask the owner to approve building a landing page for a high-demand gap."""
    try:
        import approvals
    except Exception:
        return
    for e in gap_q:
        if e["impr"] < SCOUT_GAP_APPROVAL_IMPR:
            continue
        key = "landing:" + e["query"].lower().strip().replace(" ", "-")[:60]
        approvals.request(
            key=key,
            title=f"Создать лендинг под «{e['query']}»",
            detail=(f"{e['impr']} показов, средняя позиция {e['pos']}, "
                    f"сейчас ранжируется только главная — нужен отдельный лендинг "
                    f"под этот запрос."),
            action="create_landing",
            payload={"query": e["query"], "impr": e["impr"], "pos": e["pos"]},
            risk="medium",
            requested_by="scout",
        )


def _dedup_for_telegram(findings: dict) -> dict:
    """Drop signals already announced recently with no real change.

    Without this, coverage gaps (which carry no baseline of their own) get
    re-sent every single run — the daily Scout spam the owner complained about.
    A signal is re-sent only if it is brand new, has been silent for
    SCOUT_RESEND_DAYS, or its position moved by SCOUT_RESEND_POS_DELTA+.
    """
    sent = load_json(SENT_PATH, {})
    now = datetime.now(timezone.utc)
    fresh = {"new_queries": [], "rising_queries": [], "coverage_gaps": []}

    def _is_fresh(e: dict) -> bool:
        q = e["query"].lower().strip()
        prev = sent.get(q)
        if not prev:
            return True
        try:
            quiet_days = (now - datetime.fromisoformat(prev["at"])).total_seconds() / 86400
        except Exception:
            quiet_days = 999
        if quiet_days >= SCOUT_RESEND_DAYS:
            return True
        if abs(e.get("pos", 0) - prev.get("pos", 0)) >= SCOUT_RESEND_POS_DELTA:
            return True
        return False

    for key in fresh:
        for e in findings.get(key, []):
            if _is_fresh(e):
                fresh[key].append(e)
                sent[e["query"].lower().strip()] = {"pos": e.get("pos", 0),
                                                    "at": now.isoformat()}
    save_json(SENT_PATH, sent)
    return fresh


def _maybe_send_digest(f: dict) -> None:
    # Only announce genuinely new/changed signals (kills daily repeat spam).
    f = _dedup_for_telegram(f)
    notable = f["new_queries"] or f["rising_queries"] or f["coverage_gaps"]
    if not notable:
        print("· scout: nothing new since last digest, skipping Telegram")
        return
    lines = ["<b>🛰 Scout — новые сигналы спроса</b>"]
    if f["new_queries"]:
        lines.append("\n<b>Новые запросы (нет хорошей страницы):</b>")
        for e in f["new_queries"][:6]:
            lines.append(f"  🆕 «{e['query']}» — {e['impr']} показов, поз {e['pos']}")
    if f["rising_queries"]:
        lines.append("\n<b>Растущий спрос:</b>")
        for e in f["rising_queries"][:6]:
            lines.append(f"  📈 «{e['query']}» — {e.get('from_impr','?')}→{e['impr']} показов")
    if f["coverage_gaps"]:
        lines.append("\n<b>Пробелы покрытия (ранжируется только главная):</b>")
        for e in f["coverage_gaps"][:6]:
            lines.append(f"  🕳 «{e['query']}» — {e['impr']} показов, поз {e['pos']}")
    try:
        import approvals
        pend = approvals.pending()
        if pend:
            lines.append(f"\n<b>⏳ Ждут одобрения ({len(pend)}):</b>")
            for i, a in enumerate(pend[:5], 1):
                lines.append(f"  {i}. {a.get('title', '?')}")
            lines.append("Ответь в @KDSEOSiteBot: <code>одобрить N</code>")
    except Exception:
        pass
    lines.append("\n<i>Мозг учтёт это при планировании. @KDSEOSiteBot → «спросить мозг».</i>")
    text = "\n".join(lines)
    try:
        import daily_ledger
        daily_ledger.append_event("done", text)
    except Exception as e:
        print(f"· ledger unavailable: {e}", file=sys.stderr)


def main():
    send = "--no-telegram" not in sys.argv
    run_scout(send_tg=send)


if __name__ == "__main__":
    main()
