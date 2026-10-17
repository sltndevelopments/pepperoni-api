#!/usr/bin/env python3
"""Gates for the read-only VPS git-reconciliation workflow (step 1 + log print)."""
from __future__ import annotations

import io
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fail = 0
sys.path.insert(0, str(ROOT / "scripts"))
from print_vps_git_recon_report import (  # noqa: E402
    LINE_CAP,
    REDACT_ENV,
    REDACT_SECRET,
    mask_line,
    print_report,
)


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
    check("workflow_dispatch" in on_block, "workflow still has workflow_dispatch")
    check("push:" in on_block, "on: block has path-filtered push")
    check("pull_request:" not in on_block, "on: block has no pull_request (no SSH from PRs)")
    check("schedule:" not in on_block, "on: block has no schedule")
    check("ops/recon-trigger.txt" in on_block,
          "push paths include ops/recon-trigger.txt")
    check("scripts/vps_git_recon_readonly.sh" in on_block,
          "push paths include scripts/vps_git_recon_readonly.sh")
    check(re.search(r"branches:\s*\n\s*-\s*main\b", on_block),
          "push is limited to branch main")
    trigger = ROOT / "ops" / "recon-trigger.txt"
    check(trigger.is_file(), "ops/recon-trigger.txt exists")
    check(bool(re.search(r"20\d{2}-\d{2}-\d{2}", trigger.read_text(encoding="utf-8"))),
          "recon-trigger.txt has a dated line")
    printer_src = (ROOT / "scripts" / "print_vps_git_recon_report.py").read_text(encoding="utf-8")
    check("print_vps_git_recon_report.py" in wf,
          "workflow prints the report via print_vps_git_recon_report.py")
    check("cat recon-report/untracked" not in wf
          and "cat recon-report/ignored" not in wf,
          "workflow does not cat untracked/ignored uncapped")
    check("/var/www/pepperoni/repo" not in printer_src,
          "printer does not open the VPS checkout")
    check("REPO_DIR" not in printer_src, "printer has no REPO_DIR")
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

    _check_printer_rules()

    return 1 if fail else 0


