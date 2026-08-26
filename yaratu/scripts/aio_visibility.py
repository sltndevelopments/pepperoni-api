#!/usr/bin/env python3
"""Fixed-panel Yaratu AI visibility measurement.

Memory and search are separate layers. Missing credentials produce ``skip``;
provider/network errors produce ``fail``; both always have ``score: null``.
The script measures only and never generates or edits site content.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_FILE = ROOT / "yaratu" / "data" / "aio_questions.json"
DEFAULT_OUT = ROOT / "yaratu" / "data" / "aio_baseline.json"
BRAND_PATTERNS = (
    r"\byaratu\b",
    r"\bярату\b",
    r"yaratu\.com",
)
SYSTEM = (
    "Answer the buyer's question concretely. Name real brands and websites only "
    "when supported by your knowledge or retrieved sources. Do not invent facts."
)


def _post(url: str, payload: dict, headers: dict, timeout: int = 90) -> tuple[dict | None, str | None]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")[:300]
        except Exception:
            detail = str(exc.reason)[:300]
        return None, f"HTTP {exc.code}: {detail}"
    except Exception as exc:
        return None, str(exc)[:300]


def _openai_text(data: dict) -> str:
    if data.get("output_text"):
        return str(data["output_text"])
    chunks: list[str] = []
    for item in data.get("output") or []:
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("text"):
                chunks.append(str(part["text"]))
    return "\n".join(chunks)


def ask_openai_memory(question: str) -> tuple[str, str | None]:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    payload = {
        "model": os.environ.get("YARATU_OPENAI_MEMORY_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": question},
        ],
        "temperature": 0,
        "max_tokens": 700,
    }
    data, error = _post(
        "https://api.openai.com/v1/chat/completions",
        payload,
        {"Authorization": f"Bearer {key}"},
    )
    if error:
        return "", error
    try:
        text = data["choices"][0]["message"]["content"]
        return str(text), None if str(text).strip() else "empty output"
    except Exception as exc:
        return "", f"parse: {exc}"


def ask_openai_search(question: str) -> tuple[str, str | None]:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    payload = {
        "model": os.environ.get("YARATU_OPENAI_SEARCH_MODEL", "gpt-5.6"),
        "input": f"{SYSTEM}\n\n{question}",
        "tools": [{"type": "web_search"}],
        "tool_choice": "required",
    }
    data, error = _post(
        "https://api.openai.com/v1/responses",
        payload,
        {"Authorization": f"Bearer {key}"},
    )
    if error:
        return "", error
    text = _openai_text(data or {})
    return text, None if text.strip() else "empty output"


def _ask_gemini(question: str, search: bool) -> tuple[str, str | None]:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("YARATU_GEMINI_MODEL", "gemini-3.7-flash")
    payload: dict = {
        "contents": [{"parts": [{"text": f"{SYSTEM}\n\n{question}"}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 1000},
    }
    if search:
        payload["tools"] = [{"google_search": {}}]
    data, error = _post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        payload,
        {"x-goog-api-key": key},
    )
    if error:
        return "", error
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(str(part.get("text", "")) for part in parts)
        return text, None if text.strip() else "empty output"
    except Exception as exc:
        return "", f"parse: {exc}"


def ask_gemini_memory(question: str) -> tuple[str, str | None]:
    return _ask_gemini(question, search=False)


def ask_gemini_search(question: str) -> tuple[str, str | None]:
    return _ask_gemini(question, search=True)


def ask_perplexity_search(question: str) -> tuple[str, str | None]:
    key = os.environ.get("PPLX_API_KEY", "").strip()
    payload = {
        "model": os.environ.get("YARATU_PPLX_MODEL", "sonar"),
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": question},
        ],
        "temperature": 0,
        "max_tokens": 700,
    }
    data, error = _post(
        "https://api.perplexity.ai/chat/completions",
        payload,
        {"Authorization": f"Bearer {key}"},
    )
    if error:
        return "", error
    try:
        text = data["choices"][0]["message"]["content"]
        return str(text), None if str(text).strip() else "empty output"
    except Exception as exc:
        return "", f"parse: {exc}"


LAYERS: dict[str, dict] = {
    "openai_memory": {
        "mode": "memory",
        "key": "OPENAI_API_KEY",
        "ask": ask_openai_memory,
        "model_env": "YARATU_OPENAI_MEMORY_MODEL",
        "default_model": "gpt-4o-mini",
    },
    "openai_search": {
        "mode": "search",
        "key": "OPENAI_API_KEY",
        "ask": ask_openai_search,
        "model_env": "YARATU_OPENAI_SEARCH_MODEL",
        "default_model": "gpt-5.6",
    },
    "gemini_memory": {
        "mode": "memory",
        "key": "GEMINI_API_KEY",
        "ask": ask_gemini_memory,
        "model_env": "YARATU_GEMINI_MODEL",
        "default_model": "gemini-3.7-flash",
    },
    "gemini_search": {
        "mode": "search",
        "key": "GEMINI_API_KEY",
        "ask": ask_gemini_search,
        "model_env": "YARATU_GEMINI_MODEL",
        "default_model": "gemini-3.7-flash",
    },
    "perplexity_search": {
        "mode": "search",
        "key": "PPLX_API_KEY",
        "ask": ask_perplexity_search,
        "model_env": "YARATU_PPLX_MODEL",
        "default_model": "sonar",
    },
}


def mentions_yaratu(text: str) -> bool:
    return any(re.search(pattern, text or "", re.IGNORECASE) for pattern in BRAND_PATTERNS)


def extract_sources(text: str) -> list[str]:
    return list(dict.fromkeys(
        url.rstrip(".,);]") for url in re.findall(r"https?://[^\s<>\"']+", text or "")
    ))[:10]


def load_panel(path: Path = QUESTIONS_FILE) -> dict:
    panel = json.loads(path.read_text(encoding="utf-8"))
    questions = panel.get("questions") or []
    ids = [item.get("id") for item in questions]
    buckets = {(item.get("language"), item.get("audience")) for item in questions}
    expected = {("ru", "b2c"), ("ru", "b2b"), ("en", "b2c"), ("en", "b2b")}
    if len(questions) != 20 or len(set(ids)) != 20 or buckets != expected:
        raise ValueError("panel must contain 20 unique RU+EN, B2C+B2B questions")
    for bucket in expected:
        if sum((item["language"], item["audience"]) == bucket for item in questions) != 5:
            raise ValueError(f"panel bucket {bucket} must contain exactly 5 questions")
    return panel


def run_layer(
    layer_id: str,
    questions: list[dict],
    *,
    dry_run: bool = False,
    asker: Callable[[str], tuple[str, str | None]] | None = None,
) -> dict:
    spec = LAYERS[layer_id]
    result = {
        "mode": spec["mode"],
        "status": "skip",
        "score": None,
        "cited": None,
        "answered": 0,
        "asked": len(questions),
        "model": os.environ.get(spec["model_env"], spec["default_model"]),
        "error": "dry-run" if dry_run else None,
        "items": [],
    }
    if dry_run:
        return result
    if not os.environ.get(spec["key"], "").strip():
        result["error"] = f"missing {spec['key']}"
        return result

    ask = asker or spec["ask"]
    failures: list[str] = []
    cited = 0
    for item in questions:
        text, error = ask(item["text"])
        if error:
            failures.append(f"{item['id']}: {error}")
            result["items"].append({
                "question_id": item["id"], "status": "fail", "cited": None,
                "sources": [], "error": error,
            })
            continue
        present = mentions_yaratu(text)
        cited += int(present)
        result["answered"] += 1
        result["items"].append({
            "question_id": item["id"], "status": "ok", "cited": present,
            "sources": extract_sources(text), "error": None,
            "excerpt": text.strip()[:800],
        })

    # The fixed panel is comparable only when every question got a real answer.
    if failures or result["answered"] != len(questions):
        result["status"] = "fail"
        result["score"] = None
        result["cited"] = None
        result["error"] = failures[0] if failures else "incomplete fixed panel"
        return result
    result["status"] = "ok"
    result["cited"] = cited
    result["score"] = round(cited / len(questions), 4)
    result["error"] = None
    return result


def build_snapshot(
    panel: dict,
    selected: list[str],
    *,
    dry_run: bool,
    snapshot_type: str = "baseline",
) -> dict:
    now = datetime.now(timezone.utc)
    layers = {
        layer_id: run_layer(layer_id, panel["questions"], dry_run=dry_run)
        for layer_id in selected
    }
    return {
        "schema_version": 1,
        "snapshot_type": snapshot_type,
        "panel_id": panel["panel_id"],
        "panel_version": panel["version"],
        "captured_at": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "domain": "yaratu.com",
        "question_count": len(panel["questions"]),
        "dry_run": dry_run,
        "layers": layers,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=QUESTIONS_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--layers", default=",".join(LAYERS))
    parser.add_argument("--snapshot-type", choices=("baseline", "weekly"), default="baseline")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        panel = load_panel(args.questions)
        selected = [value.strip() for value in args.layers.split(",") if value.strip()]
        unknown = [layer_id for layer_id in selected if layer_id not in LAYERS]
        if unknown:
            raise ValueError(f"unknown layers: {', '.join(unknown)}")
        snapshot = build_snapshot(
            panel,
            selected,
            dry_run=args.dry_run,
            snapshot_type=args.snapshot_type,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for layer_id, result in snapshot["layers"].items():
        print(f"{layer_id}: {result['status']} score={result['score']}")
    print(f"wrote {args.output}")
    return 1 if any(item["status"] == "fail" for item in snapshot["layers"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
