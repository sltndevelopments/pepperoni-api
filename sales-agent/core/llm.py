"""
Роутинг LLM для sales-agent:
  - Sonnet (voice) — черновики, диалог, объёмная работа
  - Fable (brain)  — гейт пограничных решений, стратегия
  - Haiku (micro)  — триаж, извлечение контактов

Все вызовы идут через scripts/opus_brain_client (общий бюджет + леджер
data/llm_costs.json). Источник тегируется как sales:<модуль> — расход
агента продаж виден отдельной строкой в телеметрии.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import env as _env  # noqa: F401 — load .env

REPO = Path(__file__).resolve().parent.parent.parent
for _scripts in (REPO / "scripts", REPO / "repo" / "scripts"):
    if (_scripts / "opus_brain_client.py").exists():
        sys.path.insert(0, str(_scripts))
        break


def _source_tag() -> str:
    base = os.path.basename(sys.argv[0] or "unknown").replace(".py", "")
    return f"sales:{base or 'unknown'}"


def _client():
    import opus_brain_client as obc  # type: ignore
    # Атрибуция в едином леджере llm_costs.json
    try:
        import claude_client  # type: ignore
        claude_client._SCRIPT = _source_tag()
    except Exception:
        pass
    return obc


def brain_available() -> bool:
    try:
        return _client().brain_available()
    except Exception:
        return False


def remaining_budget() -> float:
    try:
        return _client().remaining_budget()
    except Exception:
        return 0.0


def call_sonnet(
    prompt: str,
    system: str = "",
    max_tokens: int = 2000,
    *,
    cache_system: bool = True,
    effort: str | None = "medium",
    json_schema: dict | None = None,
) -> tuple[str, dict]:
    """Основная работа — Sonnet. Стабильный system кэшируется (10% цены входа)."""
    obc = _client()
    try:
        return obc.call_model(
            prompt, tier="voice", system=system, max_tokens=max_tokens,
            temperature=0.4, cache_system=cache_system,
            effort=effort, json_schema=json_schema,
        )
    except TypeError:
        # старый opus_brain_client без effort/json_schema
        return obc.call_voice(prompt, system=system, max_tokens=max_tokens)


def call_opus(
    prompt: str,
    system: str = "",
    max_tokens: int = 4000,
    *,
    effort: str | None = None,
    json_schema: dict | None = None,
) -> tuple[str, dict]:
    """Стратегия и гейт — Fable. effort=low для классификаций (thinking $50/MTok)."""
    obc = _client()
    try:
        return obc.call_opus(
            prompt, system=system, max_tokens=max_tokens, cache_system=True,
            effort=effort, json_schema=json_schema,
        )
    except TypeError:
        return obc.call_opus(prompt, system=system, max_tokens=max_tokens, cache_system=True)


def call_haiku(prompt: str, system: str = "", max_tokens: int = 300) -> tuple[str, dict]:
    """Триаж и извлечение — Haiku."""
    obc = _client()
    return obc.call_micro(prompt, system=system, max_tokens=max_tokens)
