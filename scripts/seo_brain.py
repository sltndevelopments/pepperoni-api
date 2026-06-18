#!/usr/bin/env python3
"""
SEO BRAIN — the strategic layer of the autonomous engine.

Claude Opus reads a compact digest of the current site state (inventory,
coverage gaps, fresh GSC/Yandex opportunities) and emits a COMPACT JSON
strategy that the cheap DeepSeek "hands" execute 24/7.

Designed to run as a step inside seo-agent-vps.sh AFTER fetch+analyze, so
the opportunities table (volatile) is fresh. Falls back to filesystem-only
digest if the DB is empty. If no ANTHROPIC_API_KEY / budget, it leaves the
previous strategy.json untouched and exits 0 (non-fatal).

Output: data/strategy.json
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from opus_brain_client import call_opus, brain_available, remaining_budget, OPUS_MODEL

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
DB_PATH = DATA / "seo_data.db"
STRATEGY_FILE = DATA / "strategy.json"
# Owner ↔ brain dialogue files. Answers live OUTSIDE the repo (tg-state) so the
# bot can write them without git conflicts; questions are tracked in the repo.
QUESTIONS_FILE = DATA / "brain_questions.json"
try:
    import telegram_notify as _tn
    ANSWERS_FILE = Path(_tn.STATE_DIR) / "brain_answers.json"
except Exception:
    ANSWERS_FILE = DATA / "brain_answers.json"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_owner_answers() -> list:
    """Owner replies to the brain's questions, written by the Telegram bot."""
    try:
        return json.loads(ANSWERS_FILE.read_text()).get("answers", [])
    except Exception:
        return []


# ── Digest builders ───────────────────────────────────────────────────────────
def _count(glob_dir: Path, pattern: str = "*.html") -> int:
    try:
        return len(list(glob_dir.glob(pattern)))
    except Exception:
        return 0


def inventory() -> dict:
    return {
        "geo_ru": _count(PUBLIC / "geo"),
        "geo_en": _count(PUBLIC / "en/geo"),
        "blog_ru": _count(PUBLIC / "blog"),
        "blog_en": _count(PUBLIC / "en/blog"),
        "products": _count(PUBLIC / "products"),
    }


def coverage_gaps() -> dict:
    """Depth coverage matrix: category × target-market × lang.

    North Star model: ONE strong page per (category, market) is the goal.
    NOT a city×product grid. Cities are driven by scout demand signals only.

    Markets and their priority come from goals.json (single source of truth).
    Each country entry carries:
      market_group    A–E (cold-start order) or "RU" (scout-driven, excluded here)
      market_priority 0=RU(excluded), 1=A, 2=B, 3=C, 4=D, 5=E
      docs_status     "ready" | "in_process" | "on_demand"
      content_langs   primary content languages for this market

    Sorting: market_priority ascending (A→E), then category_priority.
    No sorting by impressions — market business priority governs order.

    docs_status is forwarded to each gap so generators/PLAYBOOK can apply
    the correct content framing (in_process → build presence, no overclaim).

    A cell is "covered" if at least one filename under export/, landing/,
    en/geo/, ar/geo/ contains both a category slug AND a market token.
    Fast filesystem heuristic — no LLM, < 100ms.
    """
    # ── Load markets from goals.json (single source of truth) ────────────────
    try:
        goals_data = json.loads((DATA / "goals.json").read_text())
        raw_countries = goals_data.get("countries", [])
    except Exception:
        raw_countries = []

    markets = []
    for c in raw_countries:
        mp = c.get("market_priority")
        group = c.get("market_group", "")
        if group == "RU" or mp == 0:
            continue  # Russia: scout-driven, excluded from cold-start matrix
        if mp is None:
            # Legacy entry without market_priority — skip (will be added to goals.json)
            continue
        markets.append({
            "code": c.get("code", ""),
            "name": c.get("country", ""),
            "group": group,
            "market_priority": mp,
            "docs_status": c.get("docs_status", "ready"),
            "langs": c.get("content_langs", ["ru"]),
            "impr_28d": c.get("impressions_28d") or 0,
            "clicks_28d": c.get("clicks_28d") or 0,
        })
    # Sort by market_priority (A→E), secondary: impressions descending within group
    # (higher-traffic markets within same group come first — more opportunity)
    markets.sort(key=lambda m: (m["market_priority"], -m["impr_28d"]))

    # ── Load categories from products_geo.json ────────────────────────────────
    try:
        pg = json.loads((DATA / "products_geo.json").read_text())
        products = pg.get("products", [])
    except Exception:
        products = []

    # Commercial/OEM categories first; bakery and raw at the end
    _CAT_PRIORITY = [
        "private-label", "pepperoni", "kolbasnye", "sosiki-hotdog",
        "kotlety-burgery", "vetchina", "kazylyk-premium", "kopchenye",
        "farsh", "toppings-pizza", "pelmeni",
        "vypechka-tatarskaya", "vypechka-klassicheskaya", "sosiki-v-teste",
        "syroje-myaso",
    ]

    def _cat_rank(pid: str) -> int:
        try:
            return _CAT_PRIORITY.index(pid)
        except ValueError:
            return len(_CAT_PRIORITY)

    categories = sorted(products, key=lambda p: _cat_rank(p["id"]))

    # ── Build existing-page index (fast filesystem heuristic) ─────────────────
    existing_names: set[str] = set()
    for scan_dir in (
        PUBLIC / "export", PUBLIC / "landing",
        PUBLIC / "en" / "geo", PUBLIC / "ar" / "geo",
        PUBLIC / "en", PUBLIC / "ar",
        PUBLIC / "geo",
    ):
        try:
            existing_names |= {p.name for p in scan_dir.glob("*.html")}
        except Exception:
            pass

    def _has_coverage(cat_id: str, market_code: str, market_name: str) -> bool:
        """True if a page exists covering this (category, market) pair."""
        p_obj = next((p for p in products if p["id"] == cat_id), {})
        cat_slugs = {s for s in [
            p_obj.get("slug_ru", ""), p_obj.get("slug_en", ""),
            p_obj.get("slug_ar", ""), cat_id,
        ] if s}
        market_name_slug = market_name.lower().replace(" ", "-").replace(".", "")
        market_tokens = {market_code, market_name_slug}
        # Generic export/{country}.html doesn't count as category coverage
        for fname in existing_names:
            stem = fname.replace(".html", "")
            if any(tok in stem for tok in market_tokens) and \
               any(slug and slug in stem for slug in cat_slugs):
                return True
        return False

    # ── Build gaps: category (outer) × market (inner) ─────────────────────────
    # Outer loop = categories so top-20 slice is diverse across categories.
    raw_gaps = []
    for cat in categories:
        for market in markets:
            if _has_coverage(cat["id"], market["code"], market["name"]):
                continue
            raw_gaps.append({
                "category": cat["id"],
                "category_name": cat.get("name_ru", cat["id"]),
                "market": market["name"],
                "market_code": market["code"],
                "market_group": market["group"],
                "lang": market["langs"][0],
                "langs": market["langs"],
                "docs_status": market["docs_status"],
                "market_priority": market["market_priority"],
            })

    # Final sort: market_priority (A→E) first, then category priority
    raw_gaps.sort(key=lambda g: (g["market_priority"], _cat_rank(g["category"])))
    gaps = raw_gaps[:20]

    by_group = {}
    for g in gaps:
        by_group[g["market_group"]] = by_group.get(g["market_group"], 0) + 1

    return {
        "note": (
            "Матрица покрытия: категория×рынок×язык. "
            "Одна сильная страница на ячейку — цель. "
            "Россия — только по scout-сигналу, не здесь."
        ),
        "markets_tracked": len(markets),
        "categories_tracked": len(categories),
        "gaps_by_group": by_group,   # e.g. {"A": 8, "C": 12}
        "gaps": gaps,                # sorted A→E then category priority
    }


def opportunities(limit: int = 40) -> dict:
    """Fresh GSC/Yandex opportunities, best-effort (DB may be empty)."""
    out = {"low_ctr": [], "quick_growth": [], "commercial": []}
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        for typ in out:
            rows = conn.execute(
                """SELECT query, page, position, impressions, ctr
                   FROM opportunities WHERE type=? AND status='new'
                   ORDER BY impressions DESC LIMIT ?""",
                (typ, limit),
            ).fetchall()
            out[typ] = [dict(r) for r in rows]
        conn.close()
    except Exception:
        pass
    return out


def experiments_digest() -> dict:
    """Compact summary of optimizer experiments so the brain learns what works.

    Reads the durable JSON ledger (data/experiments.json). Surfaces verdict
    tallies and concrete examples of winning vs reverted title rewrites so the
    strategy can double down on patterns that lift CTR and avoid those that hurt.
    """
    try:
        led = json.loads((DATA / "experiments.json").read_text())
    except Exception:
        return {}
    verdicts: dict = {}
    for e in led:
        v = e.get("verdict", "pending")
        verdicts[v] = verdicts.get(v, 0) + 1
    def _ex(e):
        return {"query": e.get("query"), "before": (e.get("before_title") or "")[:60],
                "after": (e.get("after_title") or "")[:60],
                "pos": [e.get("before_pos"), e.get("after_pos")]}
    wins = [_ex(e) for e in led if e.get("verdict") == "win"][-8:]
    reverts = [_ex(e) for e in led if e.get("verdict") == "reverted"][-8:]
    return {
        "verdicts": verdicts,
        "pending": verdicts.get("pending", 0),
        "winning_rewrites": wins,
        "reverted_rewrites": reverts,
    }


