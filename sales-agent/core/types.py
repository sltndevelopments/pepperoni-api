"""Типы и константы контура продаж."""
from __future__ import annotations

from enum import Enum


class LeadStatus(str, Enum):
    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    REPLIED = "replied"
    MEETING = "meeting"
    PROPOSAL = "proposal"
    WON = "won"
    LOST = "lost"
    SKIP = "skip"
    FREEZE = "freeze"


class LeadTier(str, Enum):
    S = "S"      # сосиска в тесте подтверждена на сайте
    A = "A"
    B = "B"
    C = "C"
    UNKNOWN = "—"


class DraftStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"      # ждёт аппрува
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    CANCELLED = "cancelled"


class GateAction(str, Enum):
    """Действия, требующие человека перед исполнением."""
    SEND_EMAIL = "send_email"
    SEND_WHATSAPP = "send_whatsapp"
    SEND_TELEGRAM = "send_telegram"
    CREATE_PHONE_TASK = "create_phone_task"
    SUBMIT_TENDER = "submit_tender"
    SEND_PROPOSAL = "send_proposal"


# Внутренние действия — без гейта
INTERNAL_ACTIONS = frozenset({
    "enrich", "score", "crawl_site", "create_draft", "triage_inbound",
    "import_lead", "cluster_insight", "reflect",
})
