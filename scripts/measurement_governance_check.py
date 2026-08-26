#!/usr/bin/env python3
"""Validate trust-reset checkpoints, experiment limits and measurement inputs."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
GOVERNANCE = DATA / "measurement_governance.json"


def run() -> list[str]:
    errors: list[str] = []
    governance = json.loads(GOVERNANCE.read_text(encoding="utf-8"))
    checkpoints = governance.get("checkpoints") or []
    if [row.get("day") for row in checkpoints] != [30, 60, 90]:
        errors.append("checkpoints must be exactly day 30, 60 and 90")
    expected_dates = {30: "2026-09-25", 60: "2026-10-25", 90: "2026-11-24"}
    for checkpoint in checkpoints:
        day = checkpoint.get("day")
        if checkpoint.get("date") != expected_dates.get(day):
            errors.append(f"wrong checkpoint date for day {day}")
        if not checkpoint.get("objectives"):
            errors.append(f"checkpoint day {day} has no objectives")

    baseline = ROOT / str(governance.get("baseline") or "")
    if not baseline.is_file():
        errors.append(f"locked baseline missing: {baseline}")
    else:
        payload = json.loads(baseline.read_text(encoding="utf-8"))
        for key in ("search", "analytics", "ai_search", "index_policy"):
            if not payload.get(key):
                errors.append(f"baseline missing section: {key}")

    manifest = json.loads(
        (DATA / "index_manifest.json").read_text(encoding="utf-8"))
    keep = int(manifest.get("counts", {}).get("keep") or 0)
    if not 180 <= keep <= 250:
        errors.append(f"index allowlist outside 180..250: {keep}")

    experiments = json.loads(
        (DATA / "operator_experiments.json").read_text(encoding="utf-8"))
    active = [
        row for row in experiments
        if row.get("status") in {"active", "measuring"}
    ]
    legacy_payload = json.loads(
        (DATA / "ab_tests.json").read_text(encoding="utf-8"))
    legacy_active = [
        row for row in legacy_payload.get("ab_tests", [])
        if row.get("status") == "ab_running"
    ]
    maximum = int(
        governance.get("experiment_policy", {}).get("max_active") or 0)
    active_total = len(active) + len(legacy_active)
    if active_total > maximum:
        errors.append(
            f"{active_total} active experiments across both registries exceeds max {maximum}")
    operator_state = json.loads(
        (DATA / "operator_state.json").read_text(encoding="utf-8"))
    if operator_state.get("mode") == "trust_reset" and legacy_active:
        errors.append(
            f"trust_reset has {len(legacy_active)} legacy ab_running experiment(s)")
    required = set(
        governance.get("experiment_policy", {}).get("required_fields") or [])
    for row in active:
        missing = sorted(key for key in required if not row.get(key))
        if missing:
            errors.append(
                f"active experiment {row.get('id')} missing {', '.join(missing)}")

    aio_source = (ROOT / "scripts" / "aio_visibility.py").read_text(
        encoding="utf-8")
    if '"tool_choice": "required"' not in aio_source:
        errors.append("ChatGPT Search must use tool_choice=required")

    authority = json.loads(
        (DATA / "authority_program.json").read_text(encoding="utf-8"))
    if authority.get("status") != "active":
        errors.append("authority program is not active")
    if date.fromisoformat(authority["cycle"]["ends_at"]) <= date.fromisoformat(
            authority["cycle"]["starts_at"]):
        errors.append("authority cycle dates are invalid")
    return errors


def main() -> int:
    errors = run()
    if errors:
        print(f"measurement governance: {len(errors)} FAIL")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("measurement governance: OK (30/60/90; max 3 experiments)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
