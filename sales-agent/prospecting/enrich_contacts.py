"""
Обогащение лидов без email: ИНН → zachestnyibiznes.ru → телефоны/email/сайт.

Reuse паттернов sales-intel/scripts/enrich_contacts.py, но пишет в agent.db.
Запуск: python3 -m console.cli enrich [--limit N]
"""
from __future__ import annotations

import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.store import Store

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
)
ZCB = "https://zachestnyibiznes.ru"

PHONE_RE = re.compile(r"\+7[\s\(\)\-\d]{10,18}")
EMAIL_RE = re.compile(r"[\w.\-+]{2,30}@[\w\-]+\.[a-z]{2,6}")
URL_RE = re.compile(r'https?://[a-z0-9\-\.]+\.(?:ru|com|org|net|xyz|su|bz)\b[^"\' <>]*')

SKIP_URL = (
    "zachestny", "yandex", "google", "mc.yandex", "top.mail", "disqus", "cloudflare",
    "fontawesome", "gstatic", "cdnjs", "jsdelivr", "unpkg", "ya.ru", "fb.com", "vk.com",
    "facebook.com", "telegram", "instagram", "vkontakte", "twitter", "linkedin",
    "apple.com", "microsoft", "w3.org", "schema.org", "mail.ru", "rambler.",
    "bitrix", "gosuslugi.ru", "nalog.gov.ru", "nalog.ru", "egrul", "fas.gov.ru",
    "rospatent", "kontur.", "checko.", "rusprofile.", "synapsenet.", "audit-it.",
    "reestr.digital.gov.ru", "digital.gov.ru", "rkn.gov.ru", "roskomnadzor",
    "gov.ru/reestr", "gosreestr", ".jpg", ".png", ".svg", ".css", ".ico", ".webp", ".gif",
)
SKIP_EMAIL = ("noreply", "test@", "@example", "zachestny", "support@", "info@nalog")
SKIP_SITE = ("youtube.", "youtu.be", "rutube.", "ok.ru", "dzen.", "wikipedia.", "hh.ru", "avito.")


def _fetch(url: str, timeout: int = 25) -> str | None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception:
        return None


def _company_link(search_html: str) -> str | None:
    for kind in ("ul", "ip"):
        m = re.search(rf'<a[^>]+href="(/company/{kind}/[^"]+)"', search_html)
        if m:
            return m.group(1)
    return None


def _parse_contacts(html: str) -> dict:
    phones, emails, sites = [], [], []
    seen_phone: set[str] = set()
    for m in PHONE_RE.finditer(html):
        digits = re.sub(r"\D", "", m.group())
        if 11 <= len(digits) <= 12 and digits not in seen_phone:
            seen_phone.add(digits)
            phones.append(m.group().strip())
        if len(phones) >= 4:
            break
    for m in EMAIL_RE.finditer(html):
        e = m.group().lower()
        if e not in emails and len(e) <= 60 and not any(x in e for x in SKIP_EMAIL):
            emails.append(e)
        if len(emails) >= 3:
            break
    for m in URL_RE.finditer(html):
        url = m.group().rstrip(".,;)")
        low = url.lower()
        if any(skip in low for skip in SKIP_URL + SKIP_SITE) or url in sites:
            continue
        sites.append(url)
        if len(sites) >= 2:
            break
    return {"phones": phones, "emails": emails, "sites": sites}


def _emails_from_site(site: str) -> list[str]:
    """Зайти на сайт компании (+ страницу контактов), вытащить email."""
    emails: list[str] = []
    pages = [site]
    html = _fetch(site, timeout=20)
    if html:
        # найти ссылку на контакты
        m = re.search(r'href="([^"]*(?:contact|kontakt|контакт)[^"]*)"', html, re.I)
        if m:
            href = m.group(1)
            if href.startswith("http"):
                pages.append(href)
            elif href.startswith("/"):
                base = re.match(r"(https?://[^/]+)", site)
                if base:
                    pages.append(base.group(1) + href)
        for page_html in [html] + [
            _fetch(u, timeout=15) for u in pages[1:2]
        ]:
            if not page_html:
                continue
            for em in EMAIL_RE.finditer(page_html):
                e = em.group().lower()
                if e not in emails and not any(x in e for x in SKIP_EMAIL):
                    # отсечь мусор из вёрстки (png@2x и пр.)
                    if not re.search(r"\.(png|jpg|svg|gif|webp|css|js)$", e):
                        emails.append(e)
                if len(emails) >= 3:
                    return emails
    return emails


def enrich_by_inn(inn: str) -> dict | None:
    search = _fetch(f"{ZCB}/search?query={urllib.parse.quote(inn)}")
    if not search:
        return None
    link = _company_link(search)
    if not link:
        return None
    page = _fetch(ZCB + link)
    if not page:
        return None
    return _parse_contacts(page)


def _needs_enrich(lead: dict) -> bool:
    p = lead.get("profile") or {}
    return "@" not in str(p.get("emails") or p.get("email") or "")


def enrich_leads(*, store: Store | None = None, limit: int = 30, pause_sec: float = 4.0) -> dict:
    """Обогатить лиды без email (по ИНН). Пауза между запросами — вежливость к источнику."""
    store = store or Store()
    store.init()

    targets = [
        l for l in store.list_leads(limit=500)
        if _needs_enrich(l) and l.get("inn") and (l.get("status") or "new") == "new"
    ]
    # приоритет: высокий fit_score первым
    targets.sort(key=lambda x: x.get("fit_score") or 0, reverse=True)
    targets = targets[:limit]

    enriched = 0
    found_email = 0
    for lead in targets:
        contacts = enrich_by_inn(lead["inn"])
        time.sleep(pause_sec)
        if not contacts:
            continue
        # ZCB чаще отдаёт сайт, чем email — добираем email с сайта компании
        if not contacts["emails"] and contacts["sites"]:
            contacts["emails"] = _emails_from_site(contacts["sites"][0])
        profile = dict(lead.get("profile") or {})
        if contacts["emails"]:
            profile["emails"] = ",".join(contacts["emails"])
            found_email += 1
        if contacts["phones"] and not profile.get("phones"):
            profile["phones"] = ",".join(contacts["phones"])
        if contacts["sites"] and not profile.get("website"):
            profile["website"] = contacts["sites"][0]
        profile["enriched_from"] = "zachestnyibiznes"
        store.upsert_lead(
            lead["name"], lead_id=lead["id"], inn=lead.get("inn"),
            region=lead.get("region"), tier=lead.get("tier"),
            fit_score=lead.get("fit_score") or 0,
            status=lead.get("status"), source=lead.get("source"),
            profile=profile,
        )
        enriched += 1

    store.audit("enrich", "contacts", detail={
        "attempted": len(targets), "enriched": enriched, "found_email": found_email,
    })
    return {"attempted": len(targets), "enriched": enriched, "found_email": found_email}


if __name__ == "__main__":
    import json
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    print(json.dumps(enrich_leads(limit=limit), ensure_ascii=False, indent=2))
