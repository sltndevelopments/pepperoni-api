#!/usr/bin/env python3
"""Read-only VPS git snapshot. Prints a tar stream to stdout. No disk writes."""
from __future__ import annotations

import io
import os
import stat
import subprocess
import sys
import tarfile
from datetime import datetime, timezone

REPO = os.environ.get("REPO_DIR", "/var/www/pepperoni/repo")
GIT_ENV = dict(os.environ)
GIT_ENV["GIT_OPTIONAL_LOCKS"] = "0"


def die(msg):
    sys.stderr.write(msg + "\n")
    raise SystemExit(1)


def git(*args):
    return subprocess.run(
        ["git", *args],
        cwd=REPO,
        env=GIT_ENV,
        capture_output=True,
        text=True,
        check=False,
    )


def run(argv):
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    except OSError as exc:
        return "(missing %s: %s)\n" % (argv[0], exc)
    out = proc.stdout or ""
    err = proc.stderr or ""
    if proc.returncode != 0 and err:
        return out + err
    return out if out else err


def porcelain_paths(text):
    rename_arrow = " -" + chr(62) + " "
    paths = []
    for raw in text.splitlines():
        if not raw:
            continue
        if len(raw) < 2:
            continue
        line = raw[2:]
        line = line.lstrip(" ")
        if rename_arrow in line:
            line = line.split(rename_arrow, 1)[1]
        if line:
            paths.append(line)
    # unique, stable
    seen = set()
    ordered = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def mtimes_block(paths):
    lines = [
        "# last-modified times of dirty / untracked / ignored paths",
        "# format: mtime_utc  size  path",
    ]
    if not paths:
        lines.append("(working tree clean)")
        return "\n".join(lines) + "\n"
    for rel in paths:
        abs_path = os.path.join(REPO, rel)
        try:
            st = os.lstat(abs_path)
        except OSError:
            lines.append("MISSING\t-\t%s" % rel)
            continue
        mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
        lines.append("%s\t%s\t%s" % (mtime.strftime("%Y-%m-%d %H:%M:%S.%f %z"), st.st_size, rel))
    return "\n".join(lines) + "\n"


def systemd_block():
    parts = [
        "=== systemctl list-timers --all ===\n",
        run(["systemctl", "list-timers", "--all", "--no-pager"]),
        "\n=== pepperoni / seo / sync units ===\n",
    ]
    units = run(["systemctl", "list-units", "--type=service", "--all", "--no-pager"])
    interesting = [
        line for line in units.splitlines()
        if any(key in line.lower() for key in ("pepperoni", "seo-agent", "seo-worker", "sync-vps"))
    ]
    parts.append("\n".join(interesting) + ("\n" if interesting else ""))
    parts.append("\n=== unit files under /etc/systemd/system ===\n")
    roots = ("/etc/systemd/system", "/lib/systemd/system")
    mentioned = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            low = name.lower()
            path = os.path.join(root, name)
            if not (low.startswith("pepperoni") or "seo" in low or "sync" in low):
                if os.path.isfile(path):
                    try:
                        body = open(path, encoding="utf-8", errors="replace").read()
                    except OSError:
                        body = ""
                    if "/var/www/pepperoni/repo" in body:
                        mentioned.append(path)
                continue
            if not os.path.isfile(path):
                continue
            parts.append("----- %s -----\n" % path)
            try:
                body = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                body = ""
            for line in body.splitlines():
                if line.startswith((
                    "Description=",
                    "WorkingDirectory=",
                    "ExecStart=",
                    "ExecStartPre=",
                    "EnvironmentFile=",
                )):
                    parts.append(line + "\n")
            if "/var/www/pepperoni/repo" in body:
                mentioned.append(path)
    parts.append("\n=== units whose WorkingDirectory or ExecStart mention the repo ===\n")
    parts.append("\n".join(sorted(set(mentioned))) + ("\n" if mentioned else ""))
    return "".join(parts)


def crontab_block():
    parts = ["=== crontab -l ===\n", run(["crontab", "-l"]), "\n=== /etc/cron.d (pepperoni / seo / sync) ===\n"]
    cron_d = "/etc/cron.d"
    if os.path.isdir(cron_d):
        names = sorted(os.listdir(cron_d))
        if not names:
            parts.append("(no /etc/cron.d files)\n")
        else:
            hits = []
            for name in names:
                path = os.path.join(cron_d, name)
                try:
                    body = open(path, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                for i, line in enumerate(body.splitlines(), 1):
                    low = line.lower()
                    if any(key in low for key in (
                        "pepperoni", "sync-vps", "seo-agent", "seo-worker", "seo-agent-vps",
                    )):
                        hits.append("%s:%d:%s" % (path, i, line))
            parts.append("\n".join(hits) + ("\n" if hits else ""))
    else:
        parts.append("(no /etc/cron.d files)\n")
    return "".join(parts)


def main():
    if not os.path.isdir(os.path.join(REPO, ".git")):
        die("vps_git_recon_readonly: %s is not a git repo" % REPO)

    head = git("rev-parse", "HEAD")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    status = git("status", "--porcelain=v1", "-uall")
    status_ignored = git("status", "--porcelain=v1", "--ignored", "-uall")
    untracked = git("ls-files", "--others", "--exclude-standard")
    ignored = git("ls-files", "--others", "--ignored", "--exclude-standard")
    diff_stat = git("diff", "--stat")
    diff_numstat = git("diff", "--numstat")
    diff_names = git("diff", "--name-only")

    dirty = porcelain_paths(status_ignored.stdout)
    host = run(["hostname", "-f"]).strip() or run(["hostname"]).strip()
    try:
        pwd = os.getcwd()
    except OSError:
        pwd = ""

    meta_lines = [
        "# pepperoni VPS git reconciliation (READ-ONLY)",
        "collected_at_utc=%s" % datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host=%s" % host,
        "repo=%s" % os.path.realpath(REPO),
        "pwd_at_collect=%s" % pwd,
        "path_count=%d" % len(dirty),
        "untracked_count=%d" % len([ln for ln in untracked.stdout.splitlines() if ln]),
        "ignored_count=%d" % len([ln for ln in ignored.stdout.splitlines() if ln]),
        "modified_tracked_count=%d" % len([ln for ln in diff_names.stdout.splitlines() if ln]),
        "",
    ]

    files = {
        "meta.txt": "\n".join(meta_lines),
        "HEAD.txt": head.stdout,
        "branch.txt": branch.stdout,
        "git-status-porcelain.txt": status.stdout,
        "git-status-porcelain-ignored.txt": status_ignored.stdout,
        "untracked.txt": untracked.stdout,
        "ignored.txt": ignored.stdout,
        "git-diff-stat.txt": diff_stat.stdout,
        "git-diff-numstat.txt": diff_numstat.stdout,
        "git-diff-names.txt": diff_names.stdout,
        "dirty-paths.txt": ("\n".join(dirty) + "\n") if dirty else "",
        "crontab.txt": crontab_block(),
        "systemd.txt": systemd_block(),
        "mtimes.txt": mtimes_block(dirty),
    }

    # Stream tar to stdout only. Empty porcelain is a valid clean-repo report.
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as tf:
        now = int(datetime.now(timezone.utc).timestamp())
        for name, text in files.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mtime = now
            info.mode = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
            tf.addfile(info, io.BytesIO(data))

    sys.stderr.write("READ-ONLY report streamed as tar (%d members)\n" % len(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
