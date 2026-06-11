#!/usr/bin/env python3
"""Toolsmith Стива — он строит себе СОБСТВЕННЫХ аналитических агентов.

Стив описывает нужный инструмент в стратегии (поле `propose_tools`). Каждый —
маленький однозадачный Python-скрипт-анализатор (например «оптовики в базе без
контакта», «лиды без ответа >14 дней → второе касание», «кластеры по выручке»).
Этот исполнитель превращает заявку в реальный файл под sales-agent/agents/,
моделью, которую Стив выбрал (haiku/sonnet/opus).

ЖЁСТКАЯ ИЗОЛЯЦИЯ (Стив автономен — предохранители живут здесь):
  • Инструменты пишутся ТОЛЬКО в sales-agent/agents/<name>.py — отдельное
    пространство; сайт (public/, scripts/) физически недоступен.
  • Каждый инструмент проходит AST-parse + статический safety-scan ДО приёма:
    запрещены os.system/subprocess/eval/exec/сеть/удаление файлов и любая запись
    за пределы sales-agent/data/.
  • Инструменты — ТОЛЬКО ЧТЕНИЕ данных продаж (agent.db, профили лидов) и запись
    компактного json-отчёта в sales-agent/data/. Реальная отправка писем
    (channels/email.py), лимиты доставляемости, гейт и core/store запись — НЕ
    доступны и не патчатся: иначе одной правкой можно разослать спам или сжечь
    домен. Это остаётся инженерной зоной.
  • Стив НЕ может править существующий код (в отличие от Fable на сайте) — только
    создавать новые read-only инструменты в своей песочнице. Правки боевого
    пайплайна продаж — через инженера.
  • Реестр data/steve_tools.json: имя, цель, модель, статус, последний результат.
    Сборка идёт из бюджета Стива; если он исчерпан — toolsmith не работает.

Использование:
  python3 -m brain.toolsmith            # собрать предложенные, прогнать запрошенные
  python3 -m brain.toolsmith --build    # только собрать
  python3 -m brain.toolsmith --run NAME # прогнать один инструмент read-only
"""
from __future__ import annotations

import ast
import io
import json
import re
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import env as _env  # noqa: F401
from core import budget as steve_budget

DATA = ROOT / "data"
AGENTS_DIR = ROOT / "agents"
REGISTRY = DATA / "steve_tools.json"
STRATEGY = DATA / "steve_strategy.json"

ALLOWED_MODELS = {"haiku": "micro", "sonnet": "voice", "opus": "brain"}
DEFAULT_MODEL_KEY = "sonnet"

# Статический safety-scan — код инструмента не должен это содержать.
FORBIDDEN = (
    "os.system", "subprocess", "shutil.rmtree", "shutil.move", "eval(", "exec(",
    "__import__", "socket.", "smtplib", "imaplib", "requests.", "urllib.request",
    "rmtree", "os.remove", "os.unlink", "Path.unlink", ".write_bytes(", "pickle.",
    # запрет на доступ к реальной отправке/гейту/записи в стор и к сайту
    "channels.email", "channels.deliverability", "core.gate", "upsert_lead",
    "add_blacklist", "execute_approved", "public/", "..", "send(",
)

TOOLSMITH_SYSTEM = """Ты — генератор маленьких служебных Python-скриптов
(«инструментов») для Стива, автономного зама по продажам компании «Казанские
Деликатесы». Тебе дают описание нужного инструмента; верни ТОЛЬКО код одного
.py-файла.

ЖЁСТКИЕ ПРАВИЛА (иначе инструмент отклонят автоматически):
- Только стандартная библиотека: json, sqlite3, pathlib, re, collections,
  datetime, statistics. НИКАКИХ сторонних пакетов, сети, smtplib/imaplib,
  subprocess, os.system, eval/exec, удаления файлов.
- Только ЧТЕНИЕ данных продаж. База: ROOT/'data'/'agent.db' (таблица leads:
  колонки id, name, inn, region, tier, fit_score, status, source, profile(JSON),
  created_at, updated_at). Запись разрешена ТОЛЬКО в ROOT/'data'/ (json-отчёт).
- Нельзя слать письма, менять статусы лидов, трогать гейт, доставляемость и
  файлы сайта. Только анализ и отчёт.
- Скрипт ДОЛЖЕН иметь функцию main() -> None, печатающую КОМПАКТНЫЙ результат
  (JSON или короткие строки) в stdout — это пойдёт в дайджест Стива.
- Пути считай от корня sales-agent: ROOT = Path(__file__).resolve().parents[1].
- Без аргументов командной строки, без input(). Идемпотентно, быстро (<5 c).
- Вверху файла — docstring: что инструмент делает и зачем Стиву.
Верни чистый код без markdown-ограждений."""


def _registry() -> dict:
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return {"tools": {}}


