#!/usr/bin/env python3
"""Rewrite known stale fact strings to the values in data/site_facts.json.

Targeted, idempotent replacements only (no free-form prose rewriting):
  * SKU count text "77/62 SKU(s)/наименований/позиций/товаров" -> live count
  * KD-014 whole stick "1 kg"/"1 кг" -> registry weight (0.8)
Scans public/ (html/json/txt/yaml) and generator sources in scripts/,
lib/, submission/. Usage: apply_site_facts.py [--check]
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_facts import ROOT, sku_count, kd014_weight, plural_ru  # noqa: E402

N = sku_count()
STATE_FILE = ROOT / "data" / "sku_count_state.json"


def _stale_counts() -> str:
    """Historic whole-catalog totals that must never be re-baked into prose."""
    olds = {62, 72, 77}
    if STATE_FILE.exists():
        try:
            st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            for key in ("previous", "current"):
                v = st.get(key)
                if isinstance(v, int) and v > 0:
                    olds.add(v)
        except Exception:
            pass
    olds.discard(N)
    return "(?:" + "|".join(str(n) for n in sorted(olds, reverse=True)) + ")"


STALE = _stale_counts()
RULES = [
    (re.compile(rf"(?<![\d.,]){STALE}(\s+(?:halal\s+)?SKUs?\b)"), rf"{N}\1"),
    # Split HTML stats: <div class="num">62</div><div class="lbl">SKU…
    (re.compile(
        rf'(<(?:div|span) class="num">){STALE}(</(?:div|span)>\s*<(?:div|span) class="(?:lbl|label)">(?:SKUs?\b|наименовани))'
    ), rf"\g<1>{N}\2"),
    (re.compile(rf"(?<![\d.,]){STALE}\s+(наименовани)[йяе]\b"), lambda m: f"{N} {m.group(1)}{plural_ru(N, 'е', 'я', 'й')}"),
    (re.compile(rf"(?<![\d.,]){STALE}\s+(позици)[йия]\b"), lambda m: f"{N} {m.group(1)}{plural_ru(N, 'я', 'и', 'й')}"),
    (re.compile(rf"(?<![\d.,]){STALE}\s+(товар)(?:ов|а)?\b"), lambda m: f"{N} {m.group(1)}{plural_ru(N, '', 'а', 'ов')}"),
    (re.compile(r"(KD-014[^<\n]{0,40}?(?:whole stick|stick))\s+1 kg"), rf"\1 {kd014_weight('en')}"),
    (re.compile(r"(KD-014[^<\n]{0,40}?(?:целый батон|батон))\s+1 кг"), rf"\1 {kd014_weight('ru')}"),
    (re.compile(r"(целый батон|whole stick)\s+1 (кг|kg)(?=\s*\|\s*Халяль|\s*\|\s*Halal)"),
     lambda m: f"{m.group(1)} {kd014_weight('ru' if m.group(2) == 'кг' else 'en')}"),
    (re.compile(r"(KD-013 / KD-014\)</td><td>)Нарезка 0,5 кг / батон 1 кг"), rf"\1Нарезка 0,5 кг / батон {kd014_weight('ru')}"),
    (re.compile(r"1 паллета \(сборная из разных позиций возможна\)"), "1 паллета"),
    (re.compile(r"одна паллета \(сборная из разных позиций возможна\)"), "1 паллета"),
    (re.compile(r"1 паллета \(сборная возможна\)"), "1 паллета"),
    (re.compile(r"одна паллета \(сборная возможна\)"), "1 паллета"),
    (re.compile(r"Минимальный заказ — одна паллета"), "Минимальный заказ — 1 паллета"),
    (re.compile(r"Минимальный заказ: одна паллета"), "Минимальный заказ — 1 паллета"),
    (re.compile(r"минимум одна паллета"), "Минимальный заказ — 1 паллета"),
    (re.compile(r"1 pallet \(mixed pallets? possible\)"), "1 pallet"),
    (re.compile(r"one pallet \(mixed pallets? possible\)"), "1 pallet"),
    (re.compile(r"Minimum order — one pallet"), "Minimum order: 1 pallet"),
    (re.compile(r"Minimum order — 1 pallet"), "Minimum order: 1 pallet"),
    (re.compile(r"Minimum order: one pallet"), "Minimum order: 1 pallet"),
    (re.compile(r"одна паллета, сборная из разных позиций возможна"), "1 паллета"),
    (re.compile(r"сборная паллета из нескольких SKU возможна"), "1 паллета"),
    (re.compile(r"сборная паллета возможна"), "1 паллета"),
    (re.compile(r", сборная возможна"), ""),
    (re.compile(r" \(сборная возможна\)"), ""),
    (re.compile(r"mixed pallet possible"), "1 pallet"),
]
FIX_PLURAL = [
    (re.compile(rf"(?<![\d.,]){N}\s+позици[иия]\b"), lambda m: f"{N} позици{plural_ru(N, 'я', 'и', 'й')}"),
    (re.compile(rf"(?<![\d.,]){N}\s+наименовани[яе]\b"), lambda m: f"{N} наименовани{plural_ru(N, 'е', 'я', 'й')}"),
]
RULES += FIX_PLURAL
SKIP = {"node_modules", ".git", "agent_backups"}
GLOBS = {"public": ["**/*.html", "**/*.json", "**/*.txt", "**/*.yaml"],
         "scripts": ["**/*.py"], "lib": ["**/*.mjs", "**/*.js"], "submission": ["**/*.txt"]}
SELF = {
    "apply_site_facts.py", "test_halal_api_contract.py", "render_static_catalog.py",
    "gen_price_lists.py", "check_stale_counts.py", "bulk_fix_stale_content.py",
    "reconcile_sku_count.py", "check_fact_consistency.py", "test_fact_consistency.py",
    "test_seo_batch_rank.py", "test_chakchak_bakery.py",
}


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
