#!/usr/bin/env python3
"""Fable's long-term memory — the deputy's "second brain".

The autonomous strategist (seo_brain.py / the Telegram dialogue) is stateless
between runs except for ledgers. This module gives Fable a durable, self-curated
memory of the things a real deputy would carry in their head for weeks:

  • principles   — standing rules the owner gave ("never touch prices without me",
                   "Gulf market is the priority this quarter"). High weight.
  • decisions    — concrete agreements/decisions made together, with date and why.
  • okr          — Fable's own quarterly objectives + key results it set itself.
  • facts        — durable facts worth remembering (a competitor, a seasonal peak).

Fable WRITES to this memory by emitting a `memory_ops` block in its strategy
(see seo_brain.py). The owner can also add principles via the Telegram bot.
Everything is stored in data/fable_memory.json (repo-tracked → survives deploys,
visible in git history). Memory is fed back into every digest and every chat so
Fable always "remembers" the relationship.

Schema (data/fable_memory.json):
{
  "principles": [{"id","text","by","at","weight"}],
  "decisions":  [{"id","text","why","at"}],
  "okr":        [{"id","objective","key_results":[...],"quarter","status","at"}],
  "facts":      [{"id","text","at"}],
  "updated_at": "..."
}
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
MEMORY_FILE = DATA / "fable_memory.json"

SECTIONS = ("principles", "decisions", "okr", "facts")
# Soft caps so the memory stays compact enough to inline in every prompt.
CAPS = {"principles": 25, "decisions": 40, "okr": 12, "facts": 40}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40]
    return base or "item"


def load() -> dict:
    try:
        mem = json.loads(MEMORY_FILE.read_text())
    except Exception:
        mem = {}
    for s in SECTIONS:
        mem.setdefault(s, [])
    return mem


def save(mem: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    mem["updated_at"] = _now()
    MEMORY_FILE.write_text(json.dumps(mem, ensure_ascii=False, indent=1))


def _next_id(items: list, prefix: str) -> str:
    return f"{prefix}-{len(items) + 1}-{_slug(str(items))[:6]}"


def add_principle(text: str, by: str = "owner", weight: int = 5) -> str:
    mem = load()
    text = (text or "").strip()
    if not text:
        return "skip: empty"
    # Dedup near-identical principles.
    for p in mem["principles"]:
        if p.get("text", "").strip().lower() == text.lower():
            return f"exists: {p['id']}"
    pid = f"pr-{len(mem['principles']) + 1}"
    mem["principles"].append({"id": pid, "text": text, "by": by,
                              "at": _now(), "weight": int(weight)})
    mem["principles"] = mem["principles"][-CAPS["principles"]:]
    save(mem)
    return f"added principle {pid}"


def apply_ops(ops: list) -> list:
    """Apply a list of memory operations emitted by Fable in its strategy.

    Each op: {"action": "add"|"update"|"remove",
              "section": "principles|decisions|okr|facts",
              ...section-specific fields..., "id": <for update/remove>}
    Returns a list of human-readable result strings.
    """
    if not ops:
        return []
    mem = load()
    results: list[str] = []
    for op in ops:
        if not isinstance(op, dict):
            continue
        action = (op.get("action") or "add").lower()
        section = (op.get("section") or "").lower()
        if section not in SECTIONS:
            results.append(f"skip: bad section {section!r}")
            continue
        items = mem[section]

        if action == "remove":
            oid = op.get("id")
            before = len(items)
            mem[section] = [i for i in items if i.get("id") != oid]
            results.append(f"removed {section}:{oid}" if len(mem[section]) < before
                           else f"miss: {section}:{oid}")
            continue

        if action == "update":
            oid = op.get("id")
            hit = next((i for i in items if i.get("id") == oid), None)
            if not hit:
                results.append(f"miss-update: {section}:{oid}")
                continue
            for k, v in op.items():
                if k not in ("action", "section", "id"):
                    hit[k] = v
            hit["at"] = _now()
            results.append(f"updated {section}:{oid}")
            continue

        # action == "add"
        rec = {k: v for k, v in op.items() if k not in ("action", "section")}
        rec.setdefault("at", _now())
        if section == "principles":
            rec.setdefault("by", "fable")
            rec.setdefault("weight", 4)
            rec["id"] = f"pr-{len(items) + 1}"
        elif section == "decisions":
            rec["id"] = f"dec-{len(items) + 1}"
        elif section == "okr":
            rec.setdefault("status", "active")
            rec["id"] = f"okr-{len(items) + 1}"
        else:  # facts
            rec["id"] = f"fact-{len(items) + 1}"
        items.append(rec)
        mem[section] = items[-CAPS[section]:]
        results.append(f"added {section}:{rec['id']}")

    save(mem)
    return results


def digest() -> dict:
    """Compact memory view for the brain digest / chat context."""
    mem = load()
    return {
        "principles": [{"id": p["id"], "text": p["text"], "by": p.get("by")}
                       for p in sorted(mem["principles"],
                                       key=lambda x: -x.get("weight", 0))],
        "decisions": [{"id": d["id"], "text": d["text"], "why": d.get("why", ""),
                       "at": d.get("at", "")[:10]} for d in mem["decisions"][-12:]],
        "okr": [o for o in mem["okr"] if o.get("status") == "active"],
        "facts": [{"id": f["id"], "text": f["text"]} for f in mem["facts"][-12:]],
    }


def as_text(max_chars: int = 2200) -> str:
    """Human-readable memory block for inlining into a chat system prompt."""
    d = digest()
    lines: list[str] = []
    if d["principles"]:
        lines.append("ПРИНЦИПЫ (стоячие правила от владельца/мои):")
        lines += [f"  • {p['text']}" for p in d["principles"]]
    if d["okr"]:
        lines.append("МОИ ЦЕЛИ (OKR):")
        for o in d["okr"]:
            krs = "; ".join(o.get("key_results", []) or [])
            lines.append(f"  • {o.get('objective', '')} [{o.get('quarter', '')}] — {krs}")
    if d["decisions"]:
        lines.append("РЕШЕНИЯ/ДОГОВОРЁННОСТИ:")
        lines += [f"  • ({x['at']}) {x['text']}"
                  + (f" — {x['why']}" if x.get("why") else "")
                  for x in d["decisions"]]
    if d["facts"]:
        lines.append("ФАКТЫ:")
        lines += [f"  • {f['text']}" for f in d["facts"]]
    text = "\n".join(lines) if lines else "(память пока пуста)"
    return text[:max_chars]


def main() -> int:
    import sys
    args = sys.argv[1:]
    if args and args[0] == "--add-principle":
        print(add_principle(" ".join(args[1:]), by="owner"))
    else:
        print(json.dumps(digest(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
