#!/usr/bin/env python3
"""Compare Organization identity on indexable pages.

    python3 scripts/check_organization.py          # exit 1 on any mismatch
    python3 scripts/check_organization.py --apply  # write the shared fragment

taxID is not part of the check: public/brand.txt has no INN.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from organization_ld import (  # noqa: E402
    IDENTITY_KEYS,
    ORG_ID,
    ORGANIZATION,
    SAME_AS,
    SCRIPT,
)

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
MANIFEST = ROOT / "data" / "index_manifest.json"
LD_RE = re.compile(
    r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
COMPANY_NAMES = {
    "Казанские Деликатесы",
    "Kazan Delicacies",
    "Kazan Delicacies LLC",
    "ООО «Казанские Деликатесы»",
}


def keep_files() -> list[str]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return [
        entry["file"]
        for entry in manifest.get("entries", [])
        if entry.get("status") == "keep" and entry.get("file")
    ]


def _orgs(node, out: list[dict]) -> None:
    if isinstance(node, dict):
        kind = node.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "Organization" in kinds:
            out.append(node)
        for value in node.values():
            _orgs(value, out)
    elif isinstance(node, list):
        for value in node:
            _orgs(value, out)


def _is_company(org: dict) -> bool:
    if org.get("@id") == ORG_ID:
        return True
    if org.get("legalName") in COMPANY_NAMES or org.get("name") in COMPANY_NAMES:
        return True
    return False


def _problems(org: dict) -> list[str]:
    if not _is_company(org):
        return []
    bad = []
    for key in IDENTITY_KEYS:
        if org.get(key) != ORGANIZATION[key]:
            bad.append(key)
    address = org.get("address")
    street = address.get("streetAddress") if isinstance(address, dict) else None
    if street != ORGANIZATION["address"]["streetAddress"]:
        bad.append("address")
    if set(org.get("sameAs") or []) != SAME_AS:
        bad.append("sameAs")
    return bad


def _align(org: dict) -> bool:
    if not _is_company(org):
        return False
    changed = False
    for key in IDENTITY_KEYS:
        if org.get(key) != ORGANIZATION[key]:
            org[key] = ORGANIZATION[key]
            changed = True
    address = org.get("address")
    if not isinstance(address, dict):
        org["address"] = dict(ORGANIZATION["address"])
        changed = True
    else:
        for key, value in ORGANIZATION["address"].items():
            if address.get(key) != value:
                address[key] = value
                changed = True
    if set(org.get("sameAs") or []) != SAME_AS:
        org["sameAs"] = list(ORGANIZATION["sameAs"])
        changed = True
    if org.get("@id") != ORG_ID:
        org["@id"] = ORG_ID
        changed = True
    return changed


def apply_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    changed = False

    def repl(match: re.Match) -> str:
        nonlocal changed
        raw = match.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return match.group(0)
        orgs: list[dict] = []
        _orgs(data, orgs)
        touched = False
        for org in orgs:
            touched = _align(org) or touched
        if not touched:
            return match.group(0)
        changed = True
        dumped = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return f'<script type="application/ld+json">{dumped}</script>'

    text2 = LD_RE.sub(repl, text)
    if SCRIPT not in text2 and "</head>" in text2:
        text2 = text2.replace("</head>", SCRIPT + "\n</head>", 1)
        changed = True
    if changed and text2 != text:
        path.write_text(text2, encoding="utf-8")
        return True
    return False


def check_file(path: Path) -> list[str]:
    if not path.exists():
        return ["missing file"]
    text = path.read_text(encoding="utf-8")
    errors = []
    if SCRIPT not in text:
        errors.append("missing shared Organization script")
    for raw in LD_RE.findall(text):
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            errors.append("invalid JSON-LD")
            continue
        orgs: list[dict] = []
        _orgs(data, orgs)
        for org in orgs:
            bad = _problems(org)
            if bad:
                errors.append("mismatch " + ",".join(bad))
    return errors


def main() -> int:
    apply = "--apply" in sys.argv
    files = keep_files()
    if apply:
        written = 0
        for rel in files:
            if apply_file(PUBLIC / rel):
                written += 1
        print(f"organization: aligned {written} of {len(files)} keep pages")
    bad = 0
    for rel in files:
        errors = check_file(PUBLIC / rel)
        if errors:
            bad += 1
            print(f"{rel}: {'; '.join(errors[:4])}")
    print(f"organization: {len(files)} keep pages, {bad} with differences")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
