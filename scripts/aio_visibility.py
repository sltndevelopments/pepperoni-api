#!/usr/bin/env python3
"""
AIO-VISIBILITY — are we cited by AI assistants? (weekly)

Two layers, never mixed:
  memory  — weights / no live web (does the model *know* us?)
  search  — live retrieval / grounding (does it *find* us now?)

A score is written only when the provider returned real answers.
Proxy/API failure → status=fail, score=null. Missing key → status=skip.
Never record 0% for an empty panel caused by a dead proxy.

Legacy ledger aliases (do not reinterpret history):
  deepseek_score   = Claude memory (name is historical; NOT DeepSeek)
  chatgpt_score    = ChatGPT memory
  gemini_score     = Gemini memory
  perplexity_score = Perplexity search

Canonical fields: {provider}_{memory|search}_score + _status.

Env (all optional; skip the layer if unset):
  ANTHROPIC_API_KEY / ANTHROPIC_PROXY
  OPENAI_API_KEY          ChatGPT memory + search
  OPENAI_SEARCH_MODEL     default gpt-5.6
  GEMINI_API_KEY / GEMINI_MODEL (default gemini-3.7-flash)
  PPLX_API_KEY
  DEEPSEEK_API_KEY        real DeepSeek (not Claude). Probe only — never a writer.
  XAI_API_KEY             Grok
  MOONSHOT_API_KEY / KIMI_API_KEY
  MISTRAL_API_KEY
  ZHIPU_API_KEY / GLM_API_KEY
  OPENROUTER_API_KEY      fallback for Grok/Kimi/Mistral/GLM (and DeepSeek
                          if DEEPSEEK_API_KEY is missing). Not a substitute
                          for native ChatGPT/Gemini/Perplexity search.
  AIO_LAYERS              comma list to restrict providers
  AIO_CLAUDE_SEARCH=1     enable Claude web_search (off by default; cost)

Usage:
  python3 scripts/aio_visibility.py
  python3 scripts/aio_visibility.py --no-telegram --core
  python3 scripts/aio_visibility.py --layers claude_memory,chatgpt_memory
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
LEDGER = DATA / "aio_visibility.json"

PPLX_KEY = os.environ.get("PPLX_API_KEY", "").strip()
PPLX_MODEL = os.environ.get("PPLX_MODEL", "sonar")

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MEMORY_MODEL = os.environ.get("OPENAI_MEMORY_MODEL", "gpt-4o-mini").strip()
OPENAI_SEARCH_MODEL = os.environ.get("OPENAI_SEARCH_MODEL", "gpt-5.6").strip()

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.7-flash").strip() or "gemini-3.7-flash"

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()

XAI_KEY = os.environ.get("XAI_API_KEY", "").strip()
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4-1-fast").strip()

KIMI_KEY = (os.environ.get("MOONSHOT_API_KEY", "") or
            os.environ.get("KIMI_API_KEY", "")).strip()
KIMI_MODEL = os.environ.get("KIMI_MODEL", "kimi-k2.5").strip()
KIMI_BASE = os.environ.get("KIMI_BASE", "https://api.moonshot.ai/v1").rstrip("/")

MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "").strip()
MISTRAL_MODEL = os.environ.get("MISTRAL_MODEL", "mistral-small-latest").strip()

GLM_KEY = (os.environ.get("ZHIPU_API_KEY", "") or
           os.environ.get("GLM_API_KEY", "")).strip()
GLM_MODEL = os.environ.get("GLM_MODEL", "glm-4.5-flash").strip()

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Public slugs on openrouter.ai/api/v1/models (2026-08-17).
OR_GROK = os.environ.get("OPENROUTER_GROK_MODEL", "x-ai/grok-4.6").strip()
OR_KIMI = os.environ.get("OPENROUTER_KIMI_MODEL", "moonshotai/kimi-k2.5").strip()
OR_MISTRAL = os.environ.get("OPENROUTER_MISTRAL_MODEL",
                            "mistralai/mistral-small-2603").strip()
OR_GLM = os.environ.get("OPENROUTER_GLM_MODEL", "z-ai/glm-4.7-flash").strip()
OR_DEEPSEEK = os.environ.get("OPENROUTER_DEEPSEEK_MODEL",
                             "deepseek/deepseek-v4-flash").strip()

_PROXY = (os.environ.get("ANTHROPIC_PROXY", "") or
          os.environ.get("HTTPS_PROXY", "") or
          os.environ.get("HTTP_PROXY", "")).strip()

SYSTEM = (
    "You are a B2B food procurement assistant. Answer concretely: "
    "name real companies, brands and websites if you know them."
)
SYSTEM_RU = (
    "Ты помощник по B2B-закупкам продуктов питания в России. Отвечай "
    "конкретно: называй реальные компании, бренды и сайты, если знаешь."
)

CORE_QUESTIONS = [
    "Где купить халяльную пепперони оптом в России? Назови производителей.",
    "Какие компании производят халяльные сосиски для хот-догов оптом в РФ?",
    "Кто делает халяльные котлеты для бургеров (паттисы) оптом под СТМ в России?",
    "Посоветуй производителя халяльных мясных деликатесов в Казани для опта.",
    "Где заказать контрактное производство (private label) халяльных колбас в России?",
    "Кто производит казылык оптом? Назови поставщиков.",
    "Какие производители татарской выпечки (эчпочмак, чак-чак) работают оптом?",
    "Производители халяльной пепперони для пиццерий оптом в России — кого посоветуешь?",
    "أين يمكن شراء بيبروني حلال بالجملة للتصدير إلى الإمارات أو السعودية؟ اذكر مصنّعين.",
    "من هم موردو اللحوم الحلال من روسيا إلى دول الخليج؟",
    "Қазақстанға халал шұжық пен пепперониді көтерме жеткізетін өндірушілер кімдер?",
    "Halal pepperoni supplier for export to UAE and Saudi Arabia — which manufacturers do you recommend?",
]

US_PATTERNS = [
    r"pepperoni\.tatar",
    r"казанские\s+деликатес",
    r"kazandelikates",
    r"kazan\s+delicac",
    r"пепперони\s+татар",
    r"\+?7\s*9?87\s*217",
    r"217-02-02",
]

# Canonical layer ids. copilot has no public probe API.
LAYER_IDS = [
    "claude_memory", "claude_search",
    "chatgpt_memory", "chatgpt_search",
    "gemini_memory", "gemini_search",
    "perplexity_search",
    "deepseek_memory",
    "grok_memory", "grok_search",
    "kimi_memory",
    "mistral_memory",
    "glm_memory",
    "copilot",
]


def mentions_us(text: str) -> bool:
    t = (text or "").lower()
    return any(re.search(p, t, re.I) for p in US_PATTERNS)


def _rotating_questions(limit: int = 4) -> list[str]:
    import sqlite3
    from datetime import timedelta
    db = ROOT / "data" / "seo_data.db"
    if not db.exists():
        return []
    try:
        conn = sqlite3.connect(db)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=28)).strftime("%Y-%m-%d")
        rows = conn.execute("""
            SELECT query, SUM(impressions) AS impr FROM gsc_queries
            WHERE date >= ? GROUP BY query ORDER BY impr DESC LIMIT 60
        """, (cutoff,)).fetchall()
        conn.close()
    except Exception:
        return []
    commercial = [q for q, _ in rows if any(
        w in q.lower() for w in ("купить", "оптом", "производител", "поставщик",
                                 "цена", "halal", "wholesale", "supplier"))]
    if not commercial:
        return []
    week = int(datetime.now(timezone.utc).strftime("%W"))
    start = (week * limit) % max(len(commercial), 1)
    picked = (commercial + commercial)[start:start + limit]
    return [f"{q} — посоветуй конкретных производителей или поставщиков." for q in picked]


def panel_questions(with_gsc: bool) -> list[str]:
    qs = list(CORE_QUESTIONS)
    if with_gsc:
        qs.extend(_rotating_questions())
    return qs


# ---------------------------------------------------------------- HTTP

def _proxy_chain() -> list[str]:
    chain: list[str] = []
    for raw in (
        os.environ.get("ANTHROPIC_PROXY", ""),
        os.environ.get("ANTHROPIC_PROXY_FALLBACK", ""),
        *os.environ.get("ANTHROPIC_PROXIES", "").split(","),
    ):
        p = raw.strip()
        if p and p not in chain:
            chain.append(p)
    return chain


def _post_json(url: str, payload: dict, headers: dict,
               timeout: int = 45, use_proxy: bool = True) -> tuple[dict | None, str | None]:
    """POST JSON. Returns (data, error). error is set on HTTP/network failure."""
    last_err = None
    proxies = (_proxy_chain() or [None]) if use_proxy else [None]
    try:
        import requests
    except Exception:
        requests = None  # type: ignore

    if requests is not None:
        for proxy in proxies:
            try:
                kw = {"timeout": timeout, "headers": headers, "json": payload}
                if proxy:
                    kw["proxies"] = {"http": proxy, "https": proxy}
                resp = requests.post(url, **kw)
                if resp.status_code >= 400:
                    last_err = f"{resp.status_code} {resp.text[:240]}"
                    continue
                return resp.json(), None
            except Exception as e:
                last_err = str(e)[:240]
                continue

    if use_proxy and _proxy_chain():
        return None, last_err or "proxy required and requests failed"
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:240]
        except Exception:
            body = str(e.reason or "")[:240]
        return None, f"HTTP {e.code}: {body}"
    except Exception as e:
        return None, str(e)[:240]


def _message_text(msg: dict) -> str:
    c = (msg or {}).get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(
            (p.get("text") or "") for p in c if isinstance(p, dict))
    return ""


def _openai_compat(q: str, *, key: str, url: str, model: str,
                   extra_body: dict | None = None,
                   extra_headers: dict | None = None,
                   timeout: int = 45) -> tuple[str, str | None]:
    if not key:
        return "", "no key"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": q},
        ],
        "max_tokens": 600,
        "temperature": 0.2,
    }
    if extra_body:
        payload.update(extra_body)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    if extra_headers:
        headers.update(extra_headers)
    data, err = _post_json(url, payload, headers, timeout=timeout)
    if err:
        return "", err
    if data.get("error"):
        return "", str(data["error"])[:240]
    try:
        return _message_text(data["choices"][0]["message"]) or "", None
    except Exception as e:
        return "", f"parse: {e}"


def _openrouter(q: str, model: str, search: bool = False,
                timeout: int = 60) -> tuple[str, str | None]:
    extra = {}
    if search:
        extra["tools"] = [{"type": "openrouter:web_search"}]
        timeout = max(timeout, 90)
    return _openai_compat(
        q, key=OPENROUTER_KEY, url=OPENROUTER_URL, model=model,
        extra_body=extra or None, timeout=timeout,
        extra_headers={
            "HTTP-Referer": "https://pepperoni.tatar",
            "X-Title": "pepperoni-aio-visibility",
        })


# ---------------------------------------------------------------- providers

def ask_claude_memory(q: str) -> tuple[str, str | None]:
    try:
        from claude_client import call_claude, ANTHROPIC_API_KEY
    except Exception as e:
        return "", f"import: {e}"
    if not ANTHROPIC_API_KEY:
        return "", "no key"
    try:
        text, _ = call_claude(q, system=SYSTEM_RU, max_tokens=600)
        return text or "", None
    except Exception as e:
        return "", str(e)[:240]


def ask_chatgpt_memory(q: str) -> tuple[str, str | None]:
    return _openai_compat(
        q, key=OPENAI_KEY,
        url="https://api.openai.com/v1/chat/completions",
        model=OPENAI_MEMORY_MODEL)


def _openai_output_text(data: dict) -> str:
    if data.get("output_text"):
        return str(data["output_text"])
    texts: list[str] = []
    for item in data.get("output") or []:
        if isinstance(item, dict) and item.get("type") == "message":
            for c in item.get("content") or []:
                if isinstance(c, dict) and c.get("text"):
                    texts.append(c["text"])
        elif isinstance(item, dict) and item.get("content"):
            for c in item.get("content") or []:
                if isinstance(c, dict) and c.get("text"):
                    texts.append(c["text"])
    return "\n".join(texts)


def ask_chatgpt_search(q: str) -> tuple[str, str | None]:
    if not OPENAI_KEY:
        return "", "no key"
    payload = {
        "model": OPENAI_SEARCH_MODEL,
        "input": q,
        "tools": [{"type": "web_search"}],
        "tool_choice": "web_search",
    }
    data, err = _post_json(
        "https://api.openai.com/v1/responses", payload,
        {"Content-Type": "application/json",
         "Authorization": f"Bearer {OPENAI_KEY}"},
        timeout=90)
    if err:
        return "", err
    text = _openai_output_text(data or {})
    return text, None if text else "empty output"


def _gemini(q: str, search: bool) -> tuple[str, str | None]:
    if not GEMINI_KEY:
        return "", "no key"
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent")
    payload: dict = {
        "contents": [{"parts": [{"text": SYSTEM + "\n\n" + q}]}],
        "generationConfig": {
            "maxOutputTokens": 1024,
            "temperature": 0.2,
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    if search:
        payload["tools"] = [{"google_search": {}}]
    data, err = _post_json(url, payload, {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_KEY,
    }, timeout=60)
    if err:
        return "", err
    try:
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = ""
        for p in parts:
            if isinstance(p, dict) and p.get("text"):
                text += p["text"]
        return text, None if text else "empty output"
    except Exception as e:
        return "", f"parse: {e}"


def ask_gemini_memory(q: str) -> tuple[str, str | None]:
    return _gemini(q, search=False)


def ask_gemini_search(q: str) -> tuple[str, str | None]:
    return _gemini(q, search=True)


def ask_perplexity_search(q: str) -> tuple[str, str | None]:
    if not PPLX_KEY:
        return "", "no key"
    try:
        from pplx_client import pplx_search
        text, _cites = pplx_search(
            q, system="Отвечай по актуальным данным из интернета, "
                      "называй компании и сайты.",
            model=PPLX_MODEL, timeout=40)
        return text or "", None if text else "empty output"
    except Exception as e:
        return "", str(e)[:240]


def ask_deepseek_memory(q: str) -> tuple[str, str | None]:
    native = DEEPSEEK_KEY and not DEEPSEEK_KEY.startswith("sk-ant-")
    if native:
        return _openai_compat(
            q, key=DEEPSEEK_KEY,
            url="https://api.deepseek.com/chat/completions",
            model=DEEPSEEK_MODEL)
    if OPENROUTER_KEY:
        return _openrouter(q, OR_DEEPSEEK)
    if DEEPSEEK_KEY.startswith("sk-ant-"):
        return "", "DEEPSEEK_API_KEY looks like Anthropic — skip real DeepSeek"
    return "", "no key"


def ask_grok_memory(q: str) -> tuple[str, str | None]:
    if XAI_KEY:
        return _openai_compat(
            q, key=XAI_KEY,
            url="https://api.x.ai/v1/chat/completions",
            model=XAI_MODEL)
    if OPENROUTER_KEY:
        return _openrouter(q, OR_GROK)
    return "", "no key"


def ask_grok_search(q: str) -> tuple[str, str | None]:
    if XAI_KEY:
        return _openai_compat(
            q, key=XAI_KEY,
            url="https://api.x.ai/v1/chat/completions",
            model=XAI_MODEL,
            extra_body={"search_parameters": {"mode": "on"}},
            timeout=90)
    if OPENROUTER_KEY:
        return _openrouter(q, OR_GROK, search=True)
    return "", "no key"


def ask_kimi_memory(q: str) -> tuple[str, str | None]:
    if KIMI_KEY:
        return _openai_compat(
            q, key=KIMI_KEY,
            url=f"{KIMI_BASE}/chat/completions",
            model=KIMI_MODEL)
    if OPENROUTER_KEY:
        return _openrouter(q, OR_KIMI)
    return "", "no key"


def ask_mistral_memory(q: str) -> tuple[str, str | None]:
    if MISTRAL_KEY:
        return _openai_compat(
            q, key=MISTRAL_KEY,
            url="https://api.mistral.ai/v1/chat/completions",
            model=MISTRAL_MODEL)
    if OPENROUTER_KEY:
        return _openrouter(q, OR_MISTRAL)
    return "", "no key"


def ask_glm_memory(q: str) -> tuple[str, str | None]:
    if GLM_KEY:
        return _openai_compat(
            q, key=GLM_KEY,
            url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
            model=GLM_MODEL)
    if OPENROUTER_KEY:
        return _openrouter(q, OR_GLM)
    return "", "no key"


# (asker, required_key_present, model_label, skip_reason)
def _layer_spec() -> dict[str, tuple]:
    try:
        from claude_client import ANTHROPIC_API_KEY as _ak
    except Exception:
        _ak = ""
    claude_search_on = os.environ.get("AIO_CLAUDE_SEARCH", "").strip() == "1"
    return {
        "claude_memory": (ask_claude_memory, bool(_ak), "claude-sonnet",
                          None if _ak else "no ANTHROPIC_API_KEY"),
        "claude_search": (
            ask_claude_memory, False, "claude-sonnet",
            None if claude_search_on else "off (set AIO_CLAUDE_SEARCH=1); no dedicated search asker yet"),
        "chatgpt_memory": (ask_chatgpt_memory, bool(OPENAI_KEY), OPENAI_MEMORY_MODEL,
                           None if OPENAI_KEY else "no OPENAI_API_KEY"),
        "chatgpt_search": (ask_chatgpt_search, bool(OPENAI_KEY), OPENAI_SEARCH_MODEL,
                           None if OPENAI_KEY else "no OPENAI_API_KEY"),
        "gemini_memory": (ask_gemini_memory, bool(GEMINI_KEY), GEMINI_MODEL,
                          None if GEMINI_KEY else "no GEMINI_API_KEY"),
        "gemini_search": (ask_gemini_search, bool(GEMINI_KEY), GEMINI_MODEL,
                          None if GEMINI_KEY else "no GEMINI_API_KEY"),
        "perplexity_search": (ask_perplexity_search, bool(PPLX_KEY), PPLX_MODEL,
                              None if PPLX_KEY else "no PPLX_API_KEY"),
        "deepseek_memory": (
            ask_deepseek_memory,
            bool((DEEPSEEK_KEY and not DEEPSEEK_KEY.startswith("sk-ant-"))
                 or OPENROUTER_KEY),
            DEEPSEEK_MODEL if (DEEPSEEK_KEY and not DEEPSEEK_KEY.startswith("sk-ant-"))
            else f"openrouter:{OR_DEEPSEEK}",
            None if (DEEPSEEK_KEY and not DEEPSEEK_KEY.startswith("sk-ant-")) or OPENROUTER_KEY
            else ("DEEPSEEK_API_KEY looks like Anthropic" if DEEPSEEK_KEY
                  else "no DEEPSEEK_API_KEY / OPENROUTER_API_KEY")),
        "grok_memory": (
            ask_grok_memory, bool(XAI_KEY or OPENROUTER_KEY),
            XAI_MODEL if XAI_KEY else f"openrouter:{OR_GROK}",
            None if (XAI_KEY or OPENROUTER_KEY) else "no XAI_API_KEY / OPENROUTER_API_KEY"),
        "grok_search": (
            ask_grok_search, bool(XAI_KEY or OPENROUTER_KEY),
            XAI_MODEL if XAI_KEY else f"openrouter:{OR_GROK}+web",
            None if (XAI_KEY or OPENROUTER_KEY) else "no XAI_API_KEY / OPENROUTER_API_KEY"),
        "kimi_memory": (
            ask_kimi_memory, bool(KIMI_KEY or OPENROUTER_KEY),
            KIMI_MODEL if KIMI_KEY else f"openrouter:{OR_KIMI}",
            None if (KIMI_KEY or OPENROUTER_KEY)
            else "no MOONSHOT_API_KEY / OPENROUTER_API_KEY"),
        "mistral_memory": (
            ask_mistral_memory, bool(MISTRAL_KEY or OPENROUTER_KEY),
            MISTRAL_MODEL if MISTRAL_KEY else f"openrouter:{OR_MISTRAL}",
            None if (MISTRAL_KEY or OPENROUTER_KEY)
            else "no MISTRAL_API_KEY / OPENROUTER_API_KEY"),
        "glm_memory": (
            ask_glm_memory, bool(GLM_KEY or OPENROUTER_KEY),
            GLM_MODEL if GLM_KEY else f"openrouter:{OR_GLM}",
            None if (GLM_KEY or OPENROUTER_KEY)
            else "no ZHIPU_API_KEY / OPENROUTER_API_KEY"),
        "copilot": (None, False, None,
                    "no public probe API; Bing/IndexNow is P1"),
    }


def run_layer(layer_id: str, questions: list[str]) -> dict:
    spec = _layer_spec()[layer_id]
    asker, ready, model, skip_reason = spec
    out = {
        "status": "skip",
        "score": None,
        "cited": 0,
        "asked": len(questions),
        "ok_n": 0,
        "model": model,
        "error": skip_reason,
        "items": [],
    }
    if not ready or asker is None:
        return out
    errors: list[str] = []
    items = []
    for q in questions:
        text, err = asker(q)
        if err:
            errors.append(err)
            items.append({"q": q, "cited": False, "empty": True, "error": err})
            print(f"· {layer_id} fail: {err}", file=sys.stderr)
            continue
        cited = mentions_us(text)
        empty = not (text or "").strip()
        items.append({"q": q, "cited": cited, "empty": empty, "error": None})
        if not empty:
            out["ok_n"] += 1
            if cited:
                out["cited"] += 1
    out["items"] = [{"q": i["q"], "cited": i["cited"]} for i in items]
    if out["ok_n"] == 0:
        out["status"] = "fail"
        out["score"] = None
        out["error"] = errors[0] if errors else "all answers empty"
        return out
    out["status"] = "ok"
    out["score"] = round(out["cited"] / len(questions), 3)
    out["error"] = None
    return out


def _wanted_layers(cli: list[str]) -> list[str]:
    raw = ""
    for i, a in enumerate(cli):
        if a == "--layers" and i + 1 < len(cli):
            raw = cli[i + 1]
        elif a.startswith("--layers="):
            raw = a.split("=", 1)[1]
    if not raw:
        raw = os.environ.get("AIO_LAYERS", "").strip()
    if not raw:
        return list(LAYER_IDS)
    wanted = [x.strip() for x in raw.split(",") if x.strip()]
    unknown = [x for x in wanted if x not in LAYER_IDS]
    if unknown:
        print(f"❌ unknown layers: {unknown}", file=sys.stderr)
        sys.exit(2)
    return wanted


def _score_fields(layer_id: str, result: dict) -> dict:
    return {
        f"{layer_id}_score": result["score"],
        f"{layer_id}_status": result["status"],
        f"{layer_id}_model": result.get("model"),
        f"{layer_id}_error": result.get("error"),
        f"{layer_id}_cited": result.get("cited"),
        f"{layer_id}_ok_n": result.get("ok_n"),
    }


def _layer_blob(point: dict, lid: str) -> dict | None:
    if not point.get(f"{lid}_status"):
        return None
    return {
        "status": point.get(f"{lid}_status"),
        "score": point.get(f"{lid}_score"),
        "cited": point.get(f"{lid}_cited"),
        "ok_n": point.get(f"{lid}_ok_n"),
        "model": point.get(f"{lid}_model"),
        "error": point.get(f"{lid}_error"),
    }


def _merge_point(old: dict, new: dict) -> dict:
    """Same-date merge: an ok layer is never overwritten by skip/fail."""
    skip_meta = {"layers", "won", "lost"}
    merged = dict(old)
    merged.update({k: v for k, v in new.items()
                   if k not in skip_meta and k not in LAYER_IDS and not any(
                       k.startswith(lid + "_") for lid in LAYER_IDS)})
    layers = dict(old.get("layers") or {})
    for lid in LAYER_IDS:
        new_st = new.get(f"{lid}_status")
        old_st = old.get(f"{lid}_status")
        take_new = new_st == "ok" or (new_st and old_st != "ok")
        if take_new:
            for suffix in ("score", "status", "model", "error", "cited", "ok_n"):
                key = f"{lid}_{suffix}"
                if key in new:
                    merged[key] = new[key]
            blob = (new.get("layers") or {}).get(lid) or _layer_blob(new, lid)
            if blob:
                layers[lid] = blob
        elif lid not in layers:
            blob = _layer_blob(merged, lid)
            if blob:
                layers[lid] = blob
    merged["layers"] = layers
    if new.get("won"):
        merged["won"] = new["won"]
        merged["lost"] = new.get("lost") or []
    merged["ts"] = new.get("ts") or old.get("ts")
    merged["questions"] = new.get("questions") or old.get("questions")
    _apply_legacy_aliases(merged)
    return merged


def _apply_legacy_aliases(point: dict) -> None:
    # Historical name: deepseek_score was Claude memory, never DeepSeek.
    if point.get("claude_memory_status") == "ok":
        point["deepseek_score"] = point.get("claude_memory_score")
    elif "deepseek_score" not in point:
        point["deepseek_score"] = None
    if point.get("chatgpt_memory_status") == "ok":
        point["chatgpt_score"] = point.get("chatgpt_memory_score")
    if point.get("gemini_memory_status") == "ok":
        point["gemini_score"] = point.get("gemini_memory_score")
        point["gemini_model"] = point.get("gemini_memory_model")
    if point.get("perplexity_search_status") == "ok":
        point["perplexity_score"] = point.get("perplexity_search_score")


def _upsert_ledger(point: dict) -> list:
    ledger = []
    if LEDGER.exists():
        try:
            ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        except Exception:
            ledger = []
    existing = next((p for p in ledger if p.get("date") == point["date"]), None)
    if existing:
        point = _merge_point(existing, point)
        ledger = [p for p in ledger if p.get("date") != point["date"]]
    ledger.append(point)
    ledger = ledger[-52:]
    DATA.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    return ledger


def _fmt_layer(lid: str, point: dict) -> str:
    st = point.get(f"{lid}_status")
    if st is None:
        return f"{lid}: —"
    if st == "skip":
        return f"{lid}: skip ({point.get(f'{lid}_error') or 'no key'})"
    if st == "fail":
        return f"{lid}: FAIL ({point.get(f'{lid}_error') or '?'})"
    sc = point.get(f"{lid}_score")
    cited = point.get(f"{lid}_cited")
    asked = point.get("questions")
    return f"{lid}: {sc*100:.0f}% ({cited}/{asked})"


def main() -> int:
    argv = sys.argv[1:]
    with_gsc = "--with-gsc" in argv
    questions = panel_questions(with_gsc)
    wanted = _wanted_layers(argv)

    print(f"🤖 AIO-visibility: {len(questions)} questions, "
          f"layers={','.join(wanted)}", flush=True)

    layers: dict[str, dict] = {}
    point = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "ts": datetime.now(timezone.utc).isoformat(),
        "questions": len(questions),
        "panel": "core12" if not with_gsc else "core12+gsc",
        "layers": {},
        "won": [],
        "lost": [],
    }

    for lid in wanted:
        print(f"→ {lid} …", flush=True)
        result = run_layer(lid, questions)
        layers[lid] = result
        point["layers"][lid] = {
            "status": result["status"],
            "score": result["score"],
            "cited": result["cited"],
            "ok_n": result["ok_n"],
            "model": result.get("model"),
            "error": result.get("error"),
        }
        point.update(_score_fields(lid, result))
        print(f"  {_fmt_layer(lid, point)}", flush=True)
        if lid == "claude_memory" and result["status"] == "ok":
            point["won"] = [r["q"] for r in result["items"] if r["cited"]]
            point["lost"] = [r["q"] for r in result["items"] if not r["cited"]]

    _apply_legacy_aliases(point)
    ledger = _upsert_ledger(point)

    print("📊 panel")
    for lid in LAYER_IDS:
        if f"{lid}_status" in point:
            print(f"  {_fmt_layer(lid, point)}")

    if "--no-telegram" not in argv:
        send_report(point, ledger)
    return 0


def send_report(point: dict, ledger: list) -> None:
    lines = ["<b>🤖 AIO-видимость — search vs memory</b>"]
    for lid in LAYER_IDS:
        if point.get(f"{lid}_status"):
            lines.append(_fmt_layer(lid, point))
    if point.get("won"):
        lines.append("\n<b>Claude memory — называют:</b>")
        for q in point["won"][:4]:
            lines.append(f"  ✅ {q}")
    if point.get("lost") and point.get("claude_memory_status") == "ok":
        lines.append("\n<b>Claude memory — не называют:</b>")
        for q in point["lost"][:5]:
            lines.append(f"  ⬜ {q}")
    lines.append("\n<i>0% пишется только при живых ответах. fail ≠ нас нет в весах.</i>")
    try:
        import daily_ledger
        daily_ledger.append_event("done", "\n".join(lines))
    except Exception as e:
        print(f"· ledger unavailable: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
