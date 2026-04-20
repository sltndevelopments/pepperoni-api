"""
scan_sausage_in_dough.py — проверяет, выпускает ли компания сосиски в тесте /
                           хот-доги / пирожки с мясной начинкой.

Идея:
  1. Берём топ-N из bakery-leads-okved-enriched.csv.
  2. Находим сайт: либо из колонки `sites`, либо из домена корпоративного email.
  3. Скачиваем homepage + ищем ссылки на каталог/продукцию/ассортимент/меню.
  4. Скачиваем найденные каталожные страницы (до 6 на сайт).
  5. Ищем вхождения ключевых слов:
       - сосис(ка|ки) — main signal
       - хот[-\\s]?дог
       - колбаск.* (в паре с тест|слоён|выпечк|пирож)
       - пирож(ок|ки)? с сосис
       - «домашний обед/завтрак» блок со словом сосиск
  6. Пишет CSV с evidence snippet + URL.

Flags:
  --top N              (default 150)
  --timeout SEC        (default 12)
  --sleep SEC          (default 0.6)

Output: data/bakery-leads-sausage-tested.csv
"""
from __future__ import annotations

import argparse
import csv
import html
import re
import socket
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "bakery-leads-okved-enriched.csv"
OUT = ROOT / "data" / "bakery-leads-sausage-tested.csv"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15")

# ===== Keywords =====
# Evidence patterns. Order matters (strongest first).
PATTERNS = [
    ("sausage_in_dough", re.compile(r"сосис[а-я]*\s+в\s+тесте", re.I)),
    ("sausage_pastry",   re.compile(r"(?:слоён[а-я]*|слоен[а-я]*|выпеч[а-я]*|пирож[а-я]*|булоч[а-я]*|круассан[а-я]*)\s*[:,—\-]?\s*(?:с\s+)?сосиск[а-я]+", re.I)),
    ("piroshki_sausage", re.compile(r"пирож[а-я]*\s+с\s+(?:сосис|колбас|мяс[а-я]*\s+(?:и|с))", re.I)),
    ("hot_dog",          re.compile(r"хот[\-\s]?дог", re.I)),
    ("kolbaska_pastry",  re.compile(r"колбаск[а-я]*\s+в\s+(?:тест|слоён|сдоб)", re.I)),
    ("sausage_generic",  re.compile(r"\bсосиск[а-я]+\b", re.I)),
    ("meat_pastry",      re.compile(r"(?:пирож[а-я]*|слойк[а-я]*|булоч[а-я]*|самс[а-я]*|беляш[а-я]*|чебурек[а-я]*)\s+с\s+(?:мяс[а-я]*|говядин|курицей|курин)", re.I)),
]

# Hints for catalog/menu pages — both Cyrillic AND Latin (most RU bakery sites
# run on Bitrix/WordPress with English URL slugs: /catalog/, /product/, /menu/).
CATALOG_HINT_RE = re.compile(
    r"(?:"
    r"продукц|каталог|ассорт|меню|товары|выпечк|издели|продукт|"
    r"хлеб|пирог|булочн|сосиск|сдоб|бутерброд|наш[ие]|производ|пицц|"
    r"catalog|product|menu|assort|goods|item|bakery|bread|snack|"
    r"nasha|nashi|proizv|produkt|assortiment|vypechka|pirog|hleb|bulo"
    r")",
    re.I)

# Domains we skip when extracting a website
BAD_DOMAINS = (
    "mail.ru", "yandex.ru", "ya.ru", "gmail.com", "list.ru", "bk.ru",
    "inbox.ru", "rambler.ru", "internet.ru", "mail.com",
    "vk.com", "ok.ru", "facebook.com", "instagram.com", "t.me", "youtube.com",
    "youtu.be", "twitter.com", "x.com", "zen.yandex",
    "hh.ru", "superjob.ru", "avito.ru",
    "2gis.ru", "spark-interfax",
)


def _norm_domain(d: str) -> str:
    d = d.strip().lower().rstrip("/")
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0]


def pick_website(site_field: str, emails_field: str) -> str | None:
    # 1. try sites column
    for s in (site_field or "").split(","):
        s = s.strip()
        if not s:
            continue
        d = _norm_domain(s)
        if any(d.endswith(b) or d == b for b in BAD_DOMAINS):
            continue
        if d and "." in d:
            return "http://" + d
    # 2. try email corporate domain
    for e in (emails_field or "").split(","):
        e = e.strip().lower()
        if "@" in e:
            d = e.split("@", 1)[1]
            if not any(d.endswith(b) or d == b for b in BAD_DOMAINS):
                if "." in d:
                    return "http://" + d
    return None


