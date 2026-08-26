#!/usr/bin/env python3
"""Render the Yaratu nginx template without shell interpolation."""

from __future__ import annotations

import argparse
from pathlib import Path


TOKENS = {
    "__YARATU_ROOT__": "/var/www/yaratu/current",
    "__YARATU_CERTIFICATE__": "/etc/letsencrypt/live/yaratu.com/fullchain.pem",
    "__YARATU_CERTIFICATE_KEY__": "/etc/letsencrypt/live/yaratu.com/privkey.pem",
}


def safe_value(value: str, label: str) -> str:
    if not value.startswith("/") or "\n" in value or "\r" in value or ";" in value:
        raise ValueError(f"{label} must be an absolute path without newlines or semicolons")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", default=TOKENS["__YARATU_ROOT__"])
    parser.add_argument("--certificate", default=TOKENS["__YARATU_CERTIFICATE__"])
    parser.add_argument(
        "--certificate-key", default=TOKENS["__YARATU_CERTIFICATE_KEY__"]
    )
    args = parser.parse_args()

    values = {
        "__YARATU_ROOT__": safe_value(args.root, "root"),
        "__YARATU_CERTIFICATE__": safe_value(args.certificate, "certificate"),
        "__YARATU_CERTIFICATE_KEY__": safe_value(
            args.certificate_key, "certificate key"
        ),
    }
    rendered = args.template.read_text(encoding="utf-8")
    for token, value in values.items():
        if token not in rendered:
            raise ValueError(f"template token missing: {token}")
        rendered = rendered.replace(token, value)
    leftovers = [token for token in TOKENS if token in rendered]
    if leftovers:
        raise ValueError(f"unrendered template tokens: {', '.join(leftovers)}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
