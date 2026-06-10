"""Настройки автономного режима."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "autonomy.yaml"

_cache: dict | None = None


def load_autonomy() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
        except Exception:
            _cache = {}
    return _cache


def is_autonomous() -> bool:
    return bool(load_autonomy().get("autonomy", {}).get("enabled", True))


def hot_statuses() -> set[str]:
    return set(load_autonomy().get("escalation", {}).get("hot_statuses", ["hot", "escalated"]))