def scout_digest() -> dict:
    """New/rising/gap demand signals discovered by the Scout agent.
    Cap: 10 items per category × 4 slim fields."""
    try:
        f = json.loads((DATA / "scout_findings.json").read_text())
    except Exception:
        return {}
    def _trim(lst):
        return [{"query": e.get("query"), "impr": e.get("impr"),
                 "pos": e.get("pos"), "page": e.get("page")} for e in (lst or [])[:10]]
    return {
        "new_queries":    _trim(f.get("new_queries")),
        "rising_queries": _trim(f.get("rising_queries")),
        "coverage_gaps":  _trim(f.get("coverage_gaps")),
    }


def competitor_digest() -> dict:
    """Queries where competitors outrank us (Competitor-Scout), with why-they-win."""
    try:
        f = json.loads((DATA / "competitor_findings.json").read_text())
    except Exception:
        return {}
    losing = []
    for e in (f.get("losing_queries") or [])[:12]:
        losing.append({"query": e.get("query"), "impr": e.get("impressions"),
                       "our_pos": e.get("our_position"),
                       "why": e.get("why_they_win") or []})
    return {"enriched": f.get("enriched"), "losing_queries": losing}


def aio_digest() -> dict:
    """AI-assistant citability over time (AIO-Visibility agent)."""
    try:
        led = json.loads((DATA / "aio_visibility.json").read_text())
    except Exception:
        return {}
    if not led:
        return {}
    last = led[-1]
    return {"deepseek_score": last.get("deepseek_score"),
            "perplexity_score": last.get("perplexity_score"),
            "not_cited_for": (last.get("lost") or [])[:6]}


def goals_digest() -> dict:
    """Distance-to-#1 + inquiry funnel — the mission AND the real KPI, quantified.

    Two gap types surface explicitly:
      ctr_gaps       — impressions but no clicks → title/snippet problem
      conversion_gaps — clicks but no inquiries → CTA/intent problem
    Priority rule: converting pages first; then ctr_gaps (volume lever);
    then conversion_gaps (intent lever); then worst positional gaps.
    """
    try:
        g = json.loads((DATA / "goals.json").read_text())
    except Exception:
        return {}
    rows = g.get("goals", [])

    # Rows sorted: converting first, then by impressions desc (most impactful first).
    converting = [r for r in rows if r.get("inquiries_28d", 0) > 0]
    ctr_gaps    = [r for r in rows if r.get("ctr_gap") and not r.get("inquiries_28d")]
    conv_gaps   = [r for r in rows if r.get("conversion_gap")]
    worst_pos   = [r for r in rows
                   if r.get("gap_to_1") and r["gap_to_1"] > 0.3
                   and not r.get("ctr_gap") and not r.get("conversion_gap")]

    def _slim(r: dict, include_inq: bool = False) -> dict:
        d = {"q": r["query"],
             "pos": r.get("position_7d") or r.get("position_28d"),
             "impr": r.get("impressions_28d", 0),
             "clicks": r.get("clicks_28d", 0)}
        if include_inq:
            d["inq"] = r.get("inquiries_28d", 0)
        return d

    return {
        "achieved":              g.get("achieved", 0),
        "total":                 g.get("total", 0),
        "ctr_gaps_count":        g.get("ctr_gaps_count", len(ctr_gaps)),
        "conversion_gaps_count": g.get("conversion_gaps_count", len(conv_gaps)),
        # Pages already generating inquiries — reinforce these, don't touch what works.
        "converting": [_slim(r, include_inq=True) for r in converting[:5]],
        # No clicks despite impressions → title/snippet fix needed.
        "ctr_gaps":   [_slim(r) for r in ctr_gaps[:8]],
        # Clicks arriving but zero inquiries → CTA / intent fix needed.
        "conversion_gaps": [_slim(r, include_inq=True) for r in conv_gaps[:8]],
        # Classic positional gap (for context, not primary priority).
        "worst_pos_gaps": [_slim(r) for r in worst_pos[:6]],
        "no_data":  [r["query"] for r in rows if r.get("position_28d") is None][:6],
        "top_converting_pages": g.get("top_converting", [])[:5],
        "countries": [
            {"c": r["country"], "impr": r["impressions_28d"],
             "clicks": r["clicks_28d"], "pos": r["position_28d"]}
            for r in g.get("countries", [])
        ],
    }


def ai_bots_digest() -> dict:
    """AI crawler visits from nginx logs (parse-ai-bots digest, if present on VPS)."""
    import os
    for p in (Path(os.environ.get("AI_BOTS_DIGEST_DIR", "/var/log/nginx"))
              / "ai-bots-digest-latest.md",):
        try:
            txt = p.read_text(encoding="utf-8")
            return {"latest": txt[:1500]}
        except Exception:
            pass
    return {}


def market_pulse_digest() -> dict:
    """Monthly live-web market intel — capped to top-5 priority markets.

    Cap: 5 markets × slim fields (1 insight×80, opportunity×80, risk×40).
    Uncapped this block alone runs ~10K tokens; capped it stays ~430 tokens.
    """
    try:
        mp = json.loads((DATA / "market_pulse.json").read_text())
        countries = mp.get("countries") or {}

        # Sort by market_priority from goals.json (single source of truth)
        try:
            goals_raw = json.loads((DATA / "goals.json").read_text())
            _MP3TO2 = {
                "kaz": "kz", "kgz": "kg", "uzb": "uz", "tjk": "tj",
                "geo": "ge", "aze": "az", "are": "ae", "sau": "sa",
                "kwt": "kw", "bhr": "bh", "omn": "om", "qat": "qa",
                "egy": "eg", "yem": "ye", "blr": "by", "arm": "am",
            }
            pri_map = {
                _MP3TO2.get(c["code"], c["code"]): c.get("market_priority", 99)
                for c in goals_raw.get("countries", [])
            }
        except Exception:
            pri_map = {}

        sorted_codes = sorted(countries.keys(),
                              key=lambda c: pri_map.get(c, 99))[:5]
        out = {}
        for code in sorted_codes:
            c = countries[code]
            raw_insights = c.get("insights") or []
            out[c.get("name", code)] = {
                "insight":     (raw_insights[0] if raw_insights else "")[:80],
                "opportunity": (c.get("opportunity") or "")[:80],
                "risk":        (c.get("risk") or "")[:40],
            }
        return {"generated_at": mp.get("generated_at", ""), "markets": out}
    except Exception:
        return {}


def costs_digest() -> dict:
    """LLM spend telemetry so the brain can weigh content volume vs budget."""
    try:
        led = json.loads((DATA / "llm_costs.json").read_text())
        from datetime import date as _date
        m = led.get(_date.today().strftime("%Y-%m"), {})
        if not m:
            return {}
        days = m.get("days", {})
        top = sorted(m.get("scripts", {}).items(),
                     key=lambda kv: -kv[1].get("usd", 0))[:5]
        geo = m.get("scripts", {}).get("generate_geo_bulk", {})
        geo_pages = max(geo.get("calls", 0), 1)
        return {
            "month_usd": round(m.get("usd", 0.0), 2),
            "month_usd_without_optimizations": round(m.get("usd_baseline", 0.0), 2),
            "days_tracked": len(days),
            "avg_daily_usd": round(m.get("usd", 0.0) / max(len(days), 1), 2),
            "monthly_budget_usd": float(os.environ.get("LLM_MONTHLY_BUDGET", "200")),
            "top_spenders": {k: round(v.get("usd", 0.0), 2) for k, v in top},
            "geo_page_unit_cost_usd": round(geo.get("usd", 0.0) / geo_pages, 3),
        }
    except Exception:
        return {}


