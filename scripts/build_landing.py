#!/usr/bin/env python3
"""
LANDING-BUILDER — closes the Scout → human-approval → page loop.

Scout queues "create_landing" approvals when it finds real demand that only the
homepage ranks for. Once you approve in Telegram, this agent builds a high-quality
landing page for that query and registers it in the experiments ledger so the
optimizer/measure loop tracks whether it actually wins traffic.

Flow per approved request:
  approvals.take_approved("create_landing")
    → generate HTML (LLM, strict template: schema.org Service + FAQ + Breadcrumb)
    → validate, write to public/landing/<slug>.html
    → add to sitemap.xml
    → record an experiment {change_type: "new_landing", before_pos = current
      homepage position for the query} so we can measure lift later
    → Telegram confirmation

Env: DEEPSEEK_API_KEY (required), TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID (optional).

Usage:
  python3 scripts/build_landing.py                 # process all approved requests
  python3 scripts/build_landing.py --query "..."   # build one ad-hoc (no approval)
  python3 scripts/build_landing.py --max 3
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from claude_client import call_claude, DEEPSEEK_API_KEY, DEFAULT_MODEL
from seo_db import get_conn, init_db

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"
LANDING_DIR = PUBLIC / "landing"
SITEMAP = PUBLIC / "sitemap.xml"
LEDGER_PATH = ROOT / "data" / "experiments.json"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
YEAR = datetime.now().year
MAX_TOKENS = 8000

PHONE_DISPLAY = "+7 987 217-02-02"
PHONE_TEL = "+79872170202"
EMAIL = "info@kazandelikates.tatar"
ADDR_RU = "г. Казань, ул. Аграрная, 2, оф. 7"

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(query: str) -> str:
    s = re.sub(r"[^a-zа-яё0-9\s-]", "", query.lower(), flags=re.IGNORECASE)
    s = re.sub(r"\s+", "-", s.strip())
    s = "".join(TRANSLIT.get(c, c) for c in s)
    return re.sub(r"-+", "-", s).strip("-")[:60]


# ---------------------------------------------------------------- HTML helpers

_FALLBACK_FOOTER = (
    f'\n<footer class="py-4 mt-5" style="background:#1f3b2c;color:#fff">'
    f'<div class="container">'
    f'<p class="mb-1">Казанские Деликатесы (Pepperoni Tatar) — производство халяльной '
    f'мясной продукции и татарской выпечки в Казани.</p>'
    f'<p class="small mb-0">'
    f'<a href="https://pepperoni.tatar/" style="color:#fff">pepperoni.tatar</a> · '
    f'{EMAIL} · {PHONE_DISPLAY}</p>'
    f'</div></footer>\n'
)


def ensure_complete_html(html: str) -> str:
    html = (html or "").rstrip()
    low = html.lower()
    if "</body>" in low and "</html>" in low:
        return html
    lines = html.split("\n")
    if lines and lines[-1].count("<") > lines[-1].count(">"):
        html = "\n".join(lines[:-1]).rstrip()
        low = html.lower()
    if "<body" in low and "</body>" not in low:
        if "<main" in low and "</main>" not in low:
            html += "\n</main>"
        if "</footer>" not in low:
            html += _FALLBACK_FOOTER
        html += "\n</body>"
    if "</html>" not in html.lower():
        html += "\n</html>"
    return html + "\n"


def is_valid_page(html: str) -> bool:
    if any(m in html for m in ("<<<<<<<", "=======\n", ">>>>>>>")):
        return False
    low = html.lower()
    return ("</head>" in low) and ("<h1" in low) and ("</html>" in low) \
        and ("application/ld+json" in low)


GTM = ("<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),"
       "event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),"
       "dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='"
       "+i+dl;f.parentNode.insertBefore(j,f);})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>")


def related_links_block(current_slug: str) -> str:
    """Link the new landing to a few existing OEM/landing pages (cheap SEO lift)."""
    links = []
    for d, prefix in ((PUBLIC / "oem", "/oem/"), (LANDING_DIR, "/landing/")):
        if not d.exists():
            continue
        for f in sorted(d.glob("*.html")):
            if f.stem == current_slug:
                continue
            name = f.stem.replace("-", " ").title()
            links.append(f'<a href="{prefix}{f.stem}" class="me-2">{name}</a>')
            if len(links) >= 6:
                break
        if len(links) >= 6:
            break
    if not links:
        return ""
    return ('\n<section class="container my-4"><h2 class="h6 text-muted">Смотрите также</h2>'
            f'<div>{" · ".join(links)}</div></section>')


# ---------------------------------------------------------------- generation

def build_prompt(query: str) -> tuple[str, str]:
    system = (
        "Ты SEO-копирайтер B2B-производителя ХАЛЯЛЬ мясных деликатесов «Казанские "
        "Деликатесы» (pepperoni.tatar) из Казани. Пишешь убедительный, фактический "
        "контент для оптовых/HoReCa покупателей. Без воды и кликбейта."
    )
    canonical = f"/landing/{slugify(query)}"
    prompt = f"""Сделай ОДНУ посадочную HTML5-страницу под поисковый запрос «{query}».
