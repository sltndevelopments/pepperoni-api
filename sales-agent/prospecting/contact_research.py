"""
Центральный модуль контакт-ресёрча. Единственный источник правды:
  - find_company_site     — Perplexity: реальный бренд + официальный сайт
  - emails_from_site      — почта со страницы контактов сайта
  - rank_emails           — ранжирование по роли/домену (procurement > corporate > generic > freemail)
  - verify_email          — MX + A запись (RFC: нет MX → пробуем A)
  - research_contacts     — главная точка входа; deep=True для tier S/A

Оба пути используют ЭТОТ код:
  - enrich_contacts.enrich_leads   → research_contacts(deep=tier S/A)
  - bounce_recovery.recover        → research_contacts(deep=True, banned=...)

Метки пишутся в profile._agent (переживают CRM-pull):
  _agent.email_best           — лучший email
  _agent.email_quality        — procurement | corporate | generic | freemail
  _agent.email_verified       — True если домен прошёл MX/A
  _agent.email_mx_failed      — True если домен мёртвый (явно блокировать в очереди)
  _agent.contact_site         — реальный сайт бренда (может отличаться от ZCB-сайта)
  _agent.contact_researched_at — ISO timestamp последнего deep-ресёрча (cooldown 30д)
"""
from __future__ import annotations

import re
import socket
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Константы (shared with enrich_contacts — тот импортирует их отсюда)
# ---------------------------------------------------------------------------

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

# Роли закупок/сбыта — лучший сигнал для приоритизации
PROCUREMENT_PREFIXES = (
    "zakupki", "snab", "zakaz", "opt", "sales", "commercial", "export",
    "sbyt", "torg", "buyer", "purchase", "procurement",
)
# Общие ящики — хуже, но на корп. домене
GENERIC_PREFIXES = ("info", "office", "mail", "contact", "hello", "reception", "admin")

FREE_DOMAINS = ("@mail.ru", "@yandex.ru", "@gmail.com", "@bk.ru", "@inbox.ru", "@list.ru", "@rambler.ru")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# ZCB scraping (ранее в enrich_contacts, теперь здесь — единый источник)
# ---------------------------------------------------------------------------

def _company_link(search_html: str) -> str | None:
    for kind in ("ul", "ip"):
        m = re.search(rf'<a[^>]+href="(/company/{kind}/[^"]+)"', search_html)
        if m:
            return m.group(1)
    return None


def _parse_contacts(html: str) -> dict:
    phones: list[str] = []
    emails: list[str] = []
    sites: list[str] = []
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


def enrich_by_inn(inn: str) -> dict | None:
    """ZCB lookup по ИНН → {phones, emails, sites}."""
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


# ---------------------------------------------------------------------------
# Scraping реального сайта компании
# ---------------------------------------------------------------------------

def _emails_from_html(html: str) -> list[str]:
    """Вытащить email из уже скачанного HTML (без лишних запросов)."""
    emails: list[str] = []
    for em in EMAIL_RE.finditer(html):
        e = em.group().lower()
        if e not in emails and not any(x in e for x in SKIP_EMAIL):
            if not re.search(r"\.(png|jpg|svg|gif|webp|css|js)$", e):
                emails.append(e)
        if len(emails) >= 5:
            break
    return emails


def _fetch_contact_page(site: str, main_html: str) -> str | None:
    """Найти и скачать страницу контактов сайта."""
    m = re.search(r'href="([^"]*(?:contact|kontakt|контакт|about)[^"]*)"', main_html, re.I)
    if not m:
        return None
    href = m.group(1)
    if href.startswith("http"):
        return _fetch(href, timeout=15)
    elif href.startswith("/"):
        base = re.match(r"(https?://[^/]+)", site)
        return _fetch(base.group(1) + href, timeout=15) if base else None
    return None