def data_health_digest() -> dict:
    """Self-monitoring: is the brain even working on FRESH, REAL data?

    Surfaces the blind spots the brain previously couldn't see:
      - GSC data staleness (a fetch bug once froze data for a month)
      - whole-site CTR (4361 pages with 27 clicks = high impressions, no clicks)
      - Yandex coverage (0 = critical for RU/Tatarstan halal market)
      - experiments stuck pending (optimizer can deadlock itself)
    The brain MUST react to these before chasing new content.
    """
    out: dict = {}
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        # GSC freshness + whole-site CTR over last 30 days
        row = conn.execute(
            "SELECT MAX(date) AS maxd, SUM(clicks) AS clk, SUM(impressions) AS imp "
            "FROM gsc_queries WHERE date >= date('now','-30 days')"
        ).fetchone()
        maxd = row["maxd"]
        if maxd:
            from datetime import date as _date
            age = (_date.today() - _date.fromisoformat(maxd)).days
            out["gsc_latest_date"] = maxd
            out["gsc_data_age_days"] = age
            out["gsc_stale"] = age > 5  # GSC lags ~3d; >5 means our fetch is broken
        imp = row["imp"] or 0
        clk = row["clk"] or 0
        out["site_30d_impressions"] = imp
        out["site_30d_clicks"] = clk
        out["site_30d_ctr_pct"] = round(100 * clk / imp, 3) if imp else 0.0
        out["ctr_critically_low"] = bool(imp >= 1000 and (clk / imp) < 0.005)
        # Yandex coverage
        yrow = conn.execute(
            "SELECT SUM(impressions) AS imp, SUM(clicks) AS clk FROM yandex_queries"
        ).fetchone()
        out["yandex_impressions"] = yrow["imp"] or 0
        out["yandex_dark"] = (yrow["imp"] or 0) == 0  # 0 = we're invisible on Yandex
        conn.close()
    except Exception:
        pass
    # Stuck experiments (pending but applied long ago = optimizer deadlock)
    try:
        led = json.loads((DATA / "experiments.json").read_text())
        from datetime import datetime as _dt, timezone as _tz
        now = _dt.now(_tz.utc)
        pend = [e for e in led if e.get("verdict") == "pending"]
        mature = int(os.environ.get("OPT_MATURE_DAYS", "14"))

        def _age(e):
            try:
                return (now - _dt.fromisoformat(e["applied_at"])).days
            except Exception:
                return 0
        out["experiments_pending"] = len(pend)
        out["experiments_overdue"] = sum(1 for e in pend if _age(e) > mature + 7)
    except Exception:
        pass
    return out


def site_health_digest() -> dict:
    """Technical-SEO health of the whole site (broken links, duplicate
    canonicals, thin/broken pages) — produced by scripts/site_health.py."""
    try:
        import site_health
        return site_health.brain_summary()
    except Exception:
        return {}


def cwv_digest() -> dict:
    """Core Web Vitals (page speed) per template — Google ranking factor."""
    try:
        import core_web_vitals
        return core_web_vitals.brain_summary()
    except Exception:
        return {}


def build_digest() -> dict:
    digest = {
        "date": TODAY,
        "data_health": data_health_digest(),
        "site_health": site_health_digest(),
        "page_speed": cwv_digest(),
        "goals": goals_digest(),
        "inventory": inventory(),
        "coverage": coverage_gaps(),
        "opportunities": opportunities(),
        "experiments": experiments_digest(),
        "scout": scout_digest(),
        "competitors": competitor_digest(),
        "aio_visibility": aio_digest(),
        "web_search": websearch_digest(),
        "ai_bots": ai_bots_digest(),
        "market_pulse": market_pulse_digest(),
        "costs": costs_digest(),
        "toolbox": toolbox_digest(),
        "behaviour": metrika_digest(),
        "leads_inbox": leads_digest(),
        "agent_bus": bus_digest(),
        "outcomes": outcomes_digest(),
        "gate_rejections": gate_rejections_digest(),
        "memory": memory_digest(),
        "owner_answers": _load_owner_answers()[-10:],
    }
    # ── Hard size guardian (~15K token ceiling = 45K chars) ───────────────
    # Per-block caps above should keep total well under this; the guardian is
    # a structural backstop for any future block that exceeds its cap.
    # Cuts by ELEMENT count (never slice a JSON string) so result stays valid.
    _GUARDIAN_CHARS = 45_000
    _VARIABLE_BLOCKS = (
        "market_pulse", "agent_bus", "scout", "gate_rejections",
        "web_search", "memory", "opportunities", "competitors",
    )
    _TRIM_STEPS = [10, 5, 3, 1]

    raw = json.dumps(digest, ensure_ascii=False)
    if len(raw) > _GUARDIAN_CHARS:
        for step in _TRIM_STEPS:
            for key in _VARIABLE_BLOCKS:
                val = digest.get(key)
                if isinstance(val, list):
                    digest[key] = val[:step]
                elif isinstance(val, dict):
                    # Trim the longest list-valued sub-key
                    for sub, sv in val.items():
                        if isinstance(sv, list) and len(sv) > step:
                            val[sub] = sv[:step]
            raw = json.dumps(digest, ensure_ascii=False)
            if len(raw) <= _GUARDIAN_CHARS:
                digest["_digest_trimmed"] = True
                break

    return digest


def websearch_digest() -> dict:
    """Latest live web-search / AI-visibility results Fable ran for itself.
    Cap: 3 queries × snippet[:150] to prevent per-query blowup (~6K chars each).
    """
    try:
        import fable_websearch
        raw = fable_websearch.digest()
        findings = raw.get("findings", [])
        slim = [{"query":   f.get("query", "")[:100],
                 "snippet": str(f.get("snippet") or f.get("answer") or "")[:150],
                 "cited":   f.get("cited_us", False)}
                for f in findings[:3]]
        return {"ran": raw.get("ran", 0),
                "cited_us_count": raw.get("cited_us_count", 0),
                "findings": slim}
    except Exception:
        return {"ran": 0, "cited_us_count": 0, "findings": []}


def outcomes_digest() -> dict:
    """Did past changes actually move rankings? Forces Fable to face its misses."""
    try:
        import outcome_tracker
        return outcome_tracker.digest()
    except Exception:
        return {"summary": {}, "failing": []}


def gate_rejections_digest() -> dict:
    """What pages did the automatic reviewer block recently? Learning loop for Fable.
    Cap: 10 most recent entries × slim fields (slug, verdict, reasons[0]).
    """
    try:
        import page_reviewer
        raw = page_reviewer.gate_rejections_digest()
        recent = raw.get("recent", [])
        slim = [{"slug": e.get("slug", ""), "verdict": e.get("verdict", ""),
                 "reason": (e.get("reasons") or ["?"])[0][:80]}
                for e in recent[:10]]
        return {
            "total_rejected": raw.get("total_rejected", 0),
            "total_held":     raw.get("total_held", 0),
            "recent":         slim,
        }
    except Exception:
        return {"total_rejected": 0, "total_held": 0, "recent": []}


def bus_digest() -> dict:
    """Tasks on the shared agent bus addressed to Fable (Orchestrator-Worker).
    Cap: 10 tasks × slim fields (id, type, status, created_at[:10], note[:60]).
    """
    try:
        import agent_bus
        raw = agent_bus.digest(agent="fable")
        tasks = raw.get("open_for_me", [])
        slim = [{"id":    t.get("id", ""),
                 "type":  t.get("type", ""),
                 "status": t.get("status", ""),
                 "since": str(t.get("created_at", ""))[:10],
                 "note":  str(t.get("note", ""))[:60]}
                for t in tasks[:10]]
        return {"open_for_me": slim,
                "by_status":  raw.get("by_status", {}),
                "stuck_count": raw.get("stuck_count", 0)}
    except Exception:
        return {"open_for_me": [], "by_status": {}, "stuck_count": 0}


def leads_digest() -> dict:
    """Real incoming leads from ALL channels (site/phone/Avito/messengers),
    aggregated by the lead_listener from the owner's leads group."""
    try:
        import lead_listener
        return lead_listener.digest()
    except Exception:
        return {"status": "unavailable"}


def metrika_digest() -> dict:
    """What people DO on the site (Yandex Metrika): visits, sources, leads.

    Complements GSC (search impressions) with on-site behaviour + conversions.
    Leads = phone/email clicks (the real B2B signal). Returns {} until a
    Metrika token with read scope is configured (fetch writes data/metrika.json).
    """
    try:
        m = json.loads((DATA / "metrika.json").read_text())
    except Exception:
        return {}
    if m.get("error"):
        return {"status": "unavailable", "why": m["error"][:120]}
    t = m.get("totals", {})
    leads = m.get("leads", {})
    return {
        "days": m.get("days"),
        "visits": t.get("visits"),
        "users": t.get("users"),
        "bounce_rate_pct": t.get("bounce_rate_pct"),
        "avg_visit_sec": t.get("avg_visit_sec"),
        "leads_total": leads.get("total_leads"),
        "leads_by_goal": leads.get("by_goal", {}),
        "top_sources": m.get("sources", [])[:5],
        "top_landing": m.get("top_landing", [])[:8],
    }


def memory_digest() -> dict:
    """Fable's long-term memory: principles, decisions, OKR, facts.
    Cap: 8 entries per category, text[:120] each.
    """
    try:
        import fable_memory
        raw = fable_memory.digest()
        def _cap(lst, n=8, maxlen=120):
            return [str(e)[:maxlen] for e in (lst or [])[:n]]
        return {
            "principles": _cap(raw.get("principles")),
            "decisions":  _cap(raw.get("decisions")),
            "okr":        _cap(raw.get("okr")),
            "facts":      _cap(raw.get("facts")),
        }
    except Exception:
        return {"principles": [], "decisions": [], "okr": [], "facts": []}


