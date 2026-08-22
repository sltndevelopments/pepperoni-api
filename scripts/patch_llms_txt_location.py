#!/usr/bin/env python3
"""Replace nginx `location = /llms.txt { ... }` without breaking nested braces.

The previous apply path used `[^}]+`, which stopped at the inner `types { ... }`
brace. A second deploy then left a stray `}` → `nginx: unexpected "}"`.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CANONICAL_LLMS_LOCATION = """location = /llms.txt {
    alias /var/www/pepperoni/repo/public/llms.txt;
    add_header Cache-Control "public, max-age=300" always;
    add_header Access-Control-Allow-Origin "*" always;
    types { text/markdown txt; }
    default_type "text/markdown; charset=utf-8";
}"""

_START_RE = re.compile(r"location\s+=\s+/llms\.txt\s*\{", re.M)


def _matching_brace_end(text: str, open_idx: int) -> int | None:
    depth = 0
    i = open_idx
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def _consume_llms_remnants(text: str) -> int:
    """Bytes of leftover default_type / types / stray } after a botched patch."""
    i, n = 0, len(text)
    consumed_real = False
    while i < n:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if text.startswith("default_type", i):
            j, in_q = i + len("default_type"), False
            while j < n:
                c = text[j]
                if c == '"':
                    in_q = not in_q
                elif c == ";" and not in_q:
                    i = j + 1
                    break
                j += 1
            else:
                break
            consumed_real = True
            continue
        if text.startswith("types", i):
            brace = text.find("{", i)
            if brace < 0:
                break
            end = _matching_brace_end(text, brace)
            if not end:
                break
            i = end
            consumed_real = True
            continue
        if i < n and text[i] == "}":
            i += 1
            consumed_real = True
            continue
        break
    return i if consumed_real else 0


def patch_llms_txt_location(text: str, new_block: str = CANONICAL_LLMS_LOCATION) -> tuple[str, str]:
    """Return (new_text, status) where status is patched|unchanged|missing|repaired."""
    m = _START_RE.search(text)
    if not m:
        return text, "missing"
    open_idx = text.find("{", m.start())
    end = _matching_brace_end(text, open_idx)
    if end is None:
        nxt = re.search(r"\n\s*(?:location|server|#)\s", text[m.start() + 1 :])
        end = m.start() + 1 + nxt.start() if nxt else len(text)
        end += _consume_llms_remnants(text[end:])
        return text[: m.start()] + new_block + text[end:], "repaired"

    extra = _consume_llms_remnants(text[end:])
    if extra:
        end += extra
        return text[: m.start()] + new_block + text[end:], "repaired"

    old = text[m.start() : end]
    if old.strip() == new_block.strip():
        return text, "unchanged"
    return text[: m.start()] + new_block + text[end:], "patched"


def braces_ok(text: str) -> bool:
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("path")
    args = p.parse_args(argv)
    path = Path(args.path)
    text = path.read_text(encoding="utf-8")
    new, status = patch_llms_txt_location(text)
    if status == "missing":
        print(f"⚠️ could not patch /llms.txt default_type in {path}")
        return 0
    if status == "unchanged":
        print(f"· /llms.txt already text/markdown in {path}")
        return 0
    path.write_text(new, encoding="utf-8")
    print(f"✅ llms.txt type → text/markdown in {path} ({status})")
    return 0


def _self_test() -> None:
    original = """# static
location = /llms.txt {
    alias /var/www/pepperoni/repo/public/llms.txt;
    add_header Cache-Control "public, max-age=300" always;
    add_header Access-Control-Allow-Origin "*" always;
    default_type text/plain;
}
location = /robots.txt { alias /var/www/pepperoni/repo/public/robots.txt; }
"""
    once, st = patch_llms_txt_location(original)
    assert st == "patched", st
    assert braces_ok(once), once
    assert "types { text/markdown txt; }" in once
    twice, st2 = patch_llms_txt_location(once)
    assert st2 == "unchanged", st2
    assert twice == once

    broken, n = re.subn(
        r"location = /llms\.txt \{[^}]+\}",
        CANONICAL_LLMS_LOCATION,
        once,
        count=1,
    )
    assert n == 1
    assert not braces_ok(broken)
    fixed, st3 = patch_llms_txt_location(broken)
    assert st3 == "repaired", st3
    assert braces_ok(fixed), fixed
    assert fixed.count("location = /llms.txt") == 1
    assert "location = /robots.txt" in fixed
    third, st4 = patch_llms_txt_location(fixed)
    assert st4 == "unchanged"
    print("self-test ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())
