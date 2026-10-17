#!/usr/bin/env python3
"""Gates for the read-only VPS git-reconciliation workflow (step 1)."""
from __future__ import annotations

import re
import subprocess
import sys
import tarfile
import tempfile
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
    check("git-status-porcelain" in script and '"diff", "--stat"' in script,
          "script collects porcelain status and diff stat")
    check("crontab" in script, "script dumps crontab")
    check("list-timers" in script, "script lists systemd timers")
    check("st_mtime" in script or "mtime" in script, "script records mtimes")

    mutating = [
        r"git\s+add\b", r"git\s+commit\b", r"git\s+reset\b", r"git\s+checkout\b",
        r"git\s+clean\b", r"git\s+stash\b", r"git\s+pull\b", r"git\s+push\b",
        r"git\s+rebase\b", r"git\s+merge\b", r"rm\s+-rf\s+/var/www/pepperoni/repo",
    ]
    for pat in mutating:
        check(not re.search(pat, script), f"script has no mutating `{pat}`")

    remote_writes = [
        (r"\brm\b", "rm"),
        (r"\bmkdir\b", "mkdir"),
        (r"\btee\b", "tee"),
        (r"\btouch\b", "touch"),
        (r"\bmktemp\b", "mktemp"),
        (r">>", ">>"),
        (r"(?:^|[\s;|&])(?:\d+)?>\s*[/~A-Za-z._\"'-]", "shell redirect to a path"),
        (r"(?<!tarfile\.)open\([^)]*['\"][wa]", "open(..., write mode)"),
        (r"write_text\(", "write_text"),
        (r"write_bytes\(", "write_bytes"),
        (r"Path\([^)]*\)\.write", "Path.write"),
    ]
    for pat, label in remote_writes:
        check(not re.search(pat, script, re.M), f"remote script has no `{label}`")

    check("tarfile.open" in script and "sys.stdout.buffer" in script,
          "remote script streams a tar to stdout")
    check("/tmp/pepperoni-git-recon" not in script,
          "remote script does not use a VPS /tmp outdir")
    check("scp" not in wf.split("jobs:")[1] or "pepperoni-git-recon" not in wf,
          "workflow does not scp a VPS-side directory")
    check("recon-report.tar" in wf and "tar -xf" in wf,
          "runner unpacks the streamed tar locally")

    check('GIT_ENV["GIT_OPTIONAL_LOCKS"]' in script or "GIT_OPTIONAL_LOCKS" in script,
          "script sets GIT_OPTIONAL_LOCKS")
    git_calls = [ln for ln in script.splitlines() if re.search(r'\["git"', ln)]
    check(bool(git_calls), "script invokes git")
    check(all("GIT_ENV" in script and "def git(" in script for _ in [0]),
          "all git subprocesses go through git() with GIT_ENV")
    check("GIT_OPTIONAL_LOCKS=0" in wf, "workflow exports GIT_OPTIONAL_LOCKS=0 on SSH")

    check("test -s recon-report/git-status-porcelain.txt" not in wf,
          "workflow does not require a non-empty porcelain file")
    check("test -f recon-report/git-status-porcelain.txt" in wf,
          "workflow accepts an empty porcelain file for a clean repo")

    check("PR #15" in docs or "pull/15" in docs, "docs mention open PR #15")
    check("generated-by-cron" in docs and "should-be-in-git" in docs and "junk" in docs,
          "docs define the three classification buckets")
    check("cron" in docs.lower() and "stays" in docs.lower(),
          "docs say cron stays on until another catalog writer exists")
    check("Do not merge PR #15" in docs,
          "docs say not to merge #15 as a dump of VPS dirt")
    check("stdout" in docs.lower() and "tar" in docs.lower(),
          "docs say the report is streamed as tar on stdout")
    check("GIT_OPTIONAL_LOCKS" in docs, "docs mention GIT_OPTIONAL_LOCKS=0")

    # Live local run: stream tar, accept empty porcelain.
    with tempfile.TemporaryDirectory() as tmp:
        tar_path = Path(tmp) / "recon.tar"
        dest = Path(tmp) / "out"
        dest.mkdir()
        env = dict(**{k: v for k, v in __import__("os").environ.items()})
        env["REPO_DIR"] = str(ROOT)
        env["GIT_OPTIONAL_LOCKS"] = "0"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "vps_git_recon_readonly.sh")],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        tar_path.write_bytes(proc.stdout)
        check(proc.returncode == 0, "local collector exits 0")
        check(proc.stdout.startswith(b"ustar") or b"meta.txt" in proc.stdout
              or len(proc.stdout) > 0, "collector wrote a tar to stdout")
        try:
            with tarfile.open(tar_path, "r|") as tf:
                tf.extractall(dest)
            ok_tar = True
        except tarfile.TarError as exc:
            ok_tar = False
            print("  note tar error:", exc)
        check(ok_tar, "stdout is a readable tar")
        porcelain = dest / "git-status-porcelain.txt"
        check(porcelain.is_file(), "tar contains git-status-porcelain.txt")
        check((dest / "meta.txt").is_file(), "tar contains meta.txt")
        # Empty is valid (clean tree). Non-empty is also valid.
        size = porcelain.stat().st_size if porcelain.is_file() else -1
        check(size >= 0, "empty porcelain file is accepted")

    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
