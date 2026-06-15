"""Единый namespace для агентского состояния внутри lead.profile.

profile["_agent"] = {
    "owner_escalated_at": "2026-...",
    "manual_escalated_at": "2026-...",  # legacy
    "handed_off": True,
    "handed_off_at": "2026-...",
    "bounce": {"hard": True, "email": "x@x.ru", "at": "..."},
    "bounce_research": {"tried_inn": "...", "at": "...", "site": ""},
    "bounce_recovered": {"old": "...", "new": "...", "at": "..."},
    "outreach_sent": [...],
    "last_contact_at": "2026-...",
}

CRM-pull сохраняет profile["_agent"] целиком — whitelist полей больше не нужен.
Прямые ключи верхнего уровня (bounce, owner_escalated_at, ...) поддерживаются
для обратной совместимости через _get/_set с миграцией на лету.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ #
#  Базовые get/set                                                     #
# ------------------------------------------------------------------ #

def get(profile: dict, key: str, default=None):
    """Читать из _agent namespace; fallback на верхний уровень (legacy)."""
    agent = profile.get("_agent") or {}
    if key in agent:
        return agent[key]
    # legacy: те же ключи лежали на верхнем уровне профиля
    return profile.get(key, default)


def set(profile: dict, key: str, value) -> dict:
    """Писать в _agent namespace. Возвращает изменённый profile (in-place)."""
    if "_agent" not in profile or not isinstance(profile["_agent"], dict):
        profile["_agent"] = {}
    profile["_agent"][key] = value
    return profile


def update(profile: dict, **kwargs) -> dict:
    """Батч-запись нескольких ключей в _agent."""
    if "_agent" not in profile or not isinstance(profile["_agent"], dict):
        profile["_agent"] = {}
    profile["_agent"].update(kwargs)
    return profile


# ------------------------------------------------------------------ #
#  Semantic helpers                                                    #
# ------------------------------------------------------------------ #

def is_handed_off(profile: dict) -> bool:
    """Лид передан менеджеру — исключить из аутрича и эскалации."""
    if get(profile, "handed_off"):
        return True
    # legacy: статус handed_off кодировался через handed_off_at
    return bool(get(profile, "handed_off_at"))


def is_escalated(profile: dict) -> bool:
    """Лид уже эскалировался владельцу — не повторять."""
    return bool(
        get(profile, "owner_escalated_at")
        or get(profile, "manual_escalated_at")  # legacy
    )


def hard_bounce(profile: dict) -> bool:
    """Есть hard bounce в профиле (независимо от DB-статуса)."""
    b = get(profile, "bounce")
    return isinstance(b, dict) and bool(b.get("hard"))


def mark_handed_off(profile: dict) -> dict:
    return update(profile, handed_off=True, handed_off_at=_now())


def mark_escalated(profile: dict) -> dict:
    return update(profile, owner_escalated_at=_now())


def set_bounce(profile: dict, email: str) -> dict:
    return set(profile, "bounce", {"hard": True, "email": email, "at": _now()})


def bounced_addr(profile: dict) -> str:
    b = get(profile, "bounce") or {}
    return (b.get("email") or "").lower()


def migrate_legacy(profile: dict) -> dict:
    """Переносит старые верхнеуровневые флаги в _agent (идемпотентно)."""
    legacy_keys = (
        "owner_escalated_at", "manual_escalated_at",
        "handed_off_at", "bounce", "bounce_research", "bounce_recovered",
        "outreach_sent", "last_contact_at",
    )
    agent = profile.setdefault("_agent", {})
    for k in legacy_keys:
        if k in profile and k not in agent:
            agent[k] = profile[k]
    return profile
