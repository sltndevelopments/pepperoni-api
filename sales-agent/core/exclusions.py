"""Проверка: лида нельзя трогать аутричем."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "exclusions.yaml"


def _rules() -> list[dict]:
    try:
        data = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
        return data.get("do_not_contact", [])
    except Exception:
        return []


def is_excluded(lead: dict) -> tuple[bool, str]:
    name = (lead.get("name") or "").upper()
    inn = (lead.get("inn") or "").strip()
    profile = lead.get("profile") or {}
    if (profile.get("status") or lead.get("status")) in ("owner_contact", "won", "freeze"):
        return True, "status_frozen"

    for rule in _rules():
        rule_inn = (rule.get("inn") or "").strip()
        if rule_inn and inn == rule_inn:
            return True, rule.get("reason", "excluded")
        frag = (rule.get("name_contains") or "").upper()
        if frag and frag in name:
            if rule_inn and inn and inn != rule_inn:
                continue
            return True, rule.get("reason", "excluded")
    return False, ""
