import sys, pathlib, os, json, re

sys.path.insert(0, str(pathlib.Path(__file__).parent))
_REPO_ROOT = pathlib.Path(__file__).parent.parent
os.chdir(_REPO_ROOT)

from generate_geo_bulk import build_system_prompt, build_user_prompt, is_valid_page
import page_reviewer
import invariants as inv_mod

SAMPLE_DIR = pathlib.Path("data/tmp/geo_sample_krasnodar")
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

raw = json.loads(pathlib.Path("data/products_geo.json").read_text())
products = raw["products"] if isinstance(raw, dict) else raw
product = next(p for p in products if p.get("id") == "pepperoni")

# Verify usp_ru no longer has the superlative
print(f"usp_ru now: {product.get('usp_ru')}")
assert "единственн" not in product.get("usp_ru", "").lower(), "SUPERLATIVE STILL PRESENT!"

city = "Краснодар"
country = "Россия"
city_ctx = {
    "population": "~1.2 млн",
    "horeca": "600+ заведений",
    "halal_note_ru": "растущий халяль-сегмент",
    "delivery": "48 ч",
    "muslim_pct": "5%",
}

system_p = build_system_prompt("ru", "ready")
user_p   = build_user_prompt(product, city, city_ctx, "ru", "A", country)

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

print(f"\n[GENERATE] ru | {city} | pepperoni")
html = _call_llm(system_p, user_p)
if html.startswith("LLM_ERROR"):
    print(f"  ERROR: {html}")
    sys.exit(1)
html = _strip_fences(html)
if "</body>" not in html.lower():
    html += "\n</body>\n</html>"

# Double-check superlative didn't sneak back in
if re.search(r"единственн|only.*russia|russia.*only", html, re.I):
    print("  WARNING: superlative found in generated HTML!")
else:
    print("  superlative check: CLEAN")

valid = is_valid_page(html)
print(f"  is_valid_page: {valid}")

out_path = SAMPLE_DIR / "ru-pepperoni-krasnodar.html"
out_path.write_text(html, encoding="utf-8")
print(f"  saved: {out_path.name} ({len(html)} bytes)")

# page_reviewer
verdict_obj = page_reviewer.review_page(out_path)
verdict = verdict_obj.get("verdict")
reasons  = verdict_obj.get("reasons", [])
print(f"  page_reviewer: {verdict}")
for r in reasons:
    print(f"    - {r}")

# invariants
print("\n[INVARIANTS]")
violations = inv_mod.verify_invariants(semantic=False)
print(f"  Structural violations: {len(violations)}")
for v in violations:
    print(f"  ✗ {v.get('id')}: {v.get('violations', [])[:1]}")

print(f"\n=== DONE ===")
