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

import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.store import Store
from prospecting.enrich_contacts import enrich_by_inn, _emails_from_site, EMAIL_RE, SKIP_EMAIL

# мост к Perplexity (живой веб-поиск) — общий клиент SEO-проекта
REPO = ROOT.parent
for _s in (REPO / "scripts", REPO / "repo" / "scripts"):
    if (_s / "pplx_client.py").exists():
        sys.path.insert(0, str(_s))
        break


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pplx_find_contacts(lead: dict, banned: set[str]) -> tuple[str | None, str | None]:
    """Живой веб-поиск контактов компании. Возвращает (email, site)."""
    try:
        from pplx_client import pplx_search
    except Exception:
        return None, None
    name = lead.get("name", "")
    inn = lead.get("inn") or ""
    region = lead.get("region") or ""
    q = (
        f"Найди действующий официальный сайт и контактный email отдела закупок/"
        f"приёмной компании {name} (ИНН {inn}, {region}). "
        "Старый адрес недоступен. Дай только: рабочий сайт и e-mail для деловых "
        "обращений. Если нашёл несколько e-mail — перечисли через запятую."
    )
    try:
        text, citations = pplx_search(q, max_tokens=400, timeout=60)
    except Exception:
        return None, None
    emails = []
    for m in EMAIL_RE.finditer(text or ""):
        e = m.group().lower()
        if e not in emails and e not in banned and not any(x in e for x in SKIP_EMAIL):
            if not re.search(r"\.(png|jpg|svg|gif|webp)$", e):
                emails.append(e)
    site = None
    sm = re.search(r"https?://[a-z0-9.\-]+\.[a-z]{2,6}", (text or ""), re.I)
    if sm:
        site = sm.group(0)
    return (emails[0] if emails else None), site


def _is_bounced(lead: dict) -> bool:
    if (lead.get("status") or "") in ("bounced", "bounced_need_research"):
        return True
    p = lead.get("profile") or {}
    b = p.get("bounce")
    return isinstance(b, dict) and b.get("hard")


def _bounced_addr(lead: dict) -> str:
    p = lead.get("profile") or {}
    b = p.get("bounce") or {}
    return (b.get("email") or "").lower()


def find_bounced(store: Store) -> list[dict]:
    """Лиды с hard bounce + те, чей email в блэклисте (на случай несхваченных)."""
    from channels.deliverability import is_blacklisted
    out = []
    for l in store.list_leads(limit=600):
        if _is_bounced(l):
            out.append(l)
            continue
        p = l.get("profile") or {}
        emails = [e.strip().lower() for e in str(p.get("emails") or p.get("email") or "").replace(";", ",").split(",") if e.strip()]
        if emails and all(is_blacklisted(e) for e in emails):
            out.append(l)
    # приоритет крупным
    out.sort(key=lambda x: x.get("fit_score") or 0, reverse=True)
    return out


def _research_new_email(lead: dict, banned: set[str],
                        use_pplx: bool = True) -> tuple[str | None, str | None]:
    """Найти НОВЫЙ (не забаненный) email. Возвращает (email, site).

    Источники по очереди: ЕГРЮЛ/zachestnyibiznes → сайт компании → (fallback)
    живой веб-поиск через Perplexity. ZCB часто отдаёт тот же мёртвый адрес,
    поэтому Perplexity важен для крупных компаний со сменившимся контактом.
    """
    site = None
    inn = lead.get("inn")
    if inn:
        contacts = enrich_by_inn(inn)
        if contacts:
            if contacts.get("sites"):
                site = contacts["sites"][0]
            cand = [e.lower() for e in (contacts.get("emails") or [])]
            if not cand and site:
                cand = [e.lower() for e in _emails_from_site(site)]
            for e in cand:
                if e and e not in banned:
                    return e, site

    if use_pplx:
        email, pplx_site = _pplx_find_contacts(lead, banned)
        if pplx_site and not site:
            site = pplx_site
        # если pplx дал сайт, но не email — добираем email с сайта
        if not email and pplx_site:
            for e in _emails_from_site(pplx_site):
                if e.lower() not in banned:
                    email = e.lower()
                    break
        if email:
            return email, site

    return None, site


def recover(*, store: Store | None = None, limit: int = 20,
            pause_sec: float = 4.0, escalate: bool = True) -> dict:
    store = store or Store()
    store.init()
    from channels.deliverability import is_blacklisted

    targets = find_bounced(store)[:limit]
    recovered = 0
    need_research = 0

    for lead in targets:
        p = dict(lead.get("profile") or {})
        banned = {e.strip().lower() for e in
                  str(p.get("emails") or p.get("email") or "").replace(";", ",").split(",")
                  if e.strip()}
        old = _bounced_addr(lead)
        if old:
            banned.add(old)

        new_email, found_site = _research_new_email(lead, banned)
        if found_site and not p.get("website"):
            p["website"] = found_site
        time.sleep(pause_sec)

        if new_email and not is_blacklisted(new_email):
            # ставим новый адрес первым, возвращаем в очередь аутрича
            others = [e for e in str(p.get("emails") or "").replace(";", ",").split(",")
                      if e.strip() and e.strip().lower() not in banned]
            p["emails"] = ",".join([new_email] + others)
            p["bounce_recovered"] = {"old": old or "?", "new": new_email, "at": _now()}
            p.pop("bounce", None)
            store.upsert_lead(
                lead["name"], lead_id=lead["id"], inn=lead.get("inn"),
                region=lead.get("region"), tier=lead.get("tier"),
                fit_score=lead.get("fit_score") or 0,
                status="new", source=lead.get("source"), profile=p,
            )
            store.audit("bounce_recovery", "recovered", entity_id=lead["id"], detail={
                "lead": lead["name"][:60], "old": old, "new": new_email,
            })
            recovered += 1
        else:
            p["bounce_research"] = {"tried_inn": lead.get("inn"), "at": _now(),
                                    "site": (p.get("website") or "")}
            store.upsert_lead(
                lead["name"], lead_id=lead["id"], inn=lead.get("inn"),
                region=lead.get("region"), tier=lead.get("tier"),
                fit_score=lead.get("fit_score") or 0,
                status="bounced_need_research", source=lead.get("source"), profile=p,
            )
            store.audit("bounce_recovery", "need_research", entity_id=lead["id"], detail={
                "lead": lead["name"][:60], "inn": lead.get("inn"),
                "site": p.get("website"),
            })
            need_research += 1

    # эскалация владельцу: tier A, которых не удалось восстановить автоматически
    if escalate and need_research:
        manual = [l for l in targets
                  if (l.get("status") or "") != "new" and l.get("tier") in ("S", "A")]
        if manual:
            lines = ["📣 <b>Стив:</b> крупные компании с мёртвым email — нужен ручной выход "
                     "(сайт/2ГИС/звонок), это tier A, бросать нельзя:"]
            for l in manual[:10]:
                pr = l.get("profile") or {}
                lines.append(
                    f"\n• <b>{l['name'][:50]}</b> (ИНН {l.get('inn') or '—'})"
                    + (f"\n  сайт: {pr.get('website')}" if pr.get("website") else "")
                    + (f"\n  тел: {pr.get('phones')}" if pr.get("phones") else "")
                )
            try:
                from telegram.notify import notify
                notify("\n".join(lines))
            except Exception:
                pass

    return {"targets": len(targets), "recovered": recovered, "need_research": need_research}


if __name__ == "__main__":
    import json
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print(json.dumps(recover(limit=limit), ensure_ascii=False, indent=2))
