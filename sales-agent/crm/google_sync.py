"""
Двусторонний sync: agent.db ↔ Google Sheets CRM.

  crm-setup  — создать/перестроить вкладки по crm_schema.yaml
  crm-pull   — импорт лидов + правки менеджера из таблицы
  crm-push   — запись agent_* колонок и журнала «Активность»
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from core.store import Store
from crm.google_auth import get_access_token
from prospecting.contact_research import label_profile_emails

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "config" / "crm_schema.yaml"
SHEET_ID_FILE = ROOT / "data" / "crm_sheet_id.txt"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def load_schema() -> dict:
    return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8")) or {}


def sheet_id() -> str:
    sid = os.environ.get("CRM_SHEET_ID", "").strip()
    if sid:
        return sid
    if SHEET_ID_FILE.is_file():
        return SHEET_ID_FILE.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        "CRM_SHEET_ID не задан. Запустите: python -m console.cli crm-setup"
    )


def save_sheet_id(sid: str) -> None:
    SHEET_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    SHEET_ID_FILE.write_text(sid.strip(), encoding="utf-8")


def _api(
    method: str,
    url: str,
    token: str,
    body: dict | None = None,
) -> dict:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Sheets API {e.code} {method} {url}: {err}") from e


def _leads_headers(schema: dict) -> list[str]:
    return [c["header"] for c in schema["tabs"]["leads"]["columns"]]


def _activity_headers(schema: dict) -> list[str]:
    return [c["header"] for c in schema["tabs"]["activity"]["columns"]]


def _profile_field(profile: dict, key: str) -> str:
    """Маппинг старых колонок pub-CSV → схема CRM."""
    aliases = {
        "company_short": ("company_short", "name_short"),
        "region": ("region", "region_name"),
        "lookalike_score": ("lookalike_score", "score"),
        "priority": ("priority", "tier"),
    }
    if key in aliases:
        for k in aliases[key]:
            v = profile.get(k)
            if v not in (None, ""):
                return str(v).strip()
    v = profile.get(key)
    return "" if v is None else str(v).strip()


def _lead_row_from_db(lead: dict, schema: dict) -> list[str]:
    from core import agent_profile as ap
    p = lead.get("profile") or {}
    agent = ap.get(p, "agent") or p.get("agent") or {}
    lookalike = ap.get(p, "lookalike") or p.get("lookalike") or {}
    human = p.get("crm") or {}

    values: dict[str, str] = {
        "inn": lead.get("inn") or "",
        "company_short": lead.get("name") or _profile_field(p, "company_short"),
        "legal_form": _profile_field(p, "legal_form"),
        # ручной статус из таблицы приоритетен, но "new" не должен скрывать прогресс агента
        "status": (
            human.get("status")
            if human.get("status") and human.get("status") != "new"
            else (lead.get("status") or "new")
        ),
        "owner": human.get("owner") or "",
        "priority": human.get("priority") or _profile_field(p, "priority"),
        "last_touch": human.get("last_touch") or "",
        "next_action": human.get("next_action") or "",
        "notes": human.get("notes") or "",
        "lpr_name": human.get("lpr_name") or p.get("lpr_name", ""),
        "lpr_email": human.get("lpr_email") or p.get("lpr_email", ""),
        "lpr_phone": human.get("lpr_phone") or p.get("lpr_phone", ""),
        "gatekeeper_path": agent.get("gatekeeper_path") or "",
        "okved_main": _profile_field(p, "okved_main"),
        "okved_name": _profile_field(p, "okved_name"),
        "revenue_mln_rub": _profile_field(p, "revenue_mln_rub"),
        "region": lead.get("region") or _profile_field(p, "region"),
        "city": _profile_field(p, "city"),
        "phones": _profile_field(p, "phones"),
        "emails": _profile_field(p, "emails"),
        "website": _profile_field(p, "website"),
        "sausage_in_dough": _profile_field(p, "sausage_in_dough"),
        "evidence_label": _profile_field(p, "evidence_label"),
        "evidence_url": _profile_field(p, "evidence_url"),
        "agent_status": agent.get("status") or _agent_status(lead),
        "agent_temperature": agent.get("temperature") or "",
        "lookalike_score": str(lookalike.get("lookalike_score") or lead.get("fit_score") or ""),
        "lookalike_match": lookalike.get("best_match") or "",
        "emails_sent_count": str(agent.get("emails_sent_count") or ""),
        "last_email_at": agent.get("last_email_at") or "",
        "last_email_subject": agent.get("last_email_subject") or "",
        "last_draft_id": agent.get("last_draft_id") or "",
        "escalation_reason": ap.get(p, "escalation_reason") or "",
        "escalated_at": ap.get(p, "escalated_at") or ap.get(p, "owner_escalated_at") or "",
        "agent_updated_at": agent.get("updated_at") or _now(),
    }
    keys = [c["key"] for c in schema["tabs"]["leads"]["columns"]]
    return [values.get(k, "") for k in keys]


def _agent_status(lead: dict) -> str:
    st = lead.get("status") or "new"
    if st in ("hot", "escalated", "replied", "meeting", "proposal"):
        return st
    if st == "owner_contact":
        return "excluded"
    if st == "contacted":
        return "sent"
    return "idle"


def _existing_tab_titles(token: str, sid: str) -> set[str]:
    data = _api(
        "GET",
        f"https://sheets.googleapis.com/v4/spreadsheets/{sid}?fields=sheets.properties.title",
        token,
    )
    return {
        s["properties"]["title"]
        for s in data.get("sheets", [])
        if s.get("properties", {}).get("title")
    }


def _ensure_tabs(token: str, sid: str, titles: list[str]) -> list[str]:
    """Добавить вкладки CRM, не трогая существующие (например «Лист1»)."""
    have = _existing_tab_titles(token, sid)
    added: list[str] = []
    requests = []
    for title in titles:
        if title in have:
            continue
        requests.append({"addSheet": {"properties": {"title": title}}})
        added.append(title)
    if requests:
        _api(
            "POST",
            f"https://sheets.googleapis.com/v4/spreadsheets/{sid}:batchUpdate",
            token,
            {"requests": requests},
        )
    return added


def _share_with_owner(token: str, file_id: str) -> None:
    email = os.environ.get("OWNER_EMAIL", "").strip()
    if not email:
        return
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions"
    body = {"type": "user", "role": "writer", "emailAddress": email}
    _api("POST", url, token, body)


def setup_crm(*, store: Store | None = None, title: str = "KD Sales CRM") -> dict:
    """Создать таблицу или перестроить вкладки существующей."""
    schema = load_schema()
    token, sa = get_access_token()
    store = store or Store()
    store.init()

    sid = os.environ.get("CRM_SHEET_ID", "").strip()
    if not sid and SHEET_ID_FILE.is_file():
        sid = SHEET_ID_FILE.read_text(encoding="utf-8").strip()

    if not sid:
        sa_email = sa["client_email"]
        raise RuntimeError(
            "Service account не может создать новую таблицу (квота Drive = 0). "
            "Используйте вашу существующую таблицу:\n"
            f"  1. Share → Editor → {sa_email}\n"
            "  2. CRM_SHEET_ID=... из URL .../d/{ID}/edit в sales-agent/.env\n"
            "  3. python3 -m console.cli crm-setup"
        )

    save_sheet_id(sid)
    meta = _api(
        "GET",
        f"https://sheets.googleapis.com/v4/spreadsheets/{sid}?fields=spreadsheetId,properties.title,sheets.properties",
        token,
    )

    leads_title = schema["tabs"]["leads"]["title"]
    activity_title = schema["tabs"]["activity"]["title"]
    readme_title = schema["tabs"]["readme"]["title"]
    existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
    added_tabs = _ensure_tabs(token, sid, [leads_title, activity_title, readme_title])

    headers_leads = _leads_headers(schema)
    headers_activity = _activity_headers(schema)

    _api(
        "PUT",
        f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/"
        f"{urllib.parse.quote(leads_title)}!A1?valueInputOption=RAW",
        token,
        {"values": [headers_leads]},
    )
    _api(
        "PUT",
        f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/"
        f"{urllib.parse.quote(activity_title)}!A1?valueInputOption=RAW",
        token,
        {"values": [headers_activity]},
    )
    readme_lines = schema["tabs"]["readme"].get("blocks") or []
    _api(
        "PUT",
        f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/"
        f"{urllib.parse.quote(readme_title)}!A1?valueInputOption=RAW",
        token,
        {"values": [[line] for line in readme_lines]},
    )

    # Заполнить лиды из БД
    leads = store.list_leads(limit=5000)
    rows = [_lead_row_from_db(l, schema) for l in leads]
    if rows:
        _api(
            "PUT",
            f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/"
            f"{urllib.parse.quote(leads_title)}!A2?valueInputOption=RAW",
            token,
            {"values": rows},
        )

    url = f"https://docs.google.com/spreadsheets/d/{sid}/edit"
    store.audit("crm_setup", "sheet_ready", detail={"sheet_id": sid, "url": url, "rows": len(rows)})
    return {
        "sheet_id": sid,
        "url": url,
        "spreadsheet_title": meta.get("properties", {}).get("title", ""),
        "existing_tabs": existing,
        "added_tabs": added_tabs,
        "service_account": sa["client_email"],
        "leads_written": len(rows),
        "share_with": os.environ.get("OWNER_EMAIL", ""),
    }


def _read_sheet_rows(token: str, sid: str, tab: str) -> list[dict]:
    qtab = urllib.parse.quote(tab)
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{qtab}"
    data = _api("GET", url, token)
    values = data.get("values") or []
    if not values:
        return []
    headers = [h.strip() for h in values[0]]
    rows: list[dict] = []
    for line in values[1:]:
        if len(line) < len(headers):
            line = line + [""] * (len(headers) - len(line))
        rows.append(dict(zip(headers, line)))
    return rows


def pull_leads(*, store: Store | None = None, limit: int | None = None) -> dict:
    """Импорт из «Лиды» → agent.db (включая правки менеджера)."""
    schema = load_schema()
    token, _ = get_access_token()
    sid = sheet_id()
    tab = schema["tabs"]["leads"]["title"]
    parsed = _read_sheet_rows(token, sid, tab)
    store = store or Store()
    store.init()

    human_cols = schema.get("sync", {}).get("human_columns_pull") or []
    imported = 0

    for i, row in enumerate(parsed):
        if limit and i >= limit:
            break
        name = (row.get("company_short") or row.get("name_short") or "").strip()
        inn = (row.get("inn") or "").strip() or None
        if not name and not inn:
            continue

        score = 0
        try:
            score = int(float(str(row.get("lookalike_score") or row.get("score") or "0").replace(",", ".")))
        except Exception:
            pass

        tier_raw = (row.get("priority") or row.get("tier") or "—").strip()
        tier = tier_raw[0] if tier_raw and tier_raw[0] in "SABC" else "—"

        status = (row.get("status") or "new").strip()
        if inn == "7724766868":
            status = "owner_contact"

        existing = None
        if inn:
            with store._conn() as conn:
                r = conn.execute("SELECT * FROM leads WHERE inn=?", (inn,)).fetchone()
                existing = dict(r) if r else None

        # Статус "new" в таблице не должен откатывать прогресс агента
        # (contacted/hot/...). Ручные правки менеджера (qualified, won...) — применяем.
        if existing and status == "new" and (existing.get("status") or "new") != "new":
            status = existing["status"]

        profile = dict(row)
        if existing:
            try:
                old_profile = json.loads(existing.get("profile") or "{}")
            except Exception:
                old_profile = {}

            from core import agent_profile as ap

            # Сначала канонизируем весь legacy escalation/handoff state.
            # Иначе последующий pull защищает только уже существующий _agent,
            # а старые верхнеуровневые поля навсегда теряются.
            ap.migrate_legacy(old_profile)

            # Мигрируем legacy верхнеуровневые ключи аналитики в _agent,
            # чтобы они тоже жили под единым namespace и не выпали при pull.
            _migrate_keys = ("agent", "lookalike", "sausage_evidence", "score_reasons")
            if any(k in old_profile for k in _migrate_keys):
                agent_ns = old_profile.setdefault("_agent", {})
                for k in _migrate_keys:
                    if k in old_profile and k not in agent_ns:
                        agent_ns[k] = old_profile[k]

            # Сохраняем весь _agent целиком — единственное, что нужно защитить от pull.
            # Никакого whitelist: любой новый флаг автоматически переживёт синхронизацию.
            if "_agent" in old_profile:
                profile["_agent"] = old_profile["_agent"]

            # Если лид был передан менеджеру — не сбрасывать статус
            if ap.is_handed_off(old_profile):
                status = "handed_off"

        crm_patch = {k: (row.get(k) or "").strip() for k in human_cols if row.get(k)}
        if crm_patch:
            profile["crm"] = crm_patch

        # Импортированные адреса получают дешёвую предварительную разметку.
        # Это не верификация: email_verified остаётся False до contact research.
        label_profile_emails(profile)

        store.upsert_lead(
            name or f"ИНН {inn}",
            inn=inn,
            region=(row.get("region") or row.get("region_name") or "").strip() or None,
            tier=tier,
            fit_score=max(score, (existing or {}).get("fit_score") or 0),
            status=status,
            source=(
                "inbound"
                if profile.get("inbound_reason") or profile.get("interest_confirmed")
                else "crm_sheet_api"
            ),
            profile=profile,
        )
        imported += 1

    store.audit("crm_pull", "imported", detail={"count": imported, "sheet_id": sid})
    return {"imported": imported, "sheet_id": sid, "mode": "api"}


def push_leads(*, store: Store | None = None, limit: int = 5000) -> dict:
    """Записать лиды из agent.db в «Лиды» (полная перезапись данных, шапка сохраняется)."""
    schema = load_schema()
    token, _ = get_access_token()
    sid = sheet_id()
    tab = schema["tabs"]["leads"]["title"]
    store = store or Store()

    headers = _leads_headers(schema)
    leads = store.list_leads(limit=limit)
    rows = [_lead_row_from_db(l, schema) for l in leads]

    _api(
        "PUT",
        f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/"
        f"{urllib.parse.quote(tab)}!A1?valueInputOption=RAW",
        token,
        {"values": [headers] + rows},
    )
    store.audit("crm_push", "leads", detail={"count": len(rows), "sheet_id": sid})
    return {"pushed": len(rows), "sheet_id": sid}


def push_activity(*, store: Store | None = None, limit: int = 100) -> dict:
    """Дописать новые строки в «Активность» из audit_log."""
    schema = load_schema()
    token, _ = get_access_token()
    sid = sheet_id()
    tab = schema["tabs"]["activity"]["title"]
    store = store or Store()

    state_file = ROOT / "data" / "crm_activity_cursor.txt"
    last_id = state_file.read_text(encoding="utf-8").strip() if state_file.exists() else ""

    entries = store.audit_tail(limit=limit)
    entries = list(reversed(entries))
    if last_id:
        try:
            idx = next(i for i, e in enumerate(entries) if e["id"] == last_id)
            entries = entries[idx + 1:]
        except StopIteration:
            pass

    if not entries:
        return {"appended": 0, "sheet_id": sid}

    rows: list[list[str]] = []
    for e in entries:
        detail = {}
        try:
            detail = json.loads(e.get("detail") or "{}")
        except Exception:
            pass
        rows.append([
            (e.get("created_at") or "")[:19],
            detail.get("inn", ""),
            detail.get("company_short") or detail.get("lead_name", ""),
            e.get("action", ""),
            json.dumps(detail, ensure_ascii=False)[:400] if detail else "",
            detail.get("draft_id", ""),
            detail.get("model", ""),
        ])

    qtab = urllib.parse.quote(tab)
    _api(
        "POST",
        f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{qtab}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS",
        token,
        {"values": rows},
    )
    state_file.write_text(entries[-1]["id"], encoding="utf-8")
    return {"appended": len(rows), "sheet_id": sid}


def crm_sync(*, store: Store | None = None) -> dict:
    """pull → push leads → push activity."""
    store = store or Store()
    pull = pull_leads(store=store)
    push = push_leads(store=store)
    activity = push_activity(store=store)
    return {"pull": pull, "push": push, "activity": activity}
