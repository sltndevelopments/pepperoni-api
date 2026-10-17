#!/usr/bin/env python3
"""Static and fixture gates for the one-time VPS cleanup. No network."""
from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vps_cleanup.sh"
RESOLVE = ROOT / "scripts" / "vps_cleanup_resolve_mode.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "vps-cleanup.yml"
DEPLOY = ROOT / ".github" / "workflows" / "deploy-vps.yml"
RECON = ROOT / ".github" / "workflows" / "vps-git-reconciliation.yml"

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def _names_in_find(text: str) -> list[str]:
    return re.findall(r"""-name\s+['"]([^'"]+)['"]""", text)


def _resolve(status_lines: str) -> str:
    proc = subprocess.run(
        ["bash", str(RESOLVE)],
        input=status_lines,
        text=True,
        capture_output=True,
        cwd=str(ROOT),
    )
    check(proc.returncode == 0, f"resolver exits 0 for {status_lines!r}")
    return proc.stdout.strip()


def main() -> int:
    script = SCRIPT.read_text(encoding="utf-8")
    wf = WORKFLOW.read_text(encoding="utf-8")
    deploy = DEPLOY.read_text(encoding="utf-8")
    recon = RECON.read_text(encoding="utf-8")

    check("set -euo pipefail" in script, "script uses set -euo pipefail")
    check("umask 077" in script, "umask 077 at the top")
    check('MODE="${MODE:-${1:-dry-run}}"' in script, "default mode is dry-run")
    check("/var/www/pepperoni/repo/data/sync.lock" in script,
          "uses the requested lock path")
    check('exec 9<"$LOCK_FILE"' in script, "opens the lock read-only")
    check("lock missing" in script, "missing lock prints lock missing")
    check("flock -w 900" in script, "flock waits 900 s")
    check("backup failed, no changes" in script, "backup failure uses the fixed line")
    check("chmod 700 \"$BACKUP_DIR\"" in script, "backup dir chmod 700")
    check(".tmp" in script and "mv \"" in script, "backup writes .tmp then mv")
    check("if ! do_backup" not in script, "do_backup is not under if !")
    check("backup_rc=$?" in script, "captures do_backup rc")
    check("grep -RIlF" in script or "grep -IlF" in script,
          "item 6 uses grep -IlF text-only")
    check("grep -rlFZ" not in script, "item 6 no longer uses grep -rlFZ")
    check("apply_delete_manifest" in script, "apply deletes from the frozen manifest")
    check("find \"$REPO/data/tmp\" -depth -type d -empty -delete" in script,
          "empty tmp dirs deleted after manifest rm")

    apply_guard = script.find('if [[ "$MODE" != "apply" ]]')
    backup_call = script.find("\ndo_backup\n")
    check(apply_guard != -1 and backup_call != -1 and apply_guard < backup_call,
          "dry-run exits before backup")
    dry_chunk = script[apply_guard:backup_call]
    check("exit 0" in dry_chunk, "dry-run path exits 0")
    check("mkdir" not in dry_chunk, "dry-run chunk has no mkdir")
    check("apply_installs" not in dry_chunk, "dry-run chunk does not call apply")
    check("rm -f" not in dry_chunk and "sed -i" not in dry_chunk,
          "dry-run chunk has no rm/sed")

    apply_fn = script.find("apply_installs()")
    check(apply_fn != -1, "apply_installs function exists")
    check(script.find("do_backup()") < apply_fn, "do_backup() is defined before apply")
    check(script.find("sed -i") > apply_fn, "sed -i is inside apply_*")
    check(script.find("install -m 600") > apply_fn, "install -m 600 is inside apply_*")
    check(script.find("tar czf") > script.find("do_backup()"),
          "tar czf is inside do_backup")
    check("no crontab" in script, "crontab dumps tell no crontab from a read error")

    names = _names_in_find(script)
    check("agent.bak.*.db" in names, "item 4 names agent.bak.*.db")
    check("agent.db.backup-*" in names, "item 4 names agent.db.backup-*")
    check(all(not fnmatch.fnmatch("agent.db", pat) for pat in names),
          "find -name globs do not match agent.db")
    check("agent.db*" not in script, "script has no agent.db* glob")

    check(not re.search(r"\bcat\s+[\"']?\$", script), "no cat of a variable path")
    check("cat \"" not in script and "cat '" not in script, "no cat of a quoted path")
    check("echo \"$MCP" not in script and "echo \"$OLD" not in script,
          "no echo of env-path values")
    check("echo \"$p\"" not in script and "echo $p" not in script,
          "no echo of path loop variables")
    check("systemctl restart" in script and ">/dev/null" in script,
          "unit restart is quiet")

    on_block = wf.split("jobs:")[0]
    check("workflow_dispatch" in on_block, "workflow_dispatch exists")
    check("ops/cleanup-dryrun-trigger.txt" in on_block, "dry-run trigger path")
    check("ops/cleanup-apply-trigger.txt" in on_block, "apply trigger path")
    check("default: dry-run" in on_block, "dispatch default is dry-run")
    check("group: vps-recon" in wf, "concurrency group is vps-recon")
    check("cancel-in-progress: false" in wf, "does not cancel in-progress")
    check("group: deploy-vps" not in wf, "never uses deploy-vps group")
    check("group: deploy-vps" in deploy, "deploy still owns deploy-vps")
    check("group: vps-recon" in recon, "recon still owns vps-recon")
    check(re.search(r"(?m)^\s*actions:\s*read\s*$", wf), "actions: read")
    check("secrets.VPS_HOST" in wf and "secrets.VPS_SSH_KEY" in wf,
          "only the two SSH secrets")
    check(re.search(r"ssh\s+-q\s+-o\s+BatchMode=yes\b", wf), "ssh -q BatchMode")
    check("2>/dev/null" in wf, "ssh stderr hidden")
    check("vps-cleanup: ssh failed" in wf, "fixed ssh failure line")
    check("status=in_progress" in wf, "skip checks deploy in_progress")
    check("vps-cleanup: skip, deploy in_progress" in wf, "skip prints a fixed line")
    check('"$rem" -ge 2' in wf and '"$rem" -le 8' in wf, "minute guard 2..8")
    check("sleep 15" in wf and "+ 180" in wf, "minute guard cap 3 min")
    check(wf.find("status=in_progress") < wf.find("ssh -q"),
          "deploy skip precedes SSH")
    check("--name-status" in wf, "resolve mode uses git diff --name-status")
    check("vps_cleanup_resolve_mode.sh" in wf, "workflow calls the mode resolver")
    check("mode=none" in wf or "mode == 'dry-run'" in wf,
          "SSH runs only for dry-run or apply")
    check("steps.mode.outputs.mode == 'dry-run'" in wf and
          "steps.mode.outputs.mode == 'apply'" in wf,
          "SSH step requires an explicit dry-run or apply mode")
    check((ROOT / "ops/cleanup-dryrun-trigger.txt").is_file(), "dry-run trigger file exists")
    check((ROOT / "ops/cleanup-apply-trigger.txt").is_file(), "apply trigger file exists")
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    check("data/buyer_baseline_trust_reset_*" in ignore,
          "gitignore has buyer_baseline_trust_reset_*")
    readme = (ROOT / "infra/README.md").read_text(encoding="utf-8")
    check("/var/www/pepperoni/repo/infra/scripts/parse-ai-bots.py" in readme,
          "README uses the live repo path")
    check("/opt/pepperoni-api/" not in readme, "README has no old prefix")

    check(_resolve("A\tops/cleanup-dryrun-trigger.txt\n") == "none",
          "added dry-run trigger is none")
    check(_resolve("A\tops/cleanup-apply-trigger.txt\n") == "none",
          "added apply trigger is none")
    check(
        _resolve(
            "A\tops/cleanup-dryrun-trigger.txt\nA\tops/cleanup-apply-trigger.txt\n"
        ) == "none",
        "merge adding both triggers is none",
    )
    check(_resolve("M\tops/cleanup-dryrun-trigger.txt\n") == "dry-run",
          "modified dry-run trigger is dry-run")
    check(_resolve("M\tops/cleanup-apply-trigger.txt\n") == "apply",
          "modified apply trigger is apply")
    check(_resolve("M\tops/cleanup-apply-trigger.txt\nM\tREADME.md\n") == "apply",
          "modified apply trigger plus other files is apply")
    check(_resolve("M\tops/cleanup-dryrun-trigger.txt\nM\tops/cleanup-apply-trigger.txt\n")
          == "dry-run",
          "both triggers modified prefers dry-run")

    check("test_vps_cleanup.py" in {p.name for p in (ROOT / "scripts").glob("test_*.py")},
          "test file is auto-discovered")

    _fixture()
    if fail:
        print(f"test_vps_cleanup: {fail} FAIL")
        return 1
    print("test_vps_cleanup: ok")
    return 0


