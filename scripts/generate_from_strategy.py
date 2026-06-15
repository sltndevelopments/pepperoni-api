#!/usr/bin/env python3
"""
Strategy executor (HANDS) — generates blog articles and Private Label / OEM /
White Label pages from the brain's data/strategy.json directive, using cheap
DeepSeek Flash. Idempotent: skips pages that already exist on disk.

Run frequently (e.g. hourly) from seo-worker.sh. Safe no-op if no strategy.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from claude_client import call_claude

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
STRATEGY_FILE = DATA / "strategy.json"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
YEAR = datetime.now().year

MAX_BLOG = int(os.environ.get("MAX_STRATEGY_BLOG", "4"))
MAX_PL   = int(os.environ.get("MAX_STRATEGY_PL", "4"))
MAX_TOKENS = int(os.environ.get("STRATEGY_MAX_TOKENS", "4096"))

# Canonical contacts (single source of truth; never invent others)
PHONE_DISPLAY = "+7 987 217-02-02"
PHONE_TEL     = "+79872170202"
EMAIL         = "info@kazandelikates.tatar"
ADDR_RU       = "г. Казань, ул. Аграрная, 2, оф. 7"
CONTACTS_RULE = (
    f"Контакты используй СТРОГО такие: телефон {PHONE_DISPLAY} (tel:{PHONE_TEL}), "
    f"email {EMAIL}, адрес {ADDR_RU}. НИКОГДА не выдумывай 8-800 и другие адреса/email."
)


def slugify(text: str) -> str:
    t = re.sub(r"[^a-z0-9\-]+", "-", text.lower())
    return re.sub(r"-+", "-", t).strip("-")[:80]


def clean_html(html: str) -> str:
    html = re.sub(r"^```html?\s*\n?", "", html.strip(), flags=re.IGNORECASE)
    html = re.sub(r"\n?```\s*$", "", html.strip())
    return html.strip()


def load_strategy() -> dict:
    try:
        return json.loads(STRATEGY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def prep_blog(topic: dict) -> dict | None:
    """Build a batch-ready request for one blog topic (None → skip)."""
    slug = topic.get("slug") or slugify(topic.get("title_ru", ""))
    if not slug:
        return None
    out = PUBLIC / "blog" / f"{slug}.html"
    if out.exists():
        return None
    title = topic.get("title_ru", slug)
    intent = topic.get("intent", "информационный")
    from brand_system import brand_block
    system = brand_block("ru") + "\n\n" + (
        "Ты эксперт мясной/пищевой промышленности и SEO-автор для pepperoni.tatar "
        "(Казанские Деликатесы, халяль производитель). Пишешь экспертно, без воды, "
        "без упоминания свинины."
    )
    prompt = f"""Напиши {intent} SEO-статью: «{title}».
Верни ТОЛЬКО валидный HTML5 (lang="ru"), без объяснений.
Требования:
- <head>: charset, viewport, <title> (до 65 симв.), <meta description> (до 160), canonical /blog/{slug}
- Schema.org Article JSON-LD (datePublished={TODAY}, author "Казанские Деликатесы")
- Bootstrap 5 CDN, один <h1>, 4 подзаголовка H2, 700-900 слов, заключение с CTA
- Контекстные ссылки: /pepperoni, /pepperoni-optom, /private-label
- Футер: © 2022–{YEAR} Казанские Деликатесы, {ADDR_RU}, {PHONE_DISPLAY}
- {CONTACTS_RULE}
- НЕ упоминать свинину"""
    return {"out": out, "label": f"blog: /blog/{slug}",
            "system": system, "prompt": prompt}


def prep_pl(topic: dict) -> dict | None:
    """Build a batch-ready request for one PL/OEM topic (None → skip)."""
    lang = topic.get("lang", "ru")
    slug = topic.get("slug") or slugify(topic.get("title", ""))
    if not slug:
        return None
    out_dir = PUBLIC / ("private-label" if lang == "ru" else f"{lang}/private-label")
    out = out_dir / f"{slug}.html"
    if out.exists():
        return None
    title = topic.get("title", slug)
    angle = topic.get("angle", "")
    from brand_system import brand_block
    if lang == "ru":
        system = brand_block("ru") + "\n\n" + (
            "Ты B2B-эксперт по контрактному производству (Private Label / СТМ / OEM) "
            "халяль мясных изделий и выпечки для pepperoni.tatar (Казанские Деликатесы). "
            "Пишешь убедительно для закупщиков сетей, дистрибьюторов, маркетплейсов."
        )
        prompt = f"""Напиши коммерческую посадочную страницу по услуге Private Label / СТМ / OEM: «{title}».
