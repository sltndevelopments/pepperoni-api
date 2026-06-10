"""
Lookalike: похожие на эталонных клиентов pepperoni.tatar.

Скоринг по ОКВЭД, выручке, сигналам продукта, региону.
Не шлёт письма — только ранжирует для CRM / аутрича.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REF = ROOT / "config" / "reference_clients.yaml"


def _refs() -> tuple[list[dict], dict]:
    data = yaml.safe_load(REF.read_text(encoding="utf-8")) or {}
    return data.get("references", []), data.get("okved_weights", {})


def _revenue_mln(lead: dict) -> float | None:
    p = lead.get("profile") or {}
    for key in ("revenue_mln_rub", "revenue_mln", "gainSum"):
        v = p.get(key)
        if v:
            try:
                x = float(str(v).replace(",", ".").replace(" ", ""))
                if x > 1_000_000:  # тыс руб в ГИР БО
                    x = x / 1000
                return x
            except Exception:
                pass
    return None


def _revenue_band(mln: float | None) -> str:
    if mln is None:
        return "unknown"
    if mln >= 1000:
        return "giant"
    if mln >= 300:
        return "large"
    if mln >= 100:
        return "medium"
    return "small"


def _okved(lead: dict) -> str:
    p = lead.get("profile") or {}
    return (p.get("okved_main") or p.get("okved_top") or "")[:10]


def _has_signal(lead: dict, signal: str) -> bool:
    p = lead.get("profile") or {}
    if signal == "sausage_in_dough_on_site":
        return bool(p.get("sausage_evidence") or p.get("evidence_label") == "sausage_in_dough")
    if signal == "hot_dog":
        return "hot_dog" in (p.get("evidence_label") or "")
    return False


def score_lookalike(lead: dict) -> dict:
    """
    Возвращает {score, best_match, reasons[]}.
    """
    refs, okved_w = _refs()
    okved = _okved(lead)
    okved_top = okved[:5] if okved else ""
    rev = _revenue_mln(lead)
    band = _revenue_band(rev)
    name_l = (lead.get("name") or "").lower()

    best_score = 0
    best_id = ""
    reasons: list[str] = []

    for ref in refs:
        pts = 0
        ref_reasons: list[str] = []

        for o in ref.get("okved", []):
            if okved.startswith(o) or okved_top == o[:5]:
                w = okved_w.get(o, 20)
                pts += w
                ref_reasons.append(f"+{w} ОКВЭД {o}")

        bands = ref.get("revenue_band", [])
        if band in bands or band == "unknown":
            if band in bands:
                pts += 15
                ref_reasons.append(f"+15 выручка {band}")

        seg = ref.get("segment", "")
        if seg == "regional_bakery":
            if any(x in name_l for x in ("пекарн", "хлеб", "бейкер", "кондитер")):
                pts += 20
                ref_reasons.append("+20 имя пекарня")
            for sig in ref.get("signals", []):
                if _has_signal(lead, sig):
                    pts += 35
                    ref_reasons.append(f"+35 сигнал {sig}")

        if seg == "azs_foodretail" and any(x in name_l for x in ("азс", "нефть", "топлив")):
            pts += 25
            ref_reasons.append("+25 АЗС-паттерн")

        if seg == "foodservice_distributor" and any(x in name_l for x in ("дистриб", "gfc", "фудсервис")):
            pts += 25
            ref_reasons.append("+25 дистрибьютор")

        if seg == "meat_plant_stm" and any(x in name_l for x in ("мяс", "колбас", "омпк")):
            pts += 20
            ref_reasons.append("+20 мясокомбинат")

        if pts > best_score:
            best_score = pts
            best_id = ref.get("id", "")
            reasons = ref_reasons

    # базовый fit_score из CRM
    base = lead.get("fit_score") or 0
    total = best_score + min(base // 3, 30)

    return {
        "lookalike_score": total,
        "best_match": best_id,
        "revenue_band": band,
        "revenue_mln": rev,
        "okved": okved,
        "reasons": reasons,
    }


def rank_leads(leads: list[dict], *, min_score: int = 50) -> list[dict]:
    out = []
    for l in leads:
        s = score_lookalike(l)
        if s["lookalike_score"] >= min_score:
            out.append({**l, "lookalike": s})
    return sorted(out, key=lambda x: x["lookalike"]["lookalike_score"], reverse=True)


if __name__ == "__main__":
    from core.store import Store
    from core.exclusions import is_excluded

    store = Store()
    leads = store.list_leads(limit=500)
    ranked = rank_leads([l for l in leads if not is_excluded(l)[0]], min_score=40)
    for r in ranked[:15]:
        la = r["lookalike"]
        print(f"{la['lookalike_score']:3} {la['best_match']:22} {r['name'][:45]}")