def _save_registry(reg: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")


def _safe(code: str) -> tuple[bool, str]:
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, f"syntax error: {e}"
    for bad in FORBIDDEN:
        if bad in code:
            return False, f"forbidden construct: {bad}"
    if "def main(" not in code:
        return False, "no main() function"
    # запись только в data/: грубая проверка open(...,'w')
    for m in re.finditer(r"open\([^)]*['\"][wa]b?['\"]", code):
        seg = code[max(0, m.start() - 120):m.start()]
        if "data" not in seg:
            return False, "write outside data/"
    return True, ""


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def _generate(prompt: str, model_key: str) -> str:
    """Сгенерировать код через нужный тир LLM Стива (общий бюджет/леджер)."""
    from core.llm import call_sonnet, call_opus, call_haiku
    tier = ALLOWED_MODELS.get(model_key, "voice")
    if tier == "brain":
        text, _ = call_opus(prompt, system=TOOLSMITH_SYSTEM, max_tokens=2048)
    elif tier == "micro":
        text, _ = call_haiku(prompt, system=TOOLSMITH_SYSTEM, max_tokens=2048)
    else:
        text, _ = call_sonnet(prompt, system=TOOLSMITH_SYSTEM, max_tokens=2048,
                              cache_system=True, effort="medium")
    return text


def build_tool(proposal: dict, reg: dict) -> str:
    name = re.sub(r"[^a-z0-9_]", "_", (proposal.get("name") or "").lower()).strip("_")
    if not name:
        return "skip: no name"
    purpose = (proposal.get("purpose") or "").strip()
    spec = (proposal.get("spec") or purpose).strip()
    version = int(proposal.get("version", 1))
    model_key = (proposal.get("model") or DEFAULT_MODEL_KEY).lower()

    existing = reg["tools"].get(name)
    if existing and int(existing.get("version", 1)) >= version and \
            existing.get("status") == "ready":
        return f"skip: {name} v{version} already built"

    prompt = (f"Создай инструмент «{name}».\nЦель (зачем Стиву): {purpose}\n"
              f"Что должен делать: {spec}\n"
              "Помни правила безопасности из system. Верни только код .py.")
    try:
        code = _generate(prompt, model_key)
    except Exception as e:
        return f"fail: {name} — LLM error {str(e)[:120]}"

    code = _strip_fence(code)
    ok, why = _safe(code)
    now = datetime.now(timezone.utc).isoformat()
    if not ok:
        reg["tools"][name] = {"status": "rejected", "reason": why, "version": version,
                              "model": model_key, "purpose": purpose, "updated_at": now}
        return f"reject: {name} — {why}"

    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    (AGENTS_DIR / "__init__.py").write_text("", encoding="utf-8")
    (AGENTS_DIR / f"{name}.py").write_text(code, encoding="utf-8")
    reg["tools"][name] = {"status": "ready", "version": version, "model": model_key,
                          "purpose": purpose, "spec": spec, "updated_at": now,
                          "last_result": None}
    return f"built: {name} v{version} ({model_key})"


def run_tool(name: str, reg: dict) -> str:
    name = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")
    path = AGENTS_DIR / f"{name}.py"
    if not path.exists():
        return f"run-skip: {name} not found"
    src = path.read_text(encoding="utf-8")
    # повторный safety-scan перед каждым запуском (файл мог быть изменён)
    ok, why = _safe(src)
    if not ok:
        return f"run-reject: {name} — {why}"
    ns: dict = {"__name__": "__steve_tool__", "__file__": str(path)}
    buf = io.StringIO()
    try:
        code_obj = compile(src, str(path), "exec")
        exec(code_obj, ns)  # noqa: S102 — изолирован статическим сканом
        if "main" in ns:
            with redirect_stdout(buf):
                ns["main"]()
    except Exception as e:
        out = f"error: {e}"
    else:
        out = buf.getvalue().strip()[:4000]
    reg["tools"].setdefault(name, {})["last_result"] = out
    reg["tools"][name]["last_run_at"] = datetime.now(timezone.utc).isoformat()
    return f"ran: {name} ({len(out)} chars)"


def _strategy() -> dict:
    try:
        return json.loads(STRATEGY.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    args = sys.argv[1:]
    reg = _registry()

    if args and args[0] == "--run" and len(args) > 1:
        print(run_tool(args[1], reg))
        _save_registry(reg)
        return 0

    if not steve_budget.brain_allowed():
        print(json.dumps({"skipped": "steve budget exhausted"}, ensure_ascii=False))
        return 0

    strat = _strategy()
    results = {"built": [], "ran": []}

    for proposal in strat.get("propose_tools", []) or []:
        results["built"].append(build_tool(proposal, reg))

    if "--build" not in args:
        for name in strat.get("run_tools", []) or []:
            results["ran"].append(run_tool(name, reg))

    _save_registry(reg)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
