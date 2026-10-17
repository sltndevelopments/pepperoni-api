#!/usr/bin/env python3
"""Print a VPS git-reconciliation report directory to CI logs.

Reads only files inside the report dir (paths, sizes, mtimes, cron/unit
lines the collector already extracted). Never opens drifted repo files,
never prints a full untracked/ignored dump, and redacts secret-looking
lines.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LINE_CAP = 400

# Members the collector always emits. Unknown extra files: name/size/mtime only.
FULL_FILES = (
    "meta.txt",
    "HEAD.txt",
    "branch.txt",
    "git-status-porcelain.txt",
    "git-diff-stat.txt",
    "git-diff-numstat.txt",
    "git-diff-names.txt",
    "crontab.txt",
    "systemd.txt",
    "mtimes.txt",
    "dirty-paths.txt",
)
CAPPED_FILES = (
    "untracked.txt",
    "ignored.txt",
    "git-status-porcelain-ignored.txt",
)
DIR_SUMMARY_FILES = (
    "untracked.txt",
    "ignored.txt",
)
KNOWN_FILES = frozenset(FULL_FILES + CAPPED_FILES)

# KEY / TOKEN / SECRET / PASSWORD anywhere on the line (API_KEY, AUTH_TOKEN, …).
SECRET_RE = re.compile(r"(?i)(KEY|TOKEN|SECRET|PASSWORD)")
# Cron env is ALLCAPS=value. Mixed-case unit keys (ExecStart=, Description=) stay.
CRON_ENV_RE = re.compile(r"^[A-Z_][A-Z0-9_]*=")
EXPORT_RE = re.compile(r"(?i)^export\s+[A-Za-z_][A-Za-z0-9_]*=")
ENVFILE_RE = re.compile(r"(?i)^environmentfile\s*=")
SYSTEMD_ENV_RE = re.compile(r"(?i)^environment\s*=")

REDACT_SECRET = "[redacted: secret-looking line]"
REDACT_ENV = "[redacted: env value]"


def mask_line(line: str) -> str:
    """Return a printable line, or a redaction marker. Never leaks the original."""
    stripped = line.rstrip("\n")
    if SECRET_RE.search(stripped):
        return REDACT_SECRET
    left = stripped.lstrip()
    if ENVFILE_RE.match(left):
        return stripped
    if SYSTEMD_ENV_RE.match(left) or EXPORT_RE.match(left) or CRON_ENV_RE.match(left):
        return REDACT_ENV
    return stripped


def file_meta(path: Path) -> str:
    try:
        st = path.stat()
    except OSError as exc:
        return f"MISSING\t-\t{path.name}\t({exc})"
    mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    return "%s\t%s\t%s" % (
        mtime.strftime("%Y-%m-%d %H:%M:%S %z"),
        st.st_size,
        path.name,
    )


def top_level_dir(rel: str) -> str:
    rel = rel.strip().strip('"').lstrip("./")
    if not rel:
        return "."
    rel = rel.replace("\\", "/")
    if "/" not in rel:
        return "."
    return rel.split("/", 1)[0]


def dir_counts(text: str) -> list[tuple[int, str]]:
    counts: Counter[str] = Counter()
    for raw in text.splitlines():
        if not raw.strip():
            continue
        counts[top_level_dir(raw)] += 1
    return sorted(((-n, name) for name, n in counts.items()))


def emit(out, line: str) -> None:
    out.write(mask_line(line) + "\n")


def print_full(path: Path, out) -> None:
    emit(out, "=== %s (full) ===" % path.name)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        emit(out, "(unreadable: %s)" % exc)
        return
    if text == "":
        emit(out, "(empty)")
        return
    for raw in text.splitlines():
        emit(out, raw)


def print_capped(path: Path, out, cap: int) -> None:
    emit(out, "=== %s (cap %d) ===" % (path.name, cap))
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        emit(out, "(unreadable: %s)" % exc)
        return
    lines = text.splitlines()
    total = len(lines)
    shown = lines[:cap]
    for raw in shown:
        emit(out, raw)
    omitted = total - len(shown)
    emit(out, "--- %s: shown=%d omitted=%d total=%d ---" % (
        path.name, len(shown), omitted, total,
    ))


def print_dir_summary(path: Path, out) -> None:
    emit(out, "=== %s top-level directories ===" % path.name)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        emit(out, "(unreadable: %s)" % exc)
        return
    rows = dir_counts(text)
    if not rows:
        emit(out, "(none)")
        return
    for neg, name in rows:
        emit(out, "%6d  %s/" % (-neg, name))


def print_report(report_dir: Path, out=None, cap: int = LINE_CAP) -> int:
    if out is None:
        out = sys.stdout
    report_dir = Path(report_dir)
    if not report_dir.is_dir():
        out.write("print_vps_git_recon_report: not a directory: %s\n" % report_dir)
        return 2

    emit(out, "# VPS git reconciliation — job log (paths / sizes / mtimes / cron+unit lines only)")
    emit(out, "# report_dir=%s" % report_dir)
    emit(out, "=== members (mtime_utc  size  name) ===")
    names = sorted(p.name for p in report_dir.iterdir() if p.is_file())
    for name in names:
        emit(out, file_meta(report_dir / name))
    if not names:
        emit(out, "(no files)")

    for name in FULL_FILES:
        path = report_dir / name
        if path.is_file():
            print_full(path, out)
        else:
            emit(out, "=== %s (missing) ===" % name)

    for name in CAPPED_FILES:
        path = report_dir / name
        if path.is_file():
            print_capped(path, out, cap)
        else:
            emit(out, "=== %s (missing) ===" % name)

    for name in DIR_SUMMARY_FILES:
        path = report_dir / name
        if path.is_file():
            print_dir_summary(path, out)

    extras = [n for n in names if n not in KNOWN_FILES]
    if extras:
        emit(out, "=== extra members (name/size/mtime only, contents omitted) ===")
        for name in extras:
            emit(out, file_meta(report_dir / name))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "report_dir",
        nargs="?",
        default="recon-report",
        help="unpacked report directory (default: recon-report)",
    )
    parser.add_argument("--cap", type=int, default=LINE_CAP)
    args = parser.parse_args(argv)
    return print_report(Path(args.report_dir), sys.stdout, cap=args.cap)


if __name__ == "__main__":
    raise SystemExit(main())
