#!/usr/bin/env python3
"""Validate the monthly independent-authority program and scoreboard."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PROGRAM = ROOT / "data" / "authority_program.json"
OWN_DOMAINS = {"pepperoni.tatar", "api.pepperoni.tatar", "kazandelikates.tatar"}


def host(value: str) -> str:
    return (urlparse(value).hostname or value).lower().removeprefix("www.")


def check() -> list[str]:
    errors: list[str] = []
    data = json.loads(PROGRAM.read_text(encoding="utf-8"))
    goal = data.get("goal") or {}
    workstreams = data.get("workstreams") or []
    scoreboard = data.get("scoreboard") or {}
    entity = data.get("entity_template") or {}

    if data.get("status") != "active":
        errors.append("program status must be active")
    if entity.get("legal_name_ru") != "ООО «Казанские Деликатесы»":
        errors.append("wrong legal_name_ru")
    if entity.get("name_en") != "Kazan Delicacies LLC":
        errors.append("wrong English entity name")
    if entity.get("phone") != "+7 987 217-02-02":
        errors.append("wrong authority-program phone")
    if entity.get("email") != "info@kazandelikates.tatar":
        errors.append("wrong authority-program email")

    new_domain_rows = [
        row for row in workstreams if row.get("counts_as_new_domain") is True
    ]
    new_domains = {host(str(row.get("target_domain") or "")) for row in new_domain_rows}
    new_domains.discard("")
    required_domains = int(goal.get("new_independent_domains") or 0)
    if len(new_domains) < required_domains:
        errors.append(
            f"only {len(new_domains)} unique new-domain targets; "
            f"{required_domains} required")
    if new_domains & OWN_DOMAINS:
        errors.append(
            f"own domains cannot count as authority: {sorted(new_domains & OWN_DOMAINS)}")

    international = {
        host(str(row.get("target_domain") or ""))
        for row in new_domain_rows
        if row.get("international") is True
    }
    required_international = int(goal.get("international_domains_min") or 0)
    if len(international) < required_international:
        errors.append(
            f"only {len(international)} international targets; "
            f"{required_international} required")

    ids: set[str] = set()
    for row in workstreams:
        row_id = str(row.get("id") or "")
        if not row_id:
            errors.append("workstream missing id")
        elif row_id in ids:
            errors.append(f"duplicate workstream id: {row_id}")
        ids.add(row_id)
        if not row.get("owner") or not row.get("status") or not row.get("acceptance"):
            errors.append(f"incomplete workstream: {row_id or '<unknown>'}")
        candidate_host = host(str(row.get("candidate_url") or ""))
        target_host = host(str(row.get("target_domain") or ""))
        if candidate_host and candidate_host != target_host:
            errors.append(
                f"candidate host mismatch: {row_id} "
                f"{candidate_host} != {target_host}")

    published = scoreboard.get("published_nodes") or []
    published_domains: set[str] = set()
    international_published = 0
    for node in published:
        domain = host(str(node.get("url") or ""))
        if not domain or domain in OWN_DOMAINS:
            errors.append(f"invalid published authority URL: {node.get('url')!r}")
            continue
        if domain in published_domains:
            errors.append(f"published domain counted twice: {domain}")
        published_domains.add(domain)
        if node.get("international") is True:
            international_published += 1
        if not node.get("verified_at") or not node.get("supports"):
            errors.append(f"published node lacks evidence fields: {domain}")

    if int(scoreboard.get("new_domains_published") or 0) != len(published_domains):
        errors.append("new_domains_published does not match published_nodes")
    if int(scoreboard.get("international_domains_published") or 0) != international_published:
        errors.append("international_domains_published does not match published_nodes")
    return errors


def main() -> int:
    errors = check()
    if errors:
        print(f"authority program: {len(errors)} FAIL")
        for error in errors:
            print(f"  - {error}")
        return 1
    data = json.loads(PROGRAM.read_text(encoding="utf-8"))
    target = data["goal"]["new_independent_domains"]
    published = data["scoreboard"]["new_domains_published"]
    print(
        f"authority program: OK (active; {published}/{target} "
        "new domains published this cycle)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
