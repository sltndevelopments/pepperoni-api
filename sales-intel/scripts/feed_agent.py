#!/usr/bin/env python3
"""Автономная петля discovery: реестр → скоринг → обогащение → импорт в Стива.

Запуск:
  # тест на 20 компаниях (не пишет в боевую БД)
  python3 sales-intel/scripts/feed_agent.py --limit 20 --dry-run

  # боевой прогон (раз в неделю через cron)
  python3 sales-intel/scripts/feed_agent.py

Cron (VPS, /etc/cron.d/kd-feed-agent):
  0 0 * * 0 root cd /var/www/pepperoni && python3 sales-intel/scripts/feed_agent.py >> /var/log/kd-feed-agent.log 2>&1

Что делает:
  1. fetch_bo_okved  → sales-intel/raw/bo_okved_raw.jsonl
  2. score_bo_leads  → sales-intel/data/bakery-leads-okved.csv
  3. enrich_contacts → sales-intel/data/bakery-leads-okved-enriched.csv
  4. import_from_csv → sales-agent/data/agent.db
     дедуп по ИНН: _agent неприкосновенен, status сохраняется,
     fit_score/tier только повышаются, имя только если пустое.

Границы: только discovery-слой. Реальная отправка писем не затрагивается.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT_REPO = Path(__file__).resolve().parent.parent.parent  # pepperoni-api/
SCRIPTS = ROOT_REPO / "sales-intel" / "scripts"
DATA = ROOT_REPO / "sales-intel" / "data"
RAW = ROOT_REPO / "sales-intel" / "raw"
AGENT = ROOT_REPO / "sales-agent"

sys.path.insert(0, str(AGENT))
sys.path.insert(0, str(SCRIPTS))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run(label: str, cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n{'='*60}")
    print(f"[{_now()}] STEP: {label}")
    print(f"  cmd: {' '.join(cmd)}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, capture_output=False, text=True)
    if check and result.returncode != 0:
        print(f"[feed_agent] ✗ {label} failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
    return result


def step_fetch(*, limit_pages: int | None = None) -> bool:
    """Шаг 1: скрейп bo.nalog.gov.ru → raw/bo_okved_raw.jsonl."""
    RAW.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(SCRIPTS / "fetch_bo_okved.py")]
    # fetch_bo_okved.main() не принимает аргументов — запускаем как есть.
    # Для теста ограничиваем через патч: если нужен limit, используем subprocess timeout.
    _run("fetch_bo_okved", cmd)

    out = RAW / "bo_okved_raw.jsonl"
    if not out.exists() or out.stat().st_size == 0:
        print("[feed_agent] ✗ fetch вернул пустой файл — возможен блок по IP", file=sys.stderr)
        return False

    count = sum(1 for _ in out.open() if _.strip())
    print(f"[feed_agent] fetch ✓ — {count} организаций в {out.name}")
    return count > 0


def step_fetch_limited(pages_per_okved: int = 1) -> bool:
    """Шаг 1 (тест): fetch с ограничением по числу страниц через KD_FEED_MAX_PAGES."""
    import os
    RAW.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "KD_FEED_MAX_PAGES": str(pages_per_okved)}
    print(f"[feed_agent] fetch limited: KD_FEED_MAX_PAGES={pages_per_okved}")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "fetch_bo_okved.py")],
        env=env, capture_output=False, text=True,
    )
    out = RAW / "bo_okved_raw.jsonl"
    if not out.exists() or out.stat().st_size == 0:
        print("[feed_agent] ✗ fetch вернул пустой файл", file=sys.stderr)
        return False
    count = sum(1 for _ in out.open() if _.strip())
    print(f"[feed_agent] fetch (limited, {pages_per_okved}p/okved) ✓ — {count} организаций")
    return count > 0


def step_score(min_revenue_mln: float = 100.0) -> int:
    """Шаг 2: score_bo_leads → data/bakery-leads-okved.csv."""
    DATA.mkdir(parents=True, exist_ok=True)
    _run("score_bo_leads", [
        sys.executable, str(SCRIPTS / "score_bo_leads.py"),
        f"--min-revenue-mln={min_revenue_mln}",
    ])
    out = DATA / "bakery-leads-okved.csv"
    if not out.exists():
        return 0
    count = sum(1 for _ in out.open(encoding="utf-8-sig")) - 1  # minus header
    print(f"[feed_agent] score ✓ — {max(0, count)} кандидатов")
    return max(0, count)


def step_enrich(top_n: int = 80) -> dict:
    """Шаг 3: enrich_contacts → bakery-leads-okved-enriched.csv."""
    from enrich_contacts import enrich
    src = DATA / "bakery-leads-okved.csv"
    dst = DATA / "bakery-leads-okved-enriched.csv"
    result = enrich(src, dst, top_n=top_n)
    print(f"[feed_agent] enrich ✓ — {result}")
    return result


def step_import(
    *,
    limit: int | None = None,
    min_score: int = 50,
    dry_run: bool = False,
) -> dict:
    """Шаг 4: import_from_csv → agent.db."""
    from prospecting.import_intel import import_from_csv
    from core.store import Store

    csv_path = DATA / "bakery-leads-okved-enriched.csv"
    if not csv_path.exists():
        return {"error": "enriched CSV not found", "imported": 0}

    store = None if dry_run else Store()
    if store:
        store.init()

    if dry_run:
        # сухой прогон: считаем строки, не пишем в БД
        import csv as _csv
        rows = list(_csv.DictReader(csv_path.open(encoding="utf-8-sig")))
        if limit:
            rows = rows[:limit]
        new_count = sum(
            1 for r in rows
            if int(float((r.get("score") or "0").replace(",", "."))) >= min_score
        )
        return {"dry_run": True, "would_import": new_count, "path": str(csv_path)}

    result = import_from_csv(csv_path, store=store, limit=limit, min_score=min_score)
    return result


def step_verify(limit: int = 20) -> dict:
    """Проверка после импорта: сколько лидов с контактами и lookalike."""
    from core.store import Store
    from prospecting.lookalike import score_lookalike
    import core.agent_profile as ap

    store = Store()
    leads = store.list_leads(limit=limit * 3, status="new")
    # берём только свежеимпортированные (source = sales-intel)
    fresh = [l for l in leads if (l.get("source") or "").startswith("sales-intel")][:limit]

    with_email = sum(1 for l in fresh if (l.get("profile") or {}).get("emails") or (l.get("profile") or {}).get("email"))
    with_phone = sum(1 for l in fresh if (l.get("profile") or {}).get("phones"))
    with_okved = sum(1 for l in fresh if (l.get("profile") or {}).get("okved_main"))

    la_scores = []
    for l in fresh:
        la = ap.get(l.get("profile") or {}, "lookalike") or (l.get("profile") or {}).get("lookalike")
        if isinstance(la, dict):
            la_scores.append(la.get("lookalike_score", 0))
        else:
            sc = score_lookalike(l)
            la_scores.append(sc.get("lookalike_score", 0))

    return {
        "fresh_leads": len(fresh),
        "with_email": with_email,
        "with_phone": with_phone,
        "with_okved_main": with_okved,
        "lookalike_avg": round(sum(la_scores) / len(la_scores), 1) if la_scores else 0,
        "lookalike_above_45": sum(1 for s in la_scores if s >= 45),
    }


def main():
    parser = argparse.ArgumentParser(description="KD Sales Intel → Agent feed pipeline")
    parser.add_argument("--limit", type=int, default=None,
                        help="Ограничить импорт N строками (для теста)")
    parser.add_argument("--top-n-enrich", type=int, default=80,
                        help="Обогатить top-N лидов через zachestnyibiznes (default 80)")
    parser.add_argument("--min-revenue-mln", type=float, default=100.0,
                        help="Мин. выручка для фильтра, млн ₽ (default 100)")
    parser.add_argument("--min-score", type=int, default=50,
                        help="Мин. скор для импорта (default 50)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Не писать в agent.db — только показать что будет")
    parser.add_argument("--skip-fetch", action="store_true",
                        help="Пропустить fetch (использовать уже скачанный jsonl)")
    parser.add_argument("--skip-enrich", action="store_true",
                        help="Пропустить enrich (использовать уже обогащённый CSV)")
    parser.add_argument("--pages-per-okved", type=int, default=None,
                        help="Ограничить N страниц на ОКВЭД при fetch (для теста)")
    args = parser.parse_args()

    log: dict = {"started_at": _now(), "args": vars(args)}
    t0 = time.time()

    # --- Step 1: fetch ---
    if not args.skip_fetch:
        if args.pages_per_okved:
            ok = step_fetch_limited(args.pages_per_okved)
        else:
            ok = step_fetch()
        if not ok:
            print("[feed_agent] Остановлен на fetch — реестр недоступен или пуст.", file=sys.stderr)
            sys.exit(1)
    else:
        print("[feed_agent] skip fetch — используем имеющийся jsonl")

    # --- Step 2: score ---
    scored = step_score(args.min_revenue_mln)
    log["scored"] = scored
    if scored == 0:
        print("[feed_agent] 0 кандидатов после скоринга — нечего импортировать.")
        sys.exit(0)

    # --- Step 3: enrich ---
    if not args.skip_enrich:
        top_n = args.limit or args.top_n_enrich
        enrich_result = step_enrich(top_n=top_n)
        log["enrich"] = enrich_result
    else:
        print("[feed_agent] skip enrich — используем имеющийся enriched CSV")

    # --- Step 4: import ---
    import_result = step_import(
        limit=args.limit,
        min_score=args.min_score,
        dry_run=args.dry_run,
    )
    log["import"] = import_result
    print(f"\n[feed_agent] import result: {import_result}")

    # --- Step 5: verify ---
    if not args.dry_run:
        verify = step_verify(limit=args.limit or 50)
        log["verify"] = verify
        print(f"[feed_agent] verify: {json.dumps(verify, ensure_ascii=False)}")

    elapsed = round(time.time() - t0, 1)
    log["elapsed_sec"] = elapsed
    log["finished_at"] = _now()
    print(f"\n[feed_agent] ✓ done in {elapsed}s")
    print(json.dumps(log, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
