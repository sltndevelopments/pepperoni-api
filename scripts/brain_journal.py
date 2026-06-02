#!/usr/bin/env python3
"""
Brain journal — persistent protocol/memory of all interactions with the
autonomous SEO brain. Append-only JSONL on the server. Both the Telegram
bot and the daily brain read it so context carries across sessions.

Entry kinds:
  user_cmd     — a command you sent via Telegram
  brain_reply  — Opus reply / decision
  strategy     — a strategy.json was written (with summary)
  worker       — a generation tick result
  digest       — daily digest sent
  system       — notable events (errors, budget warnings)

Usage:
    from brain_journal import log_event, recent_summary, tail
    log_event("user_cmd", "запусти выпечку по Турции", who="rinat")
    print(recent_summary(max_chars=2000))
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
JOURNAL = DATA / "brain_journal.jsonl"
MAX_KEEP = int(os.environ.get("JOURNAL_MAX_KEEP", "2000"))  # rotate after N lines


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(kind: str, text: str, who: str = "system", meta: dict | None = None) -> None:
    DATA.mkdir(exist_ok=True)
    entry = {"ts": _now(), "kind": kind, "who": who, "text": str(text)[:4000]}
    if meta:
        entry["meta"] = meta
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _maybe_rotate()


def _maybe_rotate() -> None:
    try:
        lines = JOURNAL.read_text(encoding="utf-8").splitlines()
        if len(lines) > MAX_KEEP:
            JOURNAL.write_text("\n".join(lines[-MAX_KEEP:]) + "\n", encoding="utf-8")
    except Exception:
        pass


def read_all() -> list[dict]:
    out = []
    try:
        for line in JOURNAL.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return out


def tail(n: int = 20) -> list[dict]:
    return read_all()[-n:]


def recent_summary(max_chars: int = 2500, n: int = 40) -> str:
    """Compact human/AI-readable digest of recent activity for Opus context."""
    entries = tail(n)
    if not entries:
        return "Журнал пуст — это первая сессия."
    lines = []
    for e in entries:
        ts = e.get("ts", "")[:16].replace("T", " ")
        kind = e.get("kind", "?")
        who = e.get("who", "")
        text = e.get("text", "").replace("\n", " ")[:200]
        lines.append(f"[{ts}] {kind}/{who}: {text}")
    blob = "\n".join(lines)
    if len(blob) > max_chars:
        blob = blob[-max_chars:]
    return blob


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        log_event("system", "journal self-test", who="system")
    print(f"Journal: {JOURNAL}")
    print(f"Entries: {len(read_all())}")
    print("--- recent ---")
    print(recent_summary())
