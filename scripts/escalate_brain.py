#!/usr/bin/env python3
"""
BRAIN ESCALATION — out-of-band strategy refresh on strong signals (meta-agent F).

Normally the Opus "brain" replans once a day. But some signals are too important
to wait for the next cycle. This watchdog inspects the latest agent outputs and,
if a STRONG signal is present, triggers an immediate brain re-plan (subject to a
cooldown + the monthly Opus budget cap so it can never burn money runaway).

Strong signals (any one fires escalation):
  • BIG NEW DEMAND  — Scout found a new/rising query or a coverage gap with
    impressions >= ESC_DEMAND_IMPR that we don't rank well for.
  • WIN STREAK      — the optimizer logged >= ESC_WIN_STREAK fresh "win" verdicts
    (a repeatable pattern worth doubling down on, strategically).
  • TRAFFIC ANOMALY — Anomaly-Guard recorded a drop today (the brain should
    re-prioritise defensively, not keep expanding).

Guards:
  • COOLDOWN — at most one escalation per ESC_COOLDOWN_HOURS (state in
    data/escalation_state.json, git-tracked).
  • BUDGET   — defers to opus_brain_client.brain_available(); never runs if the
    monthly Opus budget is exhausted.

On escalation it runs seo_brain.main() (which respects the same budget cap) and
pings Telegram with the reason.

Env: ESC_DEMAND_IMPR(80) ESC_WIN_STREAK(3) ESC_COOLDOWN_HOURS(12)
Usage:
  python3 scripts/escalate_brain.py            # check signals, escalate if strong
  python3 scripts/escalate_brain.py --dry-run  # report decision, don't run brain
  python3 scripts/escalate_brain.py --force    # ignore cooldown (still budget-gated)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
STATE = DATA / "escalation_state.json"

ESC_DEMAND_IMPR    = int(os.environ.get("ESC_DEMAND_IMPR", "80"))
ESC_WIN_STREAK     = int(os.environ.get("ESC_WIN_STREAK", "3"))
ESC_COOLDOWN_HOURS = float(os.environ.get("ESC_COOLDOWN_HOURS", "12"))


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


# ---------------------------------------------------------------- signal detection

def _scout_signal() -> str | None:
    f = _load(DATA / "scout_findings.json", {})
    pools = []
    for key in ("new_queries", "rising_queries", "coverage_gaps"):
        pools += f.get(key) or []
    best = 0
    best_q = None
    for e in pools:
        impr = e.get("impr") or e.get("impressions") or 0
        if impr > best:
            best, best_q = impr, e.get("query")
    if best >= ESC_DEMAND_IMPR:
        return f"крупный спрос: «{best_q}» (~{best} показов) обнаружен Scout"
    return None


def _winstreak_signal() -> str | None:
    led = _load(DATA / "experiments.json", [])
    # count recent wins that haven't been "seen" by a previous escalation
    state = _load(STATE, {})
    last_seen = state.get("last_seen_wins", 0)
    wins = sum(1 for e in led if e.get("verdict") == "win")
    fresh = wins - last_seen
    if fresh >= ESC_WIN_STREAK:
        return f"серия успехов: +{fresh} выигрышных экспериментов с прошлой эскалации"
    return None


def _anomaly_signal() -> str | None:
    series = _load(DATA / "anomaly_baseline.json", [])
    if not series:
        return None
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    last = series[-1]
    if last.get("date") != today:
        return None
    # Re-derive a quick drop check vs trailing median (mirror Anomaly-Guard logic
    # lightly; the Guard already alerted — here we only decide to re-plan).
    prior = [p for p in series[:-1] if p.get("date") != today][-7:]
    if len(prior) < 4:
        return None
    import statistics
    med_clicks = statistics.median([p["clicks"] for p in prior] or [0])
    med_impr = statistics.median([p["impressions"] for p in prior] or [0])
    if med_clicks >= 5 and last["clicks"] < med_clicks * 0.65:
        return f"падение трафика: клики {last['clicks']} против медианы {med_clicks:.0f}"
    if med_impr >= 100 and last["impressions"] < med_impr * 0.65:
        return f"падение показов: {last['impressions']} против медианы {med_impr:.0f}"
    return None


def detect_signals() -> list[str]:
    sigs = []
    for fn in (_scout_signal, _winstreak_signal, _anomaly_signal):
        try:
            s = fn()
            if s:
                sigs.append(s)
        except Exception as e:
            print(f"· signal check failed ({fn.__name__}): {e}", file=sys.stderr)
    return sigs


# ---------------------------------------------------------------- cooldown

def cooldown_active() -> bool:
    state = _load(STATE, {})
    last = state.get("last_escalation_at")
    if not last:
        return False
    try:
        prev = datetime.fromisoformat(last)
    except Exception:
        return False
    return datetime.now(timezone.utc) - prev < timedelta(hours=ESC_COOLDOWN_HOURS)


def record_escalation(reasons: list[str]) -> None:
    led = _load(DATA / "experiments.json", [])
    wins = sum(1 for e in led if e.get("verdict") == "win")
    state = _load(STATE, {})
    state.update({
        "last_escalation_at": datetime.now(timezone.utc).isoformat(),
        "last_reasons": reasons,
        "last_seen_wins": wins,
    })
    DATA.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- main

def main():
    args = set(sys.argv[1:])
    dry = "--dry-run" in args
    force = "--force" in args

    operator = _load(DATA / "operator_state.json", {})
    if operator.get("mode") == "repair":
        print("· repair mode — brain escalation disabled")
        return 0

    signals = detect_signals()
    if not signals:
        print("· no strong signals — brain runs on its normal daily cycle")
        return 0

    print("⚡ strong signal(s):")
    for s in signals:
        print(f"  - {s}")

    if cooldown_active() and not force:
        print(f"· cooldown active (<{ESC_COOLDOWN_HOURS}h since last escalation) — skipping")
        return 0

    try:
        from opus_brain_client import brain_available, remaining_budget
    except Exception as e:
        print(f"⚠️  cannot import brain client: {e}", file=sys.stderr)
        return 0
    if not brain_available():
        print("· brain unavailable (no ANTHROPIC_API_KEY or budget exhausted) — skip")
        return 0

    if dry:
        print(f"[dry-run] would escalate (budget left ${remaining_budget():.2f})")
        return 0

    print(f"🧠 escalating → running brain now (budget left ${remaining_budget():.2f})")
    before = None
    try:
        before = _load(DATA / "strategy.json", {}).get("generated_at")
    except Exception:
        pass
    try:
        # Escalations are triggered by strong signals → full reasoning depth
        # (daily ticks default to BRAIN_EFFORT=medium).
        os.environ["BRAIN_EFFORT"] = os.environ.get("BRAIN_EFFORT_ESCALATED", "high")
        import seo_brain
        rc = seo_brain.main()
    except Exception as e:
        print(f"⚠️  brain run failed: {e}", file=sys.stderr)
        return 2
    after = _load(DATA / "strategy.json", {}).get("generated_at")
    if rc != 0 or not after or after == before:
        print("⚠️ brain did not atomically write a fresh strategy", file=sys.stderr)
        return 2
    record_escalation(signals)
    try:
        import daily_ledger
        daily_ledger.append_event(
            "done",
            "Мозг обновил стратегию по сильному сигналу: " + "; ".join(signals[:3]),
        )
    except Exception as e:
        print(f"· ledger unavailable: {e}", file=sys.stderr)
    # exit code 10 signals "brain was escalated this pass" to the orchestrator,
    # so the regular daily brain step can be skipped (no double Opus spend).
    return 10


if __name__ == "__main__":
    sys.exit(main())
