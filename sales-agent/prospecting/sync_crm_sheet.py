"""
Синк опубликованной Google-таблицы → agent.db.

URL: config/deliverability.yaml → crm_sheet.url
Публикация в интернете достаточна (pub?output=csv).
"""
from __future__ import annotations

import csv
import io
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.store import Store

CFG = ROOT / "config" / "deliverability.yaml"


def sheet_url() -> str:
    try:
        cfg = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
        return cfg.get("crm_sheet", {}).get("url", "")
    except Exception:
        return ""


def fetch_csv(url: str | None = None) -> str:
    url = url or sheet_url()
    if not url:
        raise RuntimeError("crm_sheet.url not configured")
    req = urllib.request.Request(url, headers={"User-Agent": "KDSalesAgent/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8-sig")


def _parse_pub_csv(raw: str) -> list[dict]:
    """
    Google pub CSV иногда отдаёт каждую строку как одну ячейку в кавычках.
    Разворачиваем во внутренний CSV.
    """
    headers: list[str] | None = None
    rows: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('"') and line.endswith('"'):
            line = line[1:-1].replace('""', '"')
        inner = next(csv.reader(io.StringIO(line)))
        if headers is None:
            headers = [h.strip() for h in inner]
            continue
        if len(inner) < len(headers):
            inner.extend([""] * (len(headers) - len(inner)))
        rows.append(dict(zip(headers, inner)))
    return rows


def _try_api_pull(*, store: Store, limit: int | None) -> dict | None:
    try:
        from crm.google_sync import pull_leads
        return pull_leads(store=store, limit=limit)
    except Exception:
        return None


def sync(*, store: Store | None = None, limit: int | None = None) -> dict:
    store = store or Store()
    api_result = _try_api_pull(store=store, limit=limit)
    if api_result is not None:
        return api_result
    raw = fetch_csv()
    parsed = _parse_pub_csv(raw)
    imported = 0
    for i, row in enumerate(parsed):
        if limit and i >= limit:
            break
        name = (row.get("name_short") or row.get("company_short") or "").strip()
        if not name:
            continue
        score = 0
        try:
            score = int(float(str(row.get("score", "0")).replace(",", ".")))
        except Exception:
            pass
        tier_raw = (row.get("tier") or "—").strip()
        tier = tier_raw[0] if tier_raw and tier_raw[0] in "SABC" else "—"
        inn = (row.get("inn") or "").strip() or None
        # Коломенский — на контакте у владельца
        status = "new"
        if inn == "7724766868" or "БКК \"КОЛОМЕНСКИЙ\"" in name.upper() or 'БКК "КОЛОМЕНСКИЙ"' in name:
            status = "owner_contact"
        store.upsert_lead(
            name,
            inn=inn,
            region=(row.get("region_name") or row.get("region") or "").strip() or None,
            tier=tier,
            fit_score=score,
            status=status,
            source="crm_sheet",
            profile=dict(row),
        )
        imported += 1
    store.audit("sync_crm_sheet", "imported", detail={"count": imported})
    return {"imported": imported, "url": sheet_url(), "parsed_rows": len(parsed)}


if __name__ == "__main__":
    import json
    print(json.dumps(sync(), ensure_ascii=False, indent=2))
