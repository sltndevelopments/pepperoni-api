"""
Bounce-recovery: hard bounce ≠ «забыли», а «найди правильный адрес и дожми».

Когда письмо вернулось навсегда (hard bounce), адрес уходит в блэклист, но
КОМПАНИЯ остаётся целью — особенно если это tier A (крупные хлебокомбинаты,
сети). Этот модуль замыкает петлю:

  1. Берёт лиды с hard bounce (статус bounced или есть profile.bounce.hard).
  2. Ресёрчит НОВЫЙ адрес по ИНН: zachestnyibiznes.ru → сайт компании
     (тот же движок, что в enrich_contacts).
  3. Если найден адрес, отличный от забаненного:
       • записывает его первым в profile.emails,
       • статус → "new" (вернётся в очередь холодного аутрича на новый адрес),
       • profile.bounce_recovered = {old, new, at}.
  4. Если новый адрес не найден:
       • статус → "bounced_need_research",
       • эскалация владельцу с ИНН + сайтом для ручного выхода (звонок/2ГИС).

Забаненный адрес из блэклиста НЕ убираем — пишем именно на новый.
Запуск: python3 -m console.cli recover-bounces  (или из цикла Стива).
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.store import Store
from core import agent_profile as ap
from prospecting.contact_research import research_contacts

# мост к Perplexity (живой веб-поиск) — общий клиент SEO-проекта
REPO = ROOT.parent
for _s in (REPO / "scripts", REPO / "repo" / "scripts"):
    if (_s / "pplx_client.py").exists():
        sys.path.insert(0, str(_s))
        break


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()




def _is_bounced(lead: dict) -> bool:
    p = lead.get("profile") or {}
    if ap.is_handed_off(p):
        return False  # передан менеджеру — не трогаем
    if (lead.get("status") or "") in ("bounced", "bounced_need_research", "handed_off"):
        # handed_off может остаться как статус до следующего CRM-pull
        return (lead.get("status") or "") in ("bounced", "bounced_need_research")
    return ap.hard_bounce(p)


def _bounced_addr(lead: dict) -> str:
    return ap.bounced_addr(lead.get("profile") or {})


def find_bounced(store: Store) -> list[dict]:
    """Лиды с hard bounce + те, чей email в блэклисте (на случай несхваченных).

    Исключает переданных менеджеру (profile._agent.handed_off).
    """
    from channels.deliverability import is_blacklisted
    out = []
    for l in store.list_leads(limit=600):
        p = l.get("profile") or {}
        if ap.is_handed_off(p):
            continue
        if _is_bounced(l):
            out.append(l)
            continue
        emails = [e.strip().lower() for e in str(p.get("emails") or p.get("email") or "").replace(";", ",").split(",") if e.strip()]
        if emails and all(is_blacklisted(e) for e in emails):
            out.append(l)
    out.sort(key=lambda x: x.get("fit_score") or 0, reverse=True)
    return out




def _research_due(p: dict, cooldown_days: int = 7) -> bool:
    """True если с последнего ресёрча прошло больше cooldown_days (или ещё не было)."""
    br = ap.get(p, "bounce_research")
    if not isinstance(br, dict):
        return True
    try:
        prev = datetime.fromisoformat(br["at"])
        return (datetime.now(timezone.utc) - prev).total_seconds() > cooldown_days * 86400
    except Exception:
        return True


def recover(*, store: Store | None = None, limit: int = 20,
            pause_sec: float = 4.0, escalate: bool = True) -> dict:
    store = store or Store()
    store.init()
    from channels.deliverability import is_blacklisted

    targets = find_bounced(store)[:limit]
    recovered = 0
    need_research = 0
    skipped_cooldown = 0

    for lead in targets:
        p = dict(lead.get("profile") or {})

        # Не повторять дорогой ресёрч чаще раза в 7 дней
        if not _research_due(p):
            skipped_cooldown += 1
            continue

        banned = {e.strip().lower() for e in
                  str(p.get("emails") or p.get("email") or "").replace(";", ",").split(",")
                  if e.strip()}
        old = _bounced_addr(lead)
        if old:
            banned.add(old)

        # Tier S/A → deep-ресёрч (Perplexity + реальный сайт); остальные → ZCB
        deep = lead.get("tier") in ("S", "A")
        research = research_contacts(lead, deep=deep, banned=banned, pause_sec=pause_sec / 4)
        new_email = research.get("best_email")

        time.sleep(pause_sec)

        if new_email and not is_blacklisted(new_email):
            others = [e for e in str(p.get("emails") or "").replace(";", ",").split(",")
                      if e.strip() and e.strip().lower() not in banned]
            p["emails"] = ",".join([new_email] + others)
            ap.update(p, bounce_recovered={"old": old or "?", "new": new_email, "at": _now()})
            # Сохраняем метки ресёрча в _agent
            ap.update(p,
                email_best=new_email,
                email_quality=research.get("quality"),
                email_verified=research.get("verified", False),
                email_mx_failed=research.get("mx_failed", False),
            )
            if research.get("site"):
                ap.set(p, "contact_site", research["site"])
                if not p.get("website"):
                    p["website"] = research["site"]
            if deep:
                from prospecting.contact_research import _now as _cr_now
                ap.set(p, "contact_researched_at", _cr_now())
            # снимаем bounce-флаг из _agent (адрес восстановлен)
            agent_ns = p.setdefault("_agent", {})
            agent_ns.pop("bounce", None)
            store.upsert_lead(
                lead["name"], lead_id=lead["id"], inn=lead.get("inn"),
                region=lead.get("region"), tier=lead.get("tier"),
                fit_score=lead.get("fit_score") or 0,
                status="new", source=lead.get("source"), profile=p,
            )
            store.audit("bounce_recovery", "recovered", entity_id=lead["id"], detail={
                "lead": lead["name"][:60], "old": old, "new": new_email,
                "quality": research.get("quality"), "verified": research.get("verified"),
            })
            recovered += 1
        else:
            ap.update(p, bounce_research={
                "tried_inn": lead.get("inn"), "at": _now(),
                "site": (research.get("site") or p.get("website") or ""),
                "mx_failed": research.get("mx_failed", False),
            })
            if research.get("site") and not p.get("website"):
                p["website"] = research["site"]
            store.upsert_lead(
                lead["name"], lead_id=lead["id"], inn=lead.get("inn"),
                region=lead.get("region"), tier=lead.get("tier"),
                fit_score=lead.get("fit_score") or 0,
                status="bounced_need_research", source=lead.get("source"), profile=p,
            )
            store.audit("bounce_recovery", "need_research", entity_id=lead["id"], detail={
                "lead": lead["name"][:60], "inn": lead.get("inn"),
                "site": p.get("website"), "mx_failed": research.get("mx_failed", False),
            })
            need_research += 1

    # Эскалация владельцу: tier S/A, которых не восстановили автоматически.
    # Каждый лид — РОВНО ОДИН РАЗ.  ap.is_escalated учитывает legacy manual_escalated_at.
    notified = 0
    if escalate and need_research:
        candidates = [
            l for l in targets
            if (l.get("status") or "") not in ("new", "handed_off")
            and l.get("tier") in ("S", "A")
            and not ap.is_escalated(l.get("profile") or {})
            and not ap.is_handed_off(l.get("profile") or {})
        ]
        to_notify = candidates[:10]
        if to_notify:
            lines = ["📣 <b>Стив:</b> крупные компании с мёртвым email — нужен ручной выход "
                     "(сайт/2ГИС/звонок), это tier A, бросать нельзя:"]
            for l in to_notify:
                pr = l.get("profile") or {}
                lines.append(
                    f"\n• <b>{l['name'][:50]}</b> (ИНН {l.get('inn') or '—'})"
                    + (f"\n  сайт: {ap.get(pr, 'website') or pr.get('website', '')}" if (ap.get(pr, "website") or pr.get("website")) else "")
                    + (f"\n  тел: {pr.get('phones')}" if pr.get("phones") else "")
                )
            lines.append(
                "\n\n<i>Это разовая эскалация. Нажми кнопку ниже, когда передашь менеджеру.</i>"
            )
            try:
                from telegram.notify import notify_with_handoff
                notify_with_handoff("\n".join(lines))
                notified = len(to_notify)
            except Exception:
                try:
                    from telegram.notify import notify
                    notify("\n".join(lines))
                    notified = len(to_notify)
                except Exception:
                    pass

            # Ставим owner_escalated_at в _agent только тем, кого реально включили в текст
            for l in to_notify:
                pr = dict(l.get("profile") or {})
                ap.mark_escalated(pr)
                store.upsert_lead(
                    l["name"], lead_id=l["id"], inn=l.get("inn"),
                    region=l.get("region"), tier=l.get("tier"),
                    fit_score=l.get("fit_score") or 0,
                    status=l.get("status"), source=l.get("source"), profile=pr,
                )

    return {"targets": len(targets), "recovered": recovered,
            "need_research": need_research, "notified": notified,
            "skipped_cooldown": skipped_cooldown}


if __name__ == "__main__":
    import json
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print(json.dumps(recover(limit=limit), ensure_ascii=False, indent=2))
