#!/usr/bin/env python3
"""
Regenerate public/llms-full.txt from the already-synced public/products.json.

This script is the *richer* successor to the llms-full.txt block emitted by
sync-sheets.mjs (Node) and sync-sheets.py — it runs after either of those
as the authoritative generator, so both sync paths converge on the same
92 KB+ AI-ready dump (per-SKU cards, buyer personas, FAQ, Q&A).

Usage:
    python3 scripts/gen-llms-full.py

Safe to run on VPS: only touches public/llms-full.txt and requires
public/products.json to already exist.
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
    print("❌ could not load scripts/sync-sheets.py", file=sys.stderr)
    sys.exit(1)
sync_sheets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_sheets)

products_path = PUBLIC / "products.json"
if not products_path.exists():
    print(f"❌ {products_path} not found — run sync first", file=sys.stderr)
    sys.exit(1)

data = json.loads(products_path.read_text(encoding="utf-8"))
products = data.get("products") or []
if not products:
    print("❌ products.json has no products", file=sys.stderr)
    sys.exit(1)

txt = sync_sheets.generate_llms_full_txt(products)
out = PUBLIC / "llms-full.txt"
out.write_text(txt, encoding="utf-8")
print(f"✅ {out} — {len(txt)} bytes, {txt.count(chr(10))} lines, {len(products)} SKUs")
