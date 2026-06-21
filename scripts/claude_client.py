#!/usr/bin/env python3
"""
Anthropic Claude API client (Messages API) — economy edition.

This project produces a halal product catalog where text quality and factual
accuracy matter more than per-token cost, so all generation runs on Claude
Sonnet (latest). DeepSeek was removed because it hallucinated non-halal
ingredients (pork) into product descriptions.

Cost controls built into this client:
  1. TELEMETRY  — every call logs tokens + USD to data/llm_costs.json
                  (per day / script / model, plus a "what it would have cost
                  without optimizations" baseline so savings are measurable).
  2. CACHING    — system prompts are sent as cache_control blocks; repeated
                  calls with the same system prefix read from cache at 10%
                  of the input price.
  3. BATCH API  — call_claude_batch() processes lists of requests at 50% of
                  standard prices (stacks with caching). Use for anything
                  generated from cron where nobody waits on the response.
  4. ADVISOR    — call_claude(..., advisor=True) attaches an Opus advisor to
                  the Sonnet executor (beta): the smart model writes a short
                  strategic brief mid-generation, the cheap model writes the
                  actual output. Falls back to a plain call if unavailable.

Public surface is unchanged so existing scripts keep working:
    from claude_client import call_claude, call_claude_cheap
    text, tokens = call_claude(prompt="...", system="...")

Auth: set ANTHROPIC_API_KEY (preferred). For backward compatibility the old
DEEPSEEK_API_KEY env var is still read as a fallback, and the module-level
DEEPSEEK_API_KEY / CLAUDE_API_KEY names remain as aliases.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

# 300s: long generations (full landing pages, 4-8K tokens out) routinely take
# >120s through the SOCKS proxy and were dying on read timeout.
SOCK_TIMEOUT_S = int(os.environ.get("ANTHROPIC_SOCK_TIMEOUT",
                                    os.environ.get("DEEPSEEK_SOCK_TIMEOUT", "300")))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", "")
ANTHROPIC_BASE = "https://api.anthropic.com"
ANTHROPIC_URL = f"{ANTHROPIC_BASE}/v1/messages"
ANTHROPIC_BATCH_URL = f"{ANTHROPIC_BASE}/v1/messages/batches"
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
# Content generation model: fast executor for templated tasks where the
# page_reviewer (Sonnet) is the quality gate. Decoupled from DEFAULT_MODEL so
# the reviewer, brain and other callers stay on Sonnet.
# Haiku tested 2026-06-21: 40% pass vs 88% on Sonnet — instruction-following
# too weak for long HTML with strict negative constraints. Keeping Sonnet here.
CONTENT_MODEL  = os.environ.get("CONTENT_MODEL", DEFAULT_MODEL)

# Advisor (beta): smart model coaches the cheap executor inside one request.
ADVISOR_MODEL = os.environ.get("ADVISOR_MODEL", "claude-opus-4-8")
ADVISOR_BETA = "advisor-tool-2026-03-01"
ADVISOR_ENABLE = os.environ.get("ADVISOR_ENABLE", "1") != "0"
_ADVISOR_BROKEN = False  # set True after a hard 4xx so we stop retrying it

# Minimum system-prompt length (chars) worth a cache_control marker.
# Anthropic ignores cache markers below the model's token minimum anyway.
CACHE_MIN_CHARS = int(os.environ.get("ANTHROPIC_CACHE_MIN_CHARS", "2000"))

# Backward-compatible aliases for scripts that import these names.
DEEPSEEK_API_KEY = ANTHROPIC_API_KEY
CLAUDE_API_KEY = ANTHROPIC_API_KEY

# ── Pricing ($ per MTok: input, output, cache_write_5m, cache_read) ──────────
PRICES = {
    "claude-sonnet": (3.0, 15.0, 3.75, 0.30),
    "claude-haiku": (1.0, 5.0, 1.25, 0.10),
    "claude-opus": (15.0, 75.0, 18.75, 1.50),
    "claude-fable": (10.0, 50.0, 12.50, 1.00),
    # Perplexity (pplx_client.py logs into the same ledger):
    "pplx-sonar-pro": (3.0, 15.0, 0.0, 0.0),
    "pplx-sonar": (1.0, 1.0, 0.0, 0.0),
    "pplx-agent": (3.0, 15.0, 0.0, 0.0),
}


def _price_for(model: str) -> tuple:
    for prefix, p in PRICES.items():
        if model.startswith(prefix):
            return p
    return PRICES["claude-sonnet"]


# ── Cost ledger ───────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
LEDGER = DATA_DIR / "llm_costs.json"
_SCRIPT = os.path.basename(sys.argv[0] or "unknown").replace(".py", "") or "unknown"

# ── Daily budget kill switch ──────────────────────────────────────────────────
# Hard cap on Anthropic spend per UTC day. Once today's logged cost crosses this,
# every new call raises BudgetExceeded BEFORE hitting the API — so a runaway loop
# (like the 630-page geo run on 2026-06-10) can never silently drain the balance
# again. Override with LLM_DAILY_BUDGET_USD; set to 0 to disable the guard.
LLM_DAILY_BUDGET_USD = float(os.environ.get("LLM_DAILY_BUDGET_USD", "5"))


class BudgetExceeded(RuntimeError):
    """Raised when today's logged LLM spend exceeds LLM_DAILY_BUDGET_USD."""


