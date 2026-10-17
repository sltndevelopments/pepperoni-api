#!/usr/bin/env python3
"""Gates for the read-only VPS git-reconciliation workflow (step 1)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def main() -> int:
    wf = (ROOT / ".github" / "workflows" / "vps-git-reconciliation.yml").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "vps_git_recon_readonly.sh").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "SERVER_GIT_RECONCILIATION.md").read_text(encoding="utf-8")
    deploy = (ROOT / ".github" / "workflows" / "deploy-vps.yml").read_text(encoding="utf-8")

    on_block = wf.split("jobs:")[0]
    check("workflow_dispatch" in on_block, "workflow is manually dispatched")
    check("push:" not in on_block, "on: block has no push")
    check("schedule:" not in on_block, "on: block has no schedule")
    check("secrets.VPS_HOST" in wf and "secrets.VPS_SSH_KEY" in wf,
          "reuses deploy-vps.yml SSH secrets")
    check("secrets.VPS_HOST" in deploy and "secrets.VPS_SSH_KEY" in deploy,
          "deploy-vps.yml still owns those secret names")
    check("root@" in wf, "SSH target is root@VPS_HOST")
    check("/var/www/pepperoni/repo" in script, "script inspects the VPS repo path")
    check("upload-artifact" in wf, "report is uploaded as an artifact")
    check("vps-git-reconciliation" in wf, "artifact name is vps-git-reconciliation")
    check("git-status-porcelain" in script and "git diff --stat" in script,
          "script collects porcelain status and diff stat")
    check("crontab -l" in script, "script dumps crontab")
    check("systemctl list-timers" in script, "script lists systemd timers")
    check("mtimes" in script or "stat --printf" in script, "script records mtimes")

    mutating = [
        r"git\s+add\b", r"git\s+commit\b", r"git\s+reset\b", r"git\s+checkout\b",
        r"git\s+clean\b", r"git\s+stash\b", r"git\s+pull\b", r"git\s+push\b",
        r"git\s+rebase\b", r"git\s+merge\b", r"rm\s+-rf\s+/var/www/pepperoni/repo",
    ]
    for pat in mutating:
        check(not re.search(pat, script), f"script has no mutating `{pat}`")
    check("OUTDIR must not be inside" in script or "must not be inside" in script,
          "script refuses to write into the repo")

    check("PR #15" in docs or "pull/15" in docs, "docs mention open PR #15")
    check("generated-by-cron" in docs and "should-be-in-git" in docs and "junk" in docs,
          "docs define the three classification buckets")
    check("cron" in docs.lower() and "stays" in docs.lower(),
          "docs say cron stays on until another catalog writer exists")
    check("Do not merge PR #15" in docs,
          "docs say not to merge #15 as a dump of VPS dirt")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