def emails_from_site(site: str) -> list[str]:
    """Зайти на сайт компании (+ страницу контактов), вытащить email.

    Ищет /contacts или /kontakty, читает и основную страницу и контактную.
    Публичный API — используется внешними модулями.
    """
    html = _fetch(site, timeout=20)
    if not html:
        return []
    emails = _emails_from_html(html)
    contact_html = _fetch_contact_page(site, html)
    if contact_html:
        for e in _emails_from_html(contact_html):
            if e not in emails:
                emails.append(e)
            if len(emails) >= 5:
                break
    return emails


# ---------------------------------------------------------------------------
# Верификация принадлежности сайта компании
# ---------------------------------------------------------------------------

def verify_site_ownership(
    site: str,
    lead: dict,
    *,
    fetch_html: str | None = None,
) -> dict:
    """Проверить, что сайт действительно принадлежит этой компании.

    Стратегия «доверяй, но проверяй»: считаем сайт подтверждённым, если
    на странице встречается хотя бы один из:
      - ИНН компании (самый сильный сигнал)
      - Точное юридическое название (или его ключевые слова)
      - Город из region компании

    Если ни одно из трёх не найдено — сайт «неподтверждён»: может быть
    другая организация, агрегатор или Perplexity-ошибка.

    Returns:
        {
            "confirmed": bool,
            "reason":    "inn" | "legal_name" | "city" | "not_found" | "fetch_error",
            "site":      str (исходный url)
        }
    """
    if not site:
        return {"confirmed": False, "reason": "no_site", "site": site}

    # Получаем HTML (или используем уже скачанный)
    html = fetch_html
    if html is None:
        html = _fetch(site, timeout=15) or ""

    if not html:
        return {"confirmed": False, "reason": "fetch_error", "site": site}

    html_lower = html.lower()

    # --- Сигнал 1: ИНН ---
    inn = (lead.get("inn") or "").strip()
    if inn and len(inn) >= 10 and inn in html:
        return {"confirmed": True, "reason": "inn", "site": site}

    # --- Сигнал 2: юридическое название ---
    legal_name = (lead.get("name") or "").strip()
    if legal_name:
        # Убираем организационно-правовую форму (ООО, АО, ЗАО...) и кавычки
        core_name = re.sub(
            r'^(?:ООО|АО|ЗАО|ОАО|ПАО|ИП|ПК|СП|НКО)\s*[«""]?|[»""]',
            "", legal_name, flags=re.I,
        ).strip().lower()
        # Берём значимые слова (>=4 символа), ищем совпадение хотя бы 2 из них
        words = [w for w in re.split(r'[\s\-_/]+', core_name) if len(w) >= 4]
        if words:
            matches = sum(1 for w in words if w in html_lower)
            if matches >= min(2, len(words)):
                return {"confirmed": True, "reason": "legal_name", "site": site}

    # --- Сигнал 3: город из region ---
    region = (lead.get("region") or "").strip().lower()
    if region:
        # Берём первое слово региона (обычно город: "Казань", "Уфа"...)
        city = re.split(r'[\s,]+', region)[0].strip()
        if len(city) >= 4 and city in html_lower:
            return {"confirmed": True, "reason": "city", "site": site}

    return {"confirmed": False, "reason": "not_found", "site": site}


# ---------------------------------------------------------------------------
# Perplexity: реальный бренд + официальный сайт
# ---------------------------------------------------------------------------

