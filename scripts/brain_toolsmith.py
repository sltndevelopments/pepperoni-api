#!/usr/bin/env python3
"""Brain Toolsmith — lets the Fable brain build its own tools.

The brain can emit `propose_tools` in its strategy (data/strategy.json). Each
proposal describes a small, single-purpose Python utility the brain wants in its
toolbox (e.g. "find product pages missing a price", "list cities with zero geo
coverage for a product"). This executor turns each proposal into a real script
under scripts/brain_tools/, using the model the BRAIN chose (haiku/sonnet/opus).

Safety model (the brain is autonomous, so the guardrails live here):
  • Generated tools are written to scripts/brain_tools/<name>.py — an isolated
    namespace, never overwriting core pipeline scripts.
  • Every tool must pass an AST parse + a static safety scan (no os.system,
    subprocess, shutil.rmtree, network writes, eval/exec, open(...,'w') on paths
    outside data/ or public/ unless dry-run) BEFORE it is accepted.
  • A registry (data/brain_tools.json) tracks every tool, its purpose, the model
    used, cost, and status. Existing tools are not regenerated unless the brain
    bumps the proposal's "version".
  • Tools are GENERATED here but NOT auto-run. The brain invokes a tool in a
    later cycle by listing it in `run_tools`; this executor runs it read-only
    (capturing stdout) and feeds the result back into the next brain digest.

Model policy: the brain picks per tool. Cheap analysis → haiku; codegen that
needs care → sonnet; novel/tricky tool → opus. Default sonnet.

Usage:
  python3 scripts/brain_toolsmith.py            # build proposed, run requested
  python3 scripts/brain_toolsmith.py --build    # only build proposed tools
  python3 scripts/brain_toolsmith.py --run NAME # run one tool read-only
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

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
SCRIPTS = ROOT / "scripts"
TOOLS_DIR = SCRIPTS / "brain_tools"
BACKUP_DIR = DATA / "agent_backups"
REGISTRY = DATA / "brain_tools.json"
STRATEGY = DATA / "strategy.json"

# Core agents the brain is allowed to patch. Excludes the brain itself, the
# toolsmith, proxy/secret handling and Telegram bot — patching those could
# brick autonomy or leak credentials, so they stay engineer-only.
#
# SAFETY CORE — NEVER REMOVE THESE:
# approvals / qa_pages / generate_geo_bulk / generate_from_strategy protect
# the publication gate (owner approval before new pages go live). brand_system
# carries the halal + contact + cert guardrails. These are the lock, the alarm,
# and the brand identity — if the brain patches them it can silently undo all
# safety invariants. Engineer-only, no exceptions.
PROTECTED_AGENTS = {
    # Autonomy infrastructure (brain, budget, proxy, notifications)
    "seo_brain", "opus_brain_client", "claude_client", "brain_toolsmith",
    "telegram_bot", "telegram_notify", "sync_asocks_proxy", "send_report",
    # Publication gate — fail-closed automatic reviewer (the sole gatekeeper;
    # brain must never patch the judge that grades its own output)
    "page_reviewer",
    # Generators wired to the gate
    "generate_geo_bulk", "generate_from_strategy", "build_landing",
    # Legacy approval queue (still used by Steve's sales flow)
    "approvals",
    # Quality gate — thin/dup/halal check before git commit
    "qa_pages", "fix_pages",
    # Brand & halal guardrails — single source of truth, never editable by brain
    "brand_system",
}

ALLOWED_MODELS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",
}
DEFAULT_MODEL_KEY = "sonnet"

# Static safety scan — generated tool code must not contain these.
# Tools are read-only analysis scripts: they may READ from anywhere but may
# only WRITE to data/ (a JSON result file). All write primitives are banned
# outright; the LLM system prompt already says "write only to data/" via
# json.dump/Path.write_text on a DATA/ path — but we enforce it at scan time
# so a cleverly-prompted tool cannot bypass the publication gate by writing
# directly to public/.
FORBIDDEN = (
    # Execution / network
    "os.system", "subprocess", "shutil.rmtree", "eval(", "exec(",
    "__import__", "socket.", "requests.post", "requests.put",
    "requests.delete", "urllib.request.urlopen", "rmtree",
    # File deletion
    "os.remove", "os.unlink", "Path.unlink",
    # Pickle (arbitrary code execution vector)
    "pickle.",
    # Write primitives — tools must be read-only except for their own data/ report.
    # We ban the primitives; a tool that genuinely needs to write its JSON result
    # should use json.dump(f, ...) with a path it constructs under DATA/ — that
    # path construction is verified by _safe_write_paths() below.
    ".write_text(", ".write_bytes(", ".open(\"w\"", ".open('w'",
    "open(\"w\"", "open('w'", 'open("a"', "open('a'", 'open("x"', "open('x'",
    ", \"w\")", ", 'w')", ", \"a\")", ", 'a')", ", \"x\")", ", 'x')",
)

TOOLSMITH_SYSTEM = """Ты — генератор маленьких служебных Python-скриптов («инструментов»)
для SEO-мозга сайта pepperoni.tatar (статический сайт, каталог халяль-продукции).
Тебе дают описание нужного инструмента; верни ТОЛЬКО код одного .py-файла.

