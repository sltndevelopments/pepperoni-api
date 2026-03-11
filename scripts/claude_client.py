#!/usr/bin/env python3
"""
Claude API client with SOCKS5 proxy support.
Proxy routes requests through US IP to bypass geo-restrictions.

Usage:
    from claude_client import call_claude
    text, tokens = call_claude(system="...", prompt="...")
"""

import json
import os
import socket
import urllib.error

# ── Proxy config ──────────────────────────────────────────────
PROXY_HOST = "190.2.137.56"
PROXY_PORT = 443
PROXY_USER = "upqr8rrkth-corp.mobile.res-country-US-state-5128638-hold-session-session-69add76542aa2"
PROXY_PASS = "u5b2xg81SwhTvPZq"

# ── Claude config ─────────────────────────────────────────────
CLAUDE_API_KEY  = os.environ.get("CLAUDE_API_KEY", "")
DEFAULT_MODEL   = "claude-sonnet-4-5"       # primary
FALLBACK_MODEL  = "claude-3-5-sonnet-20241022"  # fallback if primary fails
HAIKU_MODEL     = "claude-haiku-4-5"         # cheap model for reports
HAIKU_FALLBACK  = "claude-3-5-haiku-20241022"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _make_request_via_socks5(url: str, data: bytes, headers: dict) -> bytes:
    """Send HTTP POST via SOCKS5 proxy using raw socket + PySocks."""
    try:
        import socks
        sock = socks.socksocket()
        sock.set_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT, True, PROXY_USER, PROXY_PASS)
    except ImportError:
        raise RuntimeError("PySocks not installed: pip install PySocks")

    import ssl
    import urllib.parse

    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    port = parsed.port or 443
    path = parsed.path + (f"?{parsed.query}" if parsed.query else "")

    sock.connect((host, port))
    ctx = ssl.create_default_context()
    tls = ctx.wrap_socket(sock, server_hostname=host)

    # Build raw HTTP/1.1 request
    header_lines = "\r\n".join(f"{k}: {v}" for k, v in headers.items())
    request = (
        f"POST {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Connection: close\r\n"
        f"Content-Length: {len(data)}\r\n"
        f"{header_lines}\r\n"
        f"\r\n"
    ).encode() + data

    tls.sendall(request)

    response = b""
    while True:
        chunk = tls.recv(4096)
        if not chunk:
            break
        response += chunk
    tls.close()

    # Split HTTP headers from body
    sep = response.find(b"\r\n\r\n")
    if sep == -1:
        raise RuntimeError(f"Bad HTTP response: {response[:200]}")

    status_line = response[:response.find(b"\r\n")].decode()
    status_code = int(status_line.split()[1])
    body = response[sep + 4:]

    # Handle chunked transfer encoding
    header_section = response[:sep].decode(errors="replace").lower()
    if "transfer-encoding: chunked" in header_section:
        body = _decode_chunked(body)

    if status_code >= 400:
        raise urllib.error.HTTPError(url, status_code, status_line, {}, None)

    return body


def _decode_chunked(data: bytes) -> bytes:
    """Decode HTTP chunked transfer encoding."""
    result = b""
    while data:
        end = data.find(b"\r\n")
        if end == -1:
            break
        size = int(data[:end], 16)
        if size == 0:
            break
        result += data[end + 2: end + 2 + size]
        data = data[end + 2 + size + 2:]
    return result


def call_claude(
    prompt: str,
    system: str = "",
    model: str = None,
    max_tokens: int = 4096,
    use_proxy: bool = True,
) -> tuple[str, int]:
    """
    Call Claude API. Returns (text, tokens_used).
    Tries SOCKS5 proxy first, falls back to direct if proxy fails.
    """
    if not CLAUDE_API_KEY:
        raise RuntimeError("CLAUDE_API_KEY not set")

    model = model or DEFAULT_MODEL

    messages = [{"role": "user", "content": prompt}]
    body_dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        body_dict["system"] = system

    body = json.dumps(body_dict).encode()
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    errors = []

    # ── Try SOCKS5 proxy ──
    if use_proxy:
        try:
            raw = _make_request_via_socks5(ANTHROPIC_URL, body, headers)
            data = json.loads(raw)
            if "error" in data:
                raise RuntimeError(f"Claude error: {data['error']}")
            text = data["content"][0]["text"]
            tokens = data.get("usage", {}).get("output_tokens", 0)
            return text, tokens
        except urllib.error.HTTPError as e:
            # Try fallback model on 404 (model not found)
            if e.code == 404 and model == DEFAULT_MODEL:
                body_dict["model"] = FALLBACK_MODEL
                body = json.dumps(body_dict).encode()
                try:
                    raw = _make_request_via_socks5(ANTHROPIC_URL, body, headers)
                    data = json.loads(raw)
                    text = data["content"][0]["text"]
                    tokens = data.get("usage", {}).get("output_tokens", 0)
                    return text, tokens
                except Exception as e2:
                    errors.append(f"proxy+fallback: {e2}")
            else:
                errors.append(f"proxy: HTTP {e.code}")
        except Exception as e:
            errors.append(f"proxy: {e}")

    # ── Direct fallback (no proxy) ──
    import urllib.request
    try:
        req = urllib.request.Request(ANTHROPIC_URL, data=body, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        text = data["content"][0]["text"]
        tokens = data.get("usage", {}).get("output_tokens", 0)
        return text, tokens
    except Exception as e:
        errors.append(f"direct: {e}")

    raise RuntimeError(f"Claude API failed. Errors: {'; '.join(errors)}")


def call_claude_cheap(prompt: str, system: str = "", max_tokens: int = 2048) -> tuple[str, int]:
    """Use Haiku model (cheaper) for simple tasks like reports."""
    try:
        return call_claude(prompt, system=system, model=HAIKU_MODEL, max_tokens=max_tokens)
    except Exception:
        return call_claude(prompt, system=system, model=HAIKU_FALLBACK, max_tokens=max_tokens)


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Claude API via SOCKS5 proxy …")
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
