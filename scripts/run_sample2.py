import sys, pathlib, os, json, re, random

sys.path.insert(0, str(pathlib.Path(__file__).parent))
_REPO_ROOT = pathlib.Path(__file__).parent.parent
os.chdir(_REPO_ROOT)

from generate_geo_bulk import build_system_prompt, build_user_prompt, is_valid_page, slugify
import page_reviewer
import invariants as inv_mod

SAMPLE_DIR = pathlib.Path("data/tmp/geo_sample2")
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = [
    ("ru",  "pepperoni",    "Краснодар",   "Россия",     "ready"),
    ("en",  "kolbasnye",    "Almaty",      "Kazakhstan", "ready"),
    ("ru",  "kazylyk",      "Казань",      "Россия",     "ready"),
]

CITY_CONTEXTS = {
    "Краснодар": {"population": "~1 млн", "horeca": "500+ заведений", "halal_note_ru": "растущий халяль-сегмент", "delivery": "48 ч", "muslim_pct": "5%"},
    "Almaty":    {"population": "~2.2 mln", "horeca": "1000+ venues", "halal_note": "high halal demand", "delivery": "72 h", "muslim_pct": "70%"},
    "Казань":    {"population": "~1.3 млн", "horeca": "600+ заведений", "halal_note_ru": "флагманский регион, очень высокий спрос", "delivery": "отгрузка со склада", "muslim_pct": "50%"},
}

def _find_product(products, hint):
    for p in products:
        if hint in p.get("id", "").lower() or hint in p.get("slug_ru", "").lower():
            return p
    return products[0]

def _call_llm(system, user):
    try:
        import anthropic, httpx
        proxy = os.environ.get("ANTHROPIC_PROXY", "")
        kwargs = {}
        if proxy:
            try:
                kwargs["http_client"] = httpx.Client(proxy=proxy)
            except TypeError:
                kwargs["http_client"] = httpx.Client(proxies={"https://": proxy})
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], **kwargs)
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=6000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"LLM_ERROR: {e}"

def _strip_fences(html):
    html = html.strip()
    if html.startswith("```"):
        html = re.sub(r'^```[a-z]*\n?', '', html, count=1)
        html = re.sub(r'\n?```\s*$', '', html)
    return html.strip()

raw = json.loads(pathlib.Path("data/products_geo.json").read_text())
products = raw["products"] if isinstance(raw, dict) else raw

results = []
for lang, hint, city, country, docs_status in TARGETS:
    product = _find_product(products, hint)
    city_ctx = CITY_CONTEXTS.get(city, {})
    if "slug_ru" not in product:
        product = dict(product)
        product["slug_ru"] = slugify(product.get("name_ru") or hint)

    system_p = build_system_prompt(lang, docs_status)
    user_p = build_user_prompt(product, city, city_ctx, lang, "A", country)

    city_ascii = re.sub(r'[^a-z0-9]', '-', city.lower().encode('ascii', 'ignore').decode())
    out_path = SAMPLE_DIR / f"{lang}-{product.get('slug_ru', hint)}-{city_ascii}.html"

    print(f"\n[GENERATE] {lang} | {city} | {hint}")
    html = _call_llm(system_p, user_p)
    if html.startswith("LLM_ERROR"):
        print(f"  ERROR: {html}")
        continue
    html = _strip_fences(html)
    if "</body>" not in html.lower():
        html += "\n</body>\n</html>"

    valid = is_valid_page(html)
    print(f"  is_valid_page: {valid}")
    try:
        out_path.write_text(html, encoding="utf-8")
        print(f"  saved: {out_path.name} ({len(html)} bytes)")
    except Exception as e:
        print(f"  SAVE ERROR: {e}")
        continue

    # page_reviewer with real LLM verdict
    try:
        verdict_obj = page_reviewer.review_page(out_path)
        verdict = verdict_obj.get("verdict")
        reasons = verdict_obj.get("reasons", [])
    except Exception as e:
        verdict = "error"
        reasons = [str(e)]
    print(f"  page_reviewer: {verdict}")
    for r in reasons[:3]:
        print(f"    - {r}")
    results.append({"file": out_path.name, "lang": lang, "city": city,
                    "is_valid": valid, "verdict": verdict, "reasons": reasons})

# ── BAD page test ──
print("\n[BAD PAGE — no tldr-answer + superlatives]")
bad_html = """<!DOCTYPE html>
<html lang="ru"><head>
<title>Пепперони оптом Краснодар</title>
<meta name="description" content="Лучший пепперони оптом в Краснодаре">
</head>
<body data-city="Краснодар" data-product="pepperoni">
<h1>Пепперони халяль оптом в Краснодаре</h1>
<p>Мы — лучший производитель пепперони в России. Клиенты выбирают нас уже 10+ лет.
Поставки в 20+ стран мира. Пиццерия «Луна» увеличила продажи на 40% благодаря нашему пепперони.
Купите для семьи вкусный ужин по выгодной цене!</p>
<p>Контакты: +7 987 217-02-02, info@kazandelikates.tatar</p>
<p>Сертификаты: Халяль ДУМ РТ №614A/2024, HACCP, ISO 22000:2018</p>
<p>FAQ: Вопрос 1 — Ответ 1. Вопрос 2 — Ответ 2. Вопрос 3 — Ответ 3.</p>
<form><input type="text" placeholder="Имя"><button>Отправить заявку</button></form>
</body></html>"""
bad_path = SAMPLE_DIR / "BAD-no-tldr-superlatives.html"
bad_path.write_text(bad_html, encoding="utf-8")
bad_valid = is_valid_page(bad_html)
print(f"  is_valid_page: {bad_valid}  (expect False)")
try:
    bad_v = page_reviewer.review_page(bad_path)
    print(f"  page_reviewer: {bad_v['verdict']}  (expect reject)")
    for r in bad_v.get("reasons", [])[:4]:
        print(f"    - {r}")
except Exception as e:
    print(f"  reviewer error: {e}")

# ── Invariants ──
print("\n[INVARIANTS]")
violations = inv_mod.verify_invariants(semantic=False)
print(f"  Structural violations: {len(violations)}")
for v in violations:
    print(f"  ✗ {v.get('id')}: {v.get('violations', [])[:1]}")

(SAMPLE_DIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
print(f"\n=== DONE — {SAMPLE_DIR} ===")