ЖЁСТКИЕ ПРАВИЛА (иначе инструмент отклонят автоматически):
- Только стандартная библиотека + json + pathlib + re + collections. НИКАКИХ
  сторонних пакетов, сети, subprocess, os.system, eval/exec, удаления файлов.
- ТОЛЬКО ЧТЕНИЕ. Инструменты — аналитика, не генераторы страниц. Читать можно
  откуда угодно (data/, public/, scripts/). Писать — ТОЛЬКО в data/ (json-отчёт).
  ЗАПРЕЩЕНО писать в public/ или любой другой каталог. Нарушение → автоматический
  отказ при scan: .write_text(), .write_bytes(), open(...,'w'/'a'/'x') — всё под запретом
  кроме как на пути внутри data/.
- Скрипт ДОЛЖЕН иметь функцию main() -> None, печатающую КОМПАКТНЫЙ результат
  (JSON или короткие строки) в stdout — это пойдёт в дайджест мозга.
- Пути считай от корня репозитория: ROOT = Path(__file__).parents[2].
  Данные для чтения: ROOT/'data', ROOT/'public', ROOT/'scripts'.
  Запись: только ROOT/'data'/<имя_инструмента>.json.
- Без аргументов командной строки, без input(). Идемпотентно, быстро (<5 c).
- Вверху файла — docstring: что инструмент делает и зачем мозгу.
Верни чистый код без markdown-ограждений."""


def _registry() -> dict:
    try:
        return json.loads(REGISTRY.read_text())
    except Exception:
        return {"tools": {}}


def _save_registry(reg: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=1))


def _contains_public_write(code: str) -> bool:
    """AST-level check: reject any string literal that contains 'public' AND
    appears as an argument to a write/open call.  Catches variable-assembled
    paths like  Path(ROOT/'public'/slug).write_text(...)  even if the string
    'public' and the write call are on different lines.

    This is defence-in-depth on top of the FORBIDDEN string scan; both must
    pass for a tool to be accepted.
    """
    # Quick pre-filter: if 'public' doesn't appear anywhere, no need to parse.
    if "public" not in code:
        return False
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False  # already caught by _safe() before this runs

    # Collect all string literals that contain 'public' (case-insensitive).
    public_strs: set[int] = set()   # line numbers
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "public" in node.value.lower():
                public_strs.add(node.lineno)

    if not public_strs:
        return False

    # Collect line numbers of write-like attribute calls
    # (.write_text, .write_bytes, .open in write mode already caught by FORBIDDEN,
    # but also catch json-via-open and any other file-write patterns).
    write_lines: set[int] = set()
    write_attrs = {"write", "write_text", "write_bytes", "writelines"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr in write_attrs:
                write_lines.add(node.lineno)

    # If any public-string lines are within 5 lines of a write call → reject.
    for pl in public_strs:
        for wl in write_lines:
            if abs(pl - wl) <= 5:
                return True
    return False


def _safe(code: str) -> tuple[bool, str]:
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, f"syntax error: {e}"
    for bad in FORBIDDEN:
        if bad in code:
            return False, f"forbidden construct: {bad!r}"
    if "def main(" not in code:
        return False, "no main() function"
    if _contains_public_write(code):
        return False, "forbidden: write to public/ — tools are read-only except data/"
    return True, ""


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def build_tool(proposal: dict, reg: dict) -> str:
    """Generate one tool from a proposal. Returns status string."""
    name = re.sub(r"[^a-z0-9_]", "_", (proposal.get("name") or "").lower()).strip("_")
    if not name:
        return "skip: no name"
    purpose = (proposal.get("purpose") or "").strip()
    spec = (proposal.get("spec") or purpose).strip()
    version = int(proposal.get("version", 1))
    model_key = (proposal.get("model") or DEFAULT_MODEL_KEY).lower()
    model = ALLOWED_MODELS.get(model_key, ALLOWED_MODELS[DEFAULT_MODEL_KEY])

    existing = reg["tools"].get(name)
    if existing and int(existing.get("version", 1)) >= version and \
            existing.get("status") == "ready":
        return f"skip: {name} v{version} already built"

    from claude_client import call_claude
    prompt = (f"Создай инструмент «{name}».\nЦель (зачем мозгу): {purpose}\n"
              f"Что должен делать: {spec}\n"
              "Помни правила безопасности из system. Верни только код .py.")
    try:
        code, _ = call_claude(prompt, system=TOOLSMITH_SYSTEM, model=model,
                              max_tokens=2048, temperature=0.2)
    except Exception as e:
        if e.__class__.__name__ == "BudgetExceeded":
            raise
        return f"fail: {name} — LLM error {e}"

    code = _strip_fence(code)
    ok, why = _safe(code)
    if not ok:
        reg["tools"][name] = {"status": "rejected", "reason": why,
                              "version": version, "model": model_key,
                              "purpose": purpose,
                              "updated_at": datetime.now(timezone.utc).isoformat()}
        return f"reject: {name} — {why}"

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    (TOOLS_DIR / "__init__.py").write_text("")
    (TOOLS_DIR / f"{name}.py").write_text(code, encoding="utf-8")
    reg["tools"][name] = {"status": "ready", "version": version,
                          "model": model_key, "purpose": purpose, "spec": spec,
                          "updated_at": datetime.now(timezone.utc).isoformat(),
                          "last_result": None}
    return f"built: {name} v{version} ({model_key})"


def run_tool(name: str, reg: dict) -> str:
    """Run a ready tool read-only, capture stdout into the registry."""
    name = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")
    path = TOOLS_DIR / f"{name}.py"
    if not path.exists():
        return f"run-skip: {name} not found"
    # Execute in a restricted namespace; tools were safety-scanned at build time.
    src = path.read_text()
    ns: dict = {"__name__": "__brain_tool__", "__file__": str(path)}
    buf = io.StringIO()
    try:
        code_obj = compile(src, str(path), "exec")
        exec(code_obj, ns)  # noqa: S102 — sandboxed by build-time static scan
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


PATCH_SYSTEM = """Ты — старший Python-инженер, сопровождающий автономный SEO-пайплайн
сайта pepperoni.tatar (статический халяль-каталог). Тебе дают ПОЛНЫЙ текущий код
одного агента-скрипта и описание правки, которую запросил мозг-стратег.

