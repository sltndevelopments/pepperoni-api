"""Пятничный дайджест — АКБ / sell-out / зона риска, не активность ради активности."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from model import DAILY_CONTACT_TARGET_MIN, WEEKLY_CONTACT_TARGET
from store import Store, datetime_from_iso


def _week_bounds(now: datetime | None = None) -> tuple[str, str, str]:
    """Вернуть (week_start_iso, prev_week_start_iso, label_dates). МСК ≈ UTC+3."""
    now = now or datetime.now(timezone.utc)
    msk = now + timedelta(hours=3)
    end = msk.date()
    start = end - timedelta(days=6)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    label = f"{start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}"
    return (
        datetime(start.year, start.month, start.day, tzinfo=timezone.utc).isoformat(),
        datetime(prev_start.year, prev_start.month, prev_start.day, tzinfo=timezone.utc).isoformat(),
        label,
    )


def _arrow(cur: int, prev: int) -> str:
    if cur > prev:
        return "↑"
    if cur < prev:
        return "↓"
    return "→"


def _names(points: list[dict], limit: int = 12) -> list[str]:
    out = []
    for p in points[:limit]:
        name = p.get("name") or p.get("id") or "—"
        city = f" ({p['city']})" if p.get("city") else ""
        out.append(f"- {name}{city}")
    if len(points) > limit:
        out.append(f"- … ещё {len(points) - limit}")
    return out or ["- нет"]


def build_weekly_digest(store: Store | None = None, *, now: datetime | None = None) -> str:
    store = store or Store()
    store.init()
    now = now or datetime.now(timezone.utc)
    week_start, prev_start, label = _week_bounds(now)

    snap = store.akb_snapshot(now=now)
    akb_prev = store.akb_count_as_of(week_start)
    new_pts = store.new_points_since(week_start)

    contacts = store.count_contacts_since(week_start, productive_only=True)
    contact_pct = round(100.0 * contacts / WEEKLY_CONTACT_TARGET, 0) if WEEKLY_CONTACT_TARGET else 0

    month = store.latest_sellout_month()
    sell_lines = []
    if month:
        by_d = store.sellout_for_month(month)
        gfc = by_d.get("GFC") or {}
        sj = by_d.get("SweetLife") or {}
        sell_lines.append(
            f"Sell-out {month}: GFC {gfc.get('kg', '—')} кг · "
            f"СЖ {sj.get('kg', '—')} кг"
        )
        if gfc.get("points_count") or sj.get("points_count"):
            sell_lines.append(
                f"Точек в отчётах: GFC {gfc.get('points_count', '—')} · "
                f"СЖ {sj.get('points_count', '—')}"
            )
    else:
        sell_lines.append("Sell-out: ещё не введён (/sellout)")

    stuck = store.stuck_at_distributor(hours=72)
    stuck_lines = []
    for lead in stuck[:20]:
        try:
            changed = datetime_from_iso(lead["status_changed_at"])
            days = int((now - changed).total_seconds() // 86400)
        except Exception:
            days = "?"
        stuck_lines.append(
            f"- {lead['id']} {lead.get('company') or '—'} — "
            f"{lead.get('distributor') or '?'} · {days}д без движения"
        )
    if not stuck_lines:
        stuck_lines = ["- нет"]

    at_risk = snap["at_risk_points"]
    churned_n = snap["churned"]

    return "\n".join([
        f"ОТЧЁТ ЗА НЕДЕЛЮ {label}",
        "",
        "1. АКБ (активные точки ≤30 дней)",
        f"АКБ: {snap['akb']} точек "
        f"({_arrow(snap['akb'], akb_prev)} было {akb_prev} на начало недели)",
        f"Новых точек за неделю: {len(new_pts)}",
        *_names(new_pts, limit=10),
        "",
        "2. ЗОНА РИСКА И ОТВАЛ",
        f"В зоне риска (31–60 дней без заказа): {snap['at_risk']} — работа на следующую неделю",
        *_names(at_risk, limit=15),
        f"Отвал (>60 дней): {churned_n}",
        "",
        "3. КОНТАКТЫ (поле)",
        f"Контактов за неделю: {contacts} "
        f"(норма {WEEKLY_CONTACT_TARGET}, ≈{int(contact_pct)}%; "
        f"день {DAILY_CONTACT_TARGET_MIN}–12)",
        "",
        "4. SELL-OUT",
        *sell_lines,
        "",
        "5. ЗАСТРЯЛО У ДИСТРИБЬЮТОРА (>72ч)",
        *stuck_lines,
        "",
        f"(всего точек в справочнике: {snap['total_points']}; "
        f"prev_week_anchor={prev_start[:10]})",
    ])
