#!/usr/bin/env python3
"""
SEO Optimizer (Level 1–2 meta-agent) — data-driven, closed-loop.

Philosophy: success = clicks/traffic, NOT number of pages. This script does NOT
generate new pages. It improves what already ranks:

  --apply    Find near-page-1 (pos 5-15), low-CTR pages in GSC and rewrite their
             <title>/<meta description> to mirror the actual search-query intent.
             Every change is recorded in the `experiments` table with a "before"
             snapshot so its effect can be measured later.

  --measure  Re-read GSC (after a maturation window) and fill the "after" metrics
             for pending experiments. Classifies each as win / neutral / regression
             and AUTO-REVERTS regressions (restores the previous title/meta).

Env:
  DEEPSEEK_API_KEY        required for --apply
  OPT_MAX_CHANGES         max title/meta rewrites per --apply run (default 8)
  OPT_MIN_IMPR            min 30-day impressions to consider a page (default 25)
  OPT_POS_LOW/OPT_POS_HIGH ranking band to target (default 5..15)
  OPT_MAX_CTR             only pages below this CTR are candidates (default 0.02)
  OPT_MATURE_DAYS         min days before measuring an experiment (default 14)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from seo_db import get_conn, init_db
from claude_client import call_claude, DEEPSEEK_API_KEY, DEFAULT_MODEL

PUBLIC_DIR = Path(__file__).parent.parent / "public"
REPO_DIR   = Path(__file__).parent.parent

# The SQLite DB (data/seo_data.db) is NOT tracked in git — it is rebuilt from the
# GSC/Yandex APIs on every CI run and discarded. Experiments must outlive a single
# run for the measure/revert loop to work, so the durable source of truth is a
# git-tracked JSON ledger committed alongside the HTML changes.
LEDGER_PATH = REPO_DIR / "data" / "experiments.json"

OPT_MAX_CHANGES = int(os.environ.get("OPT_MAX_CHANGES", "8"))
OPT_MIN_IMPR    = int(os.environ.get("OPT_MIN_IMPR",    "25"))
OPT_POS_LOW     = float(os.environ.get("OPT_POS_LOW",   "5"))
OPT_POS_HIGH    = float(os.environ.get("OPT_POS_HIGH",  "15"))
OPT_MAX_CTR     = float(os.environ.get("OPT_MAX_CTR",   "0.02"))
OPT_MATURE_DAYS = int(os.environ.get("OPT_MATURE_DAYS", "14"))
OPT_WINDOW_DAYS = int(os.environ.get("OPT_WINDOW_DAYS", "30"))

# Verdict thresholds (relative to before): a "win" needs CTR up or position up.
WIN_CTR_DELTA = 0.005   # +0.5pp CTR
WIN_POS_DELTA = 1.0     # improved (decreased) average position by >=1
REGRESSION_POS_DELTA = 1.5  # position got worse by >=1.5 → revert

# Brand / navigational queries: the user already knows us, rewriting the title to
# chase them adds no clicks and risks hurting relevance for the real keyword.
BRAND_PATTERNS = ("pepperoni.tatar", "pepperoni tatar", "казанские деликатес",
                  "kazan delicac", "kazandelikates", "пепперони татар")


def is_brand_query(q: str) -> bool:
    ql = (q or "").lower()
    return any(b in ql for b in BRAND_PATTERNS)


# ---------------------------------------------------------------- ledger

def load_ledger() -> list:
    if LEDGER_PATH.exists():
        try:
            return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_ledger(rows: list) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def ledger_summary() -> dict:
    """Aggregate the ledger for reporting/strategy. Used by Telegram & the brain."""
    led = load_ledger()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    verdicts: dict[str, int] = {}
    for e in led:
        v = e.get("verdict", "pending")
        verdicts[v] = verdicts.get(v, 0) + 1
    wins = [e for e in led if e.get("verdict") == "win"]
    reverts = [e for e in led if e.get("verdict") == "reverted"]
    applied_today = [e for e in led if (e.get("applied_at") or "").startswith(today)]
    measured_today = [e for e in led if (e.get("measured_at") or "").startswith(today)]
    return {
        "total": len(led),
        "verdicts": verdicts,
        "pending": verdicts.get("pending", 0),
        "applied_today": applied_today,
        "measured_today": measured_today,
        "recent_wins": wins[-5:],
        "recent_reverts": reverts[-5:],
    }


# ---------------------------------------------------------------- helpers

def url_to_path(page_url: str) -> Path | None:
    """Map a public URL to a file in public/. Returns None if not resolvable."""
    if not page_url:
        return None
    rel = page_url.split("pepperoni.tatar", 1)[-1]
    rel = rel.split("?", 1)[0].split("#", 1)[0].strip("/")
    if not rel:
        rel = "index"
    # Clean URLs map to .html files
    candidates = [PUBLIC_DIR / f"{rel}.html", PUBLIC_DIR / rel / "index.html"]
    for c in candidates:
        if c.exists():
            return c
    return None


def get_title(path: Path) -> str:
    try:
        m = re.search(r"<title>([^<]*)</title>", path.read_text(encoding="utf-8"))
        return m.group(1) if m else ""
    except Exception:
        return ""


def get_description(path: Path) -> str:
    try:
        html = path.read_text(encoding="utf-8")
        m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']',
                      html, re.IGNORECASE)
        return m.group(1) if m else ""
    except Exception:
        return ""


def get_h1(path: Path) -> str:
    try:
        m = re.search(r"<h1[^>]*>(.*?)</h1>",
                      path.read_text(encoding="utf-8"), re.IGNORECASE | re.DOTALL)
        return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
    except Exception:
        return ""


def set_title_meta_h1(path: Path, new_title: str, new_desc: str,
                      old_h1: str = "", new_h1: str = "") -> bool:
    try:
        html = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    if new_title:
        html = re.sub(r"<title>[^<]*</title>", f"<title>{new_title}</title>", html, count=1)
    if new_desc:
        html = re.sub(
            r'(<meta\s+name=["\']description["\']\s+content=)["\'][^"\']*["\']',
            rf'\1"{new_desc}"', html, count=1, flags=re.IGNORECASE,
        )
    # Update only the literal H1 text node we read, to avoid touching og/twitter tags.
    if old_h1 and new_h1 and old_h1 != new_h1:
        html = html.replace(f">{old_h1}<", f">{new_h1}<", 1)
    path.write_text(html, encoding="utf-8")
    return True


def is_valid_html(path: Path) -> bool:
    try:
        from html.parser import HTMLParser
        HTMLParser().feed(path.read_text(encoding="utf-8"))
        t = path.read_text(encoding="utf-8")
        return "</html>" in t and "<title>" in t
    except Exception:
        return False


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       cwd=REPO_DIR, text=True).strip()
    except Exception:
        return ""


# ---------------------------------------------------------------- candidates

def find_candidates(conn) -> list:
    """Pages ranking pos LOW..HIGH with low CTR — the highest-leverage tunables.

    Picks the single best (highest-impression) target query per page, and skips
    pages that already have a pending experiment (don't double-edit before we
    can measure the previous change).
    """
    rows = conn.execute(f"""
        SELECT page,
               query,
               SUM(impressions)                                AS impr,
               SUM(clicks)                                     AS clk,
               SUM(position * impressions) / SUM(impressions)  AS wpos
        FROM gsc_queries
        WHERE date >= date('now', '-' || ? || ' days')
          AND page IS NOT NULL AND page != ''
        GROUP BY page, query
        HAVING impr >= ?
    """, (OPT_WINDOW_DAYS, OPT_MIN_IMPR)).fetchall()

    # best query per page
    best: dict[str, dict] = {}
    page_tot: dict[str, dict] = {}
    for r in rows:
        p = r["page"]
        pt = page_tot.setdefault(p, {"impr": 0, "clk": 0})
        pt["impr"] += r["impr"] or 0
        pt["clk"] += r["clk"] or 0
        cur = best.get(p)
        if cur is None or (r["impr"] or 0) > cur["impr"]:
            best[p] = {"query": r["query"], "impr": r["impr"] or 0,
                       "clk": r["clk"] or 0, "wpos": r["wpos"] or 0}

    pending_pages = {e["page"] for e in load_ledger() if e.get("verdict") == "pending"}

    out = []
    for page, b in best.items():
        if page in pending_pages:
            continue
        if is_brand_query(b["query"]):
            continue
        tot = page_tot[page]
        ctr = (tot["clk"] / tot["impr"]) if tot["impr"] else 0.0
        pos = best[page]["wpos"]
        if OPT_POS_LOW <= pos <= OPT_POS_HIGH and ctr <= OPT_MAX_CTR and tot["impr"] >= OPT_MIN_IMPR:
            out.append({"page": page, "query": b["query"], "pos": pos,
                        "ctr": ctr, "impr": tot["impr"]})
    # Highest impressions first = biggest traffic upside.
    out.sort(key=lambda x: -x["impr"])
    return out


# ---------------------------------------------------------------- apply

def rewrite_title_meta(query: str, current_title: str, current_desc: str,
                       pos: float, lang: str) -> dict | None:
    is_en = lang == "en"
    system = (
        "You are an SEO specialist for the B2B halal meat producer 'Kazan Delicacies' "
        "(pepperoni.tatar). Improve <title> and <meta description> to lift search CTR."
        if is_en else
        "Ты SEO-специалист B2B-производителя халяль мясных деликатесов «Казанские "
        "Деликатесы» (pepperoni.tatar). Улучшаешь <title> и <meta description> для роста CTR."
    )
    rules = (
        "Rules: put the EXACT query phrase at the START of the title (intent match). "
        "Title <= 65 chars, description <= 160 chars, no clickbait, factual, B2B tone. "
        "Halal already implies no pork — do not write 'no pork'. Return ONLY JSON."
        if is_en else
        "Правила: ФОРМУЛИРОВКУ запроса ставь в НАЧАЛО title (intent match). "
        "Title до 65 символов, description до 160 символов, без кликбейта, по делу, B2B-тон. "
        "«Халяль» уже подразумевает отсутствие свинины — НЕ пиши «без свинины». Верни ТОЛЬКО JSON."
    )
    prompt = f"""{rules}

