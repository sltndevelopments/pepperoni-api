"""
fetch_fns.py — batch search of active legal entities via ФНС egrul.nalog.ru
                with pagination to get all hits (not just first 20).

Output: sales-intel/raw/fns_raw.jsonl
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://egrul.nalog.ru"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15")
OUT = Path(__file__).resolve().parent.parent / "raw" / "fns_raw.jsonl"
OUT.parent.mkdir(parents=True, exist_ok=True)

PAGE_SIZE = 20              # ФНС hard limit
MAX_PAGES_PER_QUERY = 10    # safety cap (= 200 hits per query × region)
SLEEP_BETWEEN = 0.25

# Региональные коды ФНС.
REGIONS = {
    "16": "Татарстан",
    "02": "Башкортостан",
    "12": "Марий Эл",
    "18": "Удмуртия",
    "21": "Чувашия",
    "30": "Астраханская",
    "77": "Москва",
    "50": "Московская обл",
    "78": "Санкт-Петербург",
    "47": "Ленинградская обл",
    "63": "Самарская",
    "52": "Нижегородская",
    "59": "Пермский край",
    "66": "Свердловская",
    "74": "Челябинская",
    "56": "Оренбургская",
    "43": "Кировская",
    "73": "Ульяновская",
    "64": "Саратовская",
    "34": "Волгоградская",
    "61": "Ростовская",
    "23": "Краснодарский",
    "26": "Ставропольский",
    "05": "Дагестан",
    "07": "Кабардино-Балкария",
    "20": "Чечня",
    "15": "Северная Осетия",
    "09": "Карачаево-Черкесия",
    "06": "Ингушетия",
    "54": "Новосибирская",
    "22": "Алтайский край",
    "70": "Томская",
    "55": "Омская",
    "24": "Красноярский",
    "72": "Тюменская",
}

# Focused query set — terms that appear in names of bakery / meat / frozen-foods producers.
QUERIES = [
    "хлебозавод",       # classic bakery factory
    "хлебокомбинат",    # bread + pastry combine
    "пекарня",          # bakery / bakehouse
    "булочн",           # bun / roll producer
    "кондитер",         # confectionery
    "слоён",            # flaky-dough
    "пирожк",           # pastry / piroshki
    "выпечк",           # "vypechka" (baked goods)
    "бейкери",          # modern "bakery" transliterated
    "бейкер",           # modern "baker"
    "заморож",          # frozen food producer
    "полуфабрикат",     # semi-finished product
    "хот-дог",          # hot dog
    "хотдог",           # hotdog
    "сосиска",          # sausage
    "чебуреч",          # cheburek
    "мясокомбинат",     # meat combine
    "колбасн",          # sausage / kolbasa
    "мясопереработ",    # meat processing
]


def _post(path, data, timeout=20):
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=body, method="POST",
        headers={
            "User-Agent": UA,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _get(path, timeout=20):
    req = urllib.request.Request(
        BASE + path,
        headers={
            "User-Agent": UA,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def search_page(query, region, page):
    """Fetch one page of ФНС results. Returns (rows, total_hits_in_query)."""
    try:
        res = _post("/", {
            "query": query,
            "region": region,
            "vyp3CaptchaToken": "",
            "page": str(page) if page > 1 else "",
            "PreventChromeAutocomplete": "",
        })
        if res.get("captchaRequired"):
            return [], None  # signal captcha
        token = res.get("t")
        if not token:
            return [], 0
    except Exception as e:
        print(f"    ! POST error q={query!r} reg={region} p={page}: {e}")
        return [], 0

    for attempt in range(4):
        time.sleep(0.3 + attempt * 0.4)
        try:
            res = _get(f"/search-result/{token}")
        except Exception as e:
            print(f"    ! GET attempt {attempt}: {e}")
            continue
        rows = res.get("rows")
        if rows is not None:
            total = 0
            if rows:
                total = int(rows[0].get("tot", len(rows)) or len(rows))
            return rows, total
    return [], 0


def search(query, region):
    """Paginate until all hits collected or MAX_PAGES reached."""
    all_rows = []
    page = 1
    total = None
    while page <= MAX_PAGES_PER_QUERY:
        rows, tot = search_page(query, region, page)
        if tot is None:
            print(f"    ⚠️  captcha for q={query!r} reg={region} — stopping this query")
            break
        if not rows:
            break
        all_rows.extend(rows)
        if total is None:
            total = tot
        if len(all_rows) >= total or len(rows) < PAGE_SIZE:
            break
        page += 1
        time.sleep(SLEEP_BETWEEN)
    return all_rows, total or 0


def main():
    seen: dict[str, dict] = {}
    total_tasks = len(QUERIES) * len(REGIONS)
    captcha_stops = 0
    done = 0

    for q in QUERIES:
        for region, region_name in REGIONS.items():
            done += 1
            t0 = time.time()
            rows, total = search(q, region)
            if total and total > 200:
                note = f" ⚠ total={total} truncated at 200"
            else:
                note = ""

            active = [r for r in rows if not r.get("e")]
            new = 0
            for r in active:
                inn = r.get("i")
                if not inn or inn in seen:
                    continue
                seen[inn] = {
                    "inn": inn,
                    "ogrn": r.get("o"),
                    "kpp": r.get("p"),
                    "name_short": r.get("c"),
                    "name_full": r.get("n"),
                    "director": r.get("g"),
                    "registered": r.get("r"),
                    "region_code": region,
                    "region_name": r.get("rn") or region_name,
                    "kind": r.get("k"),
                    "found_by_query": q,
                }
                new += 1

            dt = time.time() - t0
            print(f"[{done:>4}/{total_tasks}] q={q!r:<18} reg={region_name:<20} "
                  f"got={len(rows):>3} active={len(active):>3} new={new:>3}"
                  f" ({dt:>4.1f}s){note}")
            time.sleep(SLEEP_BETWEEN)

    with OUT.open("w") as f:
        for e in seen.values():
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print()
    print(f"✓ Unique active legal entities: {len(seen)}")
    print(f"✓ Captcha stops: {captcha_stops}")
    print(f"✓ Saved: {OUT}")


if __name__ == "__main__":
    main()
