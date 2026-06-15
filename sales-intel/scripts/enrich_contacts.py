"""
enrich_contacts.py — pull contact info (telephone + email + ref domain)
                     for TOP-N scored leads from zachestnyibiznes.ru.

Usage:  python3 scripts/enrich_contacts.py TOP_N=60
Reads:  data/bakery-leads.csv  (sorted by score desc)
Writes: data/bakery-leads-enriched.csv   (same rows + phones/emails/site)

Source: zachestnyibiznes.ru — public, renders partial data server-side.
        Fetches /search?query={INN} → extract link → fetch company page → regex extract.
"""
from __future__ import annotations

import csv
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "data" / "bakery-leads.csv"
OUT = ROOT / "data" / "bakery-leads-enriched.csv"


def _resolve_paths(argv):
    """Allow IN=/OUT= args to override input/output CSV (for BO-based runs)."""
    global IN, OUT
    for a in argv:
        if a.startswith("IN="):
            IN = Path(a.split("=", 1)[1]).resolve()
        elif a.startswith("OUT="):
            OUT = Path(a.split("=", 1)[1]).resolve()

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15")
ZCB = "https://zachestnyibiznes.ru"


def fetch(url: str, timeout: int = 25) -> str | None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
            "Accept-Language": "ru,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data.decode("utf-8", "ignore")
    except Exception as e:
        return None


def find_company_link(search_html: str) -> str | None:
    m = re.search(r'<a[^>]+href="(/company/ul/[^"]+)"', search_html)
    if m:
        return m.group(1)
    m = re.search(r'<a[^>]+href="(/company/ip/[^"]+)"', search_html)
    if m:
        return m.group(1)
    return None


PHONE_RE = re.compile(r"\+7[\s\(\)\-\d]{10,18}")
EMAIL_RE = re.compile(r"[\w.\-+]{2,30}@[\w\-]+\.[a-z]{2,6}")
URL_RE = re.compile(r'https?://[a-z0-9\-\.]+\.(?:ru|com|org|net|xyz|su|bz)\b[^"\' <>]*')

SKIP_URL = ("zachestny", "yandex", "google", "mc.yandex", "top.mail", "disqus", "cloudflare",
            "fontawesome", "gstatic", "cdnjs", "jsdelivr", "unpkg", "ya.ru", "fb.com", "vk.com",
            "facebook.com", "telegram", "instagram", "vkontakte", "twitter", "linkedin",
            "apple.com", "microsoft", "w3.org", "schema.org", "mail.ru", "rambler.",
            "bitrix", "gosuslugi.ru", "nalog.gov.ru", "nalog.ru", "egrul", "fas.gov.ru",
            "rospatent", "kontur.", "checko.", "rusprofile.", "synapsenet.", "audit-it.",
            "reestr.digital.gov.ru", "digital.gov.ru", "rkn.gov.ru", "roskomnadzor",
            "gov.ru/reestr", "gosreestr", "ftstat", "statgosuslug", ".jpg", ".png",
            ".svg", ".css", ".ico", ".webp", ".gif")


def parse_company(html: str) -> dict:
    phones = []
    emails = []
    sites = []

    # Phones — limit per-phone dedup by digits
    seen_phone = set()
    for m in PHONE_RE.finditer(html):
        p = re.sub(r"\D", "", m.group())
        if 11 <= len(p) <= 12 and p not in seen_phone:
            seen_phone.add(p)
            phones.append(m.group().strip())
        if len(phones) >= 4:
            break

    for m in EMAIL_RE.finditer(html):
        e = m.group().lower()
        if e not in emails and len(e) <= 60 and not any(x in e for x in ("noreply", "test@", "@yandex.ru0", "@example")):
            emails.append(e)
        if len(emails) >= 3:
            break

    # Websites
    for m in URL_RE.finditer(html):
        url = m.group().rstrip(".,;)")
        low = url.lower()
        if any(skip in low for skip in SKIP_URL):
            continue
        if url in sites:
            continue
        sites.append(url)
        if len(sites) >= 3:
            break

    return {"phones": ",".join(phones),
            "emails": ",".join(emails),
            "sites": ",".join(sites)}


def enrich(
    in_path: Path | str | None = None,
    out_path: Path | str | None = None,
    top_n: int = 80,
) -> dict:
    """Programmatic entry point — вызывается из feed_agent.py без sys.argv."""
    src = Path(in_path) if in_path else IN
    dst = Path(out_path) if out_path else OUT

    if not src.exists():
        return {"error": f"file not found: {src}", "enriched": 0, "skipped": 0}

    rows = list(csv.DictReader(src.open(encoding="utf-8-sig")))
    if not rows:
        return {"error": "empty input", "enriched": 0, "skipped": 0}

    to_enrich = rows[:top_n]
    print(f"[enrich] {len(rows)} leads, enriching top {top_n}…")

    # Resume support
    already: dict[str, dict] = {}
    if dst.exists():
        for r in csv.DictReader(dst.open(encoding="utf-8-sig")):
            already[r.get("inn", "")] = r
        print(f"[enrich] resuming — {len(already)} already done")

    fieldnames = list(rows[0].keys())
    for f in ("phones", "emails", "sites", "enriched_at"):
        if f not in fieldnames:
            fieldnames.append(f)

    enriched_n = 0
    skipped_n = 0

    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as out_f:
        w = csv.DictWriter(out_f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()

        for i, r in enumerate(to_enrich, 1):
            inn = r.get("inn", "")
            if inn in already and already[inn].get("phones"):
                w.writerow(already[inn])
                skipped_n += 1
                continue

            t0 = time.time()
            search_url = f"{ZCB}/search?query={urllib.parse.quote(inn)}"
            shtml = fetch(search_url, timeout=15)
            contacts = {"phones": "", "emails": "", "sites": ""}
            if shtml:
                link = find_company_link(shtml)
                if link:
                    time.sleep(0.5)
                    chtml = fetch(ZCB + link, timeout=30)
                    if chtml:
                        contacts = parse_company(chtml)

            dt = time.time() - t0
            out_row = {**r, **contacts, "enriched_at": time.strftime("%Y-%m-%d")}
            w.writerow(out_row)
            out_f.flush()

            found = "✓" if (contacts["phones"] or contacts["emails"]) else "·"
            print(f"[enrich {i:>3}/{top_n}] {found} {r.get('name_short','')[:40]:<40} "
                  f"ph={contacts['phones'].count(',')+1 if contacts['phones'] else 0} "
                  f"em={contacts['emails'].count(',')+1 if contacts['emails'] else 0} "
                  f"({dt:.1f}s)")
            enriched_n += 1
            time.sleep(1.0)

        for r in rows[top_n:]:
            w.writerow({**r, "phones": "", "emails": "", "sites": "", "enriched_at": ""})

    print(f"[enrich] ✓ {dst}")
    return {"enriched": enriched_n, "skipped": skipped_n, "out": str(dst)}


def main():
    _resolve_paths(sys.argv[1:])
    top_n = 80
    for a in sys.argv[1:]:
        if a.startswith("TOP_N="):
            top_n = int(a.split("=", 1)[1])
    result = enrich(IN, OUT, top_n)
    print(result)


if __name__ == "__main__":
    main()
