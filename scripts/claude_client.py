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
import urllib.request

SOCK_TIMEOUT_S = int(os.environ.get("CLAUDE_SOCK_TIMEOUT", "30"))

PROXIES = [
    {
        "name": "primary-89.39.105.78",
        "host": "89.39.105.78",
        "port": 13268,
        "user": "01kdx7g91mgd99w12h7d3msgjk",
        "pass": "ClMSr77aDUVtJFhX",
    },
    {
        "name": "secondary-109.236.84.23",
        "host": "109.236.84.23",
        "port": 10468,
        "user": "01kdv36b1b66gvjd83bd6fhv67",
        "pass": "gArpzqKwZqD1EtWD",
    },
]

_env_proxy = os.environ.get("SOCKS_PROXY", "").strip()
if _env_proxy:
    try:
        import urllib.parse as _up
        _p = _up.urlparse(_env_proxy)
        if _p.hostname and _p.port:
            PROXIES.insert(0, {
                "name": f"env-{_p.hostname}",
                "host": _p.hostname,
                "port": int(_p.port),
                "user": _up.unquote(_p.username) if _p.username else "",
                "pass": _up.unquote(_p.password) if _p.password else "",
            })
    except Exception:
        pass

CLAUDE_API_KEY  = os.environ.get("CLAUDE_API_KEY", "")
DEFAULT_MODEL   = "claude-sonnet-4-5"       # primary
FALLBACK_MODEL  = "claude-3-5-sonnet-20241022"  # fallback if primary fails
HAIKU_MODEL     = "claude-haiku-4-5"         # cheap model for reports
HAIKU_FALLBACK  = "claude-3-5-haiku-20241022"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _make_request_via_socks5(url: str, data: bytes, headers: dict, proxy: dict) -> bytes:
    """Send HTTP POST via a specific SOCKS5 proxy using raw socket + PySocks.

    Uses a hard socket timeout so a dead proxy fails fast instead of hanging
    the GitHub Actions runner for 6 hours.
    """
    try:
        import socks
    except ImportError:
        raise RuntimeError("PySocks not installed: pip install PySocks")

    import ssl
    import urllib.parse

    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    port = parsed.port or 443
    path = parsed.path + (f"?{parsed.query}" if parsed.query else "")

    sock = socks.socksocket()
    sock.settimeout(SOCK_TIMEOUT_S)
    sock.set_proxy(socks.SOCKS5, proxy["host"], proxy["port"], True, proxy["user"], proxy["pass"])

    try:
        sock.connect((host, port))
        ctx = ssl.create_default_context()
        tls = ctx.wrap_socket(sock, server_hostname=host)
        tls.settimeout(SOCK_TIMEOUT_S)

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
            try:
                chunk = tls.recv(4096)
            except socket.timeout:
                raise RuntimeError(f"proxy {proxy['name']}: recv timeout after {SOCK_TIMEOUT_S}s")
            if not chunk:
                break
            response += chunk
        try:
            tls.close()
        except Exception:
            pass
    finally:
        try:
            sock.close()
        except Exception:
            pass

    sep = response.find(b"\r\n\r\n")
    if sep == -1:
        raise RuntimeError(f"proxy {proxy['name']}: bad HTTP response: {response[:200]}")

    status_line = response[:response.find(b"\r\n")].decode()
    status_code = int(status_line.split()[1])
    body = response[sep + 4:]

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


def _make_request_direct(url: str, data: bytes, headers: dict, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_claude_response(raw: bytes) -> tuple[str, int]:
    data = json.loads(raw)
    if "error" in data:
        raise RuntimeError(f"Claude error: {data['error']}")
    text = data["content"][0]["text"]
    tokens = data.get("usage", {}).get("output_tokens", 0)
    return text, tokens


def call_claude(
    prompt: str,
    system: str = "",
    model: str = None,
    max_tokens: int = 4096,
    use_proxy: bool = True,
) -> tuple[str, int]:
    """
    Call Claude API. Returns (text, tokens_used).
    Strategy: try each configured SOCKS5 proxy (fast-fail on timeout),
    then fall back to direct connection. Tries model fallback on HTTP 404.
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

    transports = []
    if use_proxy:
        for p in PROXIES:
            transports.append(("proxy:" + p["name"], lambda b=body, p=p: _make_request_via_socks5(ANTHROPIC_URL, b, headers, p)))
    transports.append(("direct", lambda b=body: _make_request_direct(ANTHROPIC_URL, b, headers)))

    for label, fn in transports:
        try:
            raw = fn()
            return _parse_claude_response(raw)
        except urllib.error.HTTPError as e:
            if e.code == 404 and body_dict["model"] == DEFAULT_MODEL:
                body_dict["model"] = FALLBACK_MODEL
                body = json.dumps(body_dict).encode()
                try:
                    raw = fn() if label == "direct" else _make_request_direct(ANTHROPIC_URL, body, headers)
                    return _parse_claude_response(raw)
                except Exception as e2:
                    errors.append(f"{label}+fallback-model: {e2}")
            else:
                errors.append(f"{label}: HTTP {e.code}")
        except Exception as e:
            errors.append(f"{label}: {e}")

    raise RuntimeError(f"Claude API failed. Errors: {'; '.join(errors)}")


def call_claude_cheap(prompt: str, system: str = "", max_tokens: int = 2048) -> tuple[str, int]:
    """Use Haiku model (cheaper) for simple tasks like reports."""
    try:
        return call_claude(prompt, system=system, model=HAIKU_MODEL, max_tokens=max_tokens)
    except Exception:
        return call_claude(prompt, system=system, model=HAIKU_FALLBACK, max_tokens=max_tokens)


if __name__ == "__main__":
    print(f"Testing Claude API via {len(PROXIES)} proxy(ies) + direct …")
    for p in PROXIES:
        print(f"  • {p['name']}  {p['host']}:{p['port']}")
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
