#!/usr/bin/env python3
"""Encrypt a VPS recon tar with age and print counts only.

Reads the tar from stdin (memory). Writes only the ciphertext file via
`age -o`. Never writes the plaintext tar, never prints paths.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from print_vps_git_recon_report import print_counts  # noqa: E402

DEFAULT_RECIPIENT = Path(__file__).resolve().parent.parent / "ops" / "recon-age.pub"


def encrypt_to_age(plaintext: bytes, recipient_file: Path, out_path: Path) -> None:
    age = shutil.which("age")
    if not age:
        raise SystemExit("seal_vps_git_recon: age is not installed")
    if not recipient_file.is_file():
        raise SystemExit("seal_vps_git_recon: missing recipient file %s" % recipient_file)
    out_path = Path(out_path)
    if out_path.exists():
        out_path.unlink()
    proc = subprocess.run(
        [age, "-R", str(recipient_file), "-o", str(out_path)],
        input=plaintext,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        if out_path.exists():
            out_path.unlink()
        raise SystemExit("seal_vps_git_recon: age failed")
    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise SystemExit("seal_vps_git_recon: age produced no ciphertext")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recipient-file",
        type=Path,
        default=DEFAULT_RECIPIENT,
        help="age recipient public key file (committed)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("recon-report.tar.age"),
        help="ciphertext path (default: recon-report.tar.age)",
    )
    args = parser.parse_args(argv)
    data = sys.stdin.buffer.read()
    if not data:
        sys.stderr.write("seal_vps_git_recon: empty stdin\n")
        return 2
    rc = print_counts(data, sys.stdout)
    if rc != 0:
        return rc
    encrypt_to_age(data, args.recipient_file, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
