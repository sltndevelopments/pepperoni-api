#!/usr/bin/env python3
"""Perplexity API client — live web intelligence for the agent system.

Perplexity is used where it beats Anthropic: real-time web search. Two entry
points:

  pplx_search(prompt)  — Chat Completions with the `sonar`/`sonar-pro` online
                         models. One question → grounded answer + citations.
  pplx_agent(input)    — Agent API (/v1/agent): multi-step research loop with
                         web_search tooling and presets (fast-search /
                         pro-search / deep-research). Use for structured
                         competitive intel and market research.

All usage is logged into the shared LLM cost ledger (data/llm_costs.json) via
claude_client, so the Telegram «💰 Бюджет» button shows Anthropic + Perplexity
spend in one place.

Env: PPLX_API_KEY (required), PPLX_AGENT_PRESET (default pro-search).
"""

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))

PPLX_KEY = os.environ.get("PPLX_API_KEY", "").strip()
PPLX_BASE = "https://api.perplexity.ai"
CHAT_URL = f"{PPLX_BASE}/chat/completions"
AGENT_URL = f"{PPLX_BASE}/v1/agent"

DEFAULT_SEARCH_MODEL = os.environ.get("PPLX_MODEL", "sonar-pro")
DEFAULT_AGENT_PRESET = os.environ.get("PPLX_AGENT_PRESET", "pro-search")
SEARCH_FEE_USD = 0.005  # ≈ $5 per 1K search requests


def _ledger(model: str, usage: dict, extra_usd: float = 0.0) -> None:
    try:
        from claude_client import _ledger_log
        _ledger_log(model, usage, extra_usd=extra_usd)
    except Exception:
        pass


def _post(url: str, payload: dict, timeout: int = 120) -> dict:
    if not PPLX_KEY:
        raise RuntimeError("PPLX_API_KEY not set")
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {PPLX_KEY}",
                 "Content-Type": "application/json"})
    raw = urllib.request.urlopen(req, timeout=timeout).read()
    return json.loads(raw)


def pplx_search(prompt: str, system: str = "", model: str = None,
                max_tokens: int = 2048, timeout: int = 90) -> tuple[str, list]:
    """One grounded web answer. Returns (text, citations)."""
    model = model or DEFAULT_SEARCH_MODEL
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    data = _post(CHAT_URL, {"model": model, "messages": messages,
                            "max_tokens": max_tokens}, timeout=timeout)
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    citations = data.get("citations") or data.get("search_results") or []
    u = data.get("usage", {}) or {}
    searches = u.get("num_search_queries") or 1
    _ledger(f"pplx-{model}",
            {"input_tokens": u.get("prompt_tokens", 0),
             "output_tokens": u.get("completion_tokens", 0)},
            extra_usd=searches * SEARCH_FEE_USD)
    return text, citations


def _walk_text(node) -> list:
    """Collect output_text blocks from an Agent API output tree."""
    out = []
    if isinstance(node, dict):
        if node.get("type") == "output_text" and node.get("text"):
            out.append(node["text"])
        for v in node.values():
            out.extend(_walk_text(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_walk_text(v))
    return out


def pplx_agent(input_text: str, instructions: str = "", preset: str = None,
               max_output_tokens: int = 3000, max_steps: int = None,
               json_schema: dict = None, timeout: int = 300) -> str:
    """Multi-step web research via the Agent API. Returns the final text.

    json_schema: when given, requests structured output validated against the
    schema — eliminates truncated/malformed JSON from free-text answers."""
    payload = {
        "preset": preset or DEFAULT_AGENT_PRESET,
        "input": input_text,
        "max_output_tokens": max_output_tokens,
    }
    if instructions:
        payload["instructions"] = instructions
    if max_steps:
        payload["max_steps"] = max_steps
    if json_schema:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "result", "schema": json_schema},
        }
    data = _post(AGENT_URL, payload, timeout=timeout)
    if data.get("error"):
        raise RuntimeError(f"pplx agent error: {str(data['error'])[:200]}")
    text = "\n".join(_walk_text(data.get("output", [])))
    u = data.get("usage", {}) or {}
    searches = (u.get("num_search_queries")
                or sum(1 for it in data.get("output", [])
                       if isinstance(it, dict) and "search" in str(it.get("type", ""))))
    _ledger("pplx-agent",
            {"input_tokens": u.get("input_tokens", u.get("prompt_tokens", 0)),
             "output_tokens": u.get("output_tokens", u.get("completion_tokens", 0))},
            extra_usd=max(searches, 1) * SEARCH_FEE_USD)
    return text


def pplx_agent_json(input_text: str, instructions: str = "", **kw) -> dict:
    """Agent call that must return JSON. Tolerates markdown fences and repairs
    output truncated at the token cap (close open strings/brackets)."""
    raw = pplx_agent(input_text, instructions=instructions, **kw)
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1].rsplit("```", 1)[0]
    start, end = s.find("{"), s.rfind("}")
    if start >= 0 and end > start:
        s = s[start:end + 1]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return json.loads(_repair_json(s[start:] if start >= 0 else s))


def _repair_json(s: str) -> str:
    """Best-effort close of a truncated JSON object."""
    out, in_str, esc = [], False, False
    stack = []
    for ch in s:
        if esc:
            esc = False
        elif ch == "\\" and in_str:
            esc = True
        elif ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch in "{[":
                stack.append("}" if ch == "{" else "]")
            elif ch in "}]" and stack:
                stack.pop()
        out.append(ch)
    if in_str:
        out.append('"')
    # Drop a dangling trailing comma / colon before closing.
    tail = "".join(out).rstrip()
    while tail and tail[-1] in ",:":
        tail = tail[:-1].rstrip()
    return tail + "".join(reversed(stack))


if __name__ == "__main__":
    print(f"PPLX key set: {bool(PPLX_KEY)}")
    if PPLX_KEY:
        try:
            text, cites = pplx_search("Кто крупнейшие производители халяль колбасы в России? Кратко.")
            print(f"✅ sonar: {text[:200]}…  ({len(cites)} citations)")
        except Exception as e:
            print(f"❌ search: {e}")
        try:
            t = pplx_agent("Top-3 Google results for 'halal pepperoni wholesale'? One line each.",
                           max_steps=2, max_output_tokens=500)
            print(f"✅ agent: {t[:200]}…")
        except Exception as e:
            print(f"❌ agent: {e}")
