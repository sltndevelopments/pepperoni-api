#!/usr/bin/env python3
"""Print aggregate counts from a search-queries tar. Never print rows."""
from __future__ import annotations

import io
import sys
import tarfile

COUNT_KEYS = (
    "gsc_rows",
    "yandex_rows",
    "yandex_url_rows",
    "gsc_indexed",
    "gsc_excluded",
    "yandex_indexed",
    "yandex_excluded",
)


def counts_from_tar_bytes(data: bytes) -> dict[str, int]:
    counts = {k: 0 for k in COUNT_KEYS}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r|") as tf:
        for info in tf:
            if info.name != "meta.txt" or not info.isfile():
                continue
            fh = tf.extractfile(info)
            text = (fh.read() if fh is not None else b"").decode("utf-8", "replace")
            for raw in text.splitlines():
                if "=" not in raw:
                    continue
                key, _, val = raw.partition("=")
                key = key.strip()
                if key not in counts:
                    continue
                try:
                    counts[key] = int(val.strip())
                except ValueError:
                    continue
            break
    return counts


def format_counts(counts: dict[str, int]) -> str:
    return " ".join(f"{k}={counts[k]}" for k in COUNT_KEYS) + "\n"


def print_counts(data: bytes, out) -> int:
    if not data:
        return 2
    out.write(format_counts(counts_from_tar_bytes(data)))
    return 0
