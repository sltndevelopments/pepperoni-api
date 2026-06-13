#!/usr/bin/env python3
"""Handoff Rules — explicit, auditable triggers that move work between agents.

Adaptive handoff WITHOUT the chaos: there is no "agents decide among themselves".
Instead, a small set of EXPLICIT rules turn observable facts (a new commercial
lead, a demand cluster without a page) into typed tasks on the agent bus. Every
handoff is a row in data/agent_bus.json — fully transparent and debuggable, which
is exactly what Fable approved for a small/mid B2B with an owner in control.

Run by cron after the lead listener (so fresh leads are routed promptly) and as
a pipeline step. Idempotent: each rule uses a dedup key so the same lead/cluster
is handed off only once.

  leads.json  ─▶ commercial lead ─▶ task(to=steve, type=warm_lead_followup)
  leads.json  ─▶ demand for X without page ─▶ task(to=fable, type=create_landing)
  (Steve, in his own cycle, can post tasks back to Fable via agent_bus.post.)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "scripts"))

import agent_bus

LEADS = DATA / "leads.json"

# Product clusters we track, mapped to a canonical landing path Fable owns.
CLUSTER_HINTS = {
    "пепперони": "/pepperoni", "pepperoni": "/pepperoni",
    "сосиск": "/sosiski-hotdog", "сосиси": "/sosiski-hotdog",
    "ветчин": "/vetchina-optom", "казылык": "/kazylyk",
    "котлет": "/kotlety-burgery", "бургер": "/kotlety-burgery",
    "пельмен": "/pelmeni", "выпечк": "/bakery", "эчпочмак": "/bakery",
    "oem": "/oem", "стм": "/private-label", "private label": "/private-label",
}


def _load_leads() -> list:
    try:
        return json.loads(LEADS.read_text()).get("leads", [])
    except Exception:
        return []


def _cluster_of(text: str) -> str | None:
    low = (text or "").lower()
    for hint, path in CLUSTER_HINTS.items():
        if hint in low:
            return path
    return None


def run() -> dict:
    """Apply all handoff rules to current state. Returns counts."""
    leads = _load_leads()
    routed_steve = 0
    routed_fable = 0

    for lead in leads:
        if lead.get("intent") != "commercial":
            continue
        lead_key = f"{lead.get('chat_id')}:{lead.get('msg_id')}"

        # Rule 1: every commercial lead → Steve for follow-up.
        tid = agent_bus.post(
            frm="handoff", to="steve", type_="warm_lead_followup",
            payload={"channel": lead.get("channel"), "phone": lead.get("phone", ""),
                     "text": lead.get("text", "")[:300]},
            trigger="lead.intent=commercial",
            note=f"Лид из {lead.get('channel')} — связаться",
            dedup_key=f"lead:{lead_key}")
        if tid:
            routed_steve += 1

        # Rule 2: if the lead names a cluster we have a page for, ask Fable to
        # make sure that landing is strong / create supporting content.
        cluster = _cluster_of(lead.get("text", ""))
        if cluster:
            agent_bus.post(
                frm="handoff", to="fable", type_="strengthen_landing",
                payload={"cluster": cluster, "evidence": "real_commercial_lead",
                         "lead_text": lead.get("text", "")[:200]},
                trigger="lead.cluster_match",
                note=f"Живой коммерческий лид по {cluster} — усилить страницу/оффер",
                dedup_key=f"cluster:{cluster}")
            routed_fable += 1

    return {"routed_to_steve": routed_steve, "routed_to_fable": routed_fable}


def main() -> int:
    res = run()
    print(f"✅ handoff: →steve {res['routed_to_steve']}, →fable {res['routed_to_fable']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
