"""
RAG-ядро: читает products.json (read-only) + capabilities.yaml.
Не пишет в public/ — только чтение для промптов и проверки фита.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
DEFAULT_PRODUCTS = REPO_ROOT / "public" / "products.json"
CAPABILITIES = ROOT / "config" / "capabilities.yaml"
PLAYBOOK = ROOT / "config" / "sales_playbook.yaml"


class KnowledgeBase:
    def __init__(self, products_path: Path | str | None = None):
        env_path = os.environ.get("PRODUCTS_JSON", "")
        self.products_path = Path(products_path or env_path or DEFAULT_PRODUCTS)
        self._catalog: dict | None = None
        self._capabilities: dict | None = None

    def load_catalog(self) -> dict:
        if self._catalog is None:
            self._catalog = json.loads(self.products_path.read_text(encoding="utf-8"))
        return self._catalog

    def load_capabilities(self) -> dict:
        if self._capabilities is None:
            try:
                import yaml
                self._capabilities = yaml.safe_load(CAPABILITIES.read_text(encoding="utf-8")) or {}
            except Exception:
                self._capabilities = {}
        return self._capabilities

    def product_count(self) -> int:
        cat = self.load_catalog()
        return cat.get("totalProducts") or len(cat.get("products", []))

    def sku_list(self) -> list[dict]:
        cat = self.load_catalog()
        return [
            {
                "sku": p.get("sku"),
                "name": p.get("name"),
                "section": p.get("section"),
                "category": p.get("category"),
                "minOrder": p.get("minOrder"),
            }
            for p in cat.get("products", [])
        ]

    def context_for_prompt(self, max_skus: int = 15) -> str:
        """Компактный контекст для LLM: что продаём и чего нет."""
        caps = self.load_capabilities()
        can = caps.get("can_produce", [])
        cannot = caps.get("cannot_produce", [])
        skus = self.sku_list()[:max_skus]

        lines = [
            f"Компания: {caps.get('company', {}).get('name', 'Казанские Деликатесы')}",
            f"Halal: {caps.get('company', {}).get('halal', True)}",
            f"SKU в каталоге: {self.product_count()}",
            "",
            "МОЖЕМ:",
        ]
        for c in can:
            lines.append(f"  - {c.get('label')} ({c.get('id')})")

        lines.append("")
        lines.append("НЕ МОЖЕМ (стоп):")
        for c in cannot:
            lines.append(f"  - {c.get('label')}: {c.get('reason', '')}")

        lines.append("")
        lines.append("Примеры SKU:")
        for s in skus:
            lines.append(f"  {s['sku']}: {s['name']} [{s.get('section', '')}]")

        return "\n".join(lines)

    def load_playbook(self) -> dict:
        try:
            import yaml
            return yaml.safe_load(PLAYBOOK.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def price_for_sku(self, sku: str) -> dict | None:
        cat = self.load_catalog()
        for p in cat.get("products", []):
            if (p.get("sku") or "").upper() == sku.upper():
                off = p.get("offers") or {}
                return {
                    "sku": p.get("sku"),
                    "name": p.get("name"),
                    "price_rub": off.get("price"),
                    "price_excl_vat": off.get("priceExclVAT"),
                    "export": off.get("exportPrices"),
                    "min_order": p.get("minOrder"),
                }
        return None

    def sales_context(self, max_skus: int = 12) -> str:
        """Полный контекст для писем и диалога."""
        import os
        pb = self.load_playbook()
        base = self.context_for_prompt(max_skus)
        adv = pb.get("advantages", [])
        disc = (pb.get("pricing") or {}).get("disclaimer", "")
        qs = pb.get("discovery_questions", [])
        owner = os.environ.get("OWNER_NAME", "Ринат Султанов")
        lines = [
            base,
            "",
            "ПРЕИМУЩЕСТВА (можно в первом касании):",
            *[f"  - {a}" for a in adv],
            "",
            f"ЦЕНЫ: можно дать из каталога по запросу. {disc}",
            "",
            "ВОПРОСЫ DISCOVERY:",
            *[f"  - {q}" for q in qs],
            "",
            f"Подпись в письме: {owner}, {os.environ.get('OWNER_PHONE', '')}, {os.environ.get('OWNER_EMAIL', '')}",
            "OEM: https://pepperoni.tatar/oem — предлагать СТМ в первом касании где уместно.",
        ]
        return "\n".join(lines)

    def find_skus_by_keyword(self, keyword: str) -> list[dict]:
        kw = keyword.lower()
        return [
            s for s in self.sku_list()
            if kw in (s.get("name") or "").lower() or kw in (s.get("category") or "").lower()
        ]