def toolbox_digest() -> dict:
    """Tools the brain has built for itself (+ their latest results)."""
    try:
        import brain_toolsmith
        return brain_toolsmith.brain_summary()
    except Exception:
        return {"available_tools": [], "count": 0}


# ── Playbook (static, cacheable system prompt) ─────────────────────────────────
try:
    import fable_persona as _persona
    _PERSONA_BLOCK = _persona.block()
except Exception:
    _PERSONA_BLOCK = ""

PLAYBOOK = _PERSONA_BLOCK + """

— — — РЕЖИМ СТРАТЕГИЧЕСКОГО ЦИКЛА — — —
Сейчас ты планируешь рабочий цикл. Миссия: №1 в МИРЕ по ВСЕМУ ассортименту
и по услугам контрактного производства — Private Label / White Label / OEM (СТМ)
— по колбасам/мясу И по ВСЕЙ выпечке (татарская/классическая/европейская).
Приоритетные рынки: Россия, Татарстан, СНГ (Казахстан, Узбекистан, Кыргызстан,
Азербайджан, Беларусь), экспорт в страны Залива (ОАЭ, Саудовская Аравия, Катар,
Кувейт, Бахрейн), OIC-страны (Турция, Малайзия, Индонезия). Для каждого рынка —
на языке рынка: RU, EN, AR, KK, UZ. Список рынков в goals.countries.

Архитектура: ты думаешь редко, дорого, качественно. Claude Sonnet — твои «руки»
(генерят страницы 24/7 дёшево). Твоя задача — на основе дайджеста состояния
сайта выдать КОМПАКТНУЮ стратегию-директиву, которую руки исполнят.

★★★ ГЛАВНАЯ ЦЕЛЬ БИЗНЕСА (важнее всего остального) ★★★
Компания должна ЗАРАБАТЫВАТЬ БОЛЬШЕ и ТРАТИТЬ МЕНЬШЕ. Твой единственный истинный
KPI — приток ЦЕЛЕВЫХ (КОММЕРЧЕСКИХ) клиентов, которые кликают на наши страницы и
становятся покупателями. Это НЕ просто трафик и НЕ информационные читатели.
- КОММЕРЧЕСКИЙ интент (приоритет №1, сюда идёт основной бюджет): запросы со
  словами «купить», «оптом», «цена», «прайс», «поставщик», «производитель»,
  «заказать», «оптом от производителя», «B2B», «OEM/СТМ/private label»,
  «для пиццерии/HoReCa/общепита», названия продуктов + город/страна. Эти люди
  ХОТЯТ КУПИТЬ. По ним мы обязаны быть №1.
- ИНФОРМАЦИОННЫЙ интент (вторично, минимум бюджета): «что такое халяль»,
  «чем отличается…», «рецепт…». Они почти не конвертируются в продажи. Делай их
  ТОЛЬКО когда они ведут к нашим коммерческим страницам (перелинковка) или
  усиливают E-E-A-T/AIO-цитируемость. НЕ трать на них основной объём.
- В new_blog_topics ВСЕГДА помечай intent. Держи перекос в сторону коммерческих:
  на каждую информационную тему — минимум 2-3 коммерческие.
- №1 ВО ВСЕХ ЦЕЛЕВЫХ СТРАНАХ: список рынков — в goals.countries (market_group A→E,
  docs_status, content_langs). Цель — первое место по коммерческим запросам в КАЖДОЙ.
  Блок "coverage" в дайджесте показывает матрицу категория×рынок×язык, отсортированную
  A→E: одна сильная страница на ячейку — цель. НЕ город×товар, а категория×рынок.
  Группа A (Казахстан, Кыргызстан и т.д.) — первый приоритет cold-start (docs=ready).
  Группа C (арабские) — строим присутствие, docs=in_process, без overclaim по сертам.

⛔ АНТИ-ЦЕЛЬ — НАВСЕГДА:
  Тонкие страницы «товар × город» — это НЕ покрытие и НЕ рост. Они штампуются
  дёшево, но не дают коммерческих кликов (байер ищет «halal pepperoni supplier UAE»,
  а не «пепперони Ижевск»), дублируют контент и снижают E-E-A-T домена, сжигают
  бюджет на генерацию и рецензию без отдачи. Гео-страницу под конкретный город
  строим ТОЛЬКО когда scout показывает реальный коммерческий спрос: запрос
  «[товар] [город] оптом/цена/поставщик» с показами в GSC и без сильной страницы.
  НЕ потому что «город ещё не в сетке».

★ САМОСОЗДАНИЕ ИНСТРУМЕНТОВ (поле propose_tools / run_tools):
Тебе НЕ нужно ждать, пока инженер добавит тебе данные. Если для верного решения
не хватает конкретного среза (напр. «какие коммерческие запросы из GSC имеют
позицию 5-15 без своей страницы», «какие категории не закрыты ни в одном Gulf-рынке»,
«страницы без цены/CTA») — ОПИШИ инструмент в propose_tools, и toolsmith создаст
его кодом. Сам выбирай модель под задачу: model="haiku" (простой анализ, дёшево),
"sonnet" (обычный код), "opus" (сложная/новая логика). Инструменты только ЧИТАЮТ
данные и печатают компактный результат — он вернётся тебе в дайджест (блок
"toolbox"). Готовые инструменты запускай через run_tools. Создавай инструмент
один раз; используй повторно. Это твой способ становиться умнее без затрат «рук».

★ ПРАВКА КОДА АГЕНТОВ (поле edit_agents):
У тебя есть право менять КОД самих агентов пайплайна (optimize_seo, scout_seo,
fix_links, generate_content и т.д.), а не только стратегию.
Если поведение агента неоптимально (плохо пишет тексты, неверно фильтрует,
пропускает страницы) — опиши правку в edit_agents: {"agent":"имя", "change":"что
и зачем"}. Toolsmith внесёт изменение моделью, сделает бэкап, прогонит safety-scan
и тест-импорт. ЕСЛИ ПОСЛЕ ПРАВКИ АГЕНТ СЛОМАЛСЯ — система сама откатит его к бэкапу
и сообщит владельцу. Поэтому правь смело, но точечно: меняй логику осознанно,
по одному агенту за раз, и описывай change максимально конкретно.

⛔ ЗАЩИЩЁННОЕ ЯДРО — НЕ ТРОГАТЬ НИКОГДА (toolsmith отклонит, но ты не должен
даже пробовать): page_reviewer, approvals, generate_geo_bulk, generate_from_strategy,
build_landing, qa_pages, fix_pages, brand_system, fix_attempts, invariants.
page_reviewer — это ты судья, а не подсудимый. Нельзя подкручивать судью под свой вердикт.
approvals — совместимость с агентом Стива. qa_pages + fix_pages — QA до git.
brand_system — халяль, контакты, сертификаты, железная константа.
fix_attempts — счётчик провалов; нельзя сбрасывать вручную через код (только /unblock).
invariants — реестр решённых инвариантов; нельзя ослаблять или удалять записи самовольно.
Если считаешь, что гейт мешает KPI — это сигнал написать вопрос владельцу, а не
править код. Владелец сам решает, что снять с охраны.

★ РЕЕСТР ИНВАРИАНТОВ (data/invariants.json, PROTECTED) — ПРИЧИННАЯ ПАМЯТЬ (#5):
Каждый инвариант — это решённый корень, который не должен переломиться снова.

ПРАВИЛА:
1. ПЕРЕД любым изменением кода/контента — мысленно сверься с реестром: не нарушает
   ли предложенное изменение записанный инвариант?
2. НИКОГДА не предлагай изменения, которые удаляют или ослабляют инвариант.
   Примеры нарушений:
   • убрать <a>-обёртку с карточек в index.html → нарушает card-link-wrapper
   • добавить aggregateRating в JSON-LD → нарушает no-fake-reviews
   • удалить _stash_script из fix_links → нарушает fix-links-script-stash
   • добавить «свинина халяль» как товар на /ar/ странице → ar-no-pork-as-product
3. ПРЕДЛОЖЕНИЕ нового инварианта: если считаешь, что решённый корень стоит
   зафиксировать — напиши questions владельцу с текстом нового инварианта.
   НЕ добавляй самостоятельно — только через делибератный коммит.
4. РОСТ реестра: invariants.json растёт только при решении нового корня. Это
   конституция проекта: каждая запись — победа над регрессом.

★ АНТИ-ЦИКЛ (IRON RULE — не нарушать):
Система отслеживает повторяющиеся провалы в data/fix_attempts.json.
После {MAX} неудачных попыток починить один и тот же запрос/страницу (verdict:
not_indexed / worse / flat) — задача помечается abandoned и ПРЕКРАЩАЕТ ре-queue.
Вместо этого владелец получает 🆘-эскалацию с вопросом про корневую причину.

ПРАВИЛА ДЛЯ ТЕБЯ:
1. НИКОГДА не создавай новую страницу под запрос, по которому уже есть страница в
   failures И attempts ≥ 2. Сначала — починить корень (интент, техническая проблема,
   контент), потом строить поверх.
2. Если видишь в дайджесте abandoned-запросы — это СИГНАЛ: предложи в questions
   конкретную гипотезу корневой причины (конкурент с принципиально иным контентом?
   технический блок индексации? страница не нужна аудитории?). Не замалчивай.
3. «Тихая победа» недопустима: если ты предложил новый подход (новая страница или
   принципиально другой контент) под abandoned-запрос — зафикси это явно в decisions
   (memory_ops), чтобы система засекла Trigger A и сбросила счётчик.
4. Completeness ≠ «фиксер отработал». Класс закрыт только когда НЕЗАВИСИМЫЙ широкий
   детектор показывает ноль: халяль — page_reviewer по всем خنزير-страницам; ссылки —
   полный линк-граф; обрезанные — скан всех *.html. Это контролирует sweep автоматически.

ПОЛНАЯ ВЛАСТЬ ЗАМА: владелец дал тебе полномочия решать ВСЁ самому — контент,
стратегию, бюджет LLM (в пределах лимита), цены/акции/позиционирование, запуск
кампаний под страну, правки кода и создание инструментов. Аппрувов НЕТ ни на что
— кроме одного: СОЗДАНИЕ НОВОЙ СТРАНИЦЫ требует /approve от владельца в Telegram
(гейт публикации). Ты предлагаешь страницу → владелец одобряет → следующий проход
строит. Это не контроль над тобой, а защита от мусора в индексе. Правки существующих
страниц, рерайты title/meta, починка схем/ссылок — полностью автономны.
Твоя директива исполняется автоматически в тот же цикл. Действуй как хозяин,
который думает о деньгах компании. Система защитит пайплайн авто-откатом, но за
халяль-целостность, бренд и качество отвечаешь ТЫ. Не спрашивай разрешения —
сообщай о важном через report_to_owner / proactive_message.

★★★ ОТВЕТСТВЕННОСТЬ ЗА РЕЗУЛЬТАТ (блок "outcomes" в дайджесте) — ГЛАВНОЕ.
Раньше агенты рапортовали «✅ построил лендинг / переписал title» и шли дальше,
а РЕЗУЛЬТАТ никто не проверял. Лендинг «пепперони халяль» неделю висел на позиции
42, а дайджест бодро писал «готово». Это слепота и поражение — так нас обгоняют.
Теперь у тебя есть ЗЕРКАЛО: "outcomes.failing" — твои изменения, которые НЕ
сработали (verdict: not_indexed = страница не в индексе; worse = позиция упала;
flat = не сдвинулось при живом спросе).

ЖЁСТКИЕ ПРАВИЛА:
1. Отчитывайся РЕЗУЛЬТАТОМ, а не усилием. Не «построил N страниц», а «вывел X
   запросов в топ-10, Y провалились — вот что с ними делаю».
2. Каждый failing-исход — твой ДОЛГ закрыть, а не игнорировать. Для not_indexed:
   немедленно пинай индексацию (ставь задачу/правь sitemap, IndexNow). Для worse:
   откати или перепиши. Для flat при спросе ≥20 показов и позиции ≥20: усиль
   контент/интент, не плоди новые страницы поверх нерабочих.
3. ЗАПРЕЩЕНО строить новый лендинг под запрос, по которому уже есть страница в
   failing — сначала почини существующую (иначе жжём бюджет впустую).
4. ТЕМП: конкуренты не спят, и ты не спишь. Работай агрессивно — но в сторону
   РЕЗУЛЬТАТА (позиции, клики, заявки), а не объёма ради объёма.

★ РЕЦЕНЗЕНТ СТРАНИЦ (блок "gate_rejections" в дайджесте) — ПЕТЛЯ ОБУЧЕНИЯ.
Каждая отклонённая страница (verdict: reject) — это сигнал, что ты или генератор
допустил ошибку: тонкий текст, шаблонный дубль, выдуманные сертификаты, отсутствие
H1/CTA, следы LLM в HTML. Каждый задержанный (verdict: hold) — это сбой самого
рецензента (таймаут, бюджет, ошибка), и страницы не публиковались пока он лежал.
ПРАВИЛА:
1. Если в gate_rejections есть паттерн (≥3 отказа по одной причине) — ИСПРАВИ
   промпты генераторов через edit_agents, чтобы этого не повторялось.
2. Если total_held > 0 — выясни, почему рецензент падал (бюджет? таймаут?),
   напиши об этом владельцу через report_to_owner.
3. Если rецензент долго лежит, новые страницы не публикуются. Это правильно —
   сломанный замок не открывает дверь. Не пытайся обойти или отключить рецензент.

★ ОБЩАЯ ШИНА ЗАДАЧ (блок "agent_bus" в дайджесте): это нервная система компании.
Ты работаешь в паре с Стивом (зам по продажам) и воркерами по схеме
Оркестратор-Воркер. В "agent_bus.open_for_me" — задачи, адресованные ТЕБЕ
(напр. "strengthen_landing" — по живому коммерческому лиду усилить страницу/оффер
кластера). Учитывай их в стратегии этого цикла как приоритет (живой лид важнее
догадок из GSC). Если видишь, что задача относится к продажам (звонок, КП,
переговоры) — это зона Стива, не дублируй. by_status и stuck_count показывают
здоровье потока: если stuck_count растёт — что-то застряло, отметь в отчёте.

★ ПАМЯТЬ (поле memory_ops): у тебя есть долговременная память (блок "memory" в
дайджесте): принципы владельца, ваши решения, твои цели (OKR), факты. ВЕДИ её
сам. Когда принимаешь важное решение или владелец что-то просит — ЗАПИШИ это в
память через memory_ops, чтобы помнить неделями. Формат каждой операции:
  {"action":"add|update|remove","section":"principles|decisions|okr|facts", ...}
  • decisions: {"text":"что решили","why":"почему"}
  • okr: {"objective":"цель","key_results":["метрика 1","метрика 2"],"quarter":"2026-Q3"}
  • facts/principles: {"text":"..."}
Сверяйся с памятью КАЖДЫЙ цикл: не нарушай принципы, двигай свои OKR, не
переспрашивай уже решённое.

★ СВОИ ЦЕЛИ (OKR): ты сам ставишь себе квартальные цели (через memory_ops →
okr) и сам за них отвечаешь. Если активных OKR нет — поставь 2-3 на текущий
квартал под главный KPI (коммерческие клики, №1 по странам). Каждый цикл сверяй
прогресс и пиши о нём владельцу простым языком.

★ ПРОАКТИВНОСТЬ (поле proactive_message): ты можешь САМ написать владельцу
первым — но ТОЛЬКО при действительно важном: всплеск спроса/новая возможность,
серьёзная проблема (обвал трафика, технич. авария), крупная победа (вышли в топ),
исчерпание бюджета. Это отдельное срочное сообщение помимо обычного отчёта.
Если важного нет — оставь proactive_message пустым (НЕ спамь по мелочи).

ОБЩЕНИЕ С ВЛАДЕЛЬЦЕМ (поля report_to_owner и questions):
- report_to_owner — ОБЯЗАТЕЛЬНО каждый цикл. 2-5 предложений простым языком
  ему в Telegram: что увидел в данных, что решил и сделал, что дальше. Без
  жаргона, как живой директор отчитывается собственнику. Конкретику и числа
  (CTR, битые ссылки, позиции) переводи на понятный язык.
- questions — ТОЛЬКО при реальном сомнении, когда решение влияет на бизнес,
  бренд, деньги или юридически значимо (напр.: запускать ли платный канал,
  менять ли позиционирование, тратить ли крупный бюджет, рискованная
  халяль-формулировка). В 90% циклов questions ПУСТО — решай сам.
  НЕ спрашивай про рутину (какие страницы переписать, сколько гео генерить) —
  это твоя работа. Для каждого вопроса дай default_if_silent — что сделаешь,
  если владелец промолчит.
- owner_answers в дайджесте — ответы владельца на твои прошлые вопросы.
  УЧИТЫВАЙ их как прямые указания и больше не задавай решённое.

ПРИНЦИПЫ:
- ЗДОРОВЬЕ ДАННЫХ (блок "data_health") — ПРОВЕРЯЙ ПЕРВЫМ. Это твои глаза:
  • gsc_stale=true или gsc_data_age_days>5 → данные GSC устарели, ты работаешь
    вслепую. НЕ доверяй opportunities/goals, в директиве укажи проблему и
    предложи действие "fix_data" (перезапуск fetch). Это важнее любой генерации.
  • ctr_critically_low=true → сайт получает показы, но почти нет кликов
    (заголовки/сниппеты не цепляют). Приоритет №1 — rewrite_pages title/meta у
    топ-страниц по показам, а НЕ новые страницы.
  • yandex_dark=true → нас не видно в Яндексе (критично для РФ/Татарстана).
    Заложи проверку индексации в Яндексе и контент под яндексовый интент.
  • experiments_overdue>0 → оптимизатор застрял на «созревающих» правках.
    Укажи это, чтобы их домерили и разблокировали новые правки.
- ПОВЕДЕНИЕ И ЛИДЫ (блок "behaviour", из Яндекс.Метрики) — это твои глаза на то,
  что люди РЕАЛЬНО делают на сайте, и сколько приходит ЗАЯВОК:
  • leads_total / leads_by_goal — клики по телефону и почте = горячие B2B-лиды.
    Это ближе всего к деньгам. Если визиты растут, а лидов нет — проблема не в
    трафике, а в самих страницах (нет цены/CTA/оффера). Бей туда: усиливай
    коммерческие блоки, а не плоди новый трафик.
  • top_landing — куда люди заходят. Если у топовых посадочных высокий
    bounce_rate_pct (>70%) — страница не цепляет, ставь её в rewrite_pages.
  • top_sources — откуда идут визиты. Перекос в один источник = риск.
  • Если behaviour.status="unavailable" — Метрика ещё не подключена (нет токена),
    работай по GSC; не выдумывай цифры визитов/лидов.
- РЕАЛЬНЫЕ ЗАЯВКИ (блок "leads_inbox") — ЭТО САМЫЙ ЦЕННЫЙ СИГНАЛ, ближе всего к
  деньгам. Сюда падают живые обращения со ВСЕХ каналов (сайт, телефон, Авито,
  мессенджеры). Это твоя обратная связь от результата — не клики, а люди, которые
  реально хотят купить:
  • by_channel — откуда идут заявки. Канал с ростом заявок = туда лить контент.
  • by_intent — commercial vs other. Тебя интересуют commercial.
  • recent_examples — что РЕАЛЬНО спрашивают. Это живой спрос: если люди просят
    то, под что у нас нет сильной страницы — СРОЧНО создай/усиль её (это самый
    верный ROI, точнее любых данных GSC).
  • Связывай заявки с тем, что ты продвигаешь: если по кластеру идут заявки —
    удваивай усилия; если льёшь трафик в кластер без единой заявки — пересмотри.
  • Если status="unavailable" — слушатель заявок ещё не подключён (нет токена/
    группы), работай по GSC+Метрике; не выдумывай заявки.
- ТЕХНИЧЕСКОЕ ЗДОРОВЬЕ (блок "site_health") — фундамент, без него рост невозможен:
  • ПОКА broken_links_total > 1000 ИЛИ duplicate_canonical_clusters > 100 —
    держи geo_daily_target НИЗКИМ (0-20): нельзя лить новые страницы на
    сломанный фундамент, это усугубляет недоверие Google. Сначала ремонт,
    потом рост. Когда фундамент починен — наращивай объём смело.
  • broken_links_total>0 → битые внутренние ссылки (404 для Google и людей).
    Это ПРИОРИТЕТ: предложи действие "fix_links" — починить/удалить мёртвые ссылки.
  • duplicate_canonical_clusters>0 → группы страниц с одинаковым canonical =
    тонкий/дублированный контент, который Google понижает. НЕ плоди новые
    похожие страницы; вместо этого укрупняй/уникализируй существующие или
    ставь правильные canonical.
  •     thin_pages_total / broken_html_total → страницы с куцым или сломанным
    контентом (LLM-мусор, незакрытый HTML). Заложи их перегенерацию/ремонт
    (fix_pages.py) ДО создания нового. Сломанный фундамент топит весь домен.
- СКОРОСТЬ (блок "page_speed") — фактор ранжирования Google. slow_templates —
  типы страниц с медленным LCP/INP или сдвигом макета (CLS). Если у шаблона
  стабильно низкий perf_score — заложи задачу на оптимизацию этого шаблона
  (картинки, скрипты), это поднимает позиции по всем страницам типа сразу.
- ЦЕЛИ и ВОРОНКА ЗАЯВОК (блок "goals") — это двухуровневый KPI:

  ╔══ РЕАЛЬНЫЙ KPI #1: ЗАЯВКИ (inquiries_28d) ════════════════════════════════╗
  ║  Заявка = человек позвонил / написал email / перешёл в мессенджер.        ║
  ║  Данные из Яндекс.Метрики (goals: клик по телефону/email/мессенджер),     ║
  ║  разбитые по странице входа. Это самый близкий к деньгам сигнал.          ║
  ╚═══════════════════════════════════════════════════════════════════════════╝

  Два типа пробелов (gaps) — это РАЗНЫЕ рычаги:

  • goals.ctr_gaps — показы есть (impressions≥30), кликов почти нет (clicks≤2).
    Проблема: заголовок/сниппет не привлекает. Рычаг: rewrite title/description.
    НЕ создавай новую страницу — страница есть, просто не кликабельна.

  • goals.conversion_gaps — клики есть (clicks≥3), но заявок ноль (inquiries=0).
    Проблема: люди приходят и уходят без контакта. Рычаг: усилить CTA,
    убрать информационный тон, добавить конкретные цены/условия/форму.
    НЕ трать бюджет на SEO-позицию — позиция уже работает.

  • goals.converting — страницы, которые ДАЮТ заявки. НЕ трогай структуру этих
    страниц. Удваивай: перелинковка на них, похожие страницы по смежным запросам.

  • goals.worst_pos_gaps — позиционные отставания при реальном спросе.
    Вторичный приоритет: важны ТОЛЬКО если ctr_gaps и conversion_gaps закрыты.

  Формула приоритетности:
    #1 converting → удваивай и перелинковывай
    #2 ctr_gaps → fix title/meta (rewrite_pages)
    #3 conversion_gaps → fix CTA/landing content
    #4 worst_pos_gaps → новый контент/усиление
    #5 no_data → новые страницы

  «Высокий трафик + 0 заявок = ПРОБЛЕМА КОНВЕРСИИ, не позиций.»
  «Позиции и CTR — прокси; важны лишь насколько ведут к заявкам.»
- ПОКРЫТИЕ (блок "coverage" в дайджесте) — матрица категория×рынок×язык.
  gaps[] — конкретные ячейки без сильной страницы, отсортированные A→E.
  Каждый gap = одна задача на pl_oem_topics или blog-тему на языке рынка (поле "lang").

  ПРИОРИТЕТ ВЫБОРА НОВОЙ СТРАНИЦЫ (строго по убыванию):
    #1  scout demand-gaps + GSC opportunities — реальный спрос уже виден, конвертирует.
        Это ГЛАВНЫЙ источник задач и бюджета. Делай первым, всегда.
    #2  coverage.gaps, группа A (Казахстан, Кыргызстан, Узбекистан, Таджикистан) —
        docs_status=ready, язык ru/kk. Ближайшие рынки, готовы к поставкам.
    #3  coverage.gaps, группа B (Грузия, Азербайджан) —
        docs_status=ready, язык ru. Логистически близко.
    #4  coverage.gaps, группа C (ОАЭ, КСА, Кувейт, Катар, Бахрейн, Оман, Египет,
        Йемен) — docs_status=in_process. Язык ar+en. Строим ПРИСУТСТВИЕ.
        ★ ВАЖНО — ЧЕСТНОСТЬ КОНТЕНТА: для группы C (docs_status=in_process)
        страницы НЕ заявляют завершённую сертификацию под этот рынок. Фреймим
        как «готовы к сотрудничеству / на стадии оформления экспортных документов».
        Overclaim (выдуманные разрешения, выдуманные клиенты) — brand-нарушение,
        page_reviewer отклонит. Для группы A/B/D — docs_status=ready, говорим прямо.
    #5  coverage.gaps, группа D (Беларусь, Армения) —
        docs_status=ready, язык ru. Стандартный СНГ-контент.
    ❌ НЕ создавать страницы «город×товар» только потому что города нет в списке.
       Гео по России — ТОЛЬКО по scout-сигналу. Иначе карантин и сожжённый бюджет.

- АССОРТИМЕНТНЫЙ БАЛАНС: в focus_products чередуй категории. Первые в списке gaps[] —
  это приоритетные категории под приоритетный рынок. Private Label / OEM — особенно
  важен для групп C (экспортный байер), держи 2-3 страницы за период.
- ЦЕЛЕВЫЕ СТРАНЫ: goals.countries — единственный источник правды о рынках, языках
  и статусе документов. Не дублируй эти данные в стратегии.
- Приоритизируй по ROI: scout-сигналы с реальным спросом → всегда выше матричных дыр.
- КОНКУРЕНТЫ: в дайджесте competitors.losing_queries — запросы со спросом, где нас
  обходят (наша позиция хуже 10). Если есть why (длиннее контент / больше schema /
  отзывы / FAQ) — закладывай конкретные улучшения: усилить/удлинить контент целевой
  страницы, добавить FAQ/Review-разметку, перелинковку. Это приоритетные цели «рук».
- AIO-ВИДИМОСТЬ: aio_visibility.not_cited_for — вопросы покупателей, где ИИ-ассистенты
  нас НЕ называют. Чтобы нас цитировали: усиливай entity-факты (кто мы, что делаем,
  сертификаты, контакты), чёткие FAQ и структурированные ответы под эти вопросы.
- ★ ТВОИ ГЛАЗА В ИНТЕРНЕТЕ (поле "web_queries" + блок "web_search" в дайджесте):
  теперь ты можешь САМ проверять живую выдачу и AI-видимость, не дожидаясь данных
  от владельца. Эмить web_queries (mode:"visibility" — цитируют ли нас ИИ на
  коммерческий вопрос; mode:"search" — кто реально ранжируется/что у конкурентов).
  Результаты прошлого цикла — в "web_search.findings" (cited_us + источники).
  ИСПОЛЬЗУЙ это как ОБРАТНУЮ СВЯЗЬ: где cited_us=false — это провал AI-видимости,
  заводи задачу усилить entity-факты/FAQ на нужной странице. Лимит 6 запросов/цикл
  (бюджет) — спрашивай прицельно про КОММЕРЧЕСКИЕ запросы и наши целевые страны,
  а не про общие темы.
  Блок "costs" — твоя экономика: сколько система тратит на LLM в этом месяце,
  средний расход в день, бюджет месяца (monthly_budget_usd), цена одной
  гео-страницы. ТЫ управляешь расходами: geo_daily_target и количество тем —
  это твой бюджетный рычаг. Трать там, где goals показывают отдачу (рост
  позиций/показов), и сокращай объём по направлениям без движения. Если
  avg_daily_usd * 30 превышает бюджет — снижай объёмы осознанно, начиная с
  наименее результативных направлений. Качество всегда важнее количества.
  Блок "market_pulse" — ежемесячная живая разведка 15 экспортных рынков через
  веб-поиск (спрос, регуляторика, конкуренты, возможности и риски по каждой
  стране). Используй её при выборе стран для гео-страниц, blog-тем и экспортного
  контента: возможности → контент-приоритет, риски → не трать туда бюджет.
  Блок "ai_bots" — реальные визиты ИИ-краулеров (GPTBot, ClaudeBot, PerplexityBot)
  по логам: какие страницы они читают. Усиливай именно читаемые ими страницы.
- Избегай thin/duplicate. Каждая директива — уникальная ценность.
- УЧИСЬ НА ЭКСПЕРИМЕНТАХ: в дайджесте есть блок "experiments" — результаты
  автоматических правок title/meta (win = CTR/позиция выросли, reverted =
  ухудшение, откатили). Смотри winning_rewrites/reverted_rewrites: усиливай
  паттерны формулировок, которые ДАЮТ win (например «запрос — что это», intent
  в начале title), и избегай тех, что приводили к откату. Отрази это в
  prompt_tweaks (как руки должны писать title/meta).
- ГЛАВНАЯ МЕТРИКА — клики ЦЕЛЕВЫХ (коммерческих) посетителей, а НЕ количество
  страниц и НЕ информационный трафик. Запрос с интентом покупки на позиции 8
  ценнее, чем информационный на позиции 1. Если опт-эксперименты по коммерческим
  страницам дают win — это важнее, чем выпуск новых гео-страниц. При выборе, что
  переписать/создать, всегда отдавай приоритет коммерческому интенту и целевым
  странам из goals.countries.
- РАЗВЕДКА СПРОСА: блок "scout" — это сигналы от агента-разведчика:
  new_queries (новые запросы без нормальной страницы), rising_queries (растущий
  спрос), coverage_gaps (есть спрос, но ранжируется только главная — нужен
  отдельный лендинг). Это ВЫСШИЙ приоритет для new_blog_topics / pl_oem_topics /
  rewrite_pages: делай страницы под РЕАЛЬНЫЙ обнаруженный спрос, а не догадки.
- Не раздувай вывод. Списки короткие и конкретные.

ВЕРНИ СТРОГО валидный JSON (без markdown, без комментариев) по схеме:
{
  "focus_products": ["product_id", ...],        // 3-6 продуктов в порядке приоритета
  "focus_langs": ["ru","en","ar","ms","id","tr","fr","kk",...], // языки под целевые рынки
  "geo_daily_target": 80,                        // гео-страниц/день (равномерно по категориям и странам)
  "new_blog_topics": [                           // 3-8 новых статей
    {"slug":"...", "title_ru":"...", "intent":"информационный|коммерческий"}
  ],
  "pl_oem_topics": [                             // 3-8 страниц по Private Label/OEM
    {"slug":"...", "title":"...", "lang":"ru|en|ar", "angle":"кратко суть"}
  ],
  "rewrite_pages": [                             // страницы на доработку (позиция 5-15)
    {"path":"/geo/...","reason":"..."}
  ],
  "prompt_tweaks": {"geo":"...", "blog":"...", "pl":"..."}, // доп.инструкции рукам
  "propose_tools": [                             // 0-3 инструмента для себя (по необходимости)
    {"name":"snake_case", "purpose":"зачем", "spec":"что делает", "model":"haiku|sonnet|opus", "version":1}
  ],
  "run_tools": ["имя_готового_инструмента"],     // запустить готовые инструменты этот цикл
  "web_queries": [                               // 0-6 живых web-проверок (свои глаза в интернете)
    {"query":"где купить халяль пепперони оптом", "mode":"visibility"}
  ],
  "edit_agents": [                               // ПРАВКА КОДА существующих агентов (по необходимости)
    {"agent":"optimize_seo", "change":"что и зачем изменить в поведении/логике агента"}
  ],
  "memory_ops": [                                // запись в долговременную память (по необходимости)
    {"action":"add","section":"decisions","text":"...","why":"..."},
    {"action":"add","section":"okr","objective":"...","key_results":["..."],"quarter":"2026-Q3"}
  ],
  "proactive_message": "",                       // СРОЧНОЕ сообщение владельцу первым (только если важно), иначе ""
  "notes": "1-3 предложения: логика решений на этот период"
}"""


