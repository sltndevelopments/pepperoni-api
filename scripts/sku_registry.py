#!/usr/bin/env python3
"""Stable SKU registry (Python mirror of sku_registry.mjs)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "data" / "sku_registry.json"
PRODUCTS_PATH = ROOT / "public" / "products.json"


def norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("«", "").replace("»", "").replace('"', "").replace("'", "")
    return s.strip()


def product_key(name: str, weight: str = "") -> str:
    return f"{norm(name)}|{norm(weight)}"


def load_registry() -> dict:
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data.setdefault("version", 1)
    data.setdefault("next_n", 1)
    data.setdefault("by_key", {})
    data.setdefault("retired", {})
    if not isinstance(data["next_n"], int) or data["next_n"] < 1:
        data["next_n"] = 1
    return data


def save_registry(reg: dict) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bootstrap_from_products(reg: dict) -> dict:
    if reg.get("by_key"):
        return reg
    try:
        products = json.loads(PRODUCTS_PATH.read_text(encoding="utf-8")).get("products") or []
    except Exception as e:
        print(f"  ⚠️  sku_registry bootstrap skipped: {e}")
        return reg
    max_n = 0
    for p in products:
        m = re.match(r"^KD-(\d+)$", str(p.get("sku") or ""), re.I)
        if not m:
            continue
        n = int(m.group(1))
        max_n = max(max_n, n)
        key = product_key(p.get("name", ""), p.get("weight", ""))
        if key not in reg["by_key"]:
            reg["by_key"][key] = str(p["sku"]).upper()
    reg["next_n"] = max(reg["next_n"], max_n + 1)
    print(
        f"  🔑 sku_registry bootstrapped from products.json: "
        f"{len(reg['by_key'])} keys, next=KD-{reg['next_n']:03d}"
    )
    return reg


def assign_sku(reg: dict, name: str, weight: str = "") -> str:
    key = product_key(name, weight)
    if key in reg["by_key"]:
        return reg["by_key"][key]
    used = set(reg["by_key"].values()) | set((reg.get("retired") or {}).keys())
    n = reg["next_n"]
    while True:
        sku = f"KD-{n:03d}"
        n += 1
        if sku not in used:
            break
    reg["by_key"][key] = sku
    reg["next_n"] = n
    return sku


def retire_missing(reg: dict, live_keys) -> int:
    live = set(live_keys)
    retired = 0
    for key, sku in list(reg["by_key"].items()):
        if key not in live:
            reg["retired"][sku] = key
            del reg["by_key"][key]
            retired += 1
    if retired:
        print(f"  🗄  sku_registry: retired {retired} SKU(s) (kept reserved, not reused)")
    return retired
