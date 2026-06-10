"""Слой 1: тендеры (zakupki, B2B-Center, СТМ сетей) — заготовка."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.store import Store

SOURCES = [
    {"id": "zakupki", "url": "https://zakupki.gov.ru", "status": "blocked_antiddos"},
    {"id": "b2b_center", "url": "https://www.b2b-center.ru", "status": "stub"},
    {"id": "magnit_stm", "label": "Магнит Выпечка без печи", "status": "stub"},
    {"id": "x5_vkus", "label": "X5 Вкус и Польза", "status": "stub"},
]


def scan_tenders(store: Store | None = None) -> dict:
    """Пока только регистрирует сигнал-заглушку. Реальный парсер — следующий слой."""
    store = store or Store()
    for src in SOURCES:
        store.add_signal("tenders", "source_check", src)
    return {"sources": len(SOURCES), "note": "Подключить парсеры после ядра и гейта"}