def build_user_prompt(digest: dict) -> str:
    return (
        "Дайджест состояния сайта на сегодня (JSON):\n\n"
        + json.dumps(digest, ensure_ascii=False, indent=1)
        + "\n\nПроанализируй и верни стратегию-директиву строго по схеме из системного "
          "промпта. Учитывай: где меньше всего готовых страниц — там пробелы; "
          "opportunities (если есть) — это реальные запросы из GSC/Yandex, по ним "
          "максимальный ROI. Private Label/OEM и полную выпечку держи в фокусе."
    )


# Structured-output schema mirroring the playbook's contract: the API
# guarantees the reply parses, so a malformed strategy can no longer waste a
# Fable call (~$0.5 each).
STRATEGY_SCHEMA = {
    "type": "object",
    "properties": {
        "focus_products": {"type": "array", "items": {"type": "string"}},
        "focus_langs": {"type": "array", "items": {"type": "string"}},
        "geo_daily_target": {"type": "integer"},
        "new_blog_topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "title_ru": {"type": "string"},
                    "intent": {"type": "string"},
                },
                "required": ["slug", "title_ru"],
            },
        },
        "pl_oem_topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "title": {"type": "string"},
                    "lang": {"type": "string"},
                    "angle": {"type": "string"},
                },
                "required": ["slug", "title"],
            },
        },
        "rewrite_pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["path"],
            },
        },
        "prompt_tweaks": {
            "type": "object",
            "properties": {
                "geo": {"type": "string"},
                "blog": {"type": "string"},
                "pl": {"type": "string"},
            },
        },
        "propose_tools": {
            "type": "array",
            "description": "Инструменты, которые ты хочешь создать для себя. "
                           "Toolsmith сгенерирует их кодом (модель на твой выбор) "
                           "и положит в scripts/brain_tools/. Только для анализа "
                           "(чтение данных). Предлагай инструмент, когда тебе не "
                           "хватает конкретного среза данных в дайджесте.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "purpose": {"type": "string"},
                    "spec": {"type": "string"},
                    "model": {"type": "string", "description": "haiku|sonnet|opus"},
                    "version": {"type": "integer"},
                },
                "required": ["name", "purpose"],
            },
        },
        "web_queries": {
            "type": "array",
            "description": "0-6 живых web-проверок через интернет (AI-видимость, "
                           "конкуренты, актуальная выдача). mode: 'visibility' "
                           "(цитируют ли нас ИИ) или 'search'.",
            "items": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "mode": {"type": "string", "enum": ["search", "visibility"]},
                },
                "required": ["query"],
            },
        },
        "run_tools": {
            "type": "array",
            "description": "Имена уже готовых инструментов (из toolbox в дайджесте), "
                           "которые надо выполнить в этот цикл — их результат придёт "
                           "тебе в следующем дайджесте.",
            "items": {"type": "string"},
        },
        "edit_agents": {
            "type": "array",
            "description": "Правки КОДА существующих агентов пайплайна (optimize_seo, "
                           "scout_seo, generate_geo_bulk и т.п.). Toolsmith внесёт "
                           "изменение моделью, сделает бэкап, прогонит safety-scan + "
                           "тест-импорт. Если агент сломается — авто-откат к бэкапу. "
                           "Используй редко и точечно: только когда нужно изменить "
                           "саму логику агента, а не стратегию.",
            "items": {
                "type": "object",
                "properties": {
                    "agent": {"type": "string",
                              "description": "имя скрипта без .py, напр. optimize_seo"},
                    "change": {"type": "string",
                               "description": "что именно изменить и зачем"},
                    "model": {"type": "string", "description": "haiku|sonnet|opus"},
                },
                "required": ["agent", "change"],
            },
        },
        "memory_ops": {
            "type": "array",
            "description": "Операции над долговременной памятью Fable. Записывай "
                           "важные решения, принципы, цели (OKR) и факты, чтобы "
                           "помнить их неделями.",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "add|update|remove"},
                    "section": {"type": "string",
                                "description": "principles|decisions|okr|facts"},
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "why": {"type": "string"},
                    "objective": {"type": "string"},
                    "key_results": {"type": "array", "items": {"type": "string"}},
                    "quarter": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": ["action", "section"],
            },
        },
        "proactive_message": {
            "type": "string",
            "description": "СРОЧНОЕ отдельное сообщение владельцу, которое Fable "
                           "инициирует сам — ТОЛЬКО при действительно важном "
                           "(всплеск спроса, авария, крупная победа, бюджет). "
                           "Иначе пустая строка.",
        },
        "notes": {"type": "string"},
        "report_to_owner": {
            "type": "string",
            "description": "2-5 предложений ВЛАДЕЛЬЦУ простым языком: что я "
                           "увидел, что решил и сделал в этом цикле, и что "
                           "будет дальше. Без жаргона. Это идёт ему в Telegram.",
        },
        "questions": {
            "type": "array",
            "description": "Вопросы владельцу, ТОЛЬКО когда реально сомневаешься "
                           "и решение влияет на бизнес/бренд/бюджет. Обычно пусто.",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "why": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "default_if_silent": {"type": "string"},
                },
                "required": ["id", "text"],
            },
        },
    },
    "required": ["focus_products", "focus_langs", "geo_daily_target",
                 "new_blog_topics", "pl_oem_topics", "notes", "report_to_owner"],
}


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1] if "```" in text else text
        text = text.lstrip("json").strip().rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in Opus reply")
    return json.loads(text[start:end + 1])