def fetch(url: str, timeout: int = 12) -> tuple[int, str, str]:
    """Return (status, final_url, body). status=0 on connect error."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(2_000_000)  # cap 2 MB
            charset = r.headers.get_content_charset() or "utf-8"
            try:
                body = raw.decode(charset, "ignore")
            except LookupError:
                body = raw.decode("utf-8", "ignore")
            return r.status, r.geturl(), body
    except (urllib.error.HTTPError, urllib.error.URLError,
            socket.timeout, ConnectionResetError, UnicodeDecodeError) as e:
        return 0, url, ""
    except Exception:
        return 0, url, ""


STRIP_SCRIPT = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")


def html_to_text(body: str) -> str:
    body = STRIP_SCRIPT.sub(" ", body)
    body = TAG_RE.sub(" ", body)
    body = html.unescape(body)
    body = re.sub(r"\s+", " ", body)
    return body


HREF_RE = re.compile(r'href=["\']([^"\']{1,300})["\']', re.I)


def find_catalog_links(body: str, base_url: str, base_domain: str) -> list[str]:
    found = []
    seen = set()
    for m in HREF_RE.finditer(body):
        raw = m.group(1).strip()
        if not raw or raw.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urllib.parse.urljoin(base_url, raw)
        try:
            parsed = urllib.parse.urlparse(absolute)
        except ValueError:
            continue
        if parsed.scheme not in ("http", "https"):
            continue
        if _norm_domain(parsed.netloc) != base_domain:
            continue
        # skip anchors/assets
        if re.search(r"\.(jpg|jpeg|png|gif|svg|webp|pdf|doc|docx|xls|xlsx|zip|rar|mp4|mp3)(\?|$)", absolute, re.I):
            continue
        # must look like a catalog link
        slug = (parsed.path + " " + (parsed.query or "")).lower()
        if not CATALOG_HINT_RE.search(slug):
            continue
        # de-dupe
        key = absolute.split("#")[0]
        if key in seen:
            continue
        seen.add(key)
        found.append(key)
        if len(found) >= 15:
            break
    return found


def find_evidence(text: str, name: str) -> tuple[str, str, dict]:
    """Return (best_label, snippet, counts_per_pattern)."""
    counts = {k: 0 for k, _ in PATTERNS}
    best_label = ""
    best_snippet = ""
    for label, pat in PATTERNS:
        for m in pat.finditer(text):
            counts[label] += 1
            if not best_label:
                best_label = label
                start = max(0, m.start() - 60)
                end = min(len(text), m.end() + 80)
                snippet = text[start:end].strip()
                snippet = re.sub(r"\s+", " ", snippet)
                best_snippet = snippet
            if counts[label] > 4:
                break
    return best_label, best_snippet, counts


def scan_site(website: str, timeout: int, sleep: float) -> dict:
    """Return dict with: website, pages_checked, evidence_label, evidence_url, snippet, counts."""
    out = {
        "website_checked": website,
        "pages_checked": 0,
        "evidence_label": "",
        "evidence_url": "",
        "evidence_snippet": "",
        "counts": {k: 0 for k, _ in PATTERNS},
        "status": "",
    }
    status, final_url, body = fetch(website, timeout)
    if status == 0 or not body:
        # Try https as fallback
        if website.startswith("http://"):
            status, final_url, body = fetch("https://" + website[len("http://"):], timeout)
        if status == 0 or not body:
            out["status"] = "unreachable"
            return out
    out["status"] = f"ok http={status}"
    base_domain = _norm_domain(urllib.parse.urlparse(final_url).netloc)
    pages = [(final_url, body)]

    # Check homepage first
    text = html_to_text(body)
    label, snippet, counts = find_evidence(text, website)
    for k, v in counts.items():
        out["counts"][k] += v
    if label and not out["evidence_label"]:
        out["evidence_label"] = label
        out["evidence_url"] = final_url
        out["evidence_snippet"] = snippet[:240]
    out["pages_checked"] = 1

    # Crawl catalog links (up to 12 — bakery Bitrix sites often have many /catalog/N/)
    cat_links = find_catalog_links(body, final_url, base_domain)
    for link in cat_links[:12]:
        time.sleep(sleep)
        s, fu, b = fetch(link, timeout)
        if s == 0 or not b:
            continue
        out["pages_checked"] += 1
        text = html_to_text(b)
        label, snippet, counts = find_evidence(text, website)
        for k, v in counts.items():
            out["counts"][k] += v
        if label and not out["evidence_label"]:
            out["evidence_label"] = label
            out["evidence_url"] = fu
            out["evidence_snippet"] = snippet[:240]
    return out


def classify(counts: dict, label: str) -> str:
    """Return: yes_sausage / yes_related / maybe / no."""
    if counts.get("sausage_in_dough", 0) >= 1 or counts.get("sausage_pastry", 0) >= 1:
        return "yes_sausage_in_dough"
    if counts.get("piroshki_sausage", 0) >= 1 or counts.get("hot_dog", 0) >= 1:
        return "yes_hotdog_or_meat_pirozhki"
    if counts.get("kolbaska_pastry", 0) >= 1:
        return "yes_kolbaska_pastry"
    if counts.get("sausage_generic", 0) >= 1:
        return "mention_only"
    if counts.get("meat_pastry", 0) >= 1:
        return "meat_pastries_only"
    return "no"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=150)
    ap.add_argument("--timeout", type=int, default=12)
    ap.add_argument("--sleep", type=float, default=0.6)
    ap.add_argument("--resume", action="store_true",
                    help="Skip INNs already present in output CSV")
    args = ap.parse_args()

    rows = list(csv.DictReader(SRC.open()))[: args.top]
    print(f"Анализируем {len(rows)} компаний")

    done_inn = set()
    if args.resume and OUT.exists():
        for r in csv.DictReader(OUT.open()):
            if r.get("status"):
                done_inn.add(r["inn"])
        print(f"Resume: пропустим {len(done_inn)} уже сделанных")

    fields = list(rows[0].keys()) + [
        "website_checked", "pages_checked", "status",
        "classification", "evidence_label",
        "evidence_url", "evidence_snippet",
        "cnt_sausage_in_dough", "cnt_sausage_pastry",
        "cnt_piroshki_sausage", "cnt_hot_dog",
        "cnt_kolbaska_pastry", "cnt_sausage_generic", "cnt_meat_pastry",
    ]

    # Re-read previous results to preserve them
    existing = {}
    if args.resume and OUT.exists():
        for r in csv.DictReader(OUT.open()):
            existing[r["inn"]] = r

    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            inn = r["inn"]
            base = {k: r.get(k, "") for k in r.keys()}
            if inn in existing:
                w.writerow({**base, **{k: existing[inn].get(k, "") for k in fields if k not in base}})
                continue

            website = pick_website(r.get("sites", ""), r.get("emails", ""))
            if not website:
                row_out = {**base,
                           "website_checked": "", "pages_checked": 0,
                           "status": "no_website",
                           "classification": "unknown",
                           "evidence_label": "", "evidence_url": "", "evidence_snippet": "",
                           "cnt_sausage_in_dough": 0, "cnt_sausage_pastry": 0,
                           "cnt_piroshki_sausage": 0, "cnt_hot_dog": 0,
                           "cnt_kolbaska_pastry": 0, "cnt_sausage_generic": 0,
                           "cnt_meat_pastry": 0}
                w.writerow(row_out)
                f.flush()
                print(f"[{i:>3}/{len(rows)}] - {r['name_short'][:42]:<42}  no website")
                continue

            t0 = time.time()
            res = scan_site(website, args.timeout, args.sleep)
            klass = classify(res["counts"], res["evidence_label"])
            dt = time.time() - t0

            row_out = {**base,
                       "website_checked": res["website_checked"],
                       "pages_checked": res["pages_checked"],
                       "status": res["status"],
                       "classification": klass,
                       "evidence_label": res["evidence_label"],
                       "evidence_url": res["evidence_url"],
                       "evidence_snippet": res["evidence_snippet"],
                       "cnt_sausage_in_dough": res["counts"]["sausage_in_dough"],
                       "cnt_sausage_pastry":  res["counts"]["sausage_pastry"],
                       "cnt_piroshki_sausage": res["counts"]["piroshki_sausage"],
                       "cnt_hot_dog":         res["counts"]["hot_dog"],
                       "cnt_kolbaska_pastry": res["counts"]["kolbaska_pastry"],
                       "cnt_sausage_generic": res["counts"]["sausage_generic"],
                       "cnt_meat_pastry":     res["counts"]["meat_pastry"]}
            w.writerow(row_out)
            f.flush()
            mark = {"yes_sausage_in_dough": "★",
                    "yes_hotdog_or_meat_pirozhki": "✓",
                    "yes_kolbaska_pastry": "✓",
                    "mention_only": "·",
                    "meat_pastries_only": "·",
                    "no": " ",
                    "unknown": "?"}[klass]
            print(f"[{i:>3}/{len(rows)}] {mark} {r['name_short'][:38]:<38} "
                  f"pp={res['pages_checked']:>2}  klass={klass:<24}  "
                  f"({dt:.1f}s) {res['website_checked'][:40]}")
            time.sleep(args.sleep)

    print(f"\n✓ Output: {OUT}")


if __name__ == "__main__":
    sys.exit(main() or 0)
