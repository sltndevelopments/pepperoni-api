#!/usr/bin/env python3
"""Stop automatic destruction of allowlisted (status=keep) pages.

QA criteria are unchanged. This module only blocks the action that follows a
failure or a generator cleanup: DELETE, quarantine (move out of public/),
410, noindex, or a mass 301/410 that would hit a keep URL.

A human override is the CLI flag ``--confirm-destructive``. Cron jobs must
not pass it.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
MANIFEST = ROOT / "data" / "index_manifest.json"
ALERT_LOG = ROOT / "data" / "logs" / "index_safety_alerts.jsonl"
CONFIRM_FLAG = "--confirm-destructive"

# Snippets installed on every deploy by scripts/apply_nginx_trust_reset.sh.
NGINX_INSTALL = (
    "jerky-redirects.conf",
    "karmin-e120-redirects.conf",
    "pepperoni-blog-redirects.conf",
    "geo-cleanup-redirects.conf",
    "geo-cleanup-gone.conf",
    "en-geo-cleanup-redirects.conf",
    "en-geo-cleanup-gone.conf",
    "trust-reset-redirects.conf",
    "trust-reset-gone.conf",
)

_EXACT_LOC = re.compile(
    r"location\s+=\s+(\S+)\s*\{[^}]*\breturn\s+(301|410)\b",
    re.I,
)
_PREFIX_LOC = re.compile(
    r"location\s+\^~\s+(\S+)\s*\{([^}]*)\}",
    re.I | re.S,
)


def destructive_confirmed(argv: list[str] | None = None) -> bool:
    argv = sys.argv if argv is None else argv
    return CONFIRM_FLAG in argv


def load_keep(manifest: Path | None = None) -> dict[str, str]:
    """Map a public-relative file path to its canonical URL."""
    path = manifest or MANIFEST
    payload = json.loads(path.read_text(encoding="utf-8"))
    keep: dict[str, str] = {}
    for row in payload.get("entries") or []:
        if row.get("status") != "keep":
            continue
        rel = str(row.get("file") or "").lstrip("/")
        url = str(row.get("url") or "")
        if rel:
            keep[rel] = url
    return keep


def public_rel(path: Path | str) -> str | None:
    raw = str(path).replace("\\", "/")
    if raw.startswith("public/"):
        return raw[len("public/"):]
    try:
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        return p.resolve().relative_to(PUBLIC.resolve()).as_posix()
    except (ValueError, OSError):
        return None


def is_keep_file(path: Path | str, keep: dict[str, str] | None = None) -> bool:
    rel = public_rel(path)
    if not rel:
        return False
    table = keep if keep is not None else load_keep()
    return rel in table


def alert(action: str, path: Path | str, detail: str) -> None:
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "path": str(path),
        "detail": detail,
    }
    line = json.dumps(rec, ensure_ascii=False)
    print(f"index_safety: BLOCK {action} {path} — {detail}", file=sys.stderr)
    try:
        ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with ALERT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        print(f"index_safety: alert log failed: {exc}", file=sys.stderr)
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from daily_ledger import append_event
        append_event(
            "emergency",
            f"🛑 index safety: {action} остановлен\n{path}\n{detail[:240]}",
        )
    except Exception:
        pass


def block_if_keep(
    action: str,
    path: Path | str,
    *,
    confirm: bool = False,
    keep: dict[str, str] | None = None,
) -> bool:
    """Return True when the destructive action must not run."""
    if confirm or not is_keep_file(path, keep):
        return False
    alert(
        action,
        path,
        "allowlisted page (status=keep); needs --confirm-destructive",
    )
    return True


def restore_keep_file(path: Path | str) -> bool:
    """Put the tracked file back from HEAD. No-op if it already matches."""
    rel = public_rel(path)
    if not rel:
        return False
    git_path = f"public/{rel}"
    try:
        proc = subprocess.run(
            ["git", "checkout", "HEAD", "--", git_path],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"index_safety: restore failed: {exc}", file=sys.stderr)
        return False
    if proc.returncode != 0:
        print(
            f"index_safety: restore failed for {git_path}: {proc.stderr.strip()}",
            file=sys.stderr,
        )
        return False
    return True


def staged_keep_deletions(keep: dict[str, str] | None = None) -> list[str]:
    table = keep if keep is not None else load_keep()
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--diff-filter=D", "--name-only"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    hits = []
    for line in proc.stdout.splitlines():
        name = line.strip()
        if name and is_keep_file(name, table):
            hits.append(name)
    return hits


def restore_staged_keep_deletions() -> list[str]:
    restored = []
    for name in staged_keep_deletions():
        if restore_keep_file(name):
            restored.append(name)
    return restored


def _norm_url(location: str) -> str:
    url = location.strip().strip("'\"")
    if not url.startswith("/"):
        url = "/" + url
    if url.endswith(".html"):
        url = url[: -len(".html")]
    if len(url) > 1 and url.endswith("/"):
        url = url[:-1]
    return url or "/"


def nginx_keep_conflicts(text: str, keep_urls: set[str]) -> list[str]:
    """Return human-readable hits where a snippet 301/410s a keep URL."""
    conflicts: list[str] = []
    for match in _EXACT_LOC.finditer(text):
        url = _norm_url(match.group(1))
        code = match.group(2)
        if url in keep_urls:
            conflicts.append(f"{code} {url}")
    for match in _PREFIX_LOC.finditer(text):
        prefix = _norm_url(match.group(1))
        body = match.group(2)
        if not re.search(r"\b(301|410)\b", body):
            continue
        for url in sorted(keep_urls):
            if url == prefix or url.startswith(prefix + "/"):
                conflicts.append(f"prefix {prefix} hits {url}")
    return conflicts


def check_nginx_install(nginx_dir: Path | None = None) -> list[str]:
    folder = nginx_dir or (ROOT / "deploy" / "nginx")
    keep_urls = set(load_keep().values())
    found: list[str] = []
    for name in NGINX_INSTALL:
        path = folder / name
        if not path.exists():
            found.append(f"missing snippet {name}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for hit in nginx_keep_conflicts(text, keep_urls):
            found.append(f"{name}: {hit}")
    return found


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--refuse-staged-keep-deletions" in argv:
        hits = staged_keep_deletions()
        for name in hits:
            alert("commit-delete", name, "autocommit will not push this deletion")
        return 2 if hits else 0
    if "--restore-staged-keep-deletions" in argv:
        restored = restore_staged_keep_deletions()
        print(f"index_safety: restored {len(restored)} allowlisted file(s)")
        return 0
    if "--check-nginx-install" in argv:
        hits = check_nginx_install()
        for hit in hits:
            print(f"index_safety: nginx {hit}", file=sys.stderr)
        return 1 if hits else 0
    print(
        "usage: index_safety.py "
        "--refuse-staged-keep-deletions | "
        "--restore-staged-keep-deletions | "
        "--check-nginx-install",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
