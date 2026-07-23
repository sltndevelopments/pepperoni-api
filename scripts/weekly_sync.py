#!/usr/bin/env python3
"""Weekly Sync — the company-wide planning meeting, once a week.

The single human-in-the-loop checkpoint Fable recommended: instead of the owner
firefighting daily, this agent assembles a 10-minute Monday briefing across BOTH
deputies (Fable = growth/SEO, Steve = sales) and the shared bus, then posts it to
Telegram. It is read-only and cheap (no LLM): pure aggregation of ledgers.

It reports, in plain language:
  • OKR progress (Fable's + Steve's self-set objectives)
  • Leads this week, by channel (real demand)
  • LLM spend vs result → cost-per-lead (ROI / cost transparency)
  • Agent-bus health: handoffs done, anything stuck/escalated
  • What needs the owner's attention this week

Run weekly via cron (Monday morning).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SALES_DATA = ROOT / "sales-agent" / "data"
sys.path.insert(0, str(ROOT / "scripts"))


def _read(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _okr_lines() -> list[str]:
    out = []
    for label, mem_path in (("Fable", DATA / "fable_memory.json"),
                            ("Стив", SALES_DATA / "sales_memory.json")):
        m = _read(mem_path) or {}
        for o in (m.get("okr") or []):
            if o.get("status", "active") != "active":
                continue
            krs = "; ".join(o.get("key_results", []) or [])
            out.append(f"  • [{label}] {o.get('objective','')} — {krs}")
    return out


def _leads_week() -> tuple[int, int, dict]:
    """(#leads 7d, #commercial 7d, by_channel 7d) from the lead listener."""
    d = _read(DATA / "leads.json") or {}
    leads = d.get("leads", [])
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    week, comm, by_ch = 0, 0, {}
    for l in leads:
        try:
            at = datetime.fromisoformat(l["at"])
        except Exception:
            continue
        if at < cutoff:
            continue
        week += 1
        by_ch[l.get("channel", "?")] = by_ch.get(l.get("channel", "?"), 0) + 1
        if l.get("intent") == "commercial":
            comm += 1
    if week == 0:
        # Lead listener may be empty while Metrika still records real contact
        # actions. Use the 7-day landing attribution as a transparent fallback.
        metrika = _read(DATA / "metrika.json") or {}
        touches = sum(
            int(periods.get("7d", 0))
            for periods in (metrika.get("inquiries_by_page") or {}).values()
        )
        if touches:
            week = comm = touches
            by_ch = {"metrika_contact": touches}
    return week, comm, by_ch


def _spend_month() -> dict:
    """Current-month LLM spend by major buckets, best-effort."""
    d = _read(DATA / "llm_costs.json") or {}
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    m = d.get(month, {}) if isinstance(d, dict) else {}
    return {"total_usd": round(m.get("usd", 0.0), 2),
            "baseline_usd": round(m.get("usd_baseline", 0.0), 2)}


def _bus_health() -> dict:
    try:
        import agent_bus
        dg = agent_bus.digest()
        return {"by_status": dg.get("by_status", {}),
                "stuck": dg.get("stuck_count", 0),
                "total": dg.get("total", 0)}
    except Exception:
        return {"by_status": {}, "stuck": 0, "total": 0}


def _operator_outcomes() -> dict:
    try:
        from experiment_registry import weekly_summary
        return weekly_summary()
    except Exception:
        return {"active": 0, "verdicts": {}, "cost_usd": 0.0,
                "next_actions": []}


def _commercial_clicks() -> int:
    goals = _read(DATA / "goals.json") or {}
    seen = set()
    total = 0
    for row in goals.get("goals", []):
        query = str(row.get("query", "")).casefold()
        if query in seen:
            continue
        seen.add(query)
        total += int(row.get("clicks_28d", 0))
    return total


def _commercial_pulse_block() -> list[str]:
    """Embed north-star experiment pulse (measuring window until ~Aug 11)."""
    try:
        import commercial_pulse
        pulse = commercial_pulse.build_pulse()
        (DATA / "commercial_pulse.json").write_text(
            json.dumps(pulse, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        lines = ["<b>North star — 3 коммерческих эксперимента</b>",
                 f"  GSC data → {pulse.get('gsc_data_through') or '—'}"]
        for it in pulse.get("experiments") or []:
            exact = it.get("exact") or {}
            flag = it.get("flag")
            note = {
                "not_ranking_yet": "ещё не в выдаче по запросу",
                "improved": "лучше baseline",
                "worse": "хуже baseline",
                "watching": "смотрим",
            }.get(flag, flag)
            lines.append(
                f"  • {it.get('query')} → {it.get('page')} "
                f"({it.get('days_left')}д) {note}; "
                f"exact pos={exact.get('position') if exact.get('position') is not None else '—'} "
                f"impr={exact.get('impr', 0)}"
            )
            top = (it.get("sitewide_top") or [{}])[0]
            if top.get("page"):
                lines.append(
                    f"    сейчас спрос на: {top['page']} "
                    f"(pos={top.get('position')}, impr={top.get('impr')})"
                )
        leads = pulse.get("leads") or {}
        lines.append(
            f"  Лиды 7д/21д: {leads.get('7d', 0)}/{leads.get('21d', 0)} "
            f"(на exp-страницах 21д: {leads.get('on_exp_pages_21d', 0)})"
        )
        lines.append("")
        return lines
    except Exception as exc:
        return [f"<b>North star pulse</b>", f"  ⚠ unavailable: {exc}", ""]


def build_report() -> str:
    week, comm, by_ch = _leads_week()
    spend = _spend_month()
    bus = _bus_health()
    outcomes = _operator_outcomes()
    commercial_clicks = _commercial_clicks()
    okr = _okr_lines()

    cost_per_lead = (f"${spend['total_usd'] / comm:.2f}" if comm
                     else "—")
    ch = ", ".join(f"{k}:{v}" for k, v in
                   sorted(by_ch.items(), key=lambda x: -x[1])) or "—"

    lines = ["📅 <b>Недельная планёрка компании</b>",
             f"<i>{datetime.now(timezone.utc):%d.%m.%Y}</i>", ""]
    lines += ["<b>Заявки за неделю</b>",
              f"  Всего: {week}  ·  коммерческих: {comm}",
              f"  По каналам: {ch}", ""]
    lines += _commercial_pulse_block()
    lines += ["<b>Бюджет LLM (месяц)</b>",
              f"  Потрачено: ${spend['total_usd']} "
              f"(без оптимизаций было бы ${spend['baseline_usd']})",
              f"  Стоимость заявки: {cost_per_lead}", ""]
    verdicts = outcomes["verdicts"]
    lines += ["<b>Outcome-эксперименты</b>",
              f"  Активно: {outcomes['active']} / 3",
              f"  Win: {verdicts.get('win', 0)} · Flat: {verdicts.get('flat', 0)} · "
              f"Worse/revert: {verdicts.get('worse', 0) + verdicts.get('reverted', 0)}",
              f"  Коммерческие клики (28д): {commercial_clicks}", ""]
    lines += ["<b>Следующие задачи (макс. 3)</b>"]
    if outcomes.get("next_actions"):
        lines += [
            f"  • {row['query']} → {row['page']} (замер {row['measure_at']})"
            for row in outcomes["next_actions"]
        ]
    else:
        lines.append("  • Новые задачи заморожены или очередь пуста")
    lines.append("")
    by_status = bus["by_status"]
    lines += ["<b>Координация (шина задач)</b>",
              f"  Задач всего: {bus['total']}  ·  "
              f"выполнено: {by_status.get('done',0)}  ·  "
              f"в работе: {by_status.get('in_progress',0)}  ·  "
              f"ждут: {by_status.get('pending',0)}",
              (f"  ⚠ Зависло: {bus['stuck']} — нужно внимание" if bus["stuck"]
               else "  ✅ Зависших задач нет"), ""]
    if okr:
        lines += ["<b>Цели (OKR)</b>"] + okr + [""]
    # Owner attention block.
    attention = []
    if bus["stuck"]:
        attention.append(f"Разобрать {bus['stuck']} зависш. задач(и) в шине")
    if comm == 0 and week == 0:
        attention.append("За неделю нет заявок — проверить каналы/трекинг")
    if not okr:
        attention.append("Не заданы OKR — агенты работают без квартальных целей")
    attention.append(
        "PSI key: ограничить IP 37.9.4.101 в GCP Credentials "
        "(ключ светился в чате)"
    )
    lines += ["<b>Требует твоего внимания</b>"]
    lines += [f"  • {a}" for a in attention] if attention else ["  ✅ Всё штатно"]
    return "\n".join(lines)


def main() -> int:
    report = build_report()
    print(report)
    # Keep the bus tidy on the weekly beat.
    try:
        import agent_bus
        agent_bus.gc()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