def find_company_site(lead: dict) -> tuple[str | None, str | None]:
    """Через Perplexity найти реальный бренд и официальный сайт компании.

    Важно для случаев «ООО Альтернатива = бренд BONTIER».
    Возвращает (brand_name, site_url). Оба могут быть None при ошибке/отсутствии.
    """
    try:
        from pplx_client import pplx_search
    except ImportError:
        return None, None

    name = lead.get("name", "")
    inn = lead.get("inn") or ""
    region = lead.get("region") or ""
    q = (
        f"Найди официальный сайт и бренд компании {name} (ИНН {inn}, {region}). "
        "Компания производит хлебобулочные/кондитерские изделия. "
        "Дай: 1) официальный сайт (URL); 2) коммерческое название бренда (если отличается от юрлица). "
        "Только факты, кратко."
    )
    try:
        text, _citations = pplx_search(q, max_tokens=300, timeout=60)
    except Exception:
        return None, None

    if not text:
        return None, None

    # Извлечь URL
    site = None
    sm = re.search(r"https?://[a-z0-9.\-]+\.[a-z]{2,6}(?:/[^\s\"'<>]*)?", text, re.I)
    if sm:
        site = sm.group(0).rstrip(".,;)")
        # Отбросить агрегаторы
        if any(skip in site.lower() for skip in ("zachestny", "kontur.", "rusprofile.", "egrul")):
            site = None

    # Попытка извлечь бренд (слово/словосочетание в кавычках рядом с "бренд"/"марка")
    brand = None
    bm = re.search(r'(?:бренд|марка|торговая марка)[:\s]+[«"]?([A-Za-zА-Яа-я0-9 \-]{2,40})[»"]?', text, re.I)
    if bm:
        brand = bm.group(1).strip()

    return brand, site


def _find_emails_via_pplx(lead: dict, banned: set[str]) -> tuple[str | None, str | None]:
    """Perplexity: email отдела закупок + сайт. Возвращает (email, site)."""
    try:
        from pplx_client import pplx_search
    except ImportError:
        return None, None

    name = lead.get("name", "")
    inn = lead.get("inn") or ""
    region = lead.get("region") or ""
    q = (
        f"Найди рабочий email отдела закупок или для деловых обращений компании "
        f"{name} (ИНН {inn}, {region}). Хлебобулочное/кондитерское производство. "
        "Старый адрес мёртвый. Дай: email для B2B и официальный сайт. "
        "Если несколько email — через запятую."
    )
    try:
        text, _citations = pplx_search(q, max_tokens=400, timeout=60)
    except Exception:
        return None, None

    emails = []
    for m in EMAIL_RE.finditer(text or ""):
        e = m.group().lower()
        if e not in emails and e not in banned and not any(x in e for x in SKIP_EMAIL):
            if not re.search(r"\.(png|jpg|svg|gif|webp)$", e):
                emails.append(e)

    site = None
    sm = re.search(r"https?://[a-z0-9.\-]+\.[a-z]{2,6}", text or "", re.I)
    if sm:
        candidate = sm.group(0)
        if not any(skip in candidate.lower() for skip in ("zachestny", "kontur.", "rusprofile.")):
            site = candidate

    return (emails[0] if emails else None), site


# ---------------------------------------------------------------------------
# Ранжирование email по качеству
# ---------------------------------------------------------------------------

def _email_domain(email: str) -> str:
    parts = email.rsplit("@", 1)
    return parts[1] if len(parts) == 2 else ""


def _email_prefix(email: str) -> str:
    return email.split("@")[0].lower()


def rank_emails(
    candidates: list[str],
    corporate_domain: str | None = None,
) -> list[tuple[str, str]]:
    """Ранжировать список email по качеству.

    Уровни (от лучшего к худшему):
      "procurement"  — роль закупок/сбыта на корп. домене
      "corporate"    — любой корп. домен (не freemail)
      "generic"      — info@/office@ на корп. домене
      "freemail"     — @mail.ru/@yandex.ru/etc или неизвестный домен

    corporate_domain: если None — определяется автоматически как не-freemail домен.
    Возвращает список (email, quality) отсортированный по убыванию качества.
    """
    if not candidates:
        return []

    # Определить корп. домен если не задан явно
    if not corporate_domain:
        for e in candidates:
            d = _email_domain(e)
            if d and not any(e.endswith(fd) for fd in FREE_DOMAINS):
                corporate_domain = d
                break

    ranked: list[tuple[str, str, int]] = []
    for e in candidates:
        e = e.strip().lower()
        if not e or "@" not in e:
            continue
        prefix = _email_prefix(e)
        domain = _email_domain(e)
        is_free = any(e.endswith(fd) for fd in FREE_DOMAINS)
        on_corp = (corporate_domain and domain == corporate_domain)

        if on_corp and any(prefix.startswith(p) for p in PROCUREMENT_PREFIXES):
            quality, order = "procurement", 0
        elif on_corp and not any(prefix.startswith(p) for p in GENERIC_PREFIXES):
            quality, order = "corporate", 1
        elif on_corp:
            quality, order = "generic", 2
        elif is_free:
            quality, order = "freemail", 3
        else:
            quality, order = "freemail", 3  # неизвестный домен — как freemail

        ranked.append((e, quality, order))

    ranked.sort(key=lambda x: x[2])
    return [(e, q) for e, q, _ in ranked]


