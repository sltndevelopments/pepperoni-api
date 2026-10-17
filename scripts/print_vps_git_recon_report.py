#!/usr/bin/env python3
"""Print aggregate counts from a VPS git-reconciliation tar.

Reads the tar from bytes or stdin. Never writes the tar, never prints
paths or member contents. Output is five integers only — safe for a
public Actions log.
"""
from __future__ import annotations

import argparse
import io
import sys
import tarfile

COUNT_KEYS = (
    "untracked",
    "ignored",
    "modified",
    "cron_entries",
    "systemd_entries",
)

META_MAP = {
    "untracked_count": "untracked",
    "ignored_count": "ignored",
    "modified_tracked_count": "modified",
}


def _decode(blob: bytes) -> str:
    return blob.decode("utf-8", errors="replace")


def count_entries(text: str) -> int:
    """Non-empty, non-header, non-comment lines. Does not return the lines."""
    n = 0
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        if s.startswith("===") or s.startswith("-----"):
            continue
        if s.startswith("(") and s.endswith(")"):
            continue
        n += 1
    return n


def _line_count(text: str) -> int:
    return sum(1 for ln in text.splitlines() if ln.strip())


def _members(data: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r|") as tf:
        for info in tf:
            if not info.isfile():
                continue
            fh = tf.extractfile(info)
            out[info.name] = fh.read() if fh is not None else b""
    return out


def counts_from_tar_bytes(data: bytes) -> dict[str, int]:
    members = _members(data)
    counts = {k: 0 for k in COUNT_KEYS}
    meta = _decode(members.get("meta.txt", b""))
    for raw in meta.splitlines():
        if "=" not in raw:
            continue
        key, _, val = raw.partition("=")
        mapped = META_MAP.get(key.strip())
        if mapped is None:
            continue
        try:
            counts[mapped] = int(val.strip())
        except ValueError:
            continue
    if "untracked.txt" in members and "untracked_count" not in meta:
        counts["untracked"] = _line_count(_decode(members["untracked.txt"]))
    if "ignored.txt" in members and "ignored_count" not in meta:
        counts["ignored"] = _line_count(_decode(members["ignored.txt"]))
    if "git-diff-names.txt" in members and "modified_tracked_count" not in meta:
        counts["modified"] = _line_count(_decode(members["git-diff-names.txt"]))
    counts["cron_entries"] = count_entries(_decode(members.get("crontab.txt", b"")))
    counts["systemd_entries"] = count_entries(_decode(members.get("systemd.txt", b"")))
    return counts


def format_counts(counts: dict[str, int]) -> str:
    return "".join("%s=%d\n" % (k, int(counts[k])) for k in COUNT_KEYS)


def print_counts(data: bytes, out=None) -> int:
    if out is None:
        out = sys.stdout
    out.write(format_counts(counts_from_tar_bytes(data)))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tar",
        nargs="?",
        help="tar path; omit to read the tar from stdin (preferred — no extra file)",
    )
    args = parser.parse_args(argv)
    if args.tar:
        # Local debug only. The workflow must pipe stdin so the tar never
        # lands on the runner disk.
        data = open(args.tar, "rb").read()
    else:
        data = sys.stdin.buffer.read()
    if not data:
        sys.stderr.write("print_vps_git_recon_report: empty input\n")
        return 2
    return print_counts(data)


if __name__ == "__main__":
    raise SystemExit(main())
