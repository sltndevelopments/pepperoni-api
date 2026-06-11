#!/usr/bin/env python3
"""Sync ANTHROPIC_PROXY from the Asocks API (api.asocks.com).

Asocks mobile/corporate ports are HTTP proxies (host:9999), NOT SOCKS5 on :443
as shown in some dashboard views. This script reads the live port list from the
API and writes the correct http://login:pass@host:port into seo-agent.env so
claude_client / opus_brain_client can reach Anthropic from the RU VPS.

Env:
  ASOCKS_API_KEY  — required (from seo-agent.env)
  SEO_AGENT_ENV   — path to env file (default /var/www/pepperoni/seo-agent.env)

Usage: python3 scripts/sync_asocks_proxy.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.asocks.com/v2"
DEFAULT_ENV = Path("/var/www/pepperoni/seo-agent.env")


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_proxies(api_key: str) -> list[dict]:
    data = _get(f"{API}/proxy/ports?apiKey={api_key}&per_page=20")
    if not data.get("success"):
        raise RuntimeError(f"asocks API error: {data}")
    msg = data.get("message") or {}
    return [p for p in (msg.get("proxies") or []) if p.get("status") == 1]


def to_proxy_url(p: dict) -> str:
    """Build http://login:pass@host:port from an asocks port record."""
    login = (p.get("login") or "").strip()
    password = (p.get("password") or "").strip()
    hostport = (p.get("proxy") or "").strip()  # e.g. 190.2.137.56:9999
    if not (login and password and hostport):
        tpl = (p.get("template") or "").strip()
        if tpl.startswith("http://"):
            return tpl  # already a full URL
        raise ValueError(f"incomplete port record: {p.get('id')}")
    return f"http://{login}:{password}@{hostport}"


def patch_env(env_path: Path, primary: str, fallbacks: list[str]) -> None:
    text = env_path.read_text() if env_path.exists() else ""
    updates = {
        "ANTHROPIC_PROXY": primary,
        "ANTHROPIC_PROXY_FALLBACK": fallbacks[0] if fallbacks else "",
        "ANTHROPIC_PROXIES": ",".join([primary] + fallbacks),
    }
    for key, val in updates.items():
        line = f"{key}={val}"
        if re.search(rf"^{re.escape(key)}=", text, re.M):
            text = re.sub(rf"^{re.escape(key)}=.*$", line, text, flags=re.M)
        else:
            text += f"\n{line}\n"
    env_path.write_text(text)


def main() -> int:
    dry = "--dry-run" in sys.argv
    api_key = os.environ.get("ASOCKS_API_KEY", "").strip()
    if not api_key:
        print("ℹ️  ASOCKS_API_KEY not set — skip asocks sync", file=sys.stderr)
        return 0
    env_path = Path(os.environ.get("SEO_AGENT_ENV", str(DEFAULT_ENV)))
    try:
        ports = fetch_proxies(api_key)
    except Exception as e:
        print(f"⚠️  asocks fetch failed: {e}", file=sys.stderr)
        return 1
    if not ports:
        print("⚠️  no active asocks ports", file=sys.stderr)
        return 1
    urls = [to_proxy_url(p) for p in ports]
    primary = urls[0]
    fallbacks = urls[1:]
    masked = re.sub(r":([^:@]+)@", ":***@", primary)
    print(f"🌐 asocks: {len(urls)} port(s) | primary {masked}")
    if not dry:
        patch_env(env_path, primary, fallbacks)
        print(f"✅ wrote ANTHROPIC_PROXY → {env_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
