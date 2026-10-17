#!/usr/bin/env python3
"""Print aggregate counts from a search-queries tar. Never print rows."""
from __future__ import annotations

import io
import sys
import tarfile

sys.tracebacklimit = 0

COUNT_KEYS = (
    "gsc_rows",
    "yandex_rows",
    "yandex_url_rows",
    "gsc_indexed",
    "gsc_excluded",
    "yandex_indexed",
    "yandex_excluded",
)
STATUS_KEYS = ("gsc", "yandex")


def counts_from_tar_bytes(data: bytes) -> dict[str, int | str]:
    counts: dict[str, int | str] = {k: 0 for k in COUNT_KEYS}
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
                val = val.strip()
                if key in STATUS_KEYS:
                    counts[key] = val
                    continue
                if key not in counts:
                    continue
                try:
                    counts[key] = int(val)
                except ValueError:
                    continue
            break
    return counts


def format_counts(counts: dict[str, int | str]) -> str:
    parts = []
    for key in STATUS_KEYS:
        if key in counts:
            parts.append(f"{key}={counts[key]}")
    parts.extend(f"{k}={counts[k]}" for k in COUNT_KEYS)
    return " ".join(parts) + "\n"


def print_counts(data: bytes, out) -> int:
    sys.tracebacklimit = 0
    try:
        if not data:
            return 2
        out.write(format_counts(counts_from_tar_bytes(data)))
        return 0
    except Exception as exc:
        sys.stderr.write(f"seal_search_queries: {type(exc).__name__}\n")
        return 1
