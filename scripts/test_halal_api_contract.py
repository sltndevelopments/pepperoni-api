#!/usr/bin/env python3
"""Public API/MCP metadata must say halal_certified and must not say no_pork."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_EMITTERS = [
    ROOT / "api" / "products.js",
    ROOT / "mcp" / "api-client.js",
    ROOT / "mcp" / "create-server.js",
    ROOT / "public" / "openapi.yaml",
]
FORBIDDEN = re.compile(
    r"свин(?!ц)|шпик|pork|porcine|\bpigs?\b|\bswine\b|\bhogs?\b|\blard\b|fatback|خنزير|no_pork",
    re.I,
)


class HalalApiContractTest(unittest.TestCase):
    def test_plural_swine_words_are_forbidden(self) -> None:
        pig = re.compile(r"\bpigs?\b", re.I)
        for sample in (
            "pig",
            "pigs",
            "pigs-in-blankets",
            "Breakfast Sausages (skinless, for pigs-in-blankets)",
        ):
            self.assertIsNotNone(pig.search(sample), sample)
        self.assertIsNone(pig.search("pigeon"))

    def test_emitters_use_halal_certified_and_not_legacy_field(self) -> None:
        for path in PUBLIC_EMITTERS:
            text = path.read_text(encoding="utf-8")
            self.assertIn("halal_certified", text, path.name)
            self.assertIsNone(FORBIDDEN.search(text), f"{path.name} still has forbidden wording")

    def test_openapi_breaking_version(self) -> None:
        text = (ROOT / "public" / "openapi.yaml").read_text(encoding="utf-8")
        self.assertIn('version: "3.0.0"', text)
        self.assertNotIn('version: "2.1.0"', text)
        self.assertNotIn("no_pork", text)

    def test_faq_polarity(self) -> None:
        ru = (ROOT / "public" / "faq.html").read_text(encoding="utf-8")
        en = (ROOT / "public" / "en" / "faq.html").read_text(encoding="utf-8")
        self.assertIn(
            "Вся ли продукция соответствует стандарту «Халяль»?</div><div class=\"faq-a\">Да.",
            ru,
        )
        self.assertIn(
            "Are all products halal-certified?</div><div class=\"faq-a\">Yes.",
            en,
        )

    def test_reconcile_does_not_restore_forbidden_claim(self) -> None:
        src = (ROOT / "scripts" / "reconcile_sku_count.py").read_text(encoding="utf-8")
        self.assertNotIn("Без свинины", src)
        self.assertNotIn("no pork", src.lower())
        sample = "62 SKU. Соответствует стандарту «Халяль». Далее текст."
        pattern = r"(\d+) SKU\. (Соответствует стандарту «Халяль»)"
        out = re.sub(pattern, r"70 SKU. \2", sample)
        self.assertEqual(
            out,
            "70 SKU. Соответствует стандарту «Халяль». Далее текст.",
        )


if __name__ == "__main__":
    unittest.main()
