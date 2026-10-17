#!/usr/bin/env python3
"""Gates for the public-safe VPS git-reconciliation workflow."""
from __future__ import annotations

import io
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fail = 0
sys.path.insert(0, str(ROOT / "scripts"))
from print_vps_git_recon_report import (  # noqa: E402
    COUNT_KEYS,
    counts_from_tar_bytes,
    format_counts,
    print_counts,
)
from seal_vps_git_recon import encrypt_to_age  # noqa: E402


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def _tar_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w|") as tf:
        for name, text in files.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = stat.S_IRUSR | stat.S_IWUSR
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


PLANTED_PATHS = (
    "public/products.json",
    "/var/www/pepperoni/repo",
    "scripts/sync-vps.sh",
    "data/runtime-secret.json",
    "seo-agent.env",
)
PLANTED_SECRETS = (
    "sk-leaked-secret-value",
    "LEAKED_CATALOG",
    "LEAKED_FROM_REPO_FILE",
)


def _fixture_tar() -> bytes:
    return _tar_bytes({
        "meta.txt": (
            "# pepperoni VPS git reconciliation (READ-ONLY)\n"
            "host=selectel-prod.example\n"
            "repo=/var/www/pepperoni/repo\n"
            "path_count=3\n"
            "untracked_count=12\n"
            "ignored_count=4\n"
            "modified_tracked_count=2\n"
        ),
        "HEAD.txt": "deadbeefcafebabe\n",
        "branch.txt": "main\n",
        "git-status-porcelain.txt": " M public/products.json\n",
        "untracked.txt": "data/runtime-secret.json\npublic/extra.html\n",
        "ignored.txt": "seo-agent.env\n__pycache__/x.pyc\n",
        "git-diff-names.txt": "public/products.json\nscripts/sync-vps.sh\n",
        "crontab.txt": (
            "=== crontab -l ===\n"
            "ANTHROPIC_API_KEY=sk-leaked-secret-value\n"
            "*/10 * * * * /var/www/pepperoni/repo/scripts/sync-vps.sh\n"
            "# comment only\n"
            "(no /etc/cron.d files)\n"
        ),
        "systemd.txt": (
            "=== systemctl list-timers --all ===\n"
            "seo-agent.timer  /var/www/pepperoni/repo/scripts/seo-agent-vps.sh\n"
            "----- /etc/systemd/system/seo-agent.service -----\n"
            "ExecStart=/usr/bin/python3 /var/www/pepperoni/repo/scripts/seo-agent-vps.sh\n"
        ),
        "mtimes.txt": "2026-10-17 00:00:00.000000 +0000\t12\tpublic/products.json\n",
        "dirty-paths.txt": "public/products.json\n",
        "products.json": '{"LEAKED_CATALOG": true}\n',
    })


