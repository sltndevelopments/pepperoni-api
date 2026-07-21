#!/usr/bin/env python3
"""Store the Avito worker OpenAI key without putting it in shell history."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

DEFAULT_ENV = "/etc/pepperoni-avito-worker.env"


def set_value(lines: list[str], key: str, value: str) -> None:
    prefix = key + "="
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f"{key}={value}"
            return
    lines.append(f"{key}={value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=DEFAULT_ENV, help="Path to runtime environment file")
    args = parser.parse_args()
    path = Path(args.env)
    if not path.is_file():
        print(f"Environment file does not exist: {path}", file=sys.stderr)
        return 1

    key = getpass.getpass("OpenAI API key (hidden input): ").strip()
    if not key:
        print("Empty key; nothing changed.", file=sys.stderr)
        return 1
    lines = path.read_text(encoding="utf-8").splitlines()
    set_value(lines, "OPENAI_API_KEY", key)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved OPENAI_API_KEY to {path}.")
    print("Restart: systemctl restart pepperoni-avito-worker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
