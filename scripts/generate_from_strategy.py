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


def gen_blog(topic: dict) -> bool:
    slug = topic.get("slug") or slugify(topic.get("title_ru", ""))
    if not slug:
        return False
    out = PUBLIC / "blog" / f"{slug}.html"
    if out.exists():
        return False
    title = topic.get("title_ru", slug)
    intent = topic.get("intent", "информационный")
    system = (
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
    html, _ = call_claude(prompt, system=system, max_tokens=MAX_TOKENS)
    html = clean_html(html)
    if "<html" not in html.lower():
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"  ✓ blog: /blog/{slug}")
    return True


def gen_pl(topic: dict) -> bool:
    lang = topic.get("lang", "ru")
    slug = topic.get("slug") or slugify(topic.get("title", ""))
    if not slug:
        return False
    out_dir = PUBLIC / ("private-label" if lang == "ru" else f"{lang}/private-label")
    out = out_dir / f"{slug}.html"
    if out.exists():
        return False
    title = topic.get("title", slug)
    angle = topic.get("angle", "")
    if lang == "ru":
        system = (
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
        system = (
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
    html, _ = call_claude(prompt, system=system, max_tokens=MAX_TOKENS)
    html = clean_html(html)
    if "<html" not in html.lower():
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"  ✓ PL/OEM [{lang}]: /private-label/{slug}")
    return True


def main():
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("❌ DEEPSEEK_API_KEY not set", file=sys.stderr)
        return 1
    strat = load_strategy()
    if not strat:
        print("ℹ️  No strategy.json — nothing to execute.")
        return 0

    print(f"🛠  Executing strategy ({strat.get('generated_at','?')})")
    made = 0
    for t in (strat.get("new_blog_topics") or [])[:MAX_BLOG]:
        try:
            made += 1 if gen_blog(t) else 0
        except Exception as e:
            print(f"  ✗ blog error: {e}", file=sys.stderr)
    for t in (strat.get("pl_oem_topics") or [])[:MAX_PL]:
        try:
            made += 1 if gen_pl(t) else 0
        except Exception as e:
            print(f"  ✗ PL error: {e}", file=sys.stderr)

    print(f"✅ Strategy executor done: {made} new pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
