#!/usr/bin/env python3
"""Encrypt a search-queries tar with age and print counts only."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from print_search_queries_report import print_counts  # noqa: E402
from seal_vps_git_recon import encrypt_to_age  # noqa: E402

DEFAULT_RECIPIENT = Path(__file__).resolve().parent.parent / "ops" / "recon-age.pub"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipient-file", type=Path, default=DEFAULT_RECIPIENT)
    parser.add_argument("--out", type=Path, default=Path("search-queries.tar.age"))
    args = parser.parse_args(argv)
    data = sys.stdin.buffer.read()
    if not data:
        sys.stderr.write("seal_search_queries: empty stdin\n")
        return 2
    rc = print_counts(data, sys.stdout)
    if rc != 0:
        return rc
    try:
        encrypt_to_age(data, args.recipient_file, args.out)
    except SystemExit:
        sys.stderr.write("seal_search_queries: age failed\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