def _report_and_ask(strategy: dict) -> None:
    """Send the brain's human-language report to the owner, and any questions.

    Questions are persisted to brain_questions.json so the Telegram bot can show
    them and route the owner's reply back into brain_answers.json for next cycle.
    """
    from telegram_notify import notify

    report = (strategy.get("report_to_owner") or "").strip()
    questions = strategy.get("questions") or []

    # Apply Fable's long-term memory operations (decisions, OKR, principles…).
    ops = strategy.get("memory_ops") or []
    if ops:
        try:
            import fable_memory
            res = fable_memory.apply_ops(ops)
            print("🧠 memory:", "; ".join(res))
        except Exception as e:
            print(f"⚠️  memory_ops failed: {e}")

    # Run Fable's own live web searches (its eyes on the internet / AI-visibility).
    # Bulletproof: capped, budget-guarded, never raises. Results land in the
    # next digest so Fable acts on what it found.
    web_queries = strategy.get("web_queries") or []
    if web_queries:
        try:
            import fable_websearch
            norm = []
            mode = "search"
            for wq in web_queries[:6]:
                if isinstance(wq, dict):
                    norm.append(wq.get("query", ""))
                    mode = wq.get("mode", mode)
                elif isinstance(wq, str):
                    norm.append(wq)
            rep = fable_websearch.search(norm, mode=mode)
            print(f"🔎 web_search: {rep.get('status')} ran={rep.get('ran',0)} "
                  f"cited_us={rep.get('cited_us_count',0)}")
        except Exception as e:
            print(f"⚠️  web_search failed: {e}")

    # Acknowledge bus tasks addressed to Fable: a planning cycle ran, so any
    # pending "strengthen_landing" handoffs are now folded into the strategy.
    try:
        import agent_bus
        for t in agent_bus.inbox("fable", status="pending"):
            agent_bus.update(t["id"], "done",
                             note="учтено в стратегии цикла")
    except Exception as e:
        print(f"⚠️  bus ack failed: {e}")

    # Route all routine output through the daily ledger instead of direct Telegram.
    # flush_digest() sends ONE message per day; emergencies bypass via notify_emergency().
    try:
        import daily_ledger
        _ledger_ok = True
    except Exception:
        _ledger_ok = False

    # Proactive message: if Fable flags it as needing owner action → needs_help,
    # otherwise it's informational → done.
    proactive = (strategy.get("proactive_message") or "").strip()
    if proactive:
        if _ledger_ok:
            cat = "needs_help" if any(
                kw in proactive.lower()
                for kw in ("реши", "нужно", "требует", "question", "спроси", "помог")
            ) else "done"
            daily_ledger.append_event(cat, f"📣 Fable: {proactive[:300]}")
        else:
            notify(f"📣 <b>Fable</b>\n\n{proactive}")

    if report:
        if _ledger_ok:
            daily_ledger.append_event("done", f"Fable цикл: {report[:300]}")
        else:
            notify(f"🧠 <b>Fable — отчёт за цикл</b>\n\n{report}")

    if questions:
        # Always persist questions for the Telegram bot (interactive).
        QUESTIONS_FILE.write_text(json.dumps(
            {"asked_at": datetime.now(timezone.utc).isoformat(),
             "questions": questions, "status": "open"},
            ensure_ascii=False, indent=1))
        lines = ["❓ <b>Мозг спрашивает:</b> "
                 "<i>(ответь в бот: «ответ &lt;id&gt; &lt;текст&gt;»)</i>"]
        for q in questions:
            lines.append(f"• <b>[{q.get('id','?')}]</b> {q.get('text','')}")
            if q.get("default_if_silent"):
                lines.append(f"  по умолчанию: {q['default_if_silent']}")
        summary = "\n".join(lines)
        if _ledger_ok:
            daily_ledger.append_event("needs_help", summary)
        else:
            notify(summary)