def today_spend_usd() -> float:
    """Anthropic USD logged for the current UTC day (0.0 on any error)."""
    try:
        led = json.loads(LEDGER.read_text())
        month = led.get(date.today().strftime("%Y-%m"), {})
        return float(month.get("days", {}).get(date.today().isoformat(), {})
                     .get("usd", 0.0))
    except Exception:
        return 0.0


def _budget_guard() -> None:
    if LLM_DAILY_BUDGET_USD <= 0:
        return
    spent = today_spend_usd()
    if spent >= LLM_DAILY_BUDGET_USD:
        raise BudgetExceeded(
            f"Дневной лимит LLM исчерпан: ${spent:.2f} >= "
            f"${LLM_DAILY_BUDGET_USD:.2f}. Генерация остановлена "
            f"(LLM_DAILY_BUDGET_USD). Завтра счётчик обнулится."
        )


def _usage_cost(model: str, usage: dict, batch: bool) -> tuple[float, float]:
    """Returns (actual_usd, baseline_usd). Baseline = no cache, no batch."""
    pin, pout, pwrite, pread = _price_for(model)
    inp = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    cw = usage.get("cache_creation_input_tokens", 0) or 0
    cr = usage.get("cache_read_input_tokens", 0) or 0
    actual = (inp * pin + out * pout + cw * pwrite + cr * pread) / 1e6
    if batch:
        actual *= 0.5
    baseline = ((inp + cw + cr) * pin + out * pout) / 1e6
    return actual, baseline


def _iterations_cost(model: str, usage: dict, batch: bool) -> tuple[float, float, dict]:
    """Cost including advisor sub-inference iterations (billed at advisor rates)."""
    iters = usage.get("iterations") or []
    if not iters:
        a, b = _usage_cost(model, usage, batch)
        return a, b, usage
    actual = baseline = 0.0
    agg = {"input_tokens": 0, "output_tokens": 0,
           "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    for it in iters:
        m = it.get("model") or model  # advisor iterations carry their own model
        a, b = _usage_cost(m, it, batch)
        actual += a
        baseline += b
        for k in agg:
            agg[k] += it.get(k, 0) or 0
    return actual, baseline, agg


def _ledger_log(model: str, usage: dict, batch: bool = False,
                extra_usd: float = 0.0) -> None:
    """Append usage to the month ledger. Never raises.

    extra_usd: per-request costs beyond tokens (e.g. Perplexity search fees);
    added to both actual and baseline."""
    try:
        actual, baseline, agg = _iterations_cost(model, usage, batch)
        actual += extra_usd
        baseline += extra_usd
        DATA_DIR.mkdir(exist_ok=True)
        lock_path = str(LEDGER) + ".lock"
        try:
            import fcntl
            lock = open(lock_path, "w")
            fcntl.flock(lock, fcntl.LOCK_EX)
        except Exception:
            lock = None
        try:
            try:
                led = json.loads(LEDGER.read_text())
            except Exception:
                led = {}
            month = date.today().strftime("%Y-%m")
            day = date.today().isoformat()
            m = led.setdefault(month, {"usd": 0.0, "usd_baseline": 0.0,
                                       "days": {}, "scripts": {}, "models": {}})

            def bump(node):
                node["calls"] = node.get("calls", 0) + 1
                node["in"] = node.get("in", 0) + (agg.get("input_tokens", 0) or 0)
                node["out"] = node.get("out", 0) + (agg.get("output_tokens", 0) or 0)
                node["cache_w"] = node.get("cache_w", 0) + (agg.get("cache_creation_input_tokens", 0) or 0)
                node["cache_r"] = node.get("cache_r", 0) + (agg.get("cache_read_input_tokens", 0) or 0)
                node["usd"] = round(node.get("usd", 0.0) + actual, 6)
                node["usd_baseline"] = round(node.get("usd_baseline", 0.0) + baseline, 6)

            m["usd"] = round(m["usd"] + actual, 6)
            m["usd_baseline"] = round(m["usd_baseline"] + baseline, 6)
            bump(m["days"].setdefault(day, {}))
            bump(m["scripts"].setdefault(_SCRIPT, {}))
            bump(m["models"].setdefault(model, {}))
            LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1))
        finally:
            if lock:
                lock.close()
    except Exception:
        pass


