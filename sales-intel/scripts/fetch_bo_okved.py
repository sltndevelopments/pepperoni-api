"""
fetch_bo_okved.py — pull organisations by ОКВЭД from ГИР БО (bo.nalog.gov.ru).

Why not ФНС ЕГРЮЛ search? — there is no way to filter by ОКВЭД there; the public
search on egrul.nalog.ru matches words in the company *name* only, which misses
companies whose name does not contain "хлеб/пекарня/булочная" (e.g. ООО
Альтернатива с брендом BONTIER). ГИР БО индексирует ОКВЭД2 + публикует выручку,
так что это единственный открытый источник, который решает обе задачи.

Поля ответа:
    shortName, inn, ogrn, region, street, house, okved2, statusCode,
    bfo.period, bfo.gainSum (выручка в тыс.руб)

Output: sales-intel/raw/bo_okved_raw.jsonl   (one org per line)

Periods & merge:
    Default — 2024 и 2025; для каждой компании выбирается запись с наибольшим
    gainSum (обычно — последний отчётный год). Так мы не теряем ни тех, кто
    подал 2025 раньше, ни тех, у кого пока только 2024.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://bo.nalog.gov.ru"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "raw" / "bo_okved_raw.jsonl"
OUT.parent.mkdir(parents=True, exist_ok=True)

# ОКВЭД2 коды = цель:
#   10.71 — производство хлеба и мучных кондитерских изделий недлительного
#           хранения (пекарни, комбинаты, сети собственных точек).
#   10.72 — производство сухарей, печенья, прочих мучных кондитерских
#           длительного хранения (промышленные производители выпечки).
#   10.85 — производство готовых блюд и полуфабрикатов (прямое попадание
#           под сосиску в тесте / замороженную выпечку / кулинарию).
#   56.10 — деятельность ресторанов и услуги по доставке питания
#           (тёмные кухни, кейтеринг, фудкорты — розничный канал).
#   56.29 — деятельность столовых и прочего питания (корпоративные кейтеры,
#           производственные столовые, сети доставки готовой еды).
#   47.11 — розничная торговля в неспециализированных магазинах с
#           преобладанием продуктов питания (только крупные сети, высокий
#           порог выручки — иначе утонем в ИП-магазинах).
#
# Лимит страниц на «большие» ОКВЭД — защита от переполнения:
#   10.71/10.72/10.85 — без лимита (компаний немного, качество высокое)
#   56.10/56.29/47.11 — MAX_SEGMENT_PAGES страниц (защита от тысяч мелочей)
OKVEDS = ["10.71", "10.72", "10.85", "56.10", "56.29", "47.11"]

# Потолок страниц для «объёмных» ОКВЭД — берём только топ по выручке
# (bo.nalog.gov.ru сортирует по убыванию gainSum внутри страниц)
# None = без лимита. Переопределяется через KD_FEED_MAX_PAGES (глобально)
# или KD_FEED_MAX_PAGES_<OKVED> (per-OKVED, например KD_FEED_MAX_PAGES_4711=2)
_SEGMENT_PAGE_LIMITS: dict[str, int | None] = {
    "10.71": None,
    "10.72": None,
    "10.85": None,
    "56.10": 3,    # ≤6000 компаний, берём топ по выручке
    "56.29": 3,
    "47.11": 2,    # очень объёмный ОКВЭД — берём только топ-4000
}

PERIODS = ["2025", "2024"]  # сначала свежий; потом добираем тех, у кого ещё нет 2025
PAGE_SIZE = 2000  # сервер молча обрезает до 2000
SLEEP_BETWEEN = 0.3

# Env KD_FEED_MAX_PAGES=1 позволяет feed_agent ограничить прогон для теста.
import os as _os
MAX_PAGES = int(_os.environ.get("KD_FEED_MAX_PAGES", "0")) or None  # None = без лимита


# Транзиентные сетевые сбои (DNS/timeout/сброс соединения) — ретраить.
# HTTP 4xx/5xx от сервера — реальная ошибка, ретрай бессмысленен.
_RETRY_BACKOFF_SEC = (5, 15, 30)


def _get_json(path: str, params: dict) -> dict:
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru,en;q=0.9",
            "Referer": BASE + "/",
        },
    )
    last_err: Exception | None = None
    for attempt, backoff in enumerate((0, *_RETRY_BACKOFF_SEC)):
        if backoff:
            time.sleep(backoff)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError:
            raise  # реальный ответ сервера (4xx/5xx) — не ретраим
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            print(f"  [retry {attempt + 1}/{len(_RETRY_BACKOFF_SEC) + 1}] "
                  f"transient error: {e}", file=sys.stderr)
    raise last_err  # type: ignore[misc]


def fetch_page(okved: str, period: str, page: int) -> dict:
    params = {
        "okved": okved,
        "period": period,
        "page": str(page),
        "size": str(PAGE_SIZE),
        "allFieldsMatch": "false",
    }
    return _get_json("/advanced-search/organizations", params)


STRIP_TAGS = re.compile(r"<[^>]+>")


def clean(val):
    if isinstance(val, str):
        return STRIP_TAGS.sub("", val).strip()
    return val


def flatten_address(row: dict) -> str:
    parts = [
        row.get("region"), row.get("district"), row.get("city"),
        row.get("settlement"), row.get("street"),
        (f"д.{row['house']}" if row.get("house") else None),
        (f"к.{row['building']}" if row.get("building") else None),
        (f"оф.{row['office']}" if row.get("office") else None),
    ]
    return ", ".join(p for p in (clean(x) for x in parts) if p)


def normalize(row: dict) -> dict:
    bfo = row.get("bfo") or {}
    return {
        "inn": clean(row.get("inn")),
        "ogrn": clean(row.get("ogrn")),
        "name_short": clean(row.get("shortName")),
        "region_name": clean(row.get("region")) or "",
        "city": clean(row.get("city")) or clean(row.get("settlement")) or "",
        "address": flatten_address(row),
        "okved2": clean(row.get("okved2")) or "",
        "okopf": row.get("okopf"),
        "status_code": row.get("statusCode"),
        "status_date": row.get("statusDate"),
        "bfo_period": bfo.get("period"),
        "bfo_actual_date": bfo.get("actualBfoDate"),
        # gainSum = выручка (строка 2110 ОФР) в тыс. рублей
        "revenue_tsd_rub": bfo.get("gainSum"),
    }


def _max_pages_for(okved: str) -> int | None:
    """Эффективный лимит страниц: глобальный MAX_PAGES побеждает per-OKVED."""
    if MAX_PAGES:
        return MAX_PAGES
    # per-OKVED override через env: KD_FEED_MAX_PAGES_1085=1 и т.п.
    env_key = "KD_FEED_MAX_PAGES_" + okved.replace(".", "")
    per_env = int(_os.environ.get(env_key, "0")) or None
    if per_env:
        return per_env
    return _SEGMENT_PAGE_LIMITS.get(okved)


def main():
    # inn -> best record (наибольшая выручка среди периодов)
    seen: dict[str, dict] = {}
    empty_bfo = 0
    stats_by_okved: dict[str, int] = {}

    for okved in OKVEDS:
        okved_new = 0
        max_pg = _max_pages_for(okved)
        for period in PERIODS:
            page = 0
            total = None
            fetched = 0
            while True:
                t0 = time.time()
                try:
                    res = fetch_page(okved, period, page)
                except Exception as e:
                    print(f"! fetch error okved={okved} period={period} page={page}: {e}")
                    print(f"FATAL_OKVED={okved} period={period} page={page} error={e}")
                    break
                total = res.get("totalElements", 0)
                rows = res.get("content") or []
                if not rows:
                    break
                new, upd = 0, 0
                for raw in rows:
                    n = normalize(raw)
                    if not n["inn"]:
                        continue
                    if n["revenue_tsd_rub"] is None:
                        empty_bfo += 1
                    prev = seen.get(n["inn"])
                    if prev is None:
                        seen[n["inn"]] = n
                        new += 1
                        okved_new += 1
                    else:
                        # keep record with highest revenue; if equal keep newer period
                        a = prev.get("revenue_tsd_rub") or 0
                        b = n.get("revenue_tsd_rub") or 0
                        if b > a or (b == a and (n.get("bfo_period") or "") > (prev.get("bfo_period") or "")):
                            seen[n["inn"]] = n
                            upd += 1
                fetched += len(rows)
                dt = time.time() - t0
                limit_note = f" [cap={max_pg}p]" if max_pg else ""
                print(f"  okved={okved} period={period} page={page:>2} rows={len(rows):>4} "
                      f"total={total:>5} new={new:>4} upd={upd:>4} ({dt:>4.1f}s){limit_note}")
                if fetched >= (total or 0) or len(rows) < PAGE_SIZE:
                    break
                if max_pg and page + 1 >= max_pg:
                    print(f"  [limit] page cap={max_pg} reached for okved={okved}")
                    break
                page += 1
                time.sleep(SLEEP_BETWEEN)
        stats_by_okved[okved] = okved_new

    with OUT.open("w") as f:
        for v in seen.values():
            f.write(json.dumps(v, ensure_ascii=False) + "\n")

    print()
    print(f"✓ Unique orgs total: {len(seen)}")
    print(f"✓ Records without revenue in bfo: {empty_bfo}")
    for ok, n in stats_by_okved.items():
        lim = _max_pages_for(ok)
        print(f"  {ok}: {n} new orgs" + (f" (capped at {lim} pages)" if lim else ""))
    print(f"✓ Saved: {OUT}")


if __name__ == "__main__":
    main()
