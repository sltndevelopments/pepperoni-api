#!/usr/bin/env python3
"""
Показать таблицу «было ЕГРЮЛ-email → стало email_best + quality + MX» на N ценных лидах.

Использует только уже сохранённые данные из agent.db (не делает новых HTTP запросов).
Для прогона нового ресёрча — запусти enrich (cli enrich) сначала.

Запуск:
  python3 sales-agent/scripts/verify_contacts_table.py [--limit 20]
"""
from __future__ import annotations
import json
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.store import Store
from core import agent_profile as ap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--tier", default=None, help="Фильтр тира (S, A, B, ...)")
    args = parser.parse_args()

    store = Store()
    store.init()

    leads = store.list_leads(limit=600)
    # Ценные лиды — tier S/A или высокий fit
    def priority(l):
        tier_rank = {"S": 4, "A": 3, "B": 2, "C": 1}.get(l.get("tier") or "—", 0)
        return (tier_rank * 100) + (l.get("fit_score") or 0)

    leads.sort(key=priority, reverse=True)
    if args.tier:
        leads = [l for l in leads if l.get("tier") == args.tier]

    # Только те, у кого есть какой-то email (ЕГРЮЛ или agent-researched)
    with_email = [
        l for l in leads
        if any([
            l.get("profile") and (
                l["profile"].get("emails") or l["profile"].get("email")
                or ap.get(l["profile"], "email_best")
            )
        ])
    ][:args.limit]

    rows = []
    for l in with_email:
        p = l.get("profile") or {}
        # Исходный ЕГРЮЛ-email (первый из profile.emails, до research)
        raw = str(p.get("emails") or p.get("email") or "").replace(";", ",").split(",")
        egrul_email = (raw[0].strip().lower() if raw else "") or "—"

        email_best = ap.get(p, "email_best") or "—"
        quality = ap.get(p, "email_quality") or "—"
        verified = ap.get(p, "email_verified")
        mx_failed = ap.get(p, "email_mx_failed")
        site = ap.get(p, "contact_site") or p.get("website") or "—"
        researched_at = ap.get(p, "contact_researched_at") or "—"

        if verified is True:
            mx_status = "✅ ok"
        elif mx_failed is True:
            mx_status = "❌ dead"
        elif verified is False and mx_failed is False:
            mx_status = "⏳ not checked"
        else:
            mx_status = "⏳ not checked"

        changed = (
            email_best != "—"
            and egrul_email != "—"
            and email_best.lower() != egrul_email.lower()
        )
        rows.append({
            "tier": l.get("tier") or "—",
            "fit": l.get("fit_score") or 0,
            "name": (l.get("name") or "")[:45],
            "inn": l.get("inn") or "—",
            "egrul_email": egrul_email[:45],
            "email_best": email_best[:45],
            "changed": "→" if changed else "=",
            "quality": quality,
            "mx": mx_status,
            "site": site[:40],
            "researched": researched_at[:10] if researched_at != "—" else "—",
        })

    # Header
    col = {
        "tier": 4, "fit": 3, "name": 30, "inn": 12, "egrul_email": 30,
        "changed": 1, "email_best": 30, "quality": 11, "mx": 12,
        "site": 35, "researched": 10,
    }
    header = (
        f"{'Tir':<{col['tier']}} {'Fit':<{col['fit']}} {'Компания':<{col['name']}} "
        f"{'ИНН':<{col['inn']}} {'ЕГРЮЛ email':<{col['egrul_email']}} "
        f"{'C':<{col['changed']}} {'email_best':<{col['email_best']}} "
        f"{'quality':<{col['quality']}} {'MX':<{col['mx']}} "
        f"{'Сайт':<{col['site']}} {'researched':<{col['researched']}}"
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for r in rows:
        print(
            f"{r['tier']:<{col['tier']}} {r['fit']:<{col['fit']}} {r['name']:<{col['name']}} "
            f"{r['inn']:<{col['inn']}} {r['egrul_email']:<{col['egrul_email']}} "
            f"{r['changed']:<{col['changed']}} {r['email_best']:<{col['email_best']}} "
            f"{r['quality']:<{col['quality']}} {r['mx']:<{col['mx']}} "
            f"{r['site']:<{col['site']}} {r['researched']:<{col['researched']}}"
        )
    print(sep)
    print(f"Итого: {len(rows)} лидов показано")

    # Сводка
    verified_count = sum(1 for r in rows if "✅" in r["mx"])
    dead_count = sum(1 for r in rows if "❌" in r["mx"])
    unchecked = sum(1 for r in rows if "⏳" in r["mx"])
    improved = sum(1 for r in rows if r["changed"] == "→")
    print(f"  MX verified: {verified_count} | dead: {dead_count} | unchecked: {unchecked}")
    print(f"  Email улучшен: {improved} | без изменений: {len(rows) - improved}")


if __name__ == "__main__":
    main()