def month_summary() -> dict:
    """Current-month cost summary for reporting (bot's «💰 Бюджет»)."""
    try:
        led = json.loads(LEDGER.read_text())
        return led.get(date.today().strftime("%Y-%m"), {})
    except Exception:
        return {}


# ── HTTP transport ────────────────────────────────────────────────────────────
def _headers(betas: list | None = None) -> dict:
    h = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    if betas:
        h["anthropic-beta"] = ",".join(betas)
    return h


# Proxy chain: primary + any fallbacks. Anthropic geo-blocks the RU VPS, and the
# mobile SOCKS5 proxies rotate/drop without warning — so we try each in turn on a
# CONNECTION error and only give up when all are exhausted. Set extras via
# ANTHROPIC_PROXY_FALLBACK (one URL) or ANTHROPIC_PROXIES (comma-separated).
def _proxy_chain() -> list[str]:
    chain = []
    if ANTHROPIC_PROXY:
        chain.append(ANTHROPIC_PROXY)
    fb = os.environ.get("ANTHROPIC_PROXY_FALLBACK", "").strip()
    if fb:
        chain.append(fb)
    for p in os.environ.get("ANTHROPIC_PROXIES", "").split(","):
        p = p.strip()
        if p:
            chain.append(p)
    # de-dup preserving order
    seen, out = set(), []
    for p in chain:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _http(method: str, url: str, body: bytes | None = None,
          headers: dict | None = None, timeout: int = None) -> bytes:
    timeout = timeout or SOCK_TIMEOUT_S
    headers = headers or _headers()
    chain = _proxy_chain()
    if chain and _HAS_REQUESTS:
        last_exc = None
        for i, proxy in enumerate(chain):
            try:
                r = _requests.request(
                    method, url, data=body, headers=headers, timeout=timeout,
                    proxies={"http": proxy, "https": proxy},
                )
            except Exception as exc:  # connection-level failure → try next proxy
                last_exc = exc
                if i + 1 < len(chain):
                    print(f"⚠️  proxy {i+1}/{len(chain)} down, trying next …",
                          file=sys.stderr)
                continue
            if r.status_code >= 400:
                import io
                # fp carries the body so callers' e.read() sees the API error text.
                raise urllib.error.HTTPError(url, r.status_code, r.text[:500],
                                             None, io.BytesIO(r.content))
            return r.content
        raise last_exc if last_exc else RuntimeError("all proxies failed")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _make_request(data: bytes, headers: dict, timeout: int = None) -> bytes:
    """Back-compat shim (old name) — POST /v1/messages."""
    return _http("POST", ANTHROPIC_URL, data, headers, timeout)


# ── Request building / response parsing ──────────────────────────────────────
def _supports_effort(model: str) -> bool:
    """output_config.effort is supported on Sonnet 4.6+, Opus 4.5+, Fable,
    Mythos — but NOT on Haiku (batch items with it get invalid_request)."""
    return (model.startswith(("claude-fable", "claude-mythos"))
            or model.startswith("claude-sonnet-4-6")
            or model.startswith(("claude-opus-4-5", "claude-opus-4-6",
                                 "claude-opus-4-7", "claude-opus-4-8")))


def _strict_schema(schema):
    """Structured outputs require additionalProperties=false on every object."""
    if isinstance(schema, dict):
        s = {k: _strict_schema(v) for k, v in schema.items()}
        if s.get("type") == "object" and "additionalProperties" not in s:
            s["additionalProperties"] = False
        return s
    if isinstance(schema, list):
        return [_strict_schema(x) for x in schema]
    return schema


