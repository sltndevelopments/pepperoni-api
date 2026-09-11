#!/usr/bin/env python3
"""Apply data/spec_holds.json to public/products.json (idempotent).

Runs in sync-vps.sh right after sync-sheets.mjs, before every generator that
reads products.json, so a held field never reaches a public surface. For each
held SKU the listed fields are blanked and `specHold` is attached:

    "specHold": {"fields": [...], "since": "...", "noteRU": "...", "noteEN": "..."}

Generators (gen-ru/en-products.py, sync-sheets.py llms writer,
gen_category_pages.py) render the note instead of the missing field.

Raw values are snapshotted once per day to data/spec_holds_raw-<date>.json for
the technologist's review; Google Sheets remains the source of truth.

Usage: python3 scripts/apply_spec_holds.py [--check]
  --check   exit 1 if any held field is still present in products.json
"""
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOLDS = ROOT / "data" / "spec_holds.json"
PRODUCTS = ROOT / "public" / "products.json"


def load_holds():
    if not HOLDS.exists():
        return {}, "", ""
    cfg = json.loads(HOLDS.read_text(encoding="utf-8"))
    return cfg.get("holds", {}), cfg.get("note_ru", ""), cfg.get("note_en", "")


def held_skus(commercial_only=False):
    holds, _, _ = load_holds()
    if commercial_only:
        return {s for s, h in holds.items() if h.get("exclude_from_commercial_pages")}
    return set(holds)


def main(check=False):
    holds, note_ru, note_en = load_holds()
    data = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    raw, changed, leaks = {}, 0, []
    for p in data.get("products", []):
        h = holds.get(p.get("sku"))
        if not h:
            continue
        for f in h["fields"]:
            if p.get(f):
                raw.setdefault(p["sku"], {})[f] = p[f]
                if check:
                    leaks.append(f"{p['sku']}.{f}")
                p[f] = ""
                changed += 1
        p["specHold"] = {"fields": h["fields"], "since": h["since"],
                         "noteRU": note_ru, "noteEN": note_en}
    if check:
        if leaks:
            print(f"spec holds: {len(leaks)} held field(s) still public: {', '.join(leaks)}")
            return 1
        print(f"spec holds: OK ({len(holds)} SKU on hold, no held field public)")
        return 0
    if raw:
        snap = ROOT / "data" / f"spec_holds_raw-{dt.date.today().isoformat()}.json"
        existing = json.loads(snap.read_text(encoding="utf-8")) if snap.exists() else {}
        existing.update(raw)
        snap.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if changed or holds:
        # same shape as sync-sheets.mjs: JSON.stringify(x, null, 2), no trailing newline
        PRODUCTS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"spec holds: {len(holds)} SKU on hold, {changed} field(s) blanked")
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
