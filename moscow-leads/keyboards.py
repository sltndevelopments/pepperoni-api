"""Inline-клавиатуры: статус в два тапа, без свободного ввода."""
from __future__ import annotations

from model import (
    CONTACT_RESULT_LABELS,
    CONTACT_TYPE_LABELS,
    DISTRIBUTORS,
    LOST_REASONS,
    POINT_SEGMENTS,
    SELLOUT_DISTRIBUTORS,
    STATUS_LABELS,
)


def _btn(text: str, data: str) -> dict:
    return {"text": text, "callback_data": data[:64]}


def main_keyboard(seq: int) -> dict:
    p = f"ml:{seq}"
    return {
        "inline_keyboard": [
            [
                _btn("📞 Связался", f"{p}:contacted"),
                _btn("📦 Отправил образцы", f"{p}:samples_sent"),
            ],
            [
                _btn("🤝 Встреча", f"{p}:meeting_done"),
                _btn("➡️ Передал дистру", f"{p}:dist_menu"),
            ],
            [
                _btn("✅ Первая отгрузка", f"{p}:first_shipment"),
                _btn("🔄 Повтор", f"{p}:repeat_shipment"),
            ],
            [
                _btn("❌ Не наш", f"{p}:lost_menu"),
                _btn("⏰ +3 дня", f"{p}:plus3"),
            ],
            [
                _btn("🏆 Выигран", f"{p}:won"),
            ],
        ]
    }


def contact_points_keyboard(points: list[dict]) -> dict:
    """Выбор точки или «новая» для фиксации контакта."""
    rows = []
    for p in points[:20]:
        seq = p["seq"]
        label = (p.get("name") or p["id"])[:40]
        rows.append([_btn(f"📍 {label}", f"mc:pt:{seq}")])
    rows.append([_btn("➕ Новая точка", "mc:new")])
    rows.append([_btn("« Отмена", "mc:cancel")])
    return {"inline_keyboard": rows}


def contact_type_keyboard(point_ref: str) -> dict:
    """point_ref = pt:<seq> | new:<token>."""
    return {
        "inline_keyboard": [[
            _btn(CONTACT_TYPE_LABELS["call"], f"mc:{point_ref}:call"),
            _btn(CONTACT_TYPE_LABELS["visit"], f"mc:{point_ref}:visit"),
        ], [_btn("« Отмена", "mc:cancel")]]
    }


def contact_result_keyboard(point_ref: str, contact_type: str) -> dict:
    return {
        "inline_keyboard": [
            [
                _btn(CONTACT_RESULT_LABELS["order"], f"mc:{point_ref}:{contact_type}:order"),
                _btn(CONTACT_RESULT_LABELS["thinking"], f"mc:{point_ref}:{contact_type}:thinking"),
            ],
            [
                _btn(CONTACT_RESULT_LABELS["refuse"], f"mc:{point_ref}:{contact_type}:refuse"),
                _btn(CONTACT_RESULT_LABELS["not_lpr"], f"mc:{point_ref}:{contact_type}:not_lpr"),
            ],
            [_btn("« Отмена", "mc:cancel")],
        ]
    }


def segment_keyboard() -> dict:
    rows = []
    row: list[dict] = []
    for seg in POINT_SEGMENTS:
        row.append(_btn(seg, f"mc:seg:{seg}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([_btn("« Отмена", "mc:cancel")])
    return {"inline_keyboard": rows}


def sellout_distributor_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [_btn(d, f"so:dist:{d}") for d in SELLOUT_DISTRIBUTORS],
            [_btn("« Отмена", "so:cancel")],
        ]
    }


def distributor_keyboard(seq: int) -> dict:
    p = f"ml:{seq}"
    row = [_btn(name, f"{p}:dist:{name}") for name in DISTRIBUTORS]
    return {
        "inline_keyboard": [
            row,
            [_btn("« Назад", f"{p}:back")],
        ]
    }


def lost_keyboard(seq: int) -> dict:
    p = f"ml:{seq}"
    labels = {
        "no_demand": "нет спроса",
        "price": "цена",
        "not_halal": "не халяль",
        "no_reply": "не отвечает",
    }
    assert set(labels) == set(LOST_REASONS)
    return {
        "inline_keyboard": [
            [_btn(labels["no_demand"], f"{p}:lost:no_demand"), _btn(labels["price"], f"{p}:lost:price")],
            [_btn(labels["not_halal"], f"{p}:lost:not_halal"), _btn(labels["no_reply"], f"{p}:lost:no_reply")],
            [_btn("« Назад", f"{p}:back")],
        ]
    }


def stuck_keyboard(seq: int) -> dict:
    p = f"ml:{seq}"
    return {
        "inline_keyboard": [[
            _btn("Запросить ОС", f"{p}:ask_os"),
            _btn("Вернуть себе", f"{p}:take_back"),
        ]]
    }


def format_card(lead: dict) -> str:
    company = lead.get("company") or "—"
    status = lead.get("status") or "new"
    label = STATUS_LABELS.get(status, status)
    lines = [
        f"{lead['id']} · {company}" + (f" ({lead['city']})" if lead.get("city") else ""),
        f"Запрос: {(lead.get('request') or '—')[:80]} · статус: {label}"
        + (f" · дедлайн: {lead['deadline']}" if lead.get("deadline") else ""),
    ]
    if lead.get("contact") or lead.get("phone"):
        lines.append(
            f"Контакт: {lead.get('contact') or '—'} · {lead.get('phone') or '—'}"
        )
    if lead.get("distributor"):
        lines.append(f"Дистрибьютор: {lead['distributor']}")
    if lead.get("next_step"):
        lines.append(f"Дальше: {lead['next_step']}")
    if lead.get("note"):
        lines.append(f"Заметка: {lead['note'][:120]}")
    return "\n".join(lines)
