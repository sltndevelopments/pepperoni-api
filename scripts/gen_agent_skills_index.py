#!/usr/bin/env python3
"""Write /.well-known/agent-skills/index.json with sha256 digests of SKILL.md files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "public" / ".well-known" / "agent-skills"
INDEX = SKILLS_DIR / "index.json"
SCHEMA = "https://schemas.agentskills.io/discovery/0.2.0/schema.json"


def frontmatter_description(text: str) -> str:
    if not text.startswith("---"):
        raise SystemExit("SKILL.md missing YAML frontmatter")
    end = text.find("\n---", 3)
    if end < 0:
        raise SystemExit("SKILL.md frontmatter not closed")
    for line in text[3:end].splitlines():
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("SKILL.md frontmatter missing description")


def main() -> None:
    skills = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        raw = skill_md.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        name = skill_md.parent.name
        desc = frontmatter_description(raw.decode("utf-8"))
        skills.append(
            {
                "name": name,
                "type": "skill-md",
                "description": desc,
                "url": f"/.well-known/agent-skills/{name}/SKILL.md",
                "digest": f"sha256:{digest}",
            }
        )
    INDEX.write_text(
        json.dumps({"$schema": SCHEMA, "skills": skills}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {INDEX.relative_to(ROOT)} ({len(skills)} skills)")

    mcp = ROOT / "public" / ".well-known" / "mcp.json"
    card_dir = ROOT / "public" / ".well-known" / "mcp"
    sep_card = card_dir / "server-card.json"
    card = json.loads(sep_card.read_text(encoding="utf-8")) if sep_card.exists() else json.loads(mcp.read_text(encoding="utf-8"))
    (card_dir / "server-cards.json").write_text(
        json.dumps({"servers": [card]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {card_dir.relative_to(ROOT)}/server-cards.json")


if __name__ == "__main__":
    main()
