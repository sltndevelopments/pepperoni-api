#!/usr/bin/env python3
"""Долговременная память Стива — «вторая голова» зама по продажам.

Стратег между прогонами без состояния (кроме леджеров). Этот модуль даёт Стиву
устойчивую, самоуправляемую память о том, что настоящий зам держит в голове
неделями:

  • principles — стоячие правила от владельца («скидку >X% только со мной»,
                 «приоритет — оптовики и сети, не розница»). Высокий вес.
  • decisions  — конкретные договорённости с датой и причиной.
  • okr        — собственные квартальные цели Стива по сделкам + ключевые
                 результаты, которые он сам себе поставил.
  • facts      — устойчивые факты (сеть, сезонный пик, поведение конкурента).

Стив ПИШЕТ в память, эмитя блок `memory_ops` в своей стратегии (см.
strategist/insights.py). Владелец также может добавить принцип через Telegram
(«запомни…/впредь…/никогда…»). Всё хранится в data/sales_memory.json
(в git → переживает деплои, видно в истории). Память подаётся в каждый цикл и
в каждый чат, чтобы Стив всегда «помнил» отношения.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MEMORY_FILE = DATA / "sales_memory.json"

SECTIONS = ("principles", "decisions", "okr", "facts")
CAPS = {"principles": 25, "decisions": 40, "okr": 12, "facts": 40}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load() -> dict:
    try:
        mem = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        mem = {}
    for s in SECTIONS:
        mem.setdefault(s, [])
    return mem


def save(mem: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    mem["updated_at"] = _now()
    MEMORY_FILE.write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")


def add_principle(text: str, by: str = "owner", weight: int = 5) -> str:
    mem = load()
    text = (text or "").strip()
    if not text:
        return "skip: empty"
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
    """Применить операции с памятью, которые Стив эмитит в стратегии.

    Каждая op: {"action": "add"|"update"|"remove",
                "section": "principles|decisions|okr|facts",
                ...поля секции..., "id": <для update/remove>}
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
            hit = next((i for i in items if i.get("id") == oid), None) if oid else None
            if not hit:
                # update без валидного id трактуем как add, чтобы не терять правку
                action = "add"
            for k, v in op.items():
                if k not in ("action", "section", "id"):
                    hit[k] = v
            hit["at"] = _now()
            results.append(f"updated {section}:{oid}")
            continue

        rec = {k: v for k, v in op.items() if k not in ("action", "section")}
        rec.setdefault("at", _now())
        if section == "principles":
            rec.setdefault("by", "steve")
            rec.setdefault("weight", 4)
            rec["id"] = f"pr-{len(items) + 1}"
        elif section == "decisions":
            rec["id"] = f"dec-{len(items) + 1}"
        elif section == "okr":
            rec.setdefault("status", "active")
            rec["id"] = f"okr-{len(items) + 1}"
        else:
            rec["id"] = f"fact-{len(items) + 1}"
        items.append(rec)
        mem[section] = items[-CAPS[section]:]
        results.append(f"added {section}:{rec['id']}")

    save(mem)
    return results


def digest() -> dict:
    """Компактный вид памяти для дайджеста стратега / контекста чата."""
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
    """Человекочитаемый блок памяти для системного промпта чата/цикла."""
    d = digest()
    lines: list[str] = []
    if d["principles"]:
        lines.append("ПРИНЦИПЫ (стоячие правила от владельца/мои):")
        lines += [f"  • {p['text']}" for p in d["principles"]]
    if d["okr"]:
        lines.append("МОИ ЦЕЛИ (OKR по сделкам):")
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


# Триггеры «запомни» из чата владельца
_REMEMBER_RE = re.compile(r"^\s*(запомни|впредь|никогда|всегда|правило)[:,\s]+(.+)",
                          re.I | re.S)


def maybe_capture_principle(text: str, by: str = "owner") -> str | None:
    """Если владелец написал «запомни …» — сохранить как принцип."""
    m = _REMEMBER_RE.match(text or "")
    if not m:
        return None
    body = m.group(2).strip()
    if not body:
        return None
    return add_principle(body, by=by, weight=5)


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
