"""
One-shot sample generator: produces 5 GEO pages into data/tmp/geo_sample/
for human review before any bulk run.

Usage:
    python3 scripts/run_geo_sample.py

Output:
    data/tmp/geo_sample/<slug>-<city>.html  — 5 generated pages
    data/tmp/geo_sample/review_results.json  — page_reviewer verdict per page
    data/tmp/geo_sample/invariants_check.json — verify_invariants result per page
"""
import sys, os, json, pathlib, random, shutil, re

sys.path.insert(0, str(pathlib.Path(__file__).parent))

# Ensure CWD is repo root regardless of where script is invoked from
_REPO_ROOT = pathlib.Path(__file__).parent.parent
os.chdir(_REPO_ROOT)

from generate_geo_bulk import build_system_prompt, build_user_prompt, is_valid_page
import page_reviewer
import invariants as inv_mod

SAMPLE_DIR = pathlib.Path("data/tmp/geo_sample")
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

# ── Hard-coded sample targets (diverse: RU, EN, AR, no-price, with-price) ──
TARGETS = [
    # (lang, product_id_hint, city_name, country_name, docs_status)
    ("ru",  "pepperoni",    "Краснодар",   "Россия",        "ready"),
    ("ru",  "sosiki",       "Уфа",         "Россия",        "ready"),
    ("en",  "pepperoni",    "Almaty",      "Kazakhstan",    "ready"),
    ("ar",  "vetchina",     "دبي",         "الإمارات",       "in_process"),
    ("ru",  "kazylyk",      "Казань",      "Россия",        "ready"),
]

CITY_CONTEXTS = {
    "Краснодар": {"population": "~1 млн", "horeca": "500+ заведений", "halal_note_ru": "растущий халяль-сегмент", "delivery": "48 ч", "muslim_pct": "5%"},
    "Уфа":       {"population": "~1.1 млн", "horeca": "400+ заведений", "halal_note_ru": "высокий халяль-спрос, 50%+ мусульмане", "delivery": "36 ч", "muslim_pct": "54%"},
    "Almaty":    {"population": "~2.2 mln", "horeca": "1000+ venues", "halal_note": "high halal demand", "delivery": "72 h", "muslim_pct": "70%"},
    "دبي":       {"population": "~3.5 mln", "horeca": "5000+ venues", "halal_note": "all halal required", "delivery": "10–14 days EXW", "muslim_pct": "75%"},
    "Казань":    {"population": "~1.3 млн", "horeca": "600+ заведений", "halal_note_ru": "флагманский регион, очень высокий спрос", "delivery": "отгрузка со склада", "muslim_pct": "50%"},
}

def _find_product(products: list, hint: str) -> dict:
    """Find a product by slug_ru/id hint."""
    for p in products:
        slug = p.get("slug_ru", p.get("id", "")).lower()
        if hint in slug:
            return p
    # fallback: first product
    return products[0]

def _call_llm(system: str, user: str) -> str:
    """Call Anthropic API. Returns raw HTML string."""
    try:
        import anthropic
        proxy = os.environ.get("ANTHROPIC_PROXY", "")
        kwargs = {}
        if proxy:
            import httpx
            # httpx ≥0.24 uses proxy= (singular), not proxies=
            try:
                kwargs["http_client"] = httpx.Client(proxy=proxy)
            except TypeError:
                kwargs["http_client"] = httpx.Client(proxies={"https://": proxy, "http://": proxy})
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


def _strip_fences(html: str) -> str:
    """Strip markdown code fences the LLM sometimes wraps HTML in."""
    html = html.strip()
    if html.startswith("```"):
        # Remove opening fence (```html or ```)
        html = re.sub(r'^```[a-z]*\n?', '', html, count=1)
        # Remove closing fence
        html = re.sub(r'\n?```\s*$', '', html)
    return html.strip()

