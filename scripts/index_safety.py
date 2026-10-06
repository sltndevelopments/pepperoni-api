#!/usr/bin/env python3
"""PHASE 1 safety rails for indexed (allowlist / status=keep) pages.

Existing indexed URLs must not be deleted, quarantined, noindexed, or
redirected by unattended automation. Detect → alert → stop (or restore).

Owner override env vars (explicit confirmation only):
  ALLOW_INDEX_RETIRE=1     drop a keep URL from the manifest
  ALLOW_INDEX_MUTATION=1   apply mass 301/410/noindex scripts
  ALLOW_AB_NOINDEX=1       let A/B apply noindex to a loser
  ALLOW_KEEP_QUARANTINE=1  allow QA to move a keep file out of public/
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
DATA = ROOT / "data"
MANIFEST = DATA / "index_manifest.json"
ALERT_DIR = DATA / "logs"

COUNTER_ENV_RETIRE = "ALLOW_INDEX_RETIRE"
COUNTER_ENV_MUTATION = "ALLOW_INDEX_MUTATION"
COUNTER_ENV_AB = "ALLOW_AB_NOINDEX"
COUNTER_ENV_QUARANTINE = "ALLOW_KEEP_QUARANTINE"


def owner_override(name: str) -> bool:
    return os.environ.get(name, "").strip() in {"1", "true", "yes", "YES"}


def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {"entries": []}
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def keep_entries() -> list[dict]:
    return [e for e in load_manifest().get("entries", []) if e.get("status") == "keep"]


def keep_files() -> set[str]:
    return {str(e.get("file") or "").replace("\\", "/") for e in keep_entries() if e.get("file")}


def keep_urls() -> set[str]:
    return {str(e.get("url") or "").rstrip("/") or "/" for e in keep_entries() if e.get("url")}


def public_rel(path: Path) -> str | None:
    try:
        resolved = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
        return str(resolved.relative_to(PUBLIC.resolve())).replace("\\", "/")
    except ValueError:
        return None


def is_keep_file(path: Path) -> bool:
    rel = public_rel(path) if isinstance(path, Path) else str(path).replace("\\", "/")
    if rel is None:
        rel = str(path).replace("\\", "/")
        if rel.startswith("public/"):
            rel = rel[len("public/"):]
    return rel in keep_files()


def is_keep_url(url: str) -> bool:
    raw = url.strip()
    for prefix in ("https://pepperoni.tatar", "http://pepperoni.tatar"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    raw = raw.split("?", 1)[0].split("#", 1)[0]
    if raw.endswith(".html"):
        raw = raw[: -len(".html")]
    raw = raw.rstrip("/") or "/"
    if not raw.startswith("/"):
        raw = "/" + raw
    return raw in keep_urls() or raw.rstrip("/") in keep_urls()


def alert(title: str, body: str, *, emergency: bool = True) -> None:
    """Write a durable alert and try Telegram / ledger. Never raises."""
    text = f"{title}\n{body}".strip()
    ALERT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).strftime("%Y%m%d-%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in title)[:60]
    (ALERT_DIR / f"index-safety-{stamp}-{safe}.log").write_text(text + "\n", encoding="utf-8")
    print(text, file=sys.stderr)
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from daily_ledger import append_event
        append_event("emergency" if emergency else "needs_help", text[:1500])
    except Exception:
        pass
    try:
        from notification_router import emit
        emit(
            "emergency" if emergency else "action",
            "index_safety",
            text[:3500],
            dedupe_key=f"index-safety:{title[:80]}",
        )
    except Exception:
        pass


def restore_from_git(path: Path) -> bool:
    """Restore a tracked keep file from HEAD. Returns True if restored."""
    rel = path if path.is_absolute() else ROOT / path
    try:
        repo_rel = str(rel.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        repo_rel = str(path)
    result = subprocess.run(
        ["git", "checkout", "HEAD", "--", repo_rel],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0 and rel.exists()


def protect_keep_from_quarantine(path: Path, reasons: list[str]) -> bool:
    """If path is a keep page, restore it and alert. Return True if blocked."""
    if owner_override(COUNTER_ENV_QUARANTINE):
        return False
    if not is_keep_file(path):
        return False
    rel = public_rel(path) or str(path)
    restored = restore_from_git(path)
    why = "; ".join(reasons)[:400]
    alert(
        "QA/карантин остановлен: страница allowlist не удаляется",
        f"Файл: public/{rel}\n"
        f"Причина QA: {why}\n"
        f"Восстановлен из git HEAD: {'да' if restored else 'нет'}\n"
        f"Файл оставлен в public/. Карантин для status=keep запрещён "
        f"(PHASE 1). Чтобы снять страницу, нужно ручное подтверждение "
        f"владельца ({COUNTER_ENV_QUARANTINE}=1).",
    )
    return True


def refuse_orphan_product_delete(paths: list[str], *, lang: str) -> list[str]:
    """Never delete product HTML automatically. Alert and return the list."""
    if not paths:
        return []
    listed = ", ".join(sorted(paths))
    alert(
        f"Карточки товаров не удалены ({lang}): SKU пропал из каталога",
        f"Генератор хотел удалить: {listed}\n"
        f"PHASE 1: файл остаётся на месте, страница не должна стать 404.\n"
        f"Удаление — только вручную после проверки показов за 90 дней.",
    )
    return paths


def staged_allowlist_deletes() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "-z"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 or not result.stdout:
        return []
    parts = result.stdout.split("\0")
    deleted: list[str] = []
    i = 0
    while i < len(parts):
        status = parts[i]
        i += 1
        if not status:
            continue
        if i >= len(parts):
            break
        name = parts[i]
        i += 1
        # Rename: status R100, then old, then new
        if status.startswith("R") or status.startswith("C"):
            i += 1  # skip new name; treat old as deleted
        if not status.startswith("D") and not status.startswith("R"):
            continue
        rel = name.replace("\\", "/")
        if rel.startswith("public/") and is_keep_file(Path(rel)):
            deleted.append(rel)
    return deleted


def unstage(paths: list[str]) -> None:
    if not paths:
        return
    subprocess.run(
        ["git", "reset", "-q", "HEAD", "--", *paths],
        cwd=str(ROOT),
        capture_output=True,
        timeout=30,
    )
    for rel in paths:
        restore_from_git(ROOT / rel)


def guard_staged_commit() -> int:
    """Unstage allowlist deletions and alert. 0 = clean, 1 = blocked deletes."""
    deleted = staged_allowlist_deletes()
    if not deleted:
        return 0
    unstage(deleted)
    alert(
        "Автокоммит отказался удалять страницы allowlist",
        "В staged-коммите были удаления файлов со status=keep:\n"
        + "\n".join(f"  {p}" for p in deleted)
        + "\nУдаления сняты со staging и восстановлены из HEAD. "
        "Остальные файлы можно коммитить. В main удаления allowlist "
        "автоматически не уходят.",
    )
    return 1


def dropped_keep_urls(new_keep: set[str], old_keep: set[str] | None = None) -> list[str]:
    previous = old_keep if old_keep is not None else keep_urls()
    return sorted(previous - new_keep)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] in {"-h", "--help"}:
        print(__doc__)
        print("Usage: index_safety.py --guard-staged-commit")
        return 0
    if args[0] == "--guard-staged-commit":
        return guard_staged_commit()
    print(f"unknown command: {args[0]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