def _build_body(prompt: str, system: str, model: str, max_tokens: int,
                temperature: float, cache_system: bool, advisor: bool,
                effort: str = None, json_schema: dict = None) -> dict:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        if cache_system and len(system) >= CACHE_MIN_CHARS:
            body["system"] = [{"type": "text", "text": system,
                               "cache_control": {"type": "ephemeral"}}]
        else:
            body["system"] = system
    # output_config: effort cuts output-token spend (the dominant cost for
    # generation: $15/MTok out vs $3 in); json_schema guarantees valid JSON.
    out_cfg = {}
    if effort and _supports_effort(model):
        out_cfg["effort"] = effort
    if json_schema:
        out_cfg["format"] = {"type": "json_schema",
                             "schema": _strict_schema(json_schema)}
    if out_cfg:
        body["output_config"] = out_cfg
    if advisor:
        body["tools"] = [{
            "type": "advisor_20260301",
            "name": "advisor",
            "model": ADVISOR_MODEL,
            "max_uses": int(os.environ.get("ADVISOR_MAX_USES", "1")),
        }]
    return body


def _parse_message(data: dict) -> tuple[str, dict]:
    if data.get("type") == "error" or "error" in data:
        raise RuntimeError(f"Anthropic error: {data.get('error', data)}")
    parts = []
    for block in data.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts), data.get("usage", {}) or {}


def _parse_response(raw: bytes) -> tuple[str, int]:
    """Back-compat: parse a Messages response into (text, output_tokens)."""
    text, usage = _parse_message(json.loads(raw))
    return text, usage.get("output_tokens", 0)


# ── Public API ────────────────────────────────────────────────────────────────
def call_claude(
    prompt: str,
    system: str = "",
    model: str = None,
    max_tokens: int = 4096,
    use_proxy: bool = True,   # kept for backward compat, ignored
    temperature: float = 0.7,
    advisor: bool = False,
    cache_system: bool = True,
    effort: str = None,
    json_schema: dict = None,
    _retries: int = 3,
) -> tuple[str, int]:
    """Call Claude Messages API. Returns (text, output_tokens).

    advisor=True attaches an Opus advisor (beta) to a Sonnet/Haiku executor for
    higher-quality output at executor prices; silently falls back when the beta
    is unavailable on this account.
    effort: "low"|"medium"|"high"|"max" — token-spend control (default high).
    json_schema: structured output — the response text is guaranteed valid JSON
    matching the schema. Both degrade gracefully on API rejection.
    """
    global _ADVISOR_BROKEN
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    _budget_guard()

    model = model or DEFAULT_MODEL
    use_advisor = (advisor and ADVISOR_ENABLE and not _ADVISOR_BROKEN
                   and not model.startswith(("claude-opus", "claude-fable")))
    use_out_cfg = bool(effort or json_schema)

    def rebuild():
        b = _build_body(prompt, system, model, max_tokens, temperature,
                        cache_system, use_advisor,
                        effort=effort if use_out_cfg else None,
                        json_schema=json_schema if use_out_cfg else None)
        return b, json.dumps(b).encode(), _headers(
            [ADVISOR_BETA] if use_advisor else None)

    body_dict, body, headers = rebuild()

    errors = []
    for attempt in range(_retries):
        try:
            raw = _make_request(body, headers)
            text, usage = _parse_message(json.loads(raw))
            _ledger_log(body_dict["model"], usage)
            return text, usage.get("output_tokens", 0)
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode()
            except Exception:
                err_body = str(e.reason or "")[:500]
            # Advisor beta rejected (no access / bad pair) → drop it and retry.
            if use_advisor and e.code in (400, 403, 404):
                _ADVISOR_BROKEN = True
                use_advisor = False
                body_dict, body, headers = rebuild()
                continue
            # output_config rejected (older model/endpoint) → drop and retry.
            if use_out_cfg and e.code == 400 and "output_config" in err_body:
                use_out_cfg = False
                body_dict, body, headers = rebuild()
                continue
            if e.code in (429, 500, 502, 503, 529) and attempt < _retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            if e.code in (404,) and body_dict["model"] == DEFAULT_MODEL:
                model = FALLBACK_MODEL
                body_dict, body, headers = rebuild()
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


def call_claude_cheap(prompt: str, system: str = "", max_tokens: int = 2048,
                      effort: str = "low") -> tuple[str, int]:
    """Use a cheaper/faster model for simple tasks like reports."""
    try:
        return call_claude(prompt, system=system, model=CHEAP_MODEL,
                           max_tokens=max_tokens, effort=effort)
    except Exception:
        return call_claude(prompt, system=system, model=CHEAP_FALLBACK,
                           max_tokens=max_tokens, effort=effort)


def count_tokens(prompt: str, system: str = "", model: str = None) -> int:
    """Free pre-flight token count (POST /v1/messages/count_tokens).

    Returns input_tokens, or -1 when the endpoint is unavailable."""
    try:
        body = {"model": model or DEFAULT_MODEL,
                "messages": [{"role": "user", "content": prompt}]}
        if system:
            body["system"] = system
        raw = _http("POST", f"{ANTHROPIC_BASE}/v1/messages/count_tokens",
                    json.dumps(body).encode(), timeout=60)
        return json.loads(raw).get("input_tokens", -1)
    except Exception:
        return -1