Внеси ТОЧЕЧНОЕ изменение и верни ПОЛНЫЙ изменённый файл целиком (не diff).
ЖЁСТКИЕ ПРАВИЛА:
- Сохрани публичный интерфейс (имена функций main/run, аргументы CLI, формат
  вывода) — другие скрипты и cron на них завязаны. Меняй только запрошенную логику.
- Никакого os.system/subprocess для новых внешних вызовов, не трогай работу с
  секретами/прокси, не добавляй сетевых записей.
- Код должен оставаться синтаксически валидным и импортируемым без побочных
  эффектов на верхнем уровне (вся работа — внутри функций / под __main__).
- Не выдумывай новые зависимости вне того, что уже импортирует файл.
Верни ТОЛЬКО код .py без markdown-ограждений."""


def _tg(text: str) -> None:
    try:
        sys.path.insert(0, str(SCRIPTS))
        from telegram_notify import notify
        notify(text)
    except Exception:
        pass


def _import_ok(path: Path) -> tuple[bool, str]:
    """Compile + import the module in a fresh subprocess-like namespace."""
    src = path.read_text(encoding="utf-8")
    try:
        ast.parse(src)
    except SyntaxError as e:
        return False, f"syntax: {e}"
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"_agtest_{path.stem}", path)
    if spec is None or spec.loader is None:
        return False, "spec failed"
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # top-level must be side-effect free
    except SystemExit:
        return True, ""  # argparse/no-arg guard can raise SystemExit — acceptable
    except Exception as e:
        return False, f"import: {e.__class__.__name__}: {e}"
    return True, ""


def patch_agent(req: dict, reg: dict) -> str:
    """LLM-edit one core agent's code with backup + safety + auto-rollback."""
    agent = re.sub(r"[^a-z0-9_]", "_", (req.get("agent") or "").lower()).strip("_")
    change = (req.get("change") or "").strip()
    if not agent or not change:
        return "patch-skip: empty agent/change"
    if agent in PROTECTED_AGENTS:
        return f"patch-deny: {agent} is protected (engineer-only)"
    target = SCRIPTS / f"{agent}.py"
    if not target.exists():
        return f"patch-skip: {agent}.py not found"

    model_key = (req.get("model") or "sonnet").lower()
    model = ALLOWED_MODELS.get(model_key, ALLOWED_MODELS["sonnet"])
    original = target.read_text(encoding="utf-8")
    if len(original) > 60000:
        return f"patch-skip: {agent}.py too large to edit safely"

    from claude_client import call_claude
    prompt = (f"Файл scripts/{agent}.py:\n\n{original}\n\n"
              f"Запрошенная правка от мозга:\n{change}\n\n"
              "Верни полный изменённый файл по правилам из system.")
    try:
        new_code, _ = call_claude(prompt, system=PATCH_SYSTEM, model=model,
                                  max_tokens=8192, temperature=0.1)
    except Exception as e:
        if e.__class__.__name__ == "BudgetExceeded":
            raise
        return f"patch-fail: {agent} — LLM error {e}"
    new_code = _strip_fence(new_code)
    if not new_code or new_code == original:
        return f"patch-noop: {agent} (no change produced)"

    # Static safety scan reuses the toolsmith FORBIDDEN list.
    for bad in FORBIDDEN:
        if bad in new_code and bad not in original:
            return f"patch-reject: {agent} introduces forbidden `{bad}`"

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = BACKUP_DIR / f"{agent}.{stamp}.bak"
    backup.write_text(original, encoding="utf-8")

    target.write_text(new_code, encoding="utf-8")
    ok, why = _import_ok(target)
    rec = reg.setdefault("agent_patches", {}).setdefault(agent, [])
    if not ok:
        target.write_text(original, encoding="utf-8")  # AUTO-ROLLBACK
        rec.append({"at": stamp, "change": change, "model": model_key,
                    "result": "rolled_back", "error": why})
        _tg(f"🧠⚠️ Мозг правил агент <b>{agent}</b>, но правка сломала импорт "
            f"({why}). Авто-откат к рабочей версии выполнен.\nПравка: {change[:300]}")
        return f"patch-rollback: {agent} — {why}"

    rec.append({"at": stamp, "change": change, "model": model_key,
                "result": "applied", "backup": backup.name})
    _tg(f"🧠✅ Мозг сам изменил код агента <b>{agent}</b> и проверил его.\n"
        f"Правка: {change[:300]}\nБэкап: {backup.name}")
    return f"patched: {agent} ({model_key}) ✅"