# ---------------------------------------------------------------------------
# MX / A верификация домена
# ---------------------------------------------------------------------------

def verify_email(email: str) -> dict:
    """Проверить, что домен способен принимать почту (MX или A-запись).

    MX-запись — прямое подтверждение. Нет MX → по RFC почта идёт на A.
    Нет ни MX, ни A → домен мёртвый.

    Хук для платного сервиса: если NEVERBOUNCE_API_KEY или ZEROBOUNCE_API_KEY
    в окружении — делегирует туда и возвращает их результат.
    Returns:
        {"ok": bool, "method": "mx"|"a_record"|"external"|"error", "detail": str}
    """
    import os

    if "@" not in email:
        return {"ok": False, "method": "error", "detail": "no @ in email"}

    domain = _email_domain(email)
    if not domain:
        return {"ok": False, "method": "error", "detail": "empty domain"}

    # Хук: платный сервис
    nb_key = os.environ.get("NEVERBOUNCE_API_KEY", "")
    zb_key = os.environ.get("ZEROBOUNCE_API_KEY", "")
    if nb_key:
        return _verify_neverbounce(email, nb_key)
    if zb_key:
        return _verify_zerobounce(email, zb_key)

    # MX-запись через dnspython (предпочтительный путь)
    try:
        import dns.resolver  # type: ignore
        try:
            dns.resolver.resolve(domain, "MX", lifetime=8)
            return {"ok": True, "method": "mx", "detail": f"MX found for {domain}"}
        except dns.resolver.NXDOMAIN:
            return {"ok": False, "method": "mx", "detail": f"domain {domain} does not exist"}
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            pass  # нет MX → пробуем A
        except Exception as e:
            pass  # ошибка резолвера → пробуем A или socket
    except ImportError:
        pass  # dnspython не установлен → socket fallback

    # A-запись через socket (RFC: почта идёт на A если нет MX)
    try:
        socket.setdefaulttimeout(5)
        socket.gethostbyname(domain)
        return {"ok": True, "method": "a_record", "detail": f"A-record found for {domain}"}
    except socket.gaierror:
        return {"ok": False, "method": "a_record", "detail": f"no DNS for {domain}"}
    except Exception as e:
        return {"ok": False, "method": "error", "detail": str(e)}


def _verify_neverbounce(email: str, api_key: str) -> dict:
    """Хук NeverBounce — подключить позже без переписывания вызовов."""
    # TODO: implement when api_key is available
    # POST https://api.neverbounce.com/v4/single/check?email=...&key=...
    return {"ok": True, "method": "external", "detail": "neverbounce stub"}


def _verify_zerobounce(email: str, api_key: str) -> dict:
    """Хук ZeroBounce — подключить позже без переписывания вызовов."""
    # TODO: implement when api_key is available
    return {"ok": True, "method": "external", "detail": "zerobounce stub"}


# ---------------------------------------------------------------------------
# Главная точка входа
# ---------------------------------------------------------------------------

