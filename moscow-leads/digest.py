"""Пятничный дайджест владельцу и Арби — тот же текст, без участия человека."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from store import Store, datetime_from_iso


def _week_bounds(now: datetime | None = None) -> tuple[str, str, str]:
    """Вернуть (week_start_iso, prev_week_start_iso, label_dates). МСК ≈ UTC+3."""
    now = now or datetime.now(timezone.utc)
    msk = now + timedelta(hours=3)
    # Неделя пн–вс: для пятничного отчёта берём последние 7 дней.
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


def build_weekly_digest(store: Store | None = None, *, now: datetime | None = None) -> str:
    store = store or Store()
    store.init()
    week_start, prev_start, label = _week_bounds(now)
    cur = store.stats_since(week_start)
    # prev week = stats since prev_start minus current week approx via two windows
    prev_all = store.stats_since(prev_start)
    prev = {k: max(0, prev_all.get(k, 0) - cur.get(k, 0)) for k in cur}

    stuck = store.stuck_at_distributor(hours=72)
    stuck_lines = []
    for lead in stuck[:20]:
        try:
            changed = datetime_from_iso(lead["status_changed_at"])
            days = int((datetime.now(timezone.utc) - changed).total_seconds() // 86400)
        except Exception:
            days = "?"
        stuck_lines.append(
            f"- {lead['id']} {lead.get('company') or '—'} — "
            f"{lead.get('distributor') or '?'} · {days}д без движения"
        )
    if not stuck_lines:
        stuck_lines = ["- нет"]

    conv = store.conversion_new_to_first(days=30)

    def line(title: str, key: str) -> str:
        return f"{title}: {cur[key]} {_arrow(cur[key], prev.get(key, 0))} (пр.нед. {prev.get(key, 0)})"

    return "\n".join([
        f"ОТЧЁТ ЗА НЕДЕЛЮ {label}",
        "",
        "1. ЛИДЫ",
        line("Пришло новых", "new"),
        line("Обработано (связался)", "contacted"),
        f"В работе сейчас: {cur['in_work']}",
        "",
        "2. ДВИЖЕНИЕ",
        line("Отправлено образцов", "samples_sent"),
        line("Проведено встреч/дегустаций", "meetings"),
        f"Передано дистрибьюторам: {cur['dist_total']} "
        f"(GFC {cur['dist_gfc']} / SweetLife {cur['dist_sweetlife']} / direct {cur['dist_direct']})",
        "",
        "3. РЕЗУЛЬТАТ",
        line("Первых отгрузок", "first_shipment"),
        line("Повторных отгрузок", "repeat_shipment"),
        "",
        "4. ЗАСТРЯЛО (>72ч у дистрибьютора)",
        *stuck_lines,
        "",
        "5. КОНВЕРСИЯ",
        f"new → first_shipment за 30 дней: {conv}%",
    ])
