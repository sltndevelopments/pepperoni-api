#!/usr/bin/env python3
"""
Anthropic brain client — the strategic "brain" of the autonomous SEO engine.

Claude Fable 5 thinks (decides strategy); Claude Sonnet executes (generates
content). Kept dependency-free (urllib) to match claude_client.py.

Hard budget cap: tracks monthly spend in data/opus_budget.json and REFUSES
to call once the monthly cap is reached. Prompt caching is used on the large
static "playbook" portion of the system prompt to cut input cost ~90%.

Usage:
    from opus_brain_client import call_opus, brain_available
    text, usage = call_opus(system=[...], prompt="...", cache_system=True)
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Optional outbound proxy (e.g. SOCKS5) - Anthropic geoblocks some regions (RU).
# Set ANTHROPIC_PROXY="socks5h://user:pass@host:port" to route around it.
ANTHROPIC_PROXY = os.environ.get("ANTHROPIC_PROXY", "").strip()

try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False

# Model is configurable so you can switch brain versions without code changes.
# Default: Claude Fable 5 — Anthropic's most capable GA model (since 2026-06-09).
OPUS_MODEL = os.environ.get("OPUS_MODEL", "claude-fable-5")

# Monthly hard cap in USD. Default 40; override with OPUS_MONTHLY_BUDGET_USD.
MONTHLY_BUDGET_USD = float(os.environ.get("OPUS_MONTHLY_BUDGET_USD", "40"))

# Pricing (USD per 1M tokens) for Fable 5. Override via env if prices change.
PRICE_INPUT       = float(os.environ.get("OPUS_PRICE_INPUT",       "10"))   # fresh input
PRICE_OUTPUT      = float(os.environ.get("OPUS_PRICE_OUTPUT",      "50"))   # output
PRICE_CACHE_WRITE = float(os.environ.get("OPUS_PRICE_CACHE_WRITE", "12.50"))# cache creation
PRICE_CACHE_READ  = float(os.environ.get("OPUS_PRICE_CACHE_READ",  "1.00")) # cache hit

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
BUDGET_FILE = DATA / "opus_budget.json"

# ── Multi-tier model registry ───────────────────────────────────────────────────
# Three tiers: "brain" (Fable 5, strategy), "voice" (Sonnet, dialogue),
# "micro" (Haiku, cheap classification). Prices USD per 1M tokens.
MODELS = {
    "brain": {
        "model": os.environ.get("OPUS_MODEL", "claude-fable-5"),
        "in": float(os.environ.get("OPUS_PRICE_INPUT", "10")),
        "out": float(os.environ.get("OPUS_PRICE_OUTPUT", "50")),
        "cache_write": float(os.environ.get("OPUS_PRICE_CACHE_WRITE", "12.50")),
        "cache_read": float(os.environ.get("OPUS_PRICE_CACHE_READ", "1.00")),
    },
    "voice": {
        "model": os.environ.get("SONNET_MODEL", "claude-sonnet-4-6"),
        "in": float(os.environ.get("SONNET_PRICE_INPUT", "3")),
        "out": float(os.environ.get("SONNET_PRICE_OUTPUT", "15")),
        "cache_write": float(os.environ.get("SONNET_PRICE_CACHE_WRITE", "3.75")),
        "cache_read": float(os.environ.get("SONNET_PRICE_CACHE_READ", "0.30")),
    },
    "micro": {
        "model": os.environ.get("HAIKU_MODEL", "claude-haiku-4-5"),
        "in": float(os.environ.get("HAIKU_PRICE_INPUT", "1")),
        "out": float(os.environ.get("HAIKU_PRICE_OUTPUT", "5")),
        "cache_write": float(os.environ.get("HAIKU_PRICE_CACHE_WRITE", "1.25")),
        "cache_read": float(os.environ.get("HAIKU_PRICE_CACHE_READ", "0.10")),
    },
}


def brain_available() -> bool:
    """True if the brain can run (key present and budget remaining)."""
    return bool(ANTHROPIC_API_KEY) and remaining_budget() > 0


def _load_budget() -> dict:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    try:
        d = json.loads(BUDGET_FILE.read_text())
        if d.get("month") != month:
            d = {"month": month, "spent_usd": 0.0, "calls": 0}
    except Exception:
        d = {"month": month, "spent_usd": 0.0, "calls": 0}
    return d


def _save_budget(d: dict) -> None:
    try:
        DATA.mkdir(exist_ok=True)
        BUDGET_FILE.write_text(json.dumps(d, indent=1))
    except Exception:
        pass


def remaining_budget() -> float:
    d = _load_budget()
    return max(0.0, MONTHLY_BUDGET_USD - d.get("spent_usd", 0.0))


def _cost(usage: dict, prices: dict | None = None) -> float:
    p = prices or {"in": PRICE_INPUT, "out": PRICE_OUTPUT,
                   "cache_write": PRICE_CACHE_WRITE, "cache_read": PRICE_CACHE_READ}
    return (
        usage.get("input_tokens", 0)               / 1_000_000 * p["in"] +
        usage.get("output_tokens", 0)              / 1_000_000 * p["out"] +
        usage.get("cache_creation_input_tokens", 0)/ 1_000_000 * p["cache_write"] +
        usage.get("cache_read_input_tokens", 0)    / 1_000_000 * p["cache_read"]
    )


def _record_spend(usage: dict, prices: dict | None = None) -> float:
    cost = _cost(usage, prices)
    d = _load_budget()
    d["spent_usd"] = round(d.get("spent_usd", 0.0) + cost, 4)
    d["calls"] = d.get("calls", 0) + 1
    _save_budget(d)
    return cost


def call_model(
    prompt: str,
    tier: str = "brain",
    system=None,
    max_tokens: int = 4000,
    temperature=None,
    cache_system: bool = True,
    retries: int = 2,
) -> tuple[str, dict]:
    """
    Call an Anthropic model by tier ("brain"=Fable 5, "voice"=Sonnet, "micro"=Haiku).
    Shared monthly budget across all tiers. Returns (text, usage_with_cost).
    Raises RuntimeError if no key or budget exhausted.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set — brain disabled")
    if remaining_budget() <= 0:
        raise RuntimeError(
            f"Monthly Anthropic budget exhausted (${MONTHLY_BUDGET_USD:.0f}/mo). "
            "Resets next month."
        )

    cfg = MODELS.get(tier, MODELS["brain"])
    prices = {"in": cfg["in"], "out": cfg["out"],
              "cache_write": cfg["cache_write"], "cache_read": cfg["cache_read"]}

    sys_blocks = []
    if isinstance(system, str) and system:
        sys_blocks = [{"type": "text", "text": system}]
    elif isinstance(system, list):
        sys_blocks = [
            (b if isinstance(b, dict) else {"type": "text", "text": str(b)})
            for b in system
        ]
    if cache_system and sys_blocks:
        sys_blocks[-1] = {**sys_blocks[-1], "cache_control": {"type": "ephemeral"}}

    body = {
        "model": cfg["model"],
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    # Models with always-on adaptive thinking (claude-fable-5, claude-opus-4-8)
    # reject `temperature` — silently drop it for them.
    _no_temp = cfg["model"].startswith(("claude-fable", "claude-mythos", "claude-opus-4-8"))
    if temperature is not None and not _no_temp:
        body["temperature"] = temperature
    if sys_blocks:
        body["system"] = sys_blocks

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    data = json.dumps(body).encode("utf-8")
    last_err = None
    for attempt in range(retries + 1):
        try:
            if ANTHROPIC_PROXY and _HAS_REQUESTS:
                r = requests.post(
                    ANTHROPIC_URL, data=data, headers=headers, timeout=180,
                    proxies={"http": ANTHROPIC_PROXY, "https": ANTHROPIC_PROXY},
                )
                if r.status_code >= 400:
                    raise urllib.error.HTTPError(
                        ANTHROPIC_URL, r.status_code, r.text[:300], None, None
                    )
                raw = r.content
            else:
                req = urllib.request.Request(ANTHROPIC_URL, data=data, headers=headers)
                with urllib.request.urlopen(req, timeout=180) as resp:
                    raw = resp.read()
            obj = json.loads(raw)
            if obj.get("type") == "error" or "error" in obj:
                raise RuntimeError(f"Anthropic error: {obj.get('error', obj)}")
            parts = obj.get("content", [])
            text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
            usage = obj.get("usage", {}) or {}
            cost = _record_spend(usage, prices)
            usage["cost_usd"] = round(cost, 4)
            usage["budget_remaining_usd"] = round(remaining_budget(), 4)
            usage["tier"] = tier
            usage["model"] = cfg["model"]
            return text, usage
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", "ignore")
            last_err = f"HTTP {e.code}: {err_body[:300]}"
            if e.code in (429, 500, 502, 503, 529) and attempt < retries:
                time.sleep(2 ** attempt * 3)
                continue
            raise RuntimeError(f"Anthropic call failed: {last_err}")
        except Exception as e:
            last_err = str(e)
            if attempt < retries:
                time.sleep(2 ** attempt * 3)
                continue
            raise RuntimeError(f"Anthropic call failed: {last_err}")
    raise RuntimeError(f"Anthropic call failed: {last_err}")


def call_opus(prompt, system=None, max_tokens=4000, temperature=None,
              cache_system=True, retries=2):
    """Backward-compatible wrapper — strategy tier (Fable 5)."""
    return call_model(prompt, tier="brain", system=system, max_tokens=max_tokens,
                      temperature=temperature, cache_system=cache_system, retries=retries)


def call_voice(prompt, system=None, max_tokens=1500, temperature=0.4, cache_system=False):
    """Dialogue tier (Sonnet) — cheap conversational replies."""
    return call_model(prompt, tier="voice", system=system, max_tokens=max_tokens,
                      temperature=temperature, cache_system=cache_system)


def call_micro(prompt, system=None, max_tokens=200, temperature=0.0):
    """Micro tier (Haiku) — cheap classification/routing."""
    return call_model(prompt, tier="micro", system=system, max_tokens=max_tokens,
                      temperature=temperature, cache_system=False)


if __name__ == "__main__":
    import sys
    print(f"Model:            {OPUS_MODEL}")
    print(f"Key present:      {bool(ANTHROPIC_API_KEY)}")
    d = _load_budget()
    print(f"Month:            {d['month']}")
    print(f"Spent this month: ${d.get('spent_usd', 0):.4f} / ${MONTHLY_BUDGET_USD:.0f}")
    print(f"Remaining:        ${remaining_budget():.4f}")
    print(f"Brain available:  {brain_available()}")
    if "--test" in sys.argv and brain_available():
        txt, usage = call_opus(
            prompt="Reply with exactly: BRAIN_OK",
            system="You are a test harness.",
            max_tokens=20, cache_system=False,
        )
        print("Test reply:", txt.strip())
        print("Usage:", usage)