def _research_due(profile: dict, cooldown_days: int = 30) -> bool:
    """True если глубокий ресёрч ещё не проводился или прошло > cooldown_days."""
    try:
        from core import agent_profile as ap
        ts = ap.get(profile, "contact_researched_at")
    except Exception:
        ts = None
    if not ts:
        return True
    try:
        prev = datetime.fromisoformat(str(ts))
        return (datetime.now(timezone.utc) - prev).total_seconds() > cooldown_days * 86400
    except Exception:
        return True


def research_contacts(
    lead: dict,
    *,
    deep: bool = False,
    banned: set[str] | None = None,
    pause_sec: float = 1.0,
) -> dict:
    """Найти лучший email для лида. Единая точка входа для enrich и bounce_recovery.

    Args:
        lead:      лид из Store (с profile)
        deep:      True → Perplexity-ресёрч (для tier S/A); False → только ZCB
        banned:    набор email-адресов, которые нельзя использовать (bounce)
        pause_sec: пауза между HTTP-запросами (вежливость к источникам)

    Returns dict:
        best_email:    лучший email или None
        quality:       "procurement"|"corporate"|"generic"|"freemail"|None
        verified:      True если домен прошёл MX/A проверку
        mx_failed:     True если домен не имеет ни MX ни A
        site:          реальный сайт (из Perplexity или ZCB)
        all_candidates: [(email, quality)] полный отранжированный список
    """
    from core import agent_profile as ap

    profile = lead.get("profile") or {}
    banned = banned or set()
    inn = lead.get("inn") or ""
    result: dict[str, Any] = {
        "best_email": None,
        "quality": None,
        "verified": False,
        "mx_failed": False,
        "site": ap.get(profile, "contact_site") or profile.get("website"),
        "all_candidates": [],
    }

    all_emails: list[str] = []
    # Флаг: подтверждён ли сайт как принадлежащий этой компании
    result["site_confirmed"] = False

    # --- DEEP: Perplexity → реальный сайт бренда ---
    if deep and _research_due(profile):
        _brand, pplx_site = find_company_site(lead)
        time.sleep(pause_sec)

        if pplx_site:
            # Скачиваем один раз — используем и для верификации, и для email
            site_html = _fetch(pplx_site, timeout=15) or ""
            ownership = verify_site_ownership(pplx_site, lead, fetch_html=site_html)
            result["site_ownership"] = ownership

            if ownership["confirmed"]:
                result["site"] = pplx_site
                result["site_confirmed"] = True
                # Email с подтверждённого сайта
                site_emails = _emails_from_html(site_html)
                # Проверяем страницу контактов (второй запрос)
                contact_html = _fetch_contact_page(pplx_site, site_html) or ""
                if contact_html:
                    site_emails.extend(_emails_from_html(contact_html))
                all_emails.extend(e for e in site_emails if e not in all_emails)
                time.sleep(pause_sec)
            else:
                # Сайт не подтверждён — НЕ берём с него email, НЕ принимаем как contact_site
                # Логируем для прозрачности
                result["site_ownership"] = ownership
                # pplx_site НЕ записываем в result["site"]

        # Если подтверждённый сайт не нашёл email — спросить Perplexity напрямую
        if not all_emails:
            pplx_email, pplx_site2 = _find_emails_via_pplx(lead, banned)
            if pplx_email:
                all_emails.append(pplx_email)
            # Второй URL от Perplexity — тоже проверяем
            if pplx_site2 and pplx_site2 != pplx_site and not result["site_confirmed"]:
                ownership2 = verify_site_ownership(pplx_site2, lead)
                if ownership2["confirmed"]:
                    result["site"] = pplx_site2
                    result["site_confirmed"] = True
                    if not all_emails:
                        site_emails2 = emails_from_site(pplx_site2)
                        all_emails.extend(site_emails2)
            time.sleep(pause_sec)

    # --- ZCB (всегда — cheap path) ---
    if inn:
        contacts = enrich_by_inn(inn)
        if contacts:
            if contacts.get("sites") and not result["site"]:
                result["site"] = contacts["sites"][0]
            zcb_emails = [e.lower() for e in (contacts.get("emails") or [])]
            all_emails.extend(e for e in zcb_emails if e not in all_emails)
            # Если ZCB дал сайт, но не дал email — добираем с сайта
            if not zcb_emails and result["site"] and result["site"] not in ("", None):
                site_e = emails_from_site(result["site"])
                all_emails.extend(e for e in site_e if e not in all_emails)
        time.sleep(pause_sec)

    # Также подхватить уже имеющиеся в профиле emails
    existing_raw = str(profile.get("emails") or profile.get("email") or "")
    for e in existing_raw.replace(";", ",").split(","):
        e = e.strip().lower()
        if e and "@" in e and e not in all_emails:
            all_emails.append(e)

    # Убрать banned и мусор
    all_emails = [
        e for e in all_emails
        if e and "@" in e and e not in banned
        and not any(x in e for x in SKIP_EMAIL)
        and not re.search(r"\.(png|jpg|svg|gif|webp|css|js)$", e)
        and len(e) <= 80
    ]

    if not all_emails:
        return result

    # --- Ранжирование ---
    corp_domain = None
    if result["site"]:
        m = re.match(r"https?://(?:www\.)?([^/]+)", result["site"])
        if m:
            corp_domain = m.group(1).lower().lstrip("www.")

    ranked = rank_emails(all_emails, corporate_domain=corp_domain)
    result["all_candidates"] = ranked

    if not ranked:
        return result

    best_email, best_quality = ranked[0]

    # --- MX / A верификация ---
    vr = verify_email(best_email)
    result["verified"] = vr["ok"]
    result["mx_failed"] = not vr["ok"]

    if vr["ok"]:
        result["best_email"] = best_email
        result["quality"] = best_quality
    else:
        # Домен мёртвый — попробуем следующий по рангу
        for e, q in ranked[1:]:
            vr2 = verify_email(e)
            if vr2["ok"]:
                result["best_email"] = e
                result["quality"] = q
                result["verified"] = True
                result["mx_failed"] = False
                break
        # Если ни один не прошёл — best_email остаётся None, mx_failed=True

    return result


