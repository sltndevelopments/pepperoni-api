#!/usr/bin/env python3
"""Pipeline watchdog — the watcher of the watchers.

The daily SEO agent must reach its completion marker (data/.pipeline_ok) and
the brain must keep data/strategy.json fresh. If either fails, this script
fires a Telegram alert. Runs from cron ~2h after the daily agent starts, so a
silent mid-pipeline death (like the set -e / exit-10 bug) is never silent again.

Checks:
  1. data/.pipeline_ok older than 26h  -> pipeline did not finish today
  2. strategy generated_at missing/older than 8d -> weekly brain is not steering
  3. data/goals.json missing/older than 48h    -> scoreboard stale (warn only)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
ENV_FILE = Path("/var/www/pepperoni/seo-agent.env")


def _load_env() -> None:
    """Cron runs without the agent env — load Telegram creds from the env file."""
    if not ENV_FILE.exists():
        return
    try:
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    except OSError:
        pass


def _age_hours(p: Path) -> float | None:
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return None
    return (datetime.now(timezone.utc).timestamp() - mtime) / 3600


def main() -> int:
    _load_env()
    problems: list[str] = []
    warnings: list[str] = []

    age = _age_hours(DATA / ".pipeline_ok")
    if age is None:
        problems.append("конвейер ни разу не дошёл до конца (нет маркера .pipeline_ok)")
    elif age > 26:
        problems.append(f"конвейер не завершался {age:.0f}ч — ежедневный цикл оборвался")

    age = None
    try:
        import json
        strategy = json.loads((DATA / "strategy.json").read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(
            str(strategy.get("generated_at", "")).replace("Z", "+00:00")
        )
        age = (datetime.now(timezone.utc) - generated).total_seconds() / 3600
    except Exception:
        pass
    if age is None:
        problems.append("strategy.json отсутствует — Мозг (Fable) не рулит")
    elif age > 8 * 24:
        problems.append(f"strategy.json устарела ({age:.0f}ч) — Мозг не обновлял стратегию")

    age = _age_hours(DATA / "goals.json")
    if age is None or age > 48:
        warnings.append("goals.json отсутствует/устарел — таблица целей не обновляется")

    # GSC data freshness: a fetch bug once froze data for a month, leaving the
    # brain and optimizer working blind on a stale snapshot. GSC lags ~3 days, so
    # the newest row should never be older than ~5 days.
    try:
        import sqlite3
        from datetime import date
        db = DATA / "seo_data.db"
        if db.exists():
            conn = sqlite3.connect(str(db))
            maxd = conn.execute("SELECT MAX(date) FROM gsc_queries").fetchone()[0]
            conn.close()
            if maxd:
                gap = (date.today() - date.fromisoformat(maxd)).days
                if gap > 5:
                    problems.append(
                        f"данные GSC устарели на {gap}д (последняя дата {maxd}) — "
                        f"мозг и оптимизатор работают вслепую, проверь fetch_gsc_queries.py")
            else:
                warnings.append("в seo_data.db нет данных GSC — нечего оптимизировать")
    except Exception:
        pass

    # LLM spend spike guard: today's cost vs LLM_DAILY_ALERT_USD (default $15).
    try:
        import json
        from datetime import date
        led = json.loads((DATA / "llm_costs.json").read_text())
        day = (led.get(date.today().strftime("%Y-%m"), {})
                  .get("days", {}).get(date.today().isoformat(), {}))
        spent = day.get("usd", 0.0)
        cap = float(os.environ.get("LLM_DAILY_ALERT_USD", "5"))
        if spent > cap:
            warnings.append(f"расход LLM за сегодня ${spent:.2f} > ${cap:.0f} — "
                            f"проверь объёмы генерации (кнопка «Бюджет» в боте)")
    except Exception:
        pass

    # Site-health: broken internal links are a silent SEO killer (we found 8k+).
    try:
        import json as _json
        sh = _json.loads((DATA / "site_health.json").read_text())
        bl = sh.get("broken_links_total", 0)
        if bl > 500:
            problems.append(
                f"битых внутренних ссылок: {bl} (на {sh.get('pages_with_broken_links',0)} стр.) — "
                f"чинит fix_links; Google и люди видят 404")
        bh = sh.get("broken_html_total", 0)
        if bh > 20:
            warnings.append(f"страниц с битым HTML: {bh} — нужен fix_pages.py")
    except Exception:
        pass

    if not problems and not warnings:
        print("watchdog: all green")
        return 0

    lines = ["<b>🚨 Watchdog: проблемы конвейера</b>" if problems
             else "<b>⚠️ Watchdog: предупреждения</b>"]
    lines += [f"• {p}" for p in problems]
    lines += [f"• (warn) {w}" for w in warnings]
    lines.append("\nЛог: /var/log/pepperoni-seo-agent.log")
    text = "\n".join(lines)
    print(text)
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        import daily_ledger
        cat = "emergency" if problems else "needs_help"
        daily_ledger.append_event(cat, text)
    except Exception as e:
        print(f"ledger unavailable: {e}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
