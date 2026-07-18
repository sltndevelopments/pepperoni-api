#!/usr/bin/env python3
"""Fail-closed control plane for autonomous SEO generation.

Collection, measurement, deterministic repairs and QA may keep running while
new content is frozen.  Generators must call ``generation_allowed`` (or this
CLI) before spending LLM budget or writing a new page.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STRATEGY = DATA / "strategy.json"
STATE = DATA / "operator_state.json"
EXPERIMENTS = DATA / "operator_experiments.json"

DEFAULT_STATE = {
    "mode": "repair",
    "repair_started_at": "2026-07-19T00:00:00+00:00",
    "repair_until": "2026-08-02T00:00:00+00:00",
    "max_active_experiments": 3,
    "daily_budget_usd": 1.0,
    "monthly_budget_usd": 30.0,
}


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def operator_state() -> dict:
    return {**DEFAULT_STATE, **(_read(STATE, {}) or {})}


def strategy_generated_at() -> datetime | None:
    raw = (_read(STRATEGY, {}) or {}).get("generated_at")
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def gsc_age_days() -> int | None:
    db = DATA / "seo_data.db"
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(str(db))
        newest = conn.execute("SELECT MAX(date) FROM gsc_queries").fetchone()[0]
        conn.close()
        return (date.today() - date.fromisoformat(newest)).days if newest else None
    except Exception:
        return None


def active_experiment_count() -> int:
    rows = _read(EXPERIMENTS, [])
    if isinstance(rows, dict):
        rows = rows.get("experiments", [])
    return sum(1 for row in rows if row.get("status") in {"approved", "running", "measuring"})


def generation_blockers(*, max_strategy_age_days: int = 8) -> list[str]:
    state = operator_state()
    blockers: list[str] = []
    if state.get("mode") != "operator":
        blockers.append(f"operator mode={state.get('mode', 'repair')}")

    generated = strategy_generated_at()
    if generated is None:
        blockers.append("strategy generated_at missing/invalid")
    else:
        age = (datetime.now(timezone.utc) - generated).total_seconds() / 86400
        if age > max_strategy_age_days:
            blockers.append(f"strategy stale ({age:.1f}d)")

    gsc_age = gsc_age_days()
    if gsc_age is None:
        blockers.append("GSC freshness unknown")
    elif gsc_age > 5:
        blockers.append(f"GSC stale ({gsc_age}d)")

    active = active_experiment_count()
    limit = int(state.get("max_active_experiments", 3))
    if active >= limit:
        blockers.append(f"active experiments {active}/{limit}")
    return blockers


def generation_allowed() -> tuple[bool, list[str]]:
    blockers = generation_blockers()
    return not blockers, blockers


def activation_blockers() -> list[str]:
    state = operator_state()
    blockers: list[str] = []
    try:
        until = datetime.fromisoformat(str(state.get("repair_until", "")))
        if datetime.now(timezone.utc) < until:
            blockers.append(f"repair window open until {until.isoformat()}")
    except ValueError:
        blockers.append("repair_until missing/invalid")
    generated = strategy_generated_at()
    if generated is None:
        blockers.append("strategy generated_at missing/invalid")
    elif (datetime.now(timezone.utc) - generated).total_seconds() > 8 * 86400:
        blockers.append("strategy stale")
    gsc_age = gsc_age_days()
    if gsc_age is None or gsc_age > 5:
        blockers.append("GSC stale or unknown")
    rows = _read(EXPERIMENTS, [])
    active_rows = [r for r in rows if r.get("status") in {"approved", "running", "measuring"}]
    keys = [r.get("key") for r in active_rows]
    if len(active_rows) > int(state.get("max_active_experiments", 3)):
        blockers.append("too many active experiments")
    if len(keys) != len(set(keys)):
        blockers.append("duplicate active experiments")
    quarantine = DATA / "quarantine"
    current_q = len(list(quarantine.rglob("*.html"))) if quarantine.exists() else 0
    if current_q > int(state.get("quarantine_baseline", current_q)):
        blockers.append(f"quarantine grew ({current_q})")
    return blockers


def activate_if_ready() -> tuple[bool, list[str]]:
    if operator_state().get("mode") == "operator":
        return True, []
    blockers = activation_blockers()
    if blockers:
        return False, blockers
    state = operator_state()
    state["mode"] = "operator"
    state["activated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(STATE)
    return True, []


def brain_refresh_needed(max_age_days: int = 6) -> bool:
    state = operator_state()
    if state.get("mode") == "repair":
        try:
            until = datetime.fromisoformat(str(state.get("repair_until", "")))
            if datetime.now(timezone.utc) < until:
                return False
        except ValueError:
            return False
    generated = strategy_generated_at()
    if generated is None:
        return True
    return (datetime.now(timezone.utc) - generated).total_seconds() >= max_age_days * 86400


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-generation", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--needs-brain", action="store_true")
    ap.add_argument("--activate-if-ready", action="store_true")
    args = ap.parse_args()
    if args.activate_if_ready:
        activated, blockers = activate_if_ready()
        print("operator mode activated" if activated
              else "operator activation blocked: " + "; ".join(blockers))
        return 0 if activated else 4
    if args.needs_brain:
        needed = brain_refresh_needed()
        print("brain refresh needed" if needed else "brain strategy still fresh")
        return 0 if needed else 4
    allowed, blockers = generation_allowed()
    payload = {
        "allowed": allowed,
        "mode": operator_state().get("mode"),
        "active_experiments": active_experiment_count(),
        "gsc_age_days": gsc_age_days(),
        "strategy_generated_at": (
            strategy_generated_at().isoformat() if strategy_generated_at() else None
        ),
        "blockers": blockers,
    }
    if args.status:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("generation allowed" if allowed else "generation blocked: " + "; ".join(blockers))
    return 0 if allowed or not args.check_generation else 3


if __name__ == "__main__":
    raise SystemExit(main())