def apply_research_to_lead(
    lead: dict,
    research: dict,
    *,
    store=None,
    deep: bool = False,
) -> None:
    """Записать результат research_contacts в profile._agent и обновить лид в Store."""
    from core import agent_profile as ap

    profile = dict(lead.get("profile") or {})

    ap.update(profile,
        email_best=research.get("best_email"),
        email_quality=research.get("quality"),
        email_verified=research.get("verified", False),
        email_mx_failed=research.get("mx_failed", False),
        site_confirmed=research.get("site_confirmed", False),
    )
    # Записываем contact_site только если сайт прошёл верификацию принадлежности
    if research.get("site") and research.get("site_confirmed"):
        ap.set(profile, "contact_site", research["site"])
    if deep:
        ap.set(profile, "contact_researched_at", _now())

    # Поставить лучший email первым в profile.emails (pick_recipient возьмёт автоматически)
    best = research.get("best_email")
    if best:
        existing = [
            e.strip().lower()
            for e in str(profile.get("emails") or "").replace(";", ",").split(",")
            if e.strip() and "@" in e
        ]
        if best in existing:
            existing.remove(best)
        profile["emails"] = ",".join([best] + existing)

    # website в профиле обновляем только из подтверждённого источника
    if research.get("site") and research.get("site_confirmed") and not profile.get("website"):
        profile["website"] = research["site"]

    if store:
        store.upsert_lead(
            lead["name"], lead_id=lead["id"], inn=lead.get("inn"),
            region=lead.get("region"), tier=lead.get("tier"),
            fit_score=lead.get("fit_score") or 0,
            status=lead.get("status"), source=lead.get("source"),
            profile=profile,
        )
