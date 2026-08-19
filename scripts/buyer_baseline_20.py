#!/usr/bin/env python3
"""Zero-point AI visibility after fact-consistency commit.

20 buyer prompts × search-grounded layers. Records:
  kd_present, rank, source_page, facts_used, above_and_why

Does not write HTML. Does not touch the leftover working tree.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from aio_visibility import (  # noqa: E402
    US_PATTERNS,
    ask_chatgpt_search,
    ask_gemini_search,
    ask_grok_search,
    ask_perplexity_search,
    mentions_us,
)

PROMPTS = json.loads((ROOT / "data" / "buyer_baseline_prompts.json").read_text())
COMMIT = PROMPTS["after_commit"]

FACT_PATTERNS = [
    ("dum_rt", r"дум\s*рт|dum\s*rt|614A"),
    ("inn_1686021074", r"1686021074"),
    ("kazan", r"казан|kazan|татарстан|tatarstan"),
    ("pepperoni_tatar", r"pepperoni\.tatar"),
    ("exw", r"\bexw\b"),
    ("moq_agreement", r"по договор|by agreement|depends on logistics|зависит от логистик"),
    ("moq_kg_number", r"от\s+\d+\s*кг|from\s+\d+\s*kg|MOQ\s+\d+"),
    ("nitrite_sku", r"sku card|карточк\w+\s+SKU|E250|нитрит"),
    ("no_jakim_claim", r"не (утвержда|claim).{0,40}JAKIM|do not claim JAKIM"),
    ("api_products", r"api\.pepperoni\.tatar|/api/products"),
]

COMPETITOR_HINTS = [
    (r"eskişehir|eskişehir|besler|pınar|pinar|namet|banvit", "TR brand"),
    (r"brasil|jbs|minerva|marfrig|brf", "BR packer"),
    (r"al\s*islami|alislami|emaar|americana|siniora", "UAE/MENA"),
    (r"midamar|ifanca|crescent", "US/IFANCA"),
    (r"останкин|aslam|омпк", "RU peer"),
    (r"kazan\s+halal|казанский\s+халяль", "local peer"),
]


def _flat_prompts() -> list[tuple[str, str]]:
    out = []
    for group, qs in PROMPTS["groups"].items():
        for q in qs:
            out.append((group, q))
    return out


def _urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s)>\"]+", text or "")


def _kd_rank(text: str) -> int | None:
    if not mentions_us(text):
        return None
    # Numbered or dashed supplier lines
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    named = []
    for ln in lines:
        if re.match(r"^(\d+[\).\]]|[-*•])\s+", ln) or re.search(
            r"(manufacturer|producer|supplier|производител|поставщик)", ln, re.I
        ):
            named.append(ln)
    if not named:
        # first-mention order among paragraphs
        lower = text.lower()
        pos = None
        for p in US_PATTERNS:
            m = re.search(p, lower, re.I)
            if m and (pos is None or m.start() < pos):
                pos = m.start()
        return 1 if pos is not None and pos < 400 else 2
    for i, ln in enumerate(named, 1):
        if mentions_us(ln):
            return i
    return 1


def _facts(text: str) -> list[str]:
    hit = []
    for name, rx in FACT_PATTERNS:
        if re.search(rx, text or "", re.I):
            hit.append(name)
    return hit


def _above(text: str) -> list[str]:
    if not mentions_us(text):
        others = []
        for rx, label in COMPETITOR_HINTS:
            if re.search(rx, text or "", re.I):
                others.append(label)
        return others
    rank = _kd_rank(text) or 99
    if rank <= 1:
        return []
    found = []
    for rx, label in COMPETITOR_HINTS:
        if re.search(rx, text or "", re.I):
            found.append(label)
    return found or [f"unnamed suppliers above rank {rank}"]


def _sources(text: str) -> list[str]:
    ours = [u.rstrip(".,);") for u in _urls(text) if "pepperoni.tatar" in u or "kazandelikates" in u]
    return ours[:6]


LAYERS = {
    "perplexity_search": ask_perplexity_search,
    "chatgpt_search": ask_chatgpt_search,
    "gemini_search": ask_gemini_search,
    "grok_search": ask_grok_search,
}


def main() -> int:
    wanted = os.environ.get("BASELINE_LAYERS", "perplexity_search,gemini_search").split(",")
    wanted = [x.strip() for x in wanted if x.strip()]
    rows = []
    print(f"baseline after {COMMIT[:12]} layers={wanted}", flush=True)
    for group, q in _flat_prompts():
        rec = {"group": group, "q": q, "layers": {}}
        for lid in wanted:
            asker = LAYERS.get(lid)
            if not asker:
                rec["layers"][lid] = {"error": "unknown layer"}
                continue
            print(f"→ {lid} [{group}] {q[:64]}…", flush=True)
            text, err = asker(q)
            if err:
                rec["layers"][lid] = {"status": "fail", "error": err}
                print(f"  fail: {err}", flush=True)
                continue
            rec["layers"][lid] = {
                "status": "ok",
                "kd_present": mentions_us(text),
                "rank": _kd_rank(text),
                "source_page": _sources(text),
                "facts_used": _facts(text),
                "above_and_why": _above(text),
                "excerpt": (text or "").strip()[:900],
            }
            print(
                f"  kd={mentions_us(text)} rank={_kd_rank(text)} src={_sources(text)[:2]}",
                flush=True,
            )
        rows.append(rec)

    out = ROOT / "data" / "buyer_baseline_2026-08-19.json"
    if out.exists() and os.environ.get("BASELINE_MERGE", "1") == "1":
        prev = json.loads(out.read_text(encoding="utf-8"))
        by_q = {r["q"]: r for r in prev.get("rows", [])}
        for rec in rows:
            old = by_q.get(rec["q"])
            if not old:
                by_q[rec["q"]] = rec
                continue
            old.setdefault("layers", {}).update(rec["layers"])
        rows = list(by_q.values())
        wanted = list(dict.fromkeys([*(prev.get("layers") or []), *wanted]))
    point = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "ts": datetime.now(timezone.utc).isoformat(),
        "after_commit": COMMIT,
        "note": "Zero point after P0 fact consistency. Site frozen for measurement.",
        "layers": wanted,
        "rows": rows,
    }
    out.write_text(json.dumps(point, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
