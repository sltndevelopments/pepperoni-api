#!/usr/bin/env python3
"""
COMPETITOR-SCOUT — competitive intelligence (meta-agent item B, runs weekly).

Answers "where are we being outranked, and why?" using our own search data first
(free, ToS-clean) and optional live-SERP enrichment when a search API key exists.

Two layers:

  1) LOSING QUERIES (always on) — from GSC/Yandex: queries with real demand
     (impressions >= threshold) where our average position is poor (> POS_BAD).
     These are exactly the queries where competitors sit above us. Ranked by
     "lost opportunity" = impressions × how far from page 1 we are.

  2) SERP ENRICHMENT (optional) — if YANDEX_SEARCH_API_KEY + YANDEX_SEARCH_USER
     are set, fetch the public Yandex XML SERP for the worst queries, take the
     top competitor URL, fetch that page over plain HTTP and compare WHY it wins:
       • content length (word count)        • schema.org types present
       • review/rating markup               • FAQ markup
     vs the best page we currently rank with. No SERP scraping — uses the
     official XML API; page fetch is a normal GET of a public URL.

Output: data/competitor_findings.json (git-tracked) for the brain + a weekly
Telegram report. Discovery only — never edits pages.

Env:
  YANDEX_SEARCH_API_KEY, YANDEX_SEARCH_USER   optional, enables SERP enrichment
  COMP_MIN_IMPR (40)   COMP_POS_BAD (10)   COMP_MAX (15)
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID       weekly report
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from seo_db import get_conn, init_db

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
FINDINGS_PATH = DATA / "competitor_findings.json"

COMP_MIN_IMPR = int(os.environ.get("COMP_MIN_IMPR", "40"))
COMP_POS_BAD  = float(os.environ.get("COMP_POS_BAD", "10"))
COMP_MAX      = int(os.environ.get("COMP_MAX", "15"))
COMP_WINDOW   = int(os.environ.get("COMP_WINDOW_DAYS", "30"))

YA_KEY  = os.environ.get("YANDEX_SEARCH_API_KEY", "").strip()
YA_USER = os.environ.get("YANDEX_SEARCH_USER", "").strip()

OUR_HOST = "pepperoni.tatar"
UA = "Mozilla/5.0 (compatible; PepperoniCompetitorScout/1.0; +https://pepperoni.tatar)"

BRAND = ("pepperoni.tatar", "pepperoni tatar", "казанские деликатес",
         "kazandelikates", "пепперони татар")


def is_brand(q: str) -> bool:
    ql = (q or "").lower()
    return any(b in ql for b in BRAND)


# ---------------------------------------------------------------- losing queries

def losing_queries(conn) -> list[dict]:
    """Queries with demand where our avg position is bad — competitors outrank us."""
    rows = []
    try:
        rows = conn.execute(f"""
            SELECT query,
                   SUM(impressions) impr,
                   SUM(clicks) clk,
                   SUM(position*impressions)/NULLIF(SUM(impressions),0) wpos,
                   MIN(position) best_pos
            FROM gsc_queries
            WHERE date >= date('now','-{COMP_WINDOW} days')
            GROUP BY query
            HAVING impr >= ? AND wpos > ?
        """, (COMP_MIN_IMPR, COMP_POS_BAD)).fetchall()
    except Exception as e:
        print(f"· gsc query failed: {e}", file=sys.stderr)

    out = []
    for r in rows:
        q = r["query"]
        if is_brand(q):
            continue
        impr = int(r["impr"] or 0)
        wpos = float(r["wpos"] or 0)
        # lost opportunity score: more impressions and worse position = bigger loss
        score = impr * min(wpos, 40) / 10.0
        out.append({
            "query": q,
            "impressions": impr,
            "clicks": int(r["clk"] or 0),
            "our_position": round(wpos, 1),
            "our_best_position": round(float(r["best_pos"] or 0), 1),
            "lost_score": round(score, 1),
        })
    out.sort(key=lambda x: x["lost_score"], reverse=True)
    return out[:COMP_MAX]


def our_best_page(conn, query: str) -> str | None:
    try:
        r = conn.execute(f"""
            SELECT page, SUM(impressions) impr
            FROM gsc_queries
            WHERE query=? AND date >= date('now','-{COMP_WINDOW} days') AND page IS NOT NULL
            GROUP BY page ORDER BY impr DESC LIMIT 1
        """, (query,)).fetchone()
        return r["page"] if r else None
    except Exception:
        return None


# ---------------------------------------------------------------- SERP (optional)

def yandex_serp_top(query: str, n: int = 5) -> list[str]:
    """Top organic URLs via the official Yandex XML search API (if key present)."""
    if not (YA_KEY and YA_USER):
        return []
    url = ("https://yandex.com/search/xml?"
           f"user={urllib.parse.quote(YA_USER)}&key={urllib.parse.quote(YA_KEY)}"
           f"&query={urllib.parse.quote(query)}&l10n=ru&groupby=attr%3D%22%22.mode%3Dflat")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        xml = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"· yandex serp failed ({query}): {e}", file=sys.stderr)
        return []
    urls = re.findall(r"<url>(.*?)</url>", xml)
    return urls[:n]


def analyze_page(url: str) -> dict:
    """Fetch a public competitor page and extract why-it-wins signals."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
    except Exception as e:
        return {"url": url, "error": str(e)[:80]}
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    words = len(re.findall(r"\w+", text))
    schema_types = sorted(set(re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', html)))
    return {
        "url": url,
        "words": words,
        "schema": schema_types,
        "has_reviews": bool(re.search(r'"(aggregateRating|review)"|itemprop="review"', html, re.I)),
        "has_faq": "FAQPage" in schema_types,
    }


def enrich(findings: list[dict], conn) -> None:
    if not (YA_KEY and YA_USER):
        return
    for f in findings[: min(8, len(findings))]:
        tops = yandex_serp_top(f["query"])
        competitors = [u for u in tops if OUR_HOST not in u]
        if not competitors:
            continue
        comp = analyze_page(competitors[0])
        ours_url = our_best_page(conn, f["query"])
        ours = analyze_page(ours_url) if ours_url else {}
        f["competitor"] = comp
        f["ours"] = ours
        # quick "why they win" heuristic
        why = []
        if comp.get("words") and ours.get("words") and comp["words"] > ours["words"] * 1.3:
            why.append(f"длиннее контент ({comp['words']} vs {ours.get('words','?')} слов)")
        extra_schema = set(comp.get("schema", [])) - set(ours.get("schema", []))
        if extra_schema:
            why.append("больше schema: " + ", ".join(sorted(extra_schema)[:4]))
        if comp.get("has_reviews") and not ours.get("has_reviews"):
            why.append("есть отзывы/рейтинг")
        if comp.get("has_faq") and not ours.get("has_faq"):
            why.append("есть FAQ-разметка")
        f["why_they_win"] = why


# ---------------------------------------------------------------- report

def telegram_report(findings: list[dict], enriched: bool) -> None:
    if not findings:
        return
    lines = ["<b>🔭 Competitor-Scout — где нас обходят</b>",
             f"<i>Запросы с спросом, где наша позиция хуже {COMP_POS_BAD:.0f} "
             f"(за {COMP_WINDOW} дн.)</i>", ""]
    for i, f in enumerate(findings[:8], 1):
        lines.append(f"{i}. «{f['query']}» — поз. {f['our_position']}, "
                     f"{f['impressions']} показов")
        for w in f.get("why_they_win", [])[:2]:
            lines.append(f"    ↳ конкурент: {w}")
    if not enriched:
        lines.append("\n<i>SERP-анализ «почему» выключен — добавь YANDEX_SEARCH_API_KEY "
                     "и YANDEX_SEARCH_USER, чтобы видеть причины (длина, schema, отзывы).</i>")
    lines.append("\n<i>Это кандидаты на усиление контента/перелинковки/лендингов.</i>")
    try:
        from telegram_notify import notify
        notify("\n".join(lines))
    except Exception as e:
        print(f"· telegram unavailable: {e}", file=sys.stderr)


# ---------------------------------------------------------------- main

def main():
    init_db()
    conn = get_conn()
    findings = losing_queries(conn)
    print(f"🔭 {len(findings)} losing queries (impr>={COMP_MIN_IMPR}, pos>{COMP_POS_BAD})")

    enriched = bool(YA_KEY and YA_USER)
    if enriched:
        print("· enriching with Yandex SERP analysis …")
        enrich(findings, conn)
    else:
        print("· SERP enrichment disabled (no YANDEX_SEARCH_API_KEY/USER)")

    conn.close()

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": COMP_WINDOW,
        "enriched": enriched,
        "losing_queries": findings,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    FINDINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    print(f"✅ wrote {FINDINGS_PATH.relative_to(ROOT)}")

    for f in findings[:8]:
        extra = ("  ← " + "; ".join(f["why_they_win"])) if f.get("why_they_win") else ""
        print(f"  • «{f['query']}» pos {f['our_position']} / {f['impressions']} impr{extra}")

    telegram_report(findings, enriched)
    return 0


if __name__ == "__main__":
    sys.exit(main())