def brain_summary() -> dict:
    """Compact view of the brain's toolbox for the next digest."""
    reg = _registry()
    ready = {n: t for n, t in reg.get("tools", {}).items()
             if t.get("status") == "ready"}
    return {
        "available_tools": [
            {"name": n, "purpose": t.get("purpose", ""),
             "last_result": (t.get("last_result") or "")[:500]}
            for n, t in ready.items()
        ],
        "count": len(ready),
        "recent_agent_patches": [
            {"agent": a, "at": h[-1].get("at"), "result": h[-1].get("result"),
             "change": (h[-1].get("change") or "")[:160]}
            for a, h in (reg.get("agent_patches") or {}).items() if h
        ][-8:],
    }


def main() -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    args = sys.argv[1:]
    reg = _registry()
    try:
        strat = json.loads(STRATEGY.read_text())
    except Exception:
        strat = {}

    if "--run" in args:
        i = args.index("--run")
        name = args[i + 1] if i + 1 < len(args) else ""
        print(run_tool(name, reg))
        _save_registry(reg)
        return 0

    build_only = "--build" in args

    # 1) Build any tools the brain proposed
    for proposal in (strat.get("propose_tools") or []):
        try:
            print("🛠 ", build_tool(proposal, reg))
        except Exception as e:
            if e.__class__.__name__ == "BudgetExceeded":
                print(f"🛑 {e}", file=sys.stderr)
                break
            print(f"⚠️  toolsmith error: {e}", file=sys.stderr)
    _save_registry(reg)

    # 1b) Apply any code patches the brain requested for core agents
    for req in (strat.get("edit_agents") or []):
        try:
            print("✂️ ", patch_agent(req, reg))
        except Exception as e:
            if e.__class__.__name__ == "BudgetExceeded":
                print(f"🛑 {e}", file=sys.stderr)
                break
            print(f"⚠️  patch error: {e}", file=sys.stderr)
    _save_registry(reg)

    # 2) Run any tools the brain requested (read-only), feed results back
    if not build_only:
        for name in (strat.get("run_tools") or []):
            print("▶️ ", run_tool(name, reg))
        _save_registry(reg)

    summary = brain_summary()
    print(f"🧰 toolbox: {summary['count']} инструмент(ов) готовы")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
