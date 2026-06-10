"""Слой 1: сигналы намерения (Telegram/VK, новые ООО) — заготовка."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.store import Store


def ingest_manual_signal(source: str, text: str, meta: dict | None = None) -> str:
    """Ручной или Grok-фид: положить сигнал в очередь."""
    store = Store()
    return store.add_signal(source, "intent", {"text": text, **(meta or {})})