Query / Запрос: «{query}»
Current title: «{current_title}»
Current description: «{current_desc}»
Avg position: {pos:.1f}

JSON: {{"title": "...", "description": "..."}}"""
    try:
        # Title/meta — микрозадача: Haiku в 3 раза дешевле Sonnet без потери
        # качества на 70-символьных заголовках.
        from claude_client import call_claude_cheap
        raw, _ = call_claude_cheap(prompt, system=system, max_tokens=400)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0))
        if not data.get("title"):
            return None
        return {"title": data["title"].strip()[:70],
                "description": (data.get("description") or "").strip()[:170]}
    except Exception as ex:
        print(f"  ⚠️  rewrite failed for «{query}»: {ex}", file=sys.stderr)
        return None


def run_apply(conn) -> int:
    if not DEEPSEEK_API_KEY:
        print("❌ DEEPSEEK_API_KEY not set — cannot rewrite.", file=sys.stderr)
        return 0
    now = datetime.now(timezone.utc).isoformat()
    ledger = load_ledger()
    cands = find_candidates(conn)
    print(f"🔎 {len(cands)} candidate pages (pos {OPT_POS_LOW:.0f}-{OPT_POS_HIGH:.0f}, "
          f"CTR<={OPT_MAX_CTR:.0%}, impr>={OPT_MIN_IMPR})")
    changed = 0
    for c in cands:
        if changed >= OPT_MAX_CHANGES:
            break
        path = url_to_path(c["page"])
        if not path:
            print(f"  · skip (no file): {c['page']}")
            continue
        lang = "en" if "/en/" in c["page"] else "ru"
        cur_title = get_title(path)
        cur_desc  = get_description(path)
        new = rewrite_title_meta(c["query"], cur_title, cur_desc, c["pos"], lang)
        if not new or new["title"] == cur_title:
            continue

        backup_title, backup_desc = cur_title, cur_desc
        set_title_meta_h1(path, new["title"], new["description"])
        if not is_valid_html(path):
            # restore on corruption
            set_title_meta_h1(path, backup_title, backup_desc)
            print(f"  ⚠️  invalid HTML after edit, reverted: {path.name}")
            continue

        rel = str(path.relative_to(REPO_DIR))
        ledger.append({
            "applied_at": now,
            "change_type": "title_meta",
            "page": c["page"],
            "file_path": rel,
            "query": c["query"],
            "before_pos": round(c["pos"], 2),
            "before_ctr": round(c["ctr"], 5),
            "before_impr": int(c["impr"]),
            "before_title": backup_title,
            "before_desc": backup_desc,
            "after_title": new["title"],
            "verdict": "pending",
            "measured_at": None,
            "after_pos": None,
            "after_ctr": None,
            "after_impr": None,
        })
        changed += 1
        print(f"  ✏️  {path.name}: «{c['query']}» pos{c['pos']:.0f} ctr{c['ctr']:.1%}")
        print(f"      {cur_title[:55]}")
        print(f"   →  {new['title'][:55]}")
    if changed:
        save_ledger(ledger)
    print(f"✅ applied {changed} title/meta optimizations (ledger: {LEDGER_PATH.name})")
    return changed


# ---------------------------------------------------------------- measure

def current_metrics(conn, page: str, query: str) -> dict | None:
    row = conn.execute("""
        SELECT SUM(impressions) impr, SUM(clicks) clk,
               SUM(position*impressions)/NULLIF(SUM(impressions),0) wpos
        FROM gsc_queries
        WHERE page=? AND query=? AND date >= date('now','-14 days')
    """, (page, query)).fetchone()
    if not row or not row["impr"]:
        return None
    return {"impr": int(row["impr"]), "clk": int(row["clk"] or 0),
            "ctr": (row["clk"] or 0) / row["impr"], "pos": row["wpos"] or 0}


def days_since(iso_ts: str) -> float:
    try:
        t = datetime.fromisoformat(iso_ts)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds() / 86400.0
    except Exception:
        return 0.0


def revert_experiment(exp: dict) -> bool:
    """Restore the previous title and description on disk."""
    path = REPO_DIR / exp["file_path"]
    if not path.exists() or not exp.get("before_title"):
        return False
    set_title_meta_h1(path, exp["before_title"], exp.get("before_desc", ""))
    return is_valid_html(path)


def run_measure(conn) -> int:
    now = datetime.now(timezone.utc).isoformat()
    ledger = load_ledger()
    matured = [e for e in ledger
               if e.get("verdict") == "pending"
               and days_since(e.get("applied_at", "")) >= OPT_MATURE_DAYS]
    print(f"📏 {len(matured)} experiments matured (>= {OPT_MATURE_DAYS}d) "
          f"of {sum(1 for e in ledger if e.get('verdict')=='pending')} pending")
    wins = neutral = reverted = 0
    for exp in matured:
        m = current_metrics(conn, exp["page"], exp["query"])
        if not m:
            exp["verdict"] = "neutral"
            exp["measured_at"] = now
            exp["notes"] = "no-after-data"
            neutral += 1
            continue

        d_ctr = m["ctr"] - (exp.get("before_ctr") or 0)
        d_pos = (exp.get("before_pos") or 0) - m["pos"]   # >0 means improved

        if d_ctr >= WIN_CTR_DELTA or d_pos >= WIN_POS_DELTA:
            verdict = "win"; wins += 1
        elif -d_pos >= REGRESSION_POS_DELTA:
            verdict = "regression"
            if revert_experiment(exp):
                verdict = "reverted"; reverted += 1
        else:
            verdict = "neutral"; neutral += 1

        exp["verdict"] = verdict
        exp["measured_at"] = now
        exp["after_pos"] = round(m["pos"], 2)
        exp["after_ctr"] = round(m["ctr"], 5)
        exp["after_impr"] = m["impr"]
        print(f"  {verdict:10s} {Path(exp['file_path']).name}: "
              f"ctr {(exp.get('before_ctr') or 0):.1%}→{m['ctr']:.1%}, "
              f"pos {(exp.get('before_pos') or 0):.1f}→{m['pos']:.1f}")

    if matured:
        save_ledger(ledger)
    print(f"✅ measured: {wins} wins, {neutral} neutral, {reverted} reverted")
    return wins + neutral + reverted


# ---------------------------------------------------------------- report

def build_report_text() -> str:
    s = ledger_summary()
    lines = ["<b>🧪 SEO-оптимизатор — отчёт</b>"]

    at = s["applied_today"]
    if at:
        lines.append(f"\n<b>Применено сегодня:</b> {len(at)} правок title/meta")
        for e in at[:6]:
            lines.append(f"  ✏️ «{e['query']}» → {e['after_title'][:48]}")
    else:
        lines.append("\nСегодня новых правок нет.")

    mt = s["measured_today"]
    if mt:
        won = sum(1 for e in mt if e["verdict"] == "win")
        rev = sum(1 for e in mt if e["verdict"] == "reverted")
        neu = sum(1 for e in mt if e["verdict"] == "neutral")
        lines.append(f"\n<b>Замерено сегодня:</b> {won} 🟢 win · {neu} ⚪ neutral · {rev} 🔴 откат")
        for e in mt:
            if e["verdict"] in ("win", "reverted"):
                icon = "🟢" if e["verdict"] == "win" else "🔴"
                bp, ap_ = e.get("before_pos"), e.get("after_pos")
                lines.append(f"  {icon} «{e['query']}»: поз {bp}→{ap_}")

    v = s["verdicts"]
    lines.append(
        f"\n<b>Всего:</b> {s['total']} | в ожидании замера: {s['pending']} | "
        f"win: {v.get('win',0)} · откатов: {v.get('reverted',0)}"
    )
    return "\n".join(lines)


def run_report() -> None:
    text = build_report_text()
    print(text.replace("<b>", "").replace("</b>", ""))
    s = ledger_summary()
    # Only ping Telegram when there is something worth seeing (avoid daily noise).
    if not (s["applied_today"] or s["measured_today"]):
        print("· nothing to report to Telegram today")
        return
    try:
        from telegram_notify import notify
        notify(text)
    except Exception as e:
        print(f"· telegram unavailable: {e}", file=sys.stderr)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Data-driven SEO optimizer (no page generation)")
    ap.add_argument("--apply", action="store_true", help="Find & rewrite low-CTR titles/meta")
    ap.add_argument("--measure", action="store_true", help="Measure matured experiments & revert regressions")
    ap.add_argument("--report", action="store_true", help="Send optimizer activity digest to Telegram")
    args = ap.parse_args()
    if not (args.apply or args.measure or args.report):
        args.apply = args.measure = True   # default: full daily cycle

    init_db()
    conn = get_conn()
    if args.measure:
        run_measure(conn)
    if args.apply:
        run_apply(conn)
    conn.commit()
    conn.close()
    if args.report:
        run_report()


if __name__ == "__main__":
    main()