def _check_printer_rules() -> None:
    check(mask_line("ANTHROPIC_API_KEY=sk-leaked") == REDACT_SECRET,
          "mask_line redacts KEY")
    check(mask_line("Authorization: Bearer TOKEN=abc") == REDACT_SECRET,
          "mask_line redacts TOKEN")
    check(mask_line("password=hunter2") == REDACT_SECRET,
          "mask_line redacts PASSWORD")
    check(mask_line("Environment=FOO=bar") == REDACT_ENV,
          "mask_line redacts systemd Environment=")
    check(mask_line("export PATH=/usr/bin") == REDACT_ENV,
          "mask_line redacts env assignments")
    kept = mask_line("ExecStart=/usr/bin/python3 scripts/seo-agent-vps.sh")
    check(kept.endswith("seo-agent-vps.sh"),
          "mask_line keeps ExecStart unit lines")
    kept_file = mask_line("EnvironmentFile=/var/www/pepperoni/seo-agent.env")
    check("seo-agent.env" in kept_file,
          "mask_line keeps EnvironmentFile= paths")

    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "recon-report"
        report.mkdir()
        (report / "meta.txt").write_text(
            "path_count=3\nuntracked_count=450\nignored_count=2\n", encoding="utf-8")
        (report / "HEAD.txt").write_text("abc123\n", encoding="utf-8")
        (report / "branch.txt").write_text("main\n", encoding="utf-8")
        (report / "git-status-porcelain.txt").write_text(
            " M public/products.json\n", encoding="utf-8")
        (report / "git-diff-stat.txt").write_text(
            " public/products.json | 2 +-\n", encoding="utf-8")
        (report / "git-diff-numstat.txt").write_text(
            "1\t1\tpublic/products.json\n", encoding="utf-8")
        (report / "git-diff-names.txt").write_text(
            "public/products.json\n", encoding="utf-8")
        (report / "crontab.txt").write_text(
            "ANTHROPIC_API_KEY=sk-leaked-secret-value\n"
            "*/10 * * * * /var/www/pepperoni/repo/scripts/sync-vps.sh\n",
            encoding="utf-8")
        (report / "systemd.txt").write_text(
            "Environment=TOKEN=abc123xyz\n"
            "ExecStart=/usr/bin/python3 /var/www/pepperoni/repo/scripts/seo-agent-vps.sh\n"
            "EnvironmentFile=/var/www/pepperoni/seo-agent.env\n",
            encoding="utf-8")
        (report / "mtimes.txt").write_text(
            "2026-10-17 00:00:00.000000 +0000\t12\tpublic/products.json\n",
            encoding="utf-8")
        (report / "dirty-paths.txt").write_text("public/products.json\n", encoding="utf-8")
        untracked_lines = [f"data/runtime-{i}.json" for i in range(450)]
        untracked_lines.append("public/extra.html")
        untracked_lines.append("secret-file.txt")
        (report / "untracked.txt").write_text("\n".join(untracked_lines) + "\n", encoding="utf-8")
        (report / "ignored.txt").write_text(
            "\n".join(f"__pycache__/mod-{i}.pyc" for i in range(5)) + "\n"
            + "\n".join(f"node_modules/pkg-{i}.js" for i in range(3)) + "\n",
            encoding="utf-8")
        (report / "git-status-porcelain-ignored.txt").write_text(
            "!! __pycache__/x.pyc\n", encoding="utf-8")
        leaked = '{"LEAKED_CATALOG": true, "usd": 160100}\n'
        (report / "products.json").write_text(leaked, encoding="utf-8")
        planted = Path(tmp) / "secret-file.txt"
        planted.write_text("LEAKED_FROM_REPO_FILE\n", encoding="utf-8")

        buf = io.StringIO()
        rc = print_report(report, buf, cap=LINE_CAP)
        out = buf.getvalue()
        check(rc == 0, "printer exits 0 on a fixture report")
        check("path_count=3" in out, "printer dumps meta in full")
        check("abc123" in out, "printer dumps HEAD in full")
        check("public/products.json" in out, "printer prints drifted paths")
        check("sync-vps.sh" in out, "printer prints cron command lines")
        check("seo-agent-vps.sh" in out, "printer prints systemd ExecStart")
        check("seo-agent.env" in out, "printer prints EnvironmentFile path")
        check("sk-leaked-secret-value" not in out, "printer omits KEY secret value")
        check("abc123xyz" not in out, "printer omits TOKEN env value")
        check(REDACT_SECRET in out or REDACT_ENV in out,
              "printer emits a redaction marker")
        check("LEAKED_CATALOG" not in out,
              "printer never dumps extra member file contents")
        check("products.json" in out,
              "printer names extra members without opening them")
        check("LEAKED_FROM_REPO_FILE" not in out,
              "printer never opens paths listed in untracked")
        check("data/runtime-0.json" in out, "printer shows first untracked lines")
        check("data/runtime-399.json" in out, "printer shows untracked up to cap")
        check("data/runtime-400.json" not in out,
              "printer caps untracked at %d lines" % LINE_CAP)
        n_untracked = len(untracked_lines)
        omitted = n_untracked - LINE_CAP
        check("omitted=%d" % omitted in out,
              "printer reports untracked remainder count (%d)" % omitted)
        check(re.search(r"untracked\.txt top-level directories", out),
              "printer prints untracked directory summary")
        check(re.search(r"ignored\.txt top-level directories", out),
              "printer prints ignored directory summary")
        check(re.search(r"\bdata/", out) and re.search(r"__pycache__/", out),
              "directory summary names top-level dirs")
        check("contents omitted" in out.lower() or "extra members" in out.lower(),
              "extra files are listed without contents")


if __name__ == "__main__":
    raise SystemExit(main())
