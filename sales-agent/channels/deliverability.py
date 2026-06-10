"""Анти-бан: лимиты скорости и чёрный список доменов."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "deliverability.yaml"
DATA = ROOT / "data"
LOG_FILE = DATA / "email_send_log.jsonl"
BLACKLIST = DATA / "email_blacklist.json"


def _cfg() -> dict:
    try:
        return yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _domain(email: str) -> str:
    return email.split("@")[-1].lower() if "@" in email else ""


def is_blacklisted(email: str) -> bool:
    try:
        bl = json.loads(BLACKLIST.read_text(encoding="utf-8"))
        return _domain(email) in bl.get("domains", []) or email.lower() in bl.get("emails", [])
    except Exception:
        return False


def add_blacklist(email: str, reason: str = "", *, domain_too: bool = True) -> None:
    """domain_too=False — бан только ящика (hard bounce одного адреса
    не должен блокировать всю компанию)."""
    DATA.mkdir(parents=True, exist_ok=True)
    bl = {"domains": [], "emails": []}
    try:
        bl = json.loads(BLACKLIST.read_text(encoding="utf-8"))
    except Exception:
        pass
    d = _domain(email)
    if domain_too and d and d not in bl["domains"]:
        bl["domains"].append(d)
    el = email.lower()
    if el not in bl["emails"]:
        bl["emails"].append(el)
    bl.setdefault("reasons", {})[el] = reason
    BLACKLIST.write_text(json.dumps(bl, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_log_today() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    today = _today()
    rows = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            if r.get("date") == today:
                rows.append(r)
        except Exception:
            pass
    return rows


def can_send(to: str) -> tuple[bool, str]:
    if is_blacklisted(to):
        return False, "blacklisted"

    cfg = _cfg().get("email", {})
    rows = _read_log_today()
    today_count = len(rows)

    # warmup cap
    w = cfg.get("warmup", {})
    if w.get("enabled"):
        # упрощённо: если мало истории — ниже cap
        total_lines = 0
        if LOG_FILE.exists():
            total_lines = sum(1 for _ in LOG_FILE.open(encoding="utf-8"))
        if total_lines < 200:
            cap = w.get("week1_daily_cap", 50)
        elif total_lines < 1000:
            cap = w.get("week2_daily_cap", 150)
        else:
            cap = w.get("week3_daily_cap", cfg.get("per_day", 300))
        if today_count >= cap:
            return False, f"daily_warmup_cap:{cap}"

    if today_count >= cfg.get("per_day", 300):
        return False, "daily_cap"

    hour_ago = time.time() - 3600
    hour_count = sum(1 for r in rows if r.get("ts", 0) > hour_ago)
    if hour_count >= cfg.get("per_hour", 40):
        return False, "hourly_cap"

    dom = _domain(to)
    dom_count = sum(1 for r in rows if _domain(r.get("to", "")) == dom)
    if dom_count >= cfg.get("max_same_domain_per_day", 3):
        return False, "domain_cap"

    if rows:
        last_ts = max(r.get("ts", 0) for r in rows)
        gap = cfg.get("min_interval_sec", 8)
        if time.time() - last_ts < gap:
            time.sleep(gap - (time.time() - last_ts))

    return True, "ok"


def record_send(to: str, subject: str = "") -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "date": _today(),
        "to": to,
        "domain": _domain(to),
        "subject": subject[:80],
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
