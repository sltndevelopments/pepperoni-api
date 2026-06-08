#!/usr/bin/env python3
"""
Anthropic Claude API client (Messages API).

This project produces a halal product catalog where text quality and factual
accuracy matter more than per-token cost, so all generation runs on Claude
Sonnet (latest). DeepSeek was removed because it hallucinated non-halal
ingredients (pork) into product descriptions.

Public surface is unchanged so existing scripts keep working:
    from claude_client import call_claude, call_claude_cheap
    text, tokens = call_claude(prompt="...", system="...")

Auth: set ANTHROPIC_API_KEY (preferred). For backward compatibility the old
DEEPSEEK_API_KEY env var is still read as a fallback, and the module-level
DEEPSEEK_API_KEY / CLAUDE_API_KEY names remain as aliases.
"""

import json
import os
import time
import urllib.error
import urllib.request

SOCK_TIMEOUT_S = int(os.environ.get("ANTHROPIC_SOCK_TIMEOUT",
                                    os.environ.get("DEEPSEEK_SOCK_TIMEOUT", "120")))

# Prefer ANTHROPIC_API_KEY; fall back to legacy DEEPSEEK_API_KEY so a partially
# migrated environment still works.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Anthropic geo-blocks some regions (e.g. the Russian VPS). Route through a
# SOCKS5/HTTP proxy when ANTHROPIC_PROXY is set, mirroring opus_brain_client.py.
ANTHROPIC_PROXY = os.environ.get("ANTHROPIC_PROXY", "").strip()
try:
    import requests as _requests  # type: ignore
    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False

DEFAULT_MODEL  = "claude-sonnet-4-6"
FALLBACK_MODEL = "claude-sonnet-4-5"   # convenience alias to latest 4.5 snapshot
CHEAP_MODEL    = "claude-haiku-4-5-20251001"
CHEAP_FALLBACK = "claude-sonnet-4-6"

# Backward-compatible aliases for scripts that import these names.
DEEPSEEK_API_KEY = ANTHROPIC_API_KEY
CLAUDE_API_KEY = ANTHROPIC_API_KEY


def _make_request(data: bytes, headers: dict, timeout: int = None) -> bytes:
    timeout = timeout or SOCK_TIMEOUT_S
    if ANTHROPIC_PROXY and _HAS_REQUESTS:
        r = _requests.post(
            ANTHROPIC_URL, data=data, headers=headers, timeout=timeout,
            proxies={"http": ANTHROPIC_PROXY, "https": ANTHROPIC_PROXY},
        )
        if r.status_code >= 400:
            raise urllib.error.HTTPError(ANTHROPIC_URL, r.status_code, r.text[:300], None, None)
        return r.content
    req = urllib.request.Request(ANTHROPIC_URL, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_response(raw: bytes) -> tuple[str, int]:
    """Parse an Anthropic Messages API response into (text, output_tokens)."""
    data = json.loads(raw)
    if data.get("type") == "error" or "error" in data:
        raise RuntimeError(f"Anthropic error: {data.get('error', data)}")
    # content is a list of blocks; concatenate the text blocks.
    parts = []
    for block in data.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    text = "".join(parts)
    tokens = data.get("usage", {}).get("output_tokens", 0)
    return text, tokens


def call_claude(
    prompt: str,
    system: str = "",
    model: str = None,
    max_tokens: int = 4096,
    use_proxy: bool = True,   # kept for backward compat, ignored
    temperature: float = 0.7,
    _retries: int = 3,
) -> tuple[str, int]:
    """Call Claude Messages API. Returns (text, output_tokens)."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    model = model or DEFAULT_MODEL

    body_dict = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body_dict["system"] = system

    body = json.dumps(body_dict).encode()
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    errors = []
    for attempt in range(_retries):
        try:
            raw = _make_request(body, headers)
            return _parse_response(raw)
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode()
            except Exception:
                pass
            # 429/5xx: back off and retry; on last try optionally fall back model.
            if e.code in (429, 500, 502, 503, 529) and attempt < _retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            if e.code in (404,) and body_dict["model"] == DEFAULT_MODEL:
                body_dict["model"] = FALLBACK_MODEL
                body = json.dumps(body_dict).encode()
                continue
            errors.append(f"HTTP {e.code}: {err_body[:300]}")
            break
        except Exception as e:  # noqa: BLE001 — network flake, retry
            errors.append(f"request: {e}")
            if attempt < _retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            break

    raise RuntimeError(f"Anthropic API failed. Errors: {'; '.join(errors)}")


def call_claude_cheap(prompt: str, system: str = "", max_tokens: int = 2048) -> tuple[str, int]:
    """Use a cheaper/faster model for simple tasks like reports."""
    try:
        return call_claude(prompt, system=system, model=CHEAP_MODEL, max_tokens=max_tokens)
    except Exception:
        return call_claude(prompt, system=system, model=CHEAP_FALLBACK, max_tokens=max_tokens)


if __name__ == "__main__":
    print("Testing Anthropic Claude API …")
    print(f"  Model: {DEFAULT_MODEL}")
    print(f"  URL:   {ANTHROPIC_URL}")
    print(f"  Key set: {bool(ANTHROPIC_API_KEY)}")
    try:
        text, tokens = call_claude(
            prompt="Say 'SEO agent online' and nothing else.",
            system="You are a helpful assistant.",
            max_tokens=20,
        )
        print(f"✅ Response: {text.strip()}")
        print(f"   Output tokens: {tokens}, Model: {DEFAULT_MODEL}")
    except Exception as e:
        print(f"❌ Error: {e}")