def main() -> int:
    wf = (ROOT / ".github" / "workflows" / "vps-git-reconciliation.yml").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "vps_git_recon_readonly.sh").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "SERVER_GIT_RECONCILIATION.md").read_text(encoding="utf-8")
    deploy = (ROOT / ".github" / "workflows" / "deploy-vps.yml").read_text(encoding="utf-8")
    sealer = (ROOT / "scripts" / "seal_vps_git_recon.py").read_text(encoding="utf-8")
    printer = (ROOT / "scripts" / "print_vps_git_recon_report.py").read_text(encoding="utf-8")
    pub = (ROOT / "ops" / "recon-age.pub").read_text(encoding="utf-8").strip()

    on_block = wf.split("jobs:")[0]
    check("workflow_dispatch" in on_block, "workflow still has workflow_dispatch")
    check("push:" in on_block, "on: block has path-filtered push")
    check("pull_request:" not in on_block, "on: block has no pull_request (no SSH from PRs)")
    check("schedule:" not in on_block, "on: block has no schedule")
    check("ops/recon-trigger.txt" in on_block,
          "push paths include ops/recon-trigger.txt")
    check("scripts/vps_git_recon_readonly.sh" not in on_block,
          "collector edits do not trigger a prod SSH")
    check(re.search(r"branches:\s*\n\s*-\s*main\b", on_block),
          "push is limited to branch main")
    trigger = ROOT / "ops" / "recon-trigger.txt"
    check(trigger.is_file(), "ops/recon-trigger.txt exists")
    check(bool(re.search(r"20\d{2}-\d{2}-\d{2}", trigger.read_text(encoding="utf-8"))),
          "recon-trigger.txt has a dated line")

    recon_group = re.search(r"(?m)^\s*group:\s*(\S+)\s*$", wf)
    deploy_group = re.search(r"(?m)^\s*group:\s*(\S+)\s*$", deploy)
    check(bool(recon_group) and bool(deploy_group),
          "both workflows declare a concurrency group")
    check(recon_group and deploy_group and recon_group.group(1) != deploy_group.group(1),
          "recon and deploy concurrency groups differ")
    check("group: vps-recon" in wf, "recon uses group vps-recon")
    check("group: deploy-vps" in deploy, "deploy uses group deploy-vps")
    check("vps-pepperoni" not in wf and "vps-pepperoni" not in deploy,
          "shared vps-pepperoni group is gone")
    check("cancel-in-progress: false" in wf and "cancel-in-progress: false" in deploy,
          "neither group cancels an in-progress run")
    check(re.search(r"(?m)^\s*actions:\s*read\s*$", wf),
          "recon has actions: read to poll deploy runs")
    check("github.token" in wf and "github.repository" in wf,
          "poll step uses github.token and github.repository")
    check("deploy-vps.yml/runs" in wf and "per_page=1" in wf,
          "poll queries deploy-vps.yml runs")
    check(all(s in wf for s in ("queued", "in_progress", "waiting", "pending", "requested")),
          "poll sums queued/in_progress/waiting/pending/requested")
    check("+ 600" in wf, "poll has a 600 s deadline")
    check("vps-git-reconciliation: deploy still active after 10 min" in wf,
          "timeout prints a fixed message")
    check(wf.find("deploy-vps.yml/runs") < wf.find("ssh -q"),
          "poll step precedes SSH")
    check("sleep 60" not in wf, "recon has no sleep 60")
    check("sleep 90" not in wf, "recon has no one-shot sleep 90")
    wait_step = wf.split("Collect, count, and encrypt")[0]
    check("sleep 15" not in wait_step,
          "deploy-wait step has no minute guard")
    check("sleep 15" in wf and "+ 180" in wf,
          "minute guard loops with sleep 15 and a 3 min cap")
    check('"$rem" -ge 2' in wf and '"$rem" -le 8' in wf,
          "minute guard waits until rem is 2..8")
    check(wf.find("sleep 15") < wf.find("ssh -q") and
          wf.rfind("sleep 15", 0, wf.find("ssh -q")) > wf.find("trap"),
          "minute guard is immediately before SSH")

    check("secrets.VPS_HOST" in wf and "secrets.VPS_SSH_KEY" in wf,
          "reuses deploy-vps.yml SSH secrets")
    check("secrets.VPS_HOST" in deploy and "secrets.VPS_SSH_KEY" in deploy,
          "deploy-vps.yml still owns those secret names")
    check("root@" in wf, "SSH target is root@VPS_HOST")
    check("/var/www/pepperoni/repo" in script, "script inspects the VPS repo path")

    check("apt-get install -y age" in wf or "apt-get install -y age" in wf.replace('"', ""),
          "workflow installs age")
    check("seal_vps_git_recon.py" in wf, "workflow seals via seal_vps_git_recon.py")
    check("ops/recon-age.pub" in wf, "workflow uses the committed recipient")
    check(pub == "age1uq55jgysck9tu0g4znardz3a8splzuxvqmpgvnxdcg2wktv4rcssnzks2d",
          "committed recipient is the requested age public key")
    check("recon-report.tar.age" in wf, "workflow writes the .age ciphertext")
    check(re.search(r"path:\s*recon-report\.tar\.age\s*$", wf, re.M),
          "upload-artifact path is only the .age file")
    check(not re.search(r"path:\s*recon-report/?\s*$", wf, re.M),
          "workflow does not upload a plaintext recon-report/ directory")
    check("tar -x" not in wf and "tar -xf" not in wf,
          "workflow does not unpack the tar on the runner")
    check(not re.search(r">\s*recon-report\.tar\s*$", wf, re.M),
          "workflow does not redirect SSH stdout to a plaintext tar")
    check("cat recon-report" not in wf, "workflow does not cat report files")
    check("vps-git-reconciliation" in wf, "artifact name is vps-git-reconciliation")
    check("test ! -e recon-report.tar" in wf, "workflow asserts no plaintext tar on disk")
    check("GIT_OPTIONAL_LOCKS=0" in wf, "workflow exports GIT_OPTIONAL_LOCKS=0 on SSH")
    check(re.search(r"trap\s+['\"]rm -f ~/.ssh/vps_key['\"]\s+EXIT", wf),
          "workflow trap deletes the SSH key on EXIT")
    check(re.search(r"ssh\s+-q\s+-o\s+BatchMode=yes\b", wf),
          "ssh runs with -q and BatchMode=yes")
    check("2>/dev/null" in wf, "ssh stderr is discarded (no public-log passthrough)")
    check("vps-git-reconciliation: ssh failed" in wf,
          "ssh failure prints only a fixed message")
    check('rcs=("${PIPESTATUS[@]}")' in wf,
          "workflow snapshots PIPESTATUS in one assignment")
    check("${rcs[0]}" in wf and "${rcs[1]}" in wf,
          "workflow reads ssh/seal rc from the PIPESTATUS snapshot")
    check("ssh_rc=${PIPESTATUS[0]}" not in wf and "seal_rc=${PIPESTATUS[1]}" not in wf,
          "workflow does not read PIPESTATUS[0] then [1]")
    _check_pipestatus_snapshot()
    check("age failed: %s" not in sealer,
          "sealer does not interpolate age stderr into the exit message")
    check('raise SystemExit("seal_vps_git_recon: age failed")' in sealer,
          "sealer uses a fixed age-failed message")

    check("open(" not in sealer.split("encrypt_to_age")[0] or "stdin" in sealer,
          "sealer reads the tar from stdin")
    check('["age"' in sealer or 'age, "-R"' in sealer or '"-R"' in sealer,
          "sealer invokes age -R")
    check("write_bytes" not in sealer and "write_text" not in sealer,
          "sealer has no Path.write of plaintext")
    check("tar -xf" not in sealer, "sealer does not unpack to disk")
    check("/var/www/pepperoni/repo" not in printer,
          "printer does not mention the VPS checkout")
    check("REPO_DIR" not in printer, "printer has no REPO_DIR")

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

    check('GIT_ENV["GIT_OPTIONAL_LOCKS"]' in script or "GIT_OPTIONAL_LOCKS" in script,
          "script sets GIT_OPTIONAL_LOCKS")
    git_calls = [ln for ln in script.splitlines() if re.search(r'\["git"', ln)]
    check(bool(git_calls), "script invokes git")
    check("def git(" in script and "GIT_ENV" in script,
          "all git subprocesses go through git() with GIT_ENV")

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
    check(".age" in docs and "age" in docs.lower(),
          "docs say the artifact is age-encrypted")
    check("counts" in docs.lower(), "docs say the job log is counts-only")
    check("trap" in docs.lower() and "batchmode" in docs.lower(),
          "docs mention trap + BatchMode failure hygiene")
    check("vps-recon" in docs and "deploy-vps" in docs and "sleep 60" not in docs,
          "docs mention distinct groups and no sleep 60")
    check("2..8" in docs and "sleep 15" in docs,
          "docs mention the pre-SSH minute-guard loop")

    # Live local collector: stream tar, accept empty porcelain.
    with tempfile.TemporaryDirectory() as tmp:
        tar_path = Path(tmp) / "recon.tar"
        dest = Path(tmp) / "out"
        dest.mkdir()
        env = dict(os.environ)
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
        check(len(proc.stdout) > 0, "collector wrote a tar to stdout")
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
        size = porcelain.stat().st_size if porcelain.is_file() else -1
        check(size >= 0, "empty porcelain file is accepted")

        # Counts-only printer on the live tar: no checkout paths in stdout.
        buf = io.StringIO()
        rc = print_counts(proc.stdout, buf)
        live_out = buf.getvalue()
        check(rc == 0, "printer exits 0 on a live collector tar")
        leaked_live = [p for p in ("scripts/", "public/", ".github/", str(ROOT))
                       if p in live_out]
        check(not leaked_live, "live printer stdout has no checkout paths %s" % leaked_live)

    _check_counts_and_seal()
    return 1 if fail else 0


