"""Фиксированная модель статусов московского контура продаж (Арби).

Других статусов быть не должно. Свободный ввод статуса запрещён.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Канонический порядок воронки (не терминальные).
PIPELINE: tuple[str, ...] = (
    "new",
    "contacted",
    "samples_sent",
    "meeting_done",
    "passed_to_distributor",
    "first_shipment",
    "repeat_shipment",
    "won",
)

TERMINAL: tuple[str, ...] = ("lost", "no_demand")

STATUSES: tuple[str, ...] = PIPELINE + TERMINAL

STATUS_LABELS: dict[str, str] = {
    "new": "новый",
    "contacted": "связался",
    "samples_sent": "образцы отправлены",
    "meeting_done": "встреча/дегустация",
    "passed_to_distributor": "передан дистрибьютору",
    "first_shipment": "первая отгрузка",
    "repeat_shipment": "повторная отгрузка",
    "won": "выигран",
    "lost": "не наш",
    "no_demand": "нет спроса",
}

# Кнопки первого тапа → целевой статус (кроме ветвлений).
PRIMARY_ACTIONS: dict[str, str] = {
    "contacted": "contacted",
    "samples_sent": "samples_sent",
    "meeting_done": "meeting_done",
    "first_shipment": "first_shipment",
    "repeat_shipment": "repeat_shipment",
    "won": "won",
}

DISTRIBUTORS: tuple[str, ...] = ("GFC", "SweetLife", "direct")

LOST_REASONS: dict[str, str] = {
    "no_demand": "нет спроса",
    "price": "цена",
    "not_halal": "не халяль",
    "no_reply": "не отвечает",
}

# lost_reason=no_demand → статус no_demand; остальные → lost
LOST_REASON_TO_STATUS: dict[str, str] = {
    "no_demand": "no_demand",
    "price": "lost",
    "not_halal": "lost",
    "no_reply": "lost",
}

SOURCES: tuple[str, ...] = ("call", "site", "avito", "manual", "telegram")

# --- Территориальный контур: точки / АКБ / контакты / sell-out ---

POINT_SEGMENTS: tuple[str, ...] = (
    "пиццерия",
    "фастфуд",
    "кафе",
    "столовая",
    "магазин",
    "пекарня",
)

POINT_DISTRIBUTORS: tuple[str, ...] = ("GFC", "SweetLife", "оба", "direct")

# Статусы точки (вычисляемые от даты последнего заказа).
POINT_STATUS_ACTIVE = "active"       # ≤30 дней
POINT_STATUS_AT_RISK = "at_risk"     # 31–60
POINT_STATUS_CHURNED = "churned"     # >60
POINT_STATUSES: tuple[str, ...] = (
    POINT_STATUS_ACTIVE,
    POINT_STATUS_AT_RISK,
    POINT_STATUS_CHURNED,
)

CONTACT_TYPES: tuple[str, ...] = ("call", "visit")
CONTACT_TYPE_LABELS: dict[str, str] = {
    "call": "📞 звонок",
    "visit": "🚶 визит",
}

CONTACT_RESULTS: tuple[str, ...] = ("order", "thinking", "refuse", "not_lpr")
CONTACT_RESULT_LABELS: dict[str, str] = {
    "order": "заказ",
    "thinking": "думает",
    "refuse": "отказ",
    "not_lpr": "не ЛПР",
}

# Результативный контакт = разговор с ЛПР (не «не ЛПР»).
PRODUCTIVE_CONTACT_RESULTS: frozenset[str] = frozenset({"order", "thinking", "refuse"})

DAILY_CONTACT_TARGET_MIN = 8
DAILY_CONTACT_TARGET_MAX = 12
WEEKLY_CONTACT_TARGET = 40  # ориентир ~8×5

SELLOUT_DISTRIBUTORS: tuple[str, ...] = ("GFC", "SweetLife")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def fmt_point_id(seq: int) -> str:
    return f"POINT-{seq:05d}"


def parse_point_id(point_id: str) -> int | None:
    text = (point_id or "").strip().upper()
    if not text.startswith("POINT-"):
        return None
    try:
        return int(text.split("-", 1)[1])
    except ValueError:
        return None


def point_status_from_last_order(last_order_at: str | None, *, now: datetime | None = None) -> str:
    """≤30 = active, 31–60 = at_risk, >60 или нет заказа = churned."""
    now = now or utcnow()
    if not last_order_at:
        return POINT_STATUS_CHURNED
    try:
        raw = last_order_at
        if "T" in raw:
            dt = datetime.fromisoformat(raw)
        else:
            dt = datetime.fromisoformat(raw + "T00:00:00+00:00")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return POINT_STATUS_CHURNED
    days = (now - dt).total_seconds() / 86400
    if days <= 30:
        return POINT_STATUS_ACTIVE
    if days <= 60:
        return POINT_STATUS_AT_RISK
    return POINT_STATUS_CHURNED


def format_actor(from_user: dict | None) -> str:
    """telegram:<user_id>:<username|noname> — кто нажал кнопку."""
    if not from_user:
        return "telegram"
    uid = from_user.get("id")
    uname = (from_user.get("username") or "").strip() or "noname"
    if uid is None:
        return f"telegram:?:{uname}"
    return f"telegram:{uid}:{uname}"


def fmt_lead_id(seq: int) -> str:
    return f"LEAD-{seq:05d}"


def parse_lead_id(lead_id: str) -> int | None:
    text = (lead_id or "").strip().upper()
    if not text.startswith("LEAD-"):
        return None
    try:
        return int(text.split("-", 1)[1])
    except ValueError:
        return None


def next_business_deadline(from_dt: datetime | None = None, days: int = 1) -> str:
    """Дедлайн +N рабочих дней (пн–пт), ISO date YYYY-MM-DD в Europe/Moscow-ish UTC day."""
    dt = from_dt or utcnow()
    # Работаем по календарным дням UTC+3 ≈ МСК без zoneinfo dependency.
    msk = dt + timedelta(hours=3)
    cur = msk.date()
    added = 0
    while added < days:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    return cur.isoformat()


def extend_deadline(deadline: str | None, days: int = 3) -> str:
    base = utcnow().date()
    if deadline:
        try:
            base = datetime.fromisoformat(deadline).date()
        except ValueError:
            pass
    return (base + timedelta(days=days)).isoformat()


def is_terminal(status: str) -> bool:
    return status in TERMINAL


def validate_status(status: str) -> bool:
    return status in STATUSES