Угол: {angle}
Верни ТОЛЬКО валидный HTML5 (lang="ru"), без объяснений.
Требования:
- <head>: <title> (до 65 симв.), <meta description> (до 160), canonical /private-label/{slug}
- Schema.org Service + Organization JSON-LD
- Bootstrap 5 CDN, <h1> с услугой, секции: что такое СТМ/OEM, что можем (колбасы, мясо, ВСЯ выпечка), этапы запуска, MOQ/сроки, сертификаты (Халяль ДУМ РТ, HACCP, ISO 22000), кейсы, FAQ (5), CTA-форма
- Кнопка «Получить расчёт СТМ» → tel:{PHONE_TEL}
- Контекстные ссылки: /private-label, /pepperoni-optom, /dlya-distributorov
- Футер: © 2022–{YEAR} Казанские Деликатесы, {ADDR_RU}, {PHONE_DISPLAY}
- {CONTACTS_RULE}
- НЕ упоминать свинину, 600-800 слов"""
    else:
        system = brand_block("en") + "\n\n" + (
            "You are a B2B expert in contract manufacturing (Private Label / White "
            "Label / OEM) of HALAL meat products and bakery for pepperoni.tatar "
            "(Kazan Delicacies). Write persuasively for export buyers (GCC, CIS)."
        )
        prompt = f"""Write a commercial landing page for the Private Label / White Label / OEM service: "{title}".
