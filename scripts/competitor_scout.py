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

import base64
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from seo_db import get_conn, init_db

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
FINDINGS_PATH = DATA / "competitor_findings.json"

COMP_MIN_IMPR = int(os.environ.get("COMP_MIN_IMPR", "10"))
COMP_POS_BAD  = float(os.environ.get("COMP_POS_BAD", "6"))
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

_SEARCH_API   = "https://searchapi.api.cloud.yandex.net/v2/web/searchAsync"
_OPERATION_API = "https://operation.api.cloud.yandex.net/operations/"


def _yandex_post(url: str, payload: dict | None = None) -> dict:
    headers = {"Authorization": f"Api-Key {YA_KEY}", "Content-Type": "application/json"}
    data = json.dumps(payload).encode() if payload is not None else None
    method = "POST" if payload is not None else "GET"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore"))


def yandex_serp_top(query: str, n: int = 5) -> list[str]:
    """Top organic URLs via the Yandex Cloud Search API v2 (async, if key present).

    Auth is the service-account API key (``YANDEX_SEARCH_API_KEY``); the folder is
    derived from the service account, so ``YANDEX_SEARCH_USER`` is optional and only
    sent as ``folderId`` when explicitly provided.
    """
    if not YA_KEY:
        return []
    body: dict = {"query": {"searchType": "SEARCH_TYPE_RU", "queryText": query}}
    if YA_USER:
        body["folderId"] = YA_USER
    try:
        op = _yandex_post(_SEARCH_API, body)
        op_id = op.get("id")
        if not op_id:
            print(f"· yandex serp: no operation id ({query}): {op}", file=sys.stderr)
            return []
        raw = None
        for _ in range(12):
            res = _yandex_post(_OPERATION_API + op_id)
            if res.get("done"):
                if res.get("error"):
                    print(f"· yandex serp op error ({query}): {res['error']}", file=sys.stderr)
                    return []
                resp = res.get("response", {})
                raw = resp.get("rawData") or resp.get("data")
                break
            time.sleep(3)
        if not raw:
            return []
        xml = base64.b64decode(raw).decode("utf-8", "ignore")
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
    if not YA_KEY:
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


def enrich_google(findings: list[dict]) -> bool:
    """Google-grade SERP intel via Perplexity Agent API.

    Yandex Search API only shows the Yandex SERP; most international/EN demand
    lives in Google. For the worst losing queries we ask Perplexity (live web)
    who actually ranks top-3 in Google and why, and store a structured brief
    the Brain can act on. Cost: ~1 agent call per query, capped."""
    try:
        from pplx_client import pplx_agent_json, PPLX_KEY
    except Exception:
        return False
    if not PPLX_KEY:
        return False

    cap = int(os.environ.get("COMP_PPLX_MAX", "6"))
    done = 0
    for f in findings:
        if done >= cap:
            break
        q = f["query"]
        try:
            brief = pplx_agent_json(
                f"Найди топ-3 результата Google по запросу «{q}» "
                f"(регион: Россия, если запрос на русском; иначе глобально). "
                f"Мы — pepperoni.tatar (халяль мясо оптом).",
                instructions=(
                    "Ты SEO-аналитик. Верни ТОЛЬКО JSON: "
                    '{"top": [{"domain": str, "title": str, '
                    '"why_ranks": str}], "gap_for_us": str}. '
                    "why_ranks — 1 фраза (контент/авторитет/коммерция). "
                    "gap_for_us — что конкретно добавить на pepperoni.tatar, "
                    "чтобы обойти их. Без markdown."),
                preset="low", max_steps=3, max_output_tokens=900)
            if brief.get("top"):
                f["google_serp"] = brief["top"][:3]
                f["google_gap"] = brief.get("gap_for_us", "")
                done += 1
        except Exception as e:
            print(f"· pplx intel failed for «{q}»: {e}", file=sys.stderr)
    print(f"· Google intel (Perplexity): {done} queries enriched")
    return done > 0


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
        for g in f.get("google_serp", [])[:2]:
            lines.append(f"    ↳ Google: {g.get('domain','?')} — "
                         f"{g.get('why_ranks','')[:80]}")
        if f.get("google_gap"):
            lines.append(f"    💡 {f['google_gap'][:120]}")
    if not enriched:
        lines.append("\n<i>SERP-анализ «почему» выключен — добавь YANDEX_SEARCH_API_KEY "
                     "(Yandex Cloud Search API v2), чтобы видеть причины (длина, schema, отзывы).</i>")
    lines.append("\n<i>Это кандидаты на усиление контента/перелинковки/лендингов.</i>")
    try:
        from notification_router import emit
        emit("info", "competitor_scout", "\n".join(lines),
             dedupe_key=f"competitor-scout:{datetime.now(timezone.utc):%Y-%m-%d}")
    except Exception as e:
        print(f"· telegram unavailable: {e}", file=sys.stderr)


# ---------------------------------------------------------------- main

def main():
    init_db()
    conn = get_conn()
    findings = losing_queries(conn)
    print(f"🔭 {len(findings)} losing queries (impr>={COMP_MIN_IMPR}, pos>{COMP_POS_BAD})")

    enriched = bool(YA_KEY)
    if enriched:
        print("· enriching with Yandex SERP analysis …")
        enrich(findings, conn)
    else:
        print("· SERP enrichment disabled (no YANDEX_SEARCH_API_KEY/USER)")

    # Google SERP intel via Perplexity (live web) — independent of Yandex.
    if findings:
        enriched = enrich_google(findings) or enriched

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