def main():
    # Load products
    prod_path = pathlib.Path("data/products_geo.json")
    raw = json.loads(prod_path.read_text(encoding="utf-8"))
    products = raw["products"] if isinstance(raw, dict) else raw

    results = []
    for lang, hint, city, country, docs_status in TARGETS:
        product = _find_product(products, hint)
        city_ctx = CITY_CONTEXTS.get(city, {"population": "N/A", "horeca": "N/A", "halal_note_ru": "", "delivery": "N/A", "muslim_pct": "N/A"})
        template_id = "A"

        # Derive slug for product — generate_geo_bulk expects slug_ru
        if "slug_ru" not in product:
            from generate_geo_bulk import slugify
            product = dict(product)
            product["slug_ru"] = slugify(product.get("name_ru") or product.get("name") or hint)

        system_p = build_system_prompt(lang, docs_status)
        user_p   = build_user_prompt(product, city, city_ctx, lang, template_id, country)

        slug = f"{product.get('slug_ru', hint)}-{re.sub(r'[^a-z0-9]', '-', city.lower().encode('ascii','ignore').decode(), flags=re.I)}"
        # Ensure ASCII-only filename for cross-platform safety
        slug = re.sub(r'-+', '-', slug).strip('-')
        out_path = SAMPLE_DIR / f"{lang}-{slug}.html"

        print(f"\n[GENERATE] {lang} | {city} | {hint} → {out_path.name}")
        html = _call_llm(system_p, user_p)

        if html.startswith("LLM_ERROR"):
            print(f"  ERROR: {html}")
            results.append({"file": out_path.name, "llm_error": html})
            continue

        # Strip markdown fences if model wrapped output
        html = _strip_fences(html)

        # Ensure complete
        if "</body>" not in html.lower():
            html += "\n</body>\n</html>"

        valid = is_valid_page(html)
        print(f"  is_valid_page: {valid}")

        try:
            out_path.write_text(html, encoding="utf-8")
            print(f"  saved: {out_path} ({len(html)} bytes)")
        except Exception as e:
            print(f"  SAVE ERROR: {e}")
            results.append({"file": out_path.name, "save_error": str(e)})
            continue

        # page_reviewer verdict
        try:
            verdict_obj = page_reviewer.review_page(out_path)
            verdict = verdict_obj.get("verdict", "error")
            reasons = verdict_obj.get("reasons", [])
        except Exception as e:
            verdict = "reviewer_error"
            reasons = [str(e)]
        print(f"  page_reviewer: {verdict} — {reasons[:2]}")

        results.append({
            "file": out_path.name,
            "lang": lang,
            "city": city,
            "is_valid": valid,
            "verdict": verdict,
            "reasons": reasons,
        })

    # ── Now run page_reviewer on a synthetic BAD page (no tldr-answer) ──
    bad_html = """<!DOCTYPE html>
<html><head><title>Test bad page</title><meta name="description" content="test"></head>
<body data-city="TestCity" data-product="test">
<h1>Пепперони оптом в TestCity</h1>
<p>Мы — лучший поставщик пепперони в России. Клиенты выбирают нас уже 10+ лет.
Поставки в 20+ стран. Пиццерия увеличила продажи на 40%.</p>
<p>Купите для семьи вкусный пепперони по выгодной цене.</p>
<p>Контакты: +7 987 217-02-02</p>
</body></html>"""
    bad_path = SAMPLE_DIR / "BAD-no-tldr-with-superlatives.html"
    bad_path.write_text(bad_html, encoding="utf-8")
    bad_valid = is_valid_page(bad_html)
    try:
        bad_verdict = page_reviewer.review_page(bad_path)
    except Exception as e:
        bad_verdict = {"verdict": "reviewer_error", "reasons": [str(e)]}
    print(f"\n[BAD PAGE TEST]")
    print(f"  is_valid_page (no tldr-answer): {bad_valid}  (expect False)")
    print(f"  page_reviewer verdict: {bad_verdict.get('verdict')}  (expect reject)")
    print(f"  reasons: {bad_verdict.get('reasons', [])}")
    results.append({
        "file": bad_path.name,
        "is_valid": bad_valid,
        "verdict": bad_verdict.get("verdict"),
        "reasons": bad_verdict.get("reasons", []),
        "_note": "synthetic BAD page — no tldr-answer, superlatives, retail framing",
    })

    # ── verify_invariants on sample dir ──
    print("\n[INVARIANTS CHECK]")
    try:
        # verify_invariants may not accept scope kwarg — call without it
        # (structural checks cover scripts + data, not generated HTML)
        violations = inv_mod.verify_invariants(semantic=False)
        print(f"  Structural violations: {len(violations)}")
        for v in violations:
            print(f"  ✗ {v}")
    except Exception as e:
        violations = [f"ERROR: {e}"]
        print(f"  ERROR: {e}")

    # Save results
    review_out = SAMPLE_DIR / "review_results.json"
    review_out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    inv_out = SAMPLE_DIR / "invariants_check.json"
    inv_out.write_text(json.dumps(violations, ensure_ascii=False, indent=2))

    print(f"\n=== DONE ===")
    print(f"Pages in: {SAMPLE_DIR}/")
    print(f"Review:   {review_out}")
    print(f"Invariants: {inv_out}")

if __name__ == "__main__":
    main()
