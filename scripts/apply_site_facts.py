#!/usr/bin/env python3
"""Rewrite known stale fact strings to the values in data/site_facts.json.

Targeted, idempotent replacements only (no free-form prose rewriting):
  * SKU count text "77/62 SKU(s)/наименований/позиций/товаров" -> live count
  * KD-014 whole stick "1 kg"/"1 кг" -> registry weight (0.8)
Scans public/ (html/json/txt/yaml) and generator sources in scripts/,
lib/, submission/. Usage: apply_site_facts.py [--check]
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_facts import ROOT, sku_count, kd014_weight  # noqa: E402

N = sku_count()
STALE = r"(?:77|62)"
RULES = [
    (re.compile(rf"(?<![\d.,]){STALE}(\s+(?:halal\s+)?SKUs?\b)"), rf"{N}\1"),
    (re.compile(rf"(?<![\d.,]){STALE}(\s+(?:наименовани[йяе]|позици[йи]|товаров)\b)"), rf"{N}\1"),
    (re.compile(r"(KD-014[^<\n]{0,40}?(?:whole stick|stick))\s+1 kg"), rf"\1 {kd014_weight('en')}"),
    (re.compile(r"(KD-014[^<\n]{0,40}?(?:целый батон|батон))\s+1 кг"), rf"\1 {kd014_weight('ru')}"),
    (re.compile(r"(целый батон|whole stick)\s+1 (кг|kg)(?=\s*\|\s*Халяль|\s*\|\s*Halal)"),
     lambda m: f"{m.group(1)} {kd014_weight('ru' if m.group(2) == 'кг' else 'en')}"),
    (re.compile(r"(KD-013 / KD-014\)</td><td>)Нарезка 0,5 кг / батон 1 кг"), rf"\1Нарезка 0,5 кг / батон {kd014_weight('ru')}"),
]
SKIP = {"node_modules", ".git", "agent_backups"}
GLOBS = {"public": ["**/*.html", "**/*.json", "**/*.txt", "**/*.yaml"],
         "scripts": ["**/*.py"], "lib": ["**/*.mjs", "**/*.js"], "submission": ["**/*.txt"]}
SELF = {"apply_site_facts.py", "test_halal_api_contract.py", "render_static_catalog.py", "gen_price_lists.py", "check_stale_counts.py", "bulk_fix_stale_content.py", "reconcile_sku_count.py"}


def main() -> int:
    check = "--check" in sys.argv
    changed = []
    for d, globs in GLOBS.items():
        for g in globs:
            for p in (ROOT / d).glob(g):
                if SKIP & set(p.parts) or p.name in SELF or not p.is_file():
                    continue
                try:
                    s = p.read_bytes().decode("utf-8")
                except Exception:
                    continue
                t = s
                for rx, rep in RULES:
                    t = rx.sub(rep, t)
                if t != s:
                    changed.append(p.relative_to(ROOT))
                    if not check:
                        p.write_bytes(t.encode("utf-8"))
    for c in changed:
        print(("STALE " if check else "fixed ") + str(c))
    print(f"{len(changed)} file(s) {'stale' if check else 'updated'}; sku_count={N}")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