# ── Batch API (50% off; stacks with prompt caching) ──────────────────────────
def call_claude_batch(
    items: list,
    poll_every: int = 30,
    timeout_s: int = int(os.environ.get("ANTHROPIC_BATCH_TIMEOUT", "5400")),
) -> dict:
    """Process many Messages requests via the Message Batches API.

    items: [{"custom_id": str, "prompt": str, "system": str?, "model": str?,
             "max_tokens": int?, "temperature": float?}]
    Returns {custom_id: {"ok": True, "text": ..., "tokens": int} |
                        {"ok": False, "error": str}}.

    Blocks until the batch ends (most batches < 1h) or timeout_s elapses.
    All usage is logged to the ledger with the 50% batch discount applied.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    _budget_guard()
    if not items:
        return {}

    requests_payload = []
    for it in items:
        body = _build_body(
            prompt=it["prompt"], system=it.get("system", ""),
            model=it.get("model") or DEFAULT_MODEL,
            max_tokens=it.get("max_tokens", 4096),
            temperature=it.get("temperature", 0.7),
            cache_system=True, advisor=False,
            effort=it.get("effort"), json_schema=it.get("json_schema"),
        )
        requests_payload.append({"custom_id": it["custom_id"], "params": body})

    raw = _http("POST", ANTHROPIC_BATCH_URL,
                json.dumps({"requests": requests_payload}).encode())
    batch = json.loads(raw)
    batch_id = batch.get("id")
    if not batch_id:
        raise RuntimeError(f"batch create failed: {str(batch)[:300]}")
    print(f"📦 batch {batch_id}: {len(items)} requests submitted", flush=True)

    deadline = time.time() + timeout_s
    results_url = None
    while time.time() < deadline:
        time.sleep(poll_every)
        try:
            st = json.loads(_http("GET", f"{ANTHROPIC_BATCH_URL}/{batch_id}"))
        except Exception as e:
            print(f"  batch poll error (retrying): {e}", file=sys.stderr)
            continue
        status = st.get("processing_status")
        if status == "ended":
            results_url = st.get("results_url")
            break
        counts = st.get("request_counts", {})
        print(f"  …batch {status}: {counts}", flush=True)
    if not results_url:
        # CRITICAL: cancel the orphan batch. Otherwise it finishes server-side
        # and bills full price while the caller falls back to sync calls —
        # paying for the same content twice.
        try:
            _http("POST", f"{ANTHROPIC_BATCH_URL}/{batch_id}/cancel", b"")
            print(f"  batch {batch_id} cancelled (timeout)", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"  batch cancel failed: {e}", file=sys.stderr)
        raise RuntimeError(f"batch {batch_id} did not finish within {timeout_s}s")

    out: dict = {}
    raw_results = _http("GET", results_url, timeout=600)
    for line in raw_results.decode().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            cid = row.get("custom_id")
            res = row.get("result", {})
            if res.get("type") == "succeeded":
                msg = res.get("message", {})
                text, usage = _parse_message(msg)
                _ledger_log(msg.get("model", DEFAULT_MODEL), usage, batch=True)
                out[cid] = {"ok": True, "text": text,
                            "tokens": usage.get("output_tokens", 0)}
            else:
                err = res.get("error", {}) or {}
                out[cid] = {"ok": False,
                            "error": f"{res.get('type')}: {str(err)[:200]}"}
        except Exception as e:
            print(f"  bad result line: {e}", file=sys.stderr)
    ok = sum(1 for v in out.values() if v.get("ok"))
    print(f"📦 batch done: {ok}/{len(items)} succeeded", flush=True)
    return out


if __name__ == "__main__":
    print("Testing Anthropic Claude API …")
    print(f"  Model: {DEFAULT_MODEL}")
    print(f"  Key set: {bool(ANTHROPIC_API_KEY)}")
    try:
        text, tokens = call_claude(
            prompt="Say 'SEO agent online' and nothing else.",
            system="You are a helpful assistant.",
            max_tokens=20,
        )
        print(f"✅ Response: {text.strip()}  ({tokens} out tok)")
        s = month_summary()
        print(f"   Month so far: ${s.get('usd', 0):.4f} "
              f"(baseline ${s.get('usd_baseline', 0):.4f})")
    except Exception as e:
        print(f"❌ Error: {e}")
