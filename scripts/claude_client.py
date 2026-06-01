#!/usr/bin/env python3
"""
DeepSeek API client (OpenAI-compatible).
Replaces Claude API — DeepSeek V4 Pro has no geo-restrictions for Russia.

Usage:
    from claude_client import call_claude
    text, tokens = call_claude(system="...", prompt="...")
"""

import json
import os
import urllib.error
import urllib.request

SOCK_TIMEOUT_S = int(os.environ.get("DEEPSEEK_SOCK_TIMEOUT", "60"))

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

DEFAULT_MODEL   = "deepseek-v4-flash"
FALLBACK_MODEL  = "deepseek-v4-flash"         # same tier; legacy deepseek-chat retires 2026-07-24
CHEAP_MODEL     = "deepseek-v4-flash"         # cheap/fast model for bulk/reports
CHEAP_FALLBACK  = "deepseek-v4-flash"         # same model, no cheaper tier

# Backward-compatible alias for scripts that import CLAUDE_API_KEY
CLAUDE_API_KEY = DEEPSEEK_API_KEY


def _make_request(url: str, data: bytes, headers: dict, timeout: int = 120) -> bytes:
    """Send HTTP POST directly (no proxy needed — DeepSeek doesn't geo-block Russia)."""
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_deepseek_response(raw: bytes) -> tuple[str, int]:
    """Parse DeepSeek (OpenAI-compatible) Chat Completions response."""
    data = json.loads(raw)
    if "error" in data:
        raise RuntimeError(f"DeepSeek error: {data['error']}")
    msg = data["choices"][0]["message"]
    text = msg.get("content") or msg.get("reasoning_content") or ""
    tokens = data.get("usage", {}).get("completion_tokens", 0)
    return text, tokens


def call_claude(
    prompt: str,
    system: str = "",
    model: str = None,
    max_tokens: int = 4096,
    use_proxy: bool = True,   # kept for backward compat, ignored
) -> tuple[str, int]:
    """
    Call DeepSeek API. Returns (text, tokens_used).
    The `use_proxy` parameter is kept for backward compatibility but DeepSeek
    has no geo-restrictions, so no proxy is needed.
    """
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    model = model or DEFAULT_MODEL

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body_dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
        "temperature": 0.7,
        # V4 models enable "thinking" by default, which burns completion tokens
        # on reasoning_content. SEO/content generation does not need chain-of-
        # thought, so disable it to cut cost and avoid empty content responses.
        "thinking": {"type": "disabled"},
    }

    body = json.dumps(body_dict).encode()
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    errors = []

    try:
        raw = _make_request(DEEPSEEK_URL, body, headers)
        return _parse_deepseek_response(raw)
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode()
        except Exception:
            pass
        if e.code in (404, 503) and body_dict["model"] == DEFAULT_MODEL:
            # Model not found or overloaded — fall back to deepseek-chat
            body_dict["model"] = FALLBACK_MODEL
            body = json.dumps(body_dict).encode()
            try:
                raw = _make_request(DEEPSEEK_URL, body, headers)
                return _parse_deepseek_response(raw)
            except Exception as e2:
                errors.append(f"fallback-model: {e2}")
        else:
            errors.append(f"HTTP {e.code}: {err_body[:300]}")
    except Exception as e:
        errors.append(f"request: {e}")

    raise RuntimeError(f"DeepSeek API failed. Errors: {'; '.join(errors)}")


def call_claude_cheap(prompt: str, system: str = "", max_tokens: int = 2048) -> tuple[str, int]:
    """Use cheap model for simple tasks like reports (renamed from Claude Haiku)."""
    try:
        return call_claude(prompt, system=system, model=CHEAP_MODEL, max_tokens=max_tokens)
    except Exception:
        return call_claude(prompt, system=system, model=CHEAP_FALLBACK, max_tokens=max_tokens)


if __name__ == "__main__":
    print(f"Testing DeepSeek API (no proxy needed) …")
    print(f"  Model: {DEFAULT_MODEL}")
    print(f"  URL:   {DEEPSEEK_URL}")
    try:
        text, tokens = call_claude(
            prompt="Say 'SEO agent online' and nothing else.",
            system="You are a helpful assistant.",
            max_tokens=20,
        )
        print(f"✅ Response: {text.strip()}")
        print(f"   Tokens: {tokens}, Model: {DEFAULT_MODEL}")
    except Exception as e:
        print(f"❌ Error: {e}")
