"""Тонкая обёртка над audit_log в Store."""
from __future__ import annotations

from .store import Store


class AuditLog:
    def __init__(self, store: Store | None = None):
        self.store = store or Store()

    def log(self, actor: str, action: str, **kwargs) -> str:
        return self.store.audit(
            actor,
            action,
            entity_type=kwargs.get("entity_type"),
            entity_id=kwargs.get("entity_id"),
            detail=kwargs.get("detail"),
        )

    def tail(self, limit: int = 30) -> list[dict]:
        return self.store.audit_tail(limit)
