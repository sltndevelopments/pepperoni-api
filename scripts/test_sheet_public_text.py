#!/usr/bin/env python3
"""Fail-closed sheet ingest: alias only Pigs-in-Blankets; reject the rest."""
from __future__ import annotations

import unittest

from public_halal_language import (
    accept_sheet_public_text,
    apply_sheet_aliases,
    first_unsafe_hit,
    scrub_sheet_products,
)


class AliasAndReject(unittest.TestCase):
    def test_pigs_in_blankets_alias_then_clean(self) -> None:
        value, hit = accept_sheet_public_text(
            "Breakfast Sausages (skinless, for Pigs-in-Blankets)"
        )
        self.assertIsNone(hit)
        self.assertEqual(value, "Breakfast Sausages (skinless, for Sausage Rolls)")
        self.assertIsNone(first_unsafe_hit(value))

    def test_lowercase_alias(self) -> None:
        value, hit = accept_sheet_public_text("for pigs-in-blankets and HORECA")
        self.assertIsNone(hit)
        self.assertEqual(value, "for sausage rolls and HORECA")

    def test_ru_negation_rejected_not_rewritten(self) -> None:
        raw = "Мраморная полубатон: отсутствие свинины и ГМО"
        value, hit = accept_sheet_public_text(raw)
        self.assertIsNone(value)
        self.assertIn("свин", (hit or "").lower())
        self.assertEqual(apply_sheet_aliases(raw), raw)

    def test_no_generic_pork_free_rewrite(self) -> None:
        value, hit = accept_sheet_public_text("pork-free chicken sausage")
        self.assertIsNone(value)
        self.assertEqual((hit or "").lower(), "pork")

    def test_leftover_pigs_after_alias_still_rejected(self) -> None:
        value, hit = accept_sheet_public_text("pigs and Pigs-in-Blankets")
        self.assertIsNone(value)
        self.assertRegex(hit or "", r"pigs?")

    def test_clean_copy_passes(self) -> None:
        value, hit = accept_sheet_public_text("Халяль колбаса из говядины")
        self.assertIsNone(hit)
        self.assertEqual(value, "Халяль колбаса из говядины")

    def test_pigeon_passes(self) -> None:
        value, hit = accept_sheet_public_text("pigeon is a bird")
        self.assertIsNone(hit)
        self.assertEqual(value, "pigeon is a bird")


class ScrubKeepsPrevious(unittest.TestCase):
    def test_rejects_ru_seo_keeps_previous(self) -> None:
        incoming = [{
            "sku": "KD-039",
            "name": "Колбаса Мраморная",
            "seoDescriptionRU": "отсутствие свинины и ГМО",
            "seoDescriptionEN": "Marble sausage, halal beef",
        }]
        previous = {
            "KD-039": {
                "sku": "KD-039",
                "name": "Колбаса Мраморная",
                "seoDescriptionRU": "Сыровяленая говяжья колбаса, халяль",
            }
        }
        logs: list[str] = []
        out = scrub_sheet_products(incoming, previous, log=logs.append)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["seoDescriptionRU"], "Сыровяленая говяжья колбаса, халяль")
        self.assertEqual(out[0]["seoDescriptionEN"], "Marble sausage, halal beef")
        self.assertTrue(any("seoDescriptionRU" in line for line in logs))

    def test_drops_field_without_fallback(self) -> None:
        incoming = [{
            "sku": "KD-001",
            "name": "Сосиски",
            "seoDescriptionRU": "без свинины",
        }]
        out = scrub_sheet_products(incoming, {}, log=lambda *_: None)
        self.assertNotIn("seoDescriptionRU", out[0])

    def test_en_alias_on_ingredients(self) -> None:
        incoming = [{
            "sku": "KD-018",
            "name": "Sausage rolls",
            "ingredientsEN": "for Pigs-in-Blankets",
        }]
        out = scrub_sheet_products(incoming, {}, log=lambda *_: None)
        self.assertEqual(out[0]["ingredientsEN"], "for Sausage Rolls")


if __name__ == "__main__":
    unittest.main()