def _check_pipestatus_snapshot() -> None:
    """Exercise the workflow's PIPESTATUS snapshot under bash set -u."""
    success = r"""
set -euo pipefail
set +e
true | true
rcs=("${PIPESTATUS[@]}")
ssh_rc=${rcs[0]}
seal_rc=${rcs[1]}
set -e
if [ "$ssh_rc" -ne 0 ]; then
  echo "vps-git-reconciliation: ssh failed" >&2
  exit 1
fi
if [ "$seal_rc" -ne 0 ]; then
  echo "vps-git-reconciliation: seal failed" >&2
  exit 1
fi
printf 'OK ssh_rc=%s seal_rc=%s\n' "$ssh_rc" "$seal_rc"
"""
    proc = subprocess.run(
        ["bash", "-c", success],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    check(proc.returncode == 0, "PIPESTATUS snapshot success path exits 0 under set -u")
    check("OK ssh_rc=0 seal_rc=0" in proc.stdout,
          "PIPESTATUS snapshot success path reads both rcs")
    check("unbound variable" not in (proc.stderr or ""),
          "PIPESTATUS snapshot success path has no unbound-variable error")

    broken = r"""
set -euo pipefail
set +e
true | true
ssh_rc=${PIPESTATUS[0]}
seal_rc=${PIPESTATUS[1]}
printf 'reached ssh_rc=%s seal_rc=%s\n' "$ssh_rc" "$seal_rc"
"""
    broken_proc = subprocess.run(
        ["bash", "-c", broken],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    check(broken_proc.returncode != 0,
          "naive PIPESTATUS[0] then [1] fails under set -u")
    check("unbound variable" in (broken_proc.stderr or ""),
          "naive PIPESTATUS[1] is the unbound-variable failure")


def _check_counts_and_seal() -> None:
    data = _fixture_tar()
    counts = counts_from_tar_bytes(data)
    check(counts["untracked"] == 12, "counts take untracked from meta.txt")
    check(counts["ignored"] == 4, "counts take ignored from meta.txt")
    check(counts["modified"] == 2, "counts take modified from meta.txt")
    check(counts["cron_entries"] == 2, "cron_entries skips headers/comments")
    check(counts["systemd_entries"] == 2, "systemd_entries skips headers")

    buf = io.StringIO()
    rc = print_counts(data, buf)
    out = buf.getvalue()
    check(rc == 0, "printer exits 0 on a fixture tar")
    check(out == format_counts(counts), "printer stdout is exactly the five counts")
    for key in COUNT_KEYS:
        check("%s=%d" % (key, counts[key]) in out, "printer emits %s" % key)
    leaked = [needle for needle in (*PLANTED_PATHS, *PLANTED_SECRETS,
                                    "selectel-prod.example", "deadbeefcafebabe",
                                    "untracked.txt", "meta.txt")
              if needle in out]
    check(not leaked, "printer stdout has no paths/contents %s" % leaked)

    # Seal with a fake age so CI (no age package) still proves no plaintext write.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        recip = tmp_path / "recip.pub"
        recip.write_text(
            "age1uq55jgysck9tu0g4znardz3a8splzuxvqmpgvnxdcg2wktv4rcssnzks2d\n",
            encoding="utf-8",
        )
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        fake_age = fake_bin / "age"
        fake_age.write_text(
            "#!/bin/sh\n"
            "out=''\n"
            "while [ $# -gt 0 ]; do\n"
            "  if [ \"$1\" = \"-o\" ]; then out=$2; shift 2; continue; fi\n"
            "  shift\n"
            "done\n"
            "cat > /dev/null\n"
            "printf 'age-encryption.org/v1\\nfake\\n' > \"$out\"\n",
            encoding="utf-8",
        )
        fake_age.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
        out_age = tmp_path / "recon-report.tar.age"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "seal_vps_git_recon.py"),
             "--recipient-file", str(recip), "--out", str(out_age)],
            cwd=tmp_path,
            env=env,
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        stdout = proc.stdout.decode("utf-8", errors="replace")
        check(proc.returncode == 0, "sealer exits 0 with a fake age")
        check(out_age.is_file() and out_age.read_bytes().startswith(b"age-encryption.org/v1"),
              "sealer writes only an age ciphertext")
        check(not (tmp_path / "recon-report.tar").exists(),
              "sealer does not write a plaintext tar")
        check(not (tmp_path / "recon-report").exists(),
              "sealer does not unpack a report directory")
        leaked_seal = [n for n in (*PLANTED_PATHS, *PLANTED_SECRETS) if n in stdout]
        check(not leaked_seal, "sealer stdout has no paths/contents %s" % leaked_seal)
        check("untracked=12" in stdout and "cron_entries=2" in stdout,
              "sealer prints aggregate counts")

        # Failed age: planted stderr must not appear in sealer output.
        fail_bin = tmp_path / "failbin"
        fail_bin.mkdir()
        fail_age = fail_bin / "age"
        fail_age.write_text(
            "#!/bin/sh\n"
            "echo 'age diagnostic: data/runtime-secret.json sk-leaked-secret-value' >&2\n"
            "exit 7\n",
            encoding="utf-8",
        )
        fail_age.chmod(0o755)
        fail_env = dict(os.environ)
        fail_env["PATH"] = str(fail_bin) + os.pathsep + fail_env.get("PATH", "")
        fail_out = tmp_path / "fail.tar.age"
        fail_proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "seal_vps_git_recon.py"),
             "--recipient-file", str(recip), "--out", str(fail_out)],
            cwd=tmp_path,
            env=fail_env,
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        fail_err = fail_proc.stderr.decode("utf-8", errors="replace")
        fail_out_text = fail_proc.stdout.decode("utf-8", errors="replace")
        check(fail_proc.returncode != 0, "sealer exits non-zero when age fails")
        check("seal_vps_git_recon: age failed" in fail_err,
              "failed age prints the fixed error message")
        leaked_fail = [n for n in (*PLANTED_PATHS, *PLANTED_SECRETS,
                                   "age diagnostic", "exit 7")
                       if n in fail_err or n in fail_out_text]
        check(not leaked_fail, "failed age does not leak age stderr %s" % leaked_fail)
        check(not fail_out.exists(), "failed age does not leave a ciphertext file")

        # Real age, when present (local / recon workflow). Same no-path contract.
        if __import__("shutil").which("age"):
            real_out = tmp_path / "real.tar.age"
            try:
                encrypt_to_age(data, ROOT / "ops" / "recon-age.pub", real_out)
                blob = real_out.read_bytes()
                check(blob.startswith(b"age-encryption.org/v1"),
                      "real age ciphertext has the age header")
                check(b"public/products.json" not in blob,
                      "ciphertext does not contain planted paths in the clear")
            except SystemExit as exc:
                check(False, "real age encrypt: %s" % exc)
        else:
            check(True, "real age not installed; fake-age seal test covers the contract")


if __name__ == "__main__":
    raise SystemExit(main())