Angle: {angle}
Return ONLY valid HTML5 (lang="{lang}"), no explanations.
Requirements:
- <head>: <title> (<=65 chars), <meta description> (<=160), canonical /{lang}/private-label/{slug}
- Schema.org Service + Organization JSON-LD
- Bootstrap 5 CDN, <h1>, sections: what is OEM/White Label, capabilities (sausages, meat, ALL bakery), launch steps, MOQ/lead time, certifications (Halal DUM RT, HACCP, ISO 22000), cases, FAQ (5), CTA form
- "Request OEM quote" button → tel:{PHONE_TEL}
- Footer with contacts: {PHONE_DISPLAY}, {EMAIL}
- Use EXACTLY these contacts, never invent others. No pork mentions. 600-800 words"""
    return {"out": out, "label": f"PL/OEM [{lang}]: /private-label/{slug}",
            "system": system, "prompt": prompt}


def _write_page(prep: dict, html: str) -> bool:
    html = clean_html(html)
    if "<html" not in html.lower():
        return False
    prep["out"].parent.mkdir(parents=True, exist_ok=True)
    prep["out"].write_text(html, encoding="utf-8")
    print(f"  ✓ {prep['label']}")
    return True


def _generate_one(prep: dict) -> str:
    """Synchronous single-page generation — used for owner-approved rebuilds."""
    try:
        html, _ = call_claude(prep["prompt"], system=prep.get("system", ""),
                              max_tokens=MAX_TOKENS, effort="medium")
        return html
    except Exception as e:
        print(f"  ✗ _generate_one {prep.get('label','?')}: {e}", file=sys.stderr)
        return ""


def _approval_key(prep: dict) -> str:
    """Stable approval key derived from the output path."""
    label = prep.get("label", "")
    action = prep.get("action", "new_page")
    slug = re.sub(r"[^a-z0-9-]", "", str(prep["out"].stem).lower())[:60]
    return f"{action}:{slug}"


def main():
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")):
        print("❌ ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1
    strat = load_strategy()
    if not strat:
        print("ℹ️  No strategy.json — nothing to execute.")
        return 0

    print(f"🛠  Executing strategy ({strat.get('generated_at','?')})")

    # ── Phase 0: build pages the owner already approved ───────────────────────
    try:
        import approvals as _appr
        for action in ("blog_post", "pl_page"):
            approved = _appr.get_approved_new_pages(action=action)
            for entry in approved:
                pl = entry.get("payload") or {}
                out_path = Path(pl.get("out_path", ""))
                if not out_path or out_path.exists():
                    continue
                # Reconstruct prep from stored payload so we can generate.
                topic = pl.get("topic") or {}
                prep = (prep_blog(topic) if action == "blog_post" else prep_pl(topic))
                if prep:
                    print(f"  🔓 Building approved: {entry.get('title','')}")
                    _write_page(prep, _generate_one(prep))
    except Exception as _e:
        print(f"⚠️  approved-strategy phase failed (non-fatal): {_e}")

    # ── Phase 1: collect candidates from current strategy ─────────────────────
    all_preps = []
    for t in (strat.get("new_blog_topics") or [])[:MAX_BLOG]:
        try:
            p = prep_blog(t)
            if p:
                p["action"] = "blog_post"
                p["topic"] = t
                all_preps.append(p)
        except Exception as e:
            print(f"  ✗ blog prep error: {e}", file=sys.stderr)
    for t in (strat.get("pl_oem_topics") or [])[:MAX_PL]:
        try:
            p = prep_pl(t)
            if p:
                p["action"] = "pl_page"
                p["topic"] = t
                all_preps.append(p)
        except Exception as e:
            print(f"  ✗ PL prep error: {e}", file=sys.stderr)

    if not all_preps:
        print("✅ Strategy executor done: nothing new to generate")
        return 0

    # ── Phase 2: gate — queue unapproved pages, keep approved ones ────────────
    preps = []
    queued_count = 0
    try:
        import approvals as _appr
        for p in all_preps:
            key    = _approval_key(p)
            action = p.get("action", "new_page")
            status = _appr.request_new_page(
                key=key,
                title=p.get("label", key),
                detail=f"action={action}",
                action=action,
                payload={"out_path": str(p["out"]), "topic": p.get("topic", {})},
                requested_by="strategy_executor",
            )
            if status == "approved":
                preps.append(p)
            elif status in ("queued", "pending"):
                queued_count += 1
            # "rejected" → silently skip
        if queued_count:
            print(f"⏳ {queued_count} strategy page(s) queued for owner approval")
    except Exception as _e:
        print(f"⚠️  approval gate failed — running without gate: {_e}")
        preps = all_preps   # fall back: build everything (preserves old behaviour)

    if not preps:
        print("✅ Strategy executor done: all pages pending or rejected")
        return 0

    made = 0
    # Cron job, nobody waits → Batch API (−50%). Fall back to sync calls.
    use_batch = os.environ.get("WORKER_BATCH", "1") != "0" and len(preps) >= 2
    if use_batch:
        try:
            from claude_client import call_claude_batch
            items = [{"custom_id": f"w{i}", "prompt": p["prompt"],
                      "system": p["system"], "max_tokens": MAX_TOKENS,
                      "effort": "medium"}
                     for i, p in enumerate(preps)]
            out = call_claude_batch(items)
            for i, p in enumerate(preps):
                res = out.get(f"w{i}") or {}
                if res.get("ok"):
                    made += 1 if _write_page(p, res["text"]) else 0
                else:
                    print(f"  ✗ {p['label']}: {res.get('error','no result')}",
                          file=sys.stderr)
            print(f"✅ Strategy executor done (batch): {made} new pages")
            return 0
        except Exception as e:
            print(f"⚠️  batch failed ({e}) — falling back to sync", file=sys.stderr)

    for p in preps:
        try:
            html, _ = call_claude(p["prompt"], system=p["system"],
                                  max_tokens=MAX_TOKENS, effort="medium")
            made += 1 if _write_page(p, html) else 0
        except Exception as e:
            print(f"  ✗ {p['label']}: {e}", file=sys.stderr)

    print(f"✅ Strategy executor done: {made} new pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
