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
import sys
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


def _proxy_chain() -> list:
    """Primary proxy + fallbacks (mobile SOCKS5 proxies drop without warning)."""
    chain = [ANTHROPIC_PROXY] if ANTHROPIC_PROXY else []
    fb = os.environ.get("ANTHROPIC_PROXY_FALLBACK", "").strip()
    if fb:
        chain.append(fb)
    for p in os.environ.get("ANTHROPIC_PROXIES", "").split(","):
        p = p.strip()
        if p:
            chain.append(p)
    seen, out = set(), []
    for p in chain:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out

try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False

# Model is configurable so you can switch brain versions without code changes.
# Default: Claude Opus 4.8 — Fable 5 was suspended for all customers by a US
# government export-control directive on 2026-06-12 (returns HTTP 404, recommends
# Opus 4.8). Switch back to claude-fable-5 via OPUS_MODEL if/when it returns.
OPUS_MODEL = os.environ.get("OPUS_MODEL", "claude-opus-4-8")

# Monthly hard cap in USD. Default 40; override with OPUS_MONTHLY_BUDGET_USD.
MONTHLY_BUDGET_USD = float(os.environ.get("OPUS_MONTHLY_BUDGET_USD", "40"))

# Pricing (USD per 1M tokens) for Opus 4.8 (half of Fable 5). Override via env.
PRICE_INPUT       = float(os.environ.get("OPUS_PRICE_INPUT",       "5"))    # fresh input
PRICE_OUTPUT      = float(os.environ.get("OPUS_PRICE_OUTPUT",      "25"))   # output
PRICE_CACHE_WRITE = float(os.environ.get("OPUS_PRICE_CACHE_WRITE", "6.25")) # cache creation
PRICE_CACHE_READ  = float(os.environ.get("OPUS_PRICE_CACHE_READ",  "0.50")) # cache hit

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
BUDGET_FILE = DATA / "opus_budget.json"

# ── Multi-tier model registry ───────────────────────────────────────────────────
# Three tiers: "brain" (Fable 5, strategy), "voice" (Sonnet, dialogue),
# "micro" (Haiku, cheap classification). Prices USD per 1M tokens.
MODELS = {
    "brain": {
        "model": os.environ.get("OPUS_MODEL", "claude-opus-4-8"),
        "in": float(os.environ.get("OPUS_PRICE_INPUT", "5")),
        "out": float(os.environ.get("OPUS_PRICE_OUTPUT", "25")),
        "cache_write": float(os.environ.get("OPUS_PRICE_CACHE_WRITE", "6.25")),
        "cache_read": float(os.environ.get("OPUS_PRICE_CACHE_READ", "0.50")),
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
    effort: str = None,
    json_schema: dict = None,
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
    # output_config: effort trims thinking/output spend (Fable bills $50/MTok
    # out); json_schema makes the strategy JSON structurally guaranteed.
    out_cfg = {}
    if effort:
        out_cfg["effort"] = effort
    if json_schema:
        try:
            from claude_client import _strict_schema
            json_schema = _strict_schema(json_schema)
        except Exception:
            pass
        out_cfg["format"] = {"type": "json_schema", "schema": json_schema}
    if out_cfg:
        body["output_config"] = out_cfg

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    data = json.dumps(body).encode("utf-8")
    last_err = None
    for attempt in range(retries + 1):
        try:
            chain = _proxy_chain()
            if chain and _HAS_REQUESTS:
                r = None
                conn_err = None
                for i, proxy in enumerate(chain):
                    try:
                        r = requests.post(
                            ANTHROPIC_URL, data=data, headers=headers, timeout=180,
                            proxies={"http": proxy, "https": proxy},
                        )
                        break
                    except Exception as ce:  # connection-level → next proxy
                        conn_err = ce
                        r = None
                        if i + 1 < len(chain):
                            print(f"⚠️  brain proxy {i+1}/{len(chain)} down, "
                                  f"trying next …", file=sys.stderr)
                if r is None:
                    raise conn_err if conn_err else RuntimeError("all proxies failed")
                if r.status_code >= 400:
                    # requests responses have no urllib `.fp` file object, so a
                    # bare HTTPError(..., fp=None) makes the except-block's
                    # e.read() raise KeyError('file') internally — swallowing
                    # the real Anthropic error body and logging "HTTP 400: ()"
                    # forever. Carry the body as an attribute instead.
                    http_err = urllib.error.HTTPError(
                        ANTHROPIC_URL, r.status_code, r.reason or "", None, None
                    )
                    http_err.body = r.text[:300]
                    raise http_err
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
            # Mirror into the unified LLM cost ledger (data/llm_costs.json).
            try:
                from claude_client import _ledger_log
                _ledger_log(cfg["model"], usage)
            except Exception:
                pass
            return text, usage
        except urllib.error.HTTPError as e:
            # Prefer the body we stashed for requests-originated errors (fp is
            # None there, so e.read() raises KeyError('file') and hides the
            # real message). Fall back to a real urllib file read otherwise.
            err_body = getattr(e, "body", None)
            if err_body is None:
                try:
                    err_body = e.read().decode("utf-8", "ignore")
                except Exception:
                    err_body = str(e.reason or e.msg or "")
            last_err = f"HTTP {e.code}: {err_body[:300]}"
            # output_config not supported here → drop it once and retry.
            if e.code == 400 and "output_config" in err_body and "output_config" in body:
                body.pop("output_config", None)
                data = json.dumps(body).encode("utf-8")
                continue
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
              cache_system=True, retries=2, effort=None, json_schema=None):
    """Backward-compatible wrapper — strategy tier (Fable 5)."""
    return call_model(prompt, tier="brain", system=system, max_tokens=max_tokens,
                      temperature=temperature, cache_system=cache_system,
                      retries=retries, effort=effort, json_schema=json_schema)


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
