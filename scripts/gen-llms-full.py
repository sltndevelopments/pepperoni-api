#!/usr/bin/env python3
"""
Regenerate the four llms.txt artefacts from public/products.json:

  public/llms.txt           — RU rich content (formerly a thin "pointer")
  public/llms-full.txt      — RU full LLM context dump (same content)
  public/en/llms.txt        — EN rich content
  public/en/llms-full.txt   — EN full LLM context dump (same content)

Why two RU files and two EN files?
- llms.txt is what most LLM crawlers fetch first.
- llms-full.txt is the canonical "deepest" dump.
- Keeping both at the same rich content (vs. a one-line pointer) prevents
  AI crawlers that ignore cross-link follow-ups from missing the catalog.

Runs after sync-sheets.{py,mjs} populates products.json. Safe to run on
the VPS (only writes the four files; reads products.json).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"

spec = importlib.util.spec_from_file_location(
    "sync_sheets", ROOT / "scripts" / "sync-sheets.py"
)
if spec is None or spec.loader is None:
    print("ERR: could not load scripts/sync-sheets.py", file=sys.stderr)
    sys.exit(1)
sync_sheets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_sheets)

products_path = PUBLIC / "products.json"
if not products_path.exists():
    print(f"ERR: {products_path} not found — run sync first", file=sys.stderr)
    sys.exit(1)

data = json.loads(products_path.read_text(encoding="utf-8"))
products = data.get("products") or []
if not products:
    print("ERR: products.json has no products", file=sys.stderr)
    sys.exit(1)

# Russian
ru_txt = sync_sheets.generate_llms_full_txt(products)
(PUBLIC / "llms-full.txt").write_text(ru_txt, encoding="utf-8")
(PUBLIC / "llms.txt").write_text(ru_txt, encoding="utf-8")
print(f"OK RU: llms.txt + llms-full.txt — {len(ru_txt)} chars, {len(products)} SKUs")

# English
en_txt = sync_sheets.generate_llms_full_txt_en(products)
en_dir = PUBLIC / "en"
en_dir.mkdir(parents=True, exist_ok=True)
(en_dir / "llms-full.txt").write_text(en_txt, encoding="utf-8")
(en_dir / "llms.txt").write_text(en_txt, encoding="utf-8")
print(f"OK EN: en/llms.txt + en/llms-full.txt — {len(en_txt)} chars, {len(products)} SKUs")

# Product feed (GMC / OpenAI Commerce / Bing Shopping / Perplexity Shopping)
try:
    import subprocess
    res = subprocess.run(
        ["python3", str(ROOT / "scripts" / "gen-products-feed.py")],
        capture_output=True, text=True, check=False,
    )
    if res.returncode == 0:
        print("OK Product feed regenerated (CSV + XML + JSON)")
        for line in res.stdout.strip().splitlines():
            if line.startswith("OK"):
                print(f"   {line}")
    else:
        print(f"WARN gen-products-feed failed: {res.stderr[:200]}", file=sys.stderr)
except Exception as e:
    print(f"WARN gen-products-feed exception: {e}", file=sys.stderr)