def _run(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **env}
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=merged,
    )


def _fixture() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        repo = base / "repo"
        cron_d = base / "cron.d"
        etc_pep = base / "pepperoni"
        systemd = base / "systemd"
        spool = base / "spool"
        supervisor = base / "supervisor"
        root_cfg = base / "root-config"
        backups = base / "backups"
        lock = base / "sync.lock"
        for d in (
            repo / "scripts",
            repo / "data" / "tmp" / "nested",
            repo / "data" / "quarantine",
            repo / "data" / "logs",
            repo / "sales-agent" / "data",
            repo / "infra" / "scripts",
            repo / "deploy",
            cron_d,
            etc_pep,
            systemd,
            spool,
            supervisor,
            root_cfg,
        ):
            d.mkdir(parents=True, exist_ok=True)
        lock.write_bytes(b"")
        (repo / "scripts" / "_wtest").write_bytes(b"")
        (repo / "data" / "tmp" / "stale").write_text("x", encoding="utf-8")
        (repo / "data" / "tmp" / "link").symlink_to(repo / "data" / "tmp" / "stale")
        (repo / "data" / "quarantine_baseline.json").write_text("{}", encoding="utf-8")
        old_q = repo / "data" / "quarantine" / "old.html"
        old_q.write_text("q", encoding="utf-8")
        os.utime(old_q, (0, 0))
        (repo / "data" / "quarantine" / "fresh.html").write_text("n", encoding="utf-8")
        old_log = repo / "data" / "logs" / "old.log"
        old_log.write_text("l", encoding="utf-8")
        os.utime(old_log, (0, 0))
        keep_db = repo / "sales-agent" / "data" / "agent.db"
        keep_db.write_text("live", encoding="utf-8")
        (repo / "sales-agent" / "data" / "agent.bak.1.db").write_text("b", encoding="utf-8")
        (repo / "sales-agent" / "data" / "agent.db.backup-1").write_text("b2", encoding="utf-8")
        (repo / "infra" / "scripts" / "parse-ai-bots.py").write_text("# ok\n", encoding="utf-8")
        mcp = repo / "deploy" / "rinatsultan-mcp.env"
        mcp.write_text("PLACEHOLDER=1\n", encoding="utf-8")
        unit = systemd / "demo.service"
        unit.write_text(
            f"EnvironmentFile={repo}/deploy/rinatsultan-mcp.env\n",
            encoding="utf-8",
        )
        (cron_d / "pepperoni-ai-bots").write_text(
            "5 6 * * * root /usr/bin/python3 /opt/pepperoni-api/infra/scripts/parse-ai-bots.py\n",
            encoding="utf-8",
        )

        env = {
            "MODE": "dry-run",
            "REPO": str(repo),
            "LOCK_FILE": str(lock),
            "BACKUP_DIR": str(backups),
            "CRON_D": str(cron_d),
            "ETC_PEPPERONI": str(etc_pep),
            "SYSTEMD_DIR": str(systemd),
            "CRON_SPOOL": str(spool),
            "SUPERVISOR_DIR": str(supervisor),
            "ROOT_CONFIG": str(root_cfg),
            "OLD_ROOT": str(base / "opt-missing"),
            "MCP_SRC": str(mcp),
            "MCP_DST": str(etc_pep / "rinatsultan-mcp.env"),
            "AI_BOTS_CRON": str(cron_d / "pepperoni-ai-bots"),
            "LOG_CRON": str(cron_d / "pepperoni-log-retention"),
        }

        missing = dict(env)
        missing["LOCK_FILE"] = str(base / "no-such-lock")
        miss = _run(missing)
        check(miss.returncode != 0, "missing lock exits nonzero")
        check("lock missing" in miss.stderr, "missing lock prints lock missing")

        dry = _run(env)
        check(dry.returncode == 0, f"fixture dry-run exits 0 ({dry.stderr.strip()})")
        out = dry.stdout
        check("backup would include" in out, "dry-run reports backup would include")
        check(keep_db.read_text(encoding="utf-8") == "live", "dry-run leaves agent.db")
        check(mcp.is_file(), "dry-run does not move the env file")
        check(not backups.exists() or not list(backups.glob("cleanup-*.tar.gz")),
              "dry-run writes no backup")
        check(not backups.exists(), "dry-run does not mkdir the backup dir")
        check("/opt/pepperoni-api/" in (cron_d / "pepperoni-ai-bots").read_text(encoding="utf-8"),
              "dry-run does not rewrite cron")
        for line in out.splitlines():
            check("agent.db" not in line, "dry-run log has no agent.db name")
            check("rinatsultan" not in line, "dry-run log has no env filename")
            check("PLACEHOLDER" not in line, "dry-run log has no env value")
            check("demo.service" not in line, "dry-run log has no unit name")

        env["MODE"] = "apply"
        applied = _run(env)
        check(applied.returncode == 0, f"fixture apply exits 0 ({applied.stderr.strip()})")
        check("backup:" in applied.stdout and "bytes" in applied.stdout,
              "apply prints backup size")
        check(not (repo / "scripts" / "_wtest").exists(), "apply removes empty _wtest")
        check(not (repo / "data" / "tmp" / "stale").exists(), "apply empties tmp files")
        check(not (repo / "data" / "tmp" / "link").exists(), "apply removes tmp symlink")
        check(not old_q.exists(), "apply deletes old quarantine file")
        check((repo / "data" / "quarantine" / "fresh.html").is_file(),
              "apply keeps recent quarantine file")
        check((repo / "data" / "quarantine_baseline.json").is_file(),
              "apply keeps quarantine baseline")
        check(not old_log.exists(), "apply deletes old log")
        check(keep_db.is_file() and keep_db.read_text(encoding="utf-8") == "live",
              "apply never deletes agent.db")
        check(not (repo / "sales-agent" / "data" / "agent.bak.1.db").exists(),
              "apply deletes agent.bak.*.db")
        check(not mcp.exists(), "apply removes env source after cmp")
        check((etc_pep / "rinatsultan-mcp.env").is_file(), "apply installs env dest")
        cron = (cron_d / "pepperoni-ai-bots").read_text(encoding="utf-8")
        check("/var/www/pepperoni/repo/" in cron, "apply rewrites ai-bots cron")
        check("/opt/pepperoni-api/" not in cron, "apply cron has no old prefix")
        check((cron_d / "pepperoni-log-retention").is_file(), "apply writes log cron")
        tars = list(backups.glob("cleanup-*.tar.gz"))
        check(len(tars) == 1, "apply wrote one backup archive")
        if tars:
            check(oct(tars[0].stat().st_mode & 0o777) == "0o600", "backup is mode 600")
            check(not tars[0].name.endswith(".tmp"), "backup is not left as .tmp")

        env["MODE"] = "dry-run"
        after = _run(env)
        check(after.returncode == 0, "post-apply dry-run exits 0")
        zeros = re.findall(r"^(\d): (\d+) files, (\d+) bytes$", after.stdout, re.M)
        check(zeros and all(n == "0" and b == "0" for _, n, b in zeros),
              f"post-apply dry-run is zeros ({zeros})")
        check(keep_db.read_text(encoding="utf-8") == "live",
              "agent.db still intact after apply")


if __name__ == "__main__":
    raise SystemExit(main())