Верни ТОЛЬКО валидный HTML, без markdown и пояснений.

ЖЁСТКИЕ ТРЕБОВАНИЯ:
- <!DOCTYPE html>, <html lang="ru">
- <head>: charset, viewport,
  <title> с запросом «{query}» в начале (до 65 символов),
  <meta name="description"> (до 160 символов, с запросом и УТП),
  <link rel="canonical" href="https://pepperoni.tatar{canonical}">,
  hreflang ru + x-default на этот же URL,
  Bootstrap 5 CDN,
  ТРИ JSON-LD блока: Service (контрактное производство/опт), FAQPage (4-5 вопросов
  с реальными ответами под запрос), BreadcrumbList (Каталог → {query}).
- <body>: сразу после <body> вставь ровно это: {GTM}
- <h1> с запросом «{query}».
- Секции: вводный абзац, преимущества (ul/li: халяль-сертификат ДУМ РТ,
  ХАССП, ISO 22000:2018, опт от 500 кг/мес, доставка по РФ и СНГ),
  ассортимент/спецификации, условия поставки, FAQ (видимый текст, дублирует JSON-LD),
  CTA с tel:{PHONE_TEL} и mailto:{EMAIL}.
- Контакты СТРОГО: {PHONE_DISPLAY}, {EMAIL}, {ADDR_RU}. Не выдумывай 8-800 и др.
- ХАЛЯЛЬ уже подразумевает отсутствие свинины — НЕ пиши «без свинины».
- Ссылка «← Каталог» на «/».
- Футер: © 2022–{YEAR} Казанские Деликатесы, {ADDR_RU}, {PHONE_DISPLAY}, {EMAIL}."""
    return system, prompt


def build_one(query: str, conn) -> dict:
    slug = slugify(query)
    if not slug:
        return {"status": "error", "query": query, "error": "empty slug"}
    out_path = LANDING_DIR / f"{slug}.html"
    url = f"https://pepperoni.tatar/landing/{slug}"

    system, prompt = build_prompt(query)
    html, tokens = call_claude(prompt, system=system, max_tokens=MAX_TOKENS)
    html = (html or "").strip()
    if html.startswith("```"):
        html = re.sub(r"^```[a-zA-Z]*\n?", "", html).rstrip("`").rstrip()
    html = ensure_complete_html(html)
    # inject related links before </body>
    block = related_links_block(slug)
    if block:
        html = html.replace("</body>", block + "\n</body>", 1)

    if not is_valid_page(html):
        return {"status": "error", "query": query, "slug": slug,
                "error": "invalid/incomplete HTML — not saved"}

    LANDING_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    add_to_sitemap([url])
    record_experiment(conn, url, str(out_path.relative_to(ROOT)), query)
    return {"status": "ok", "query": query, "slug": slug, "url": url,
            "path": str(out_path), "tokens": tokens}


# ---------------------------------------------------------------- sitemap

def add_to_sitemap(urls: list[str]) -> None:
    if not SITEMAP.exists():
        return
    content = SITEMAP.read_text(encoding="utf-8")
    existing = set(re.findall(r"<loc>(.*?)</loc>", content))
    new = []
    for u in urls:
        if u not in existing:
            new.append(
                f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{TODAY}</lastmod>\n"
                f"    <changefreq>monthly</changefreq>\n    <priority>0.7</priority>\n  </url>")
    if new:
        content = content.replace("</urlset>", "\n".join(new) + "\n</urlset>")
        SITEMAP.write_text(content, encoding="utf-8")
        print(f"  ✅ sitemap += {len(new)} url")


# ---------------------------------------------------------------- experiments

def _homepage_pos_for_query(conn, query: str) -> tuple[float, float, int]:
    """Current position/ctr/impr the homepage gets for this query — our baseline."""
    try:
        row = conn.execute("""
            SELECT SUM(impressions) impr, SUM(clicks) clk,
                   SUM(position*impressions)/NULLIF(SUM(impressions),0) wpos
            FROM gsc_queries
            WHERE query=? AND date >= date('now','-30 days')
        """, (query,)).fetchone()
        if row and row["impr"]:
            return (row["wpos"] or 0.0,
                    (row["clk"] or 0) / row["impr"],
                    int(row["impr"]))
    except Exception:
        pass
    return (0.0, 0.0, 0)


def record_experiment(conn, url: str, rel_path: str, query: str) -> None:
    try:
        ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8")) if LEDGER_PATH.exists() else []
    except Exception:
        ledger = []
    pos, ctr, impr = _homepage_pos_for_query(conn, query)
    ledger.append({
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "change_type": "new_landing",
        "page": url,
        "file_path": rel_path,
        "query": query,
        "before_pos": round(pos, 2) if pos else None,
        "before_ctr": round(ctr, 5) if impr else None,
        "before_impr": impr,
        "before_title": "(none — homepage only)",
        "before_desc": "",
        "after_title": f"landing:{query}",
        "verdict": "pending",
        "measured_at": None,
        "after_pos": None,
        "after_ctr": None,
        "after_impr": None,
    })
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- notify

def notify_built(results: list) -> None:
    ok = [r for r in results if r["status"] == "ok"]
    if not ok:
        return
    lines = ["<b>🏗 Landing-Builder — построены лендинги</b>"]
    for r in ok:
        lines.append(f"  ✅ «{r['query']}» → {r['url']}")
    lines.append("\n<i>Добавлены в sitemap и в контур экспериментов — оптимизатор "
                 "измерит прирост трафика через ~14 дней.</i>")
    try:
        from telegram_notify import notify
        notify("\n".join(lines))
    except Exception as e:
        print(f"· telegram unavailable: {e}", file=sys.stderr)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Build approved landing pages (Scout→approve→page)")
    ap.add_argument("--query", help="Build one landing ad-hoc, bypassing the approval queue")
    ap.add_argument("--max", type=int, default=int(os.environ.get("LANDING_MAX", "5")),
                    help="Max landings to build this run")
    args = ap.parse_args()

    if not DEEPSEEK_API_KEY:
        print("❌ DEEPSEEK_API_KEY not set — cannot build.", file=sys.stderr)
        return 1

    init_db()
    conn = get_conn()
    results = []

    if args.query:
        print(f"🏗 ad-hoc landing: «{args.query}»")
        results.append(build_one(args.query, conn))
    else:
        try:
            import approvals
        except Exception as e:
            print(f"❌ approvals module unavailable: {e}", file=sys.stderr)
            return 1
        approved = approvals.take_approved("create_landing")
        if not approved:
            print("· no approved create_landing requests")
            conn.close()
            return 0
        print(f"🏗 {len(approved)} approved landing request(s)")
        for a in approved[: args.max]:
            q = (a.get("payload") or {}).get("query") or a.get("title", "")
            if not q:
                continue
            print(f"  → building «{q}»")
            results.append(build_one(q, conn))

    conn.close()

    for r in results:
        if r["status"] == "ok":
            print(f"✅ {r['url']} ({r.get('tokens','?')} tokens)")
        else:
            print(f"⚠️  {r.get('query')}: {r.get('error')}", file=sys.stderr)
    notify_built(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