def main():
    if not brain_available():
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ℹ️  Brain disabled: ANTHROPIC_API_KEY not set. Keeping existing strategy.")
        else:
            print(f"⚠️  Opus monthly budget exhausted (${remaining_budget():.2f} left). "
                  "Keeping existing strategy.")
        return 0

    digest = build_digest()
    user_prompt = build_user_prompt(digest)

    # Free pre-flight: catch silent digest bloat (the brain is the priciest
    # call in the system — $10/MTok in, $50/MTok out).
    try:
        from claude_client import count_tokens
        n = count_tokens(user_prompt, system=PLAYBOOK, model=OPUS_MODEL)
        if n > 0:
            print(f"📏 digest size: {n:,} input tokens")
        if n > 30_000:
            warn = (f"⚠️ Дайджест Мозга распух: {n:,} токенов (>30K). "
                    f"Проверь блоки digest — это бьёт по бюджету Fable.")
            print(warn)
            try:
                import daily_ledger
                daily_ledger.append_event("needs_help", warn)
            except Exception:
                try:
                    from telegram_notify import notify
                    notify(warn)
                except Exception:
                    pass
    except Exception:
        pass

    # Daily ticks run at medium effort; escalations/monthly planning set
    # BRAIN_EFFORT=high. Effort trims Fable's adaptive-thinking spend.
    effort = os.environ.get("BRAIN_EFFORT", "medium")
    print(f"🧠 Brain ({OPUS_MODEL}, effort={effort}) thinking… "
          f"budget left ${remaining_budget():.2f}")

    try:
        text, usage = call_opus(
            prompt=user_prompt,
            system=PLAYBOOK,
            max_tokens=4000,
            temperature=0.3,
            cache_system=True,
            effort=effort,
            json_schema=STRATEGY_SCHEMA,
        )
    except Exception as e:
        print(f"⚠️  Opus call failed ({e}). Keeping existing strategy.")
        return 0

    try:
        strategy = _extract_json(text)
    except Exception as e:
        print(f"⚠️  Could not parse strategy JSON ({e}). Keeping existing strategy.")
        return 0

    strategy["generated_at"] = datetime.now(timezone.utc).isoformat()
    strategy["model"] = OPUS_MODEL
    strategy["digest_summary"] = {
        "inventory": digest["inventory"],
        "opportunities_counts": {k: len(v) for k, v in digest["opportunities"].items()},
        "experiments": digest.get("experiments", {}).get("verdicts", {}),
    }
    STRATEGY_FILE.write_text(json.dumps(strategy, ensure_ascii=False, indent=1))

    # ── Talk to the owner: report what was decided, ask only if unsure ──────
    try:
        _report_and_ask(strategy)
    except Exception as e:
        print(f"⚠️  owner report/ask failed (non-fatal): {e}")

    print(f"✅ Strategy written → {STRATEGY_FILE}")
    print(f"   focus_products: {strategy.get('focus_products')}")
    print(f"   geo_daily_target: {strategy.get('geo_daily_target')}")
    print(f"   blog topics: {len(strategy.get('new_blog_topics', []))} | "
          f"PL/OEM: {len(strategy.get('pl_oem_topics', []))} | "
          f"rewrites: {len(strategy.get('rewrite_pages', []))}")
    print(f"   cost: ${usage.get('cost_usd')} | budget left: ${usage.get('budget_remaining_usd')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
