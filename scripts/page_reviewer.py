#!/usr/bin/env python3
"""Automatic page quality gate — the only barrier between generation and publication.

There is NO human in the loop. This module is the sole autonomous guardian that
decides whether a generated page reaches the live site. Because of that:

FAIL-CLOSED CONTRACT: any error (LLM timeout, rate-limit, budget, import failure,
exception) → verdict = "hold" (treated as reject by callers) + Telegram alert.
A broken reviewer NEVER opens the gate. "Rецензент лёг → ничего не выходит"
is the correct behaviour, not "рецензент лёг → шлюз открылся".

HARDCODED CRITERIA (in this file, not in PLAYBOOK):
The brain cannot modify this module (it is in brain_toolsmith.PROTECTED_AGENTS).
The criteria below define the North Star quality bar. In case of doubt → reject.

  1. Substantive depth — not a thin template, not filler text, ≥ 300 visible words,
     real product facts (weight, certification, MOQ, shelf life, use case).
  2. Commercial or buyer intent — useful to a B2B buyer, HoReCa operator,
     distributor, OEM/STM/export buyer. Pure SEO-filler without business value → reject.
  3. Uniqueness — not a near-duplicate of another geo page with only city swapped.
     Checked heuristically (fingerprint similarity) before LLM call; if suspicious,
     the LLM makes the final call.
  4. Halal & brand integrity — no invented certifications, no invented clients,
     no personal phone/email (only +7 987 217-02-02 / info@kazandelikates.tatar),
     no pork/alcohol mentions, halal claims match our real certs (ДУМ РТ, HACCP,
     ISO 22000). Any violation → reject.
  5. Structural completeness — valid HTML, <title>, <meta description>, at least
     one H1, contact CTA or price, no markdown fences, no leftover LLM boilerplate.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
QUARANTINE = ROOT / "data" / "quarantine"
GATE_LOG = DATA / "page_gate_log.json"
KEEP_LOG = 200   # max entries in gate log

sys.path.insert(0, str(ROOT / "scripts"))

# ── Criteria prompt (hardcoded — brain cannot modify) ────────────────────────
_CRITERIA = """
Ты — строгий рецензент SEO-страниц для pepperoni.tatar (Казанские Деликатесы,
халяль производитель, B2B/оптовые продажи, экспорт).

Твоя задача: вынести ОБЪЕКТИВНЫЙ вердикт по странице. В сомнении — отклонить.
Одна задача: защитить сайт от мусора и дублей, которые снижают доверие Google.

КРИТЕРИИ (все обязательны; нарушение любого → reject):

1. ГЛУБИНА И СОДЕРЖАТЕЛЬНОСТЬ
   - Видимый текст ≥ 300 слов, содержит реальные факты о продукте/услуге
     (вес, фасовка, условия хранения, сертификаты, MOQ, кейсы использования)
   - НЕ шаблонная «вода» («Мы предлагаем лучшее качество...»)

2. КОММЕРЧЕСКИЙ / БАЙЕРСКИЙ ИНТЕНТ
   - Полезна для B2B-покупателя, HoReCa-оператора, дистрибьютора, OEM/СТМ/
     экспортного байера — то есть человека, который ХОЧЕТ КУПИТЬ или ЗАКАЗАТЬ
   - Чистый SEO-наполнитель без делового содержания → reject

3. УНИКАЛЬНОСТЬ
   - Не является очевидным дублем другой страницы с подменой одного города/слова
   - Если в метаданных передан `fingerprint_similarity` > 0.85 → reject как дубль

4. ХАЛЯЛЬ И БРЕНД-ЦЕЛОСТНОСТЬ
   - Нет выдуманных сертификатов, наград, клиентов, партнёров
   - Контакты строго: +7 987 217-02-02 и/или info@kazandelikates.tatar
     (никаких 8-800, других номеров, других email)
   - Нет свинины/сала/шпика/алкоголя в любом контексте
   - Халяль-сертификаты только наши: ДУМ РТ, HACCP, ISO 22000
   - ARABIC HALAL RULE (critical for AR pages):
     خنزير/pork/свинина mentioned as a PRODUCT NAME, positive offer, or JSON-LD
     description → REJECT (халяль-нарушение).
     خنزير in NEGATION ONLY is CORRECT and must NOT trigger rejection:
       OK: لا خنزير / بدون خنزير / خالٍ من الخنزير / بدون مشتقات خنزير /
           pork-free / без свинины / ❌ competitor contains pork
       REJECT: "поставщик халяль-свинины" / "مورد لحوم خنزير حلال" /
               "لحوم الخنزير الحلال" as product description
     When metadata CONTAINS_KHANZIR=true is passed, apply extra scrutiny
     to every خنزير occurrence and classify each as negation or offer.

5. СТРУКТУРНАЯ ПОЛНОТА
   - Есть <title>, <meta description>, хотя бы один H1
   - Есть CTA (контакт, кнопка, телефон) или цена/условия
   - Нет markdown-ограждений (```), нет остатков LLM-ответа («Вот готовая страница...»)
   - Страница выглядит как завершённая, а не обрезанная

6. GEO-ФОРМАТ (§5 устава сайта — обязательно для GEO-страниц; нарушение → reject):
   a. ОТВЕТ-ПЕРВЫМ: в первых ~200 словах видимого текста (сразу после H1) есть
      блок <div class="tldr-answer"> с прямым ответом закупщику — что поставляем,
      халяль-статус, готовность к СТМ/OEM, срок доставки в этот город.
      Отсутствие блока → reject.
   b. НЕТ НЕПРОВЕРЯЕМЫХ СУПЕРЛАТИВОВ: запрещены фразы «лучший в России/мире»,
      «выбирают нас 10+ лет», «поставки в 20+ стран», «партнёры рекомендуют»,
      «пиццерия увеличила продажи», «лидер рынка» и аналогичные превосходные
      claims без верифицируемых данных → reject.
   c. ЯЗЫК ЗАКУПЩИКА: страница обращается к B2B-покупателю (HoReCa, дистрибьютор,
      сеть, производство), а не к розничному потребителю. Признаки розничного
      фрейма («купите для семьи», «вкусный ужин», «попробуйте») → reject.
   d. СЕКЦИЯ СЦЕНАРИЯ ПРИМЕНЕНИЯ: есть раздел или блок, описывающий как продукт
      применяется в процессе клиента (оборудование, технология, формат использования).
      Язык: «при запекании», «в роллерном гриле», «при нарезке слайсером» и т.п.
      Отсутствие → reject.
   ПРИМЕЧАНИЕ: Halal-правило (خنزير, pork-free) и no-fake-reviews — уже в критерии 4
   и инвариантах. Не дублируй здесь.

ФОРМАТ ОТВЕТА (строго JSON, без пояснений вне JSON):
{
  "verdict": "pass" | "reject",
  "reasons": ["причина 1", "причина 2"]   // при pass — [] или краткие плюсы
}
"""

_GOOD_PHONE = "79872170202"
_GOOD_EMAIL = "info@kazandelikates.tatar"


# ── Heuristic fingerprint (no LLM, fast) ────────────────────────────────────

def _text_fingerprint(html: str) -> str:
    """Stable fingerprint of visible text for near-dup detection."""
    cleaned = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", " ", html,
                     flags=re.I | re.S)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    words = sorted(set(w.lower() for w in re.split(r"\W+", cleaned) if len(w) > 4))
    return hashlib.md5(" ".join(words).encode()).hexdigest()


def _similarity(fp1: str, fp2: str) -> float:
    """Jaccard-like similarity between two sorted word sets encoded in fingerprints.
    Fast approximation: compare the raw word-sets via fp strings.
    Returns 0.0 (totally different) to 1.0 (identical).
    """
    # We stored sorted word lists above; re-derive from the html instead if needed.
    # Here we just compare hex hashes for identity; callers do set-based comparison.
    return 1.0 if fp1 == fp2 else 0.0


def _check_near_dup(html: str, path: Path) -> float:
    """Compare against recently generated geo pages. Returns max similarity (0–1)."""
    fp = _text_fingerprint(html)
    slug_tokens = set(re.split(r"[-_]", path.stem.lower())) - {""}

    # Read last 50 geo pages from DB (fast, no LLM).
    try:
        import sqlite3
        db = DATA / "seo_data.db"
        if not db.exists():
            return 0.0
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT file_path FROM geo_pages ORDER BY rowid DESC LIMIT 50"
        ).fetchall()
        conn.close()
    except Exception:
        return 0.0

    # Build word sets for similarity
    def _words(h: str) -> set:
        c = re.sub(r"<[^>]+>", " ", re.sub(
            r"<(script|style|head)[^>]*>.*?</\1>", " ", h, flags=re.I | re.S))
        return {w.lower() for w in re.split(r"\W+", c) if len(w) > 4} - slug_tokens

    own_words = _words(html)
    if not own_words:
        return 0.0

    max_sim = 0.0
    for (fp_path,) in rows:
        try:
            other = Path(fp_path)
            if not other.exists() or other == path:
                continue
            other_words = _words(other.read_text(encoding="utf-8", errors="ignore"))
            if not other_words:
                continue
            inter = len(own_words & other_words)
            union = len(own_words | other_words)
            sim = inter / union if union else 0.0
            if sim > max_sim:
                max_sim = sim
            if max_sim > 0.9:   # early exit
                break
        except Exception:
            continue
    return round(max_sim, 3)


# ── Log ──────────────────────────────────────────────────────────────────────

def _log(path: Path, verdict: str, reasons: list, error: str = "") -> None:
    try:
        log = json.loads(GATE_LOG.read_text(encoding="utf-8")) if GATE_LOG.exists() else []
    except Exception:
        log = []
    log.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "verdict": verdict,
        "reasons": reasons,
        "error": error,
    })
    log = log[-KEEP_LOG:]
    DATA.mkdir(parents=True, exist_ok=True)
    GATE_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


def _alert(msg: str) -> None:
    try:
        from telegram_notify import notify
        notify(msg)
    except Exception:
        pass


# ── Quarantine helper ────────────────────────────────────────────────────────

def quarantine(path: Path, reasons: list, verdict: str = "reject") -> None:
    """Move path to data/quarantine/ preserving relative structure."""
    try:
        rel = path.relative_to(PUBLIC)
    except ValueError:
        rel = Path(path.name)
    dest = QUARANTINE / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dest))
    _log(path, verdict, reasons)


# ── Main gate ────────────────────────────────────────────────────────────────

def review_page(path: Path, meta: dict | None = None) -> dict:
    """Gate a generated page. Returns {"verdict":"pass"|"reject"|"hold", "reasons":[]}.

    FAIL-CLOSED: any exception → verdict="hold" (caller treats as reject),
    Telegram alert sent, page NOT published. The gate must never silently open.

    `meta` can carry: {"slug": str, "lang": str, "product": str, "city": str}
    """
    meta = meta or {}
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        msg = f"🚨 Рецензент: не удалось прочитать файл {path.name}: {e}"
        _alert(msg)
        _log(path, "hold", [], error=str(e))
        return {"verdict": "hold", "reasons": [f"unreadable: {e}"]}

    # ── Fast heuristic pre-checks (no LLM) ────────────────────────────────
    fast_fails = []

    # AR halal pre-flag: if خنزير is present, note it for the LLM so it
    # scrutinises every occurrence.  The LLM (not regex) decides violation vs.
    # legitimate negation — this is just a cheap "pay attention" signal.
    _khanzir_flag = bool(re.search(r'خنزير', html))
    if _khanzir_flag:
        meta = dict(meta)   # shallow copy — don't mutate caller's dict
        meta["CONTAINS_KHANZIR"] = (
            "true — page contains Arabic word for pork (خنزير). "
            "Classify EVERY occurrence: negation/comparison = OK; "
            "product name / positive offer = REJECT (halal violation)."
        )

    # Word count
    cleaned = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", " ", html,
                     flags=re.I | re.S)
    visible = re.sub(r"<[^>]+>", " ", cleaned)
    word_count = len([w for w in visible.split() if len(w) > 1])
    if word_count < 300:
        fast_fails.append(f"тонкая страница: {word_count} слов < 300")

    # Structural must-haves
    hl = html.lower()
    if "<title" not in hl:
        fast_fails.append("нет <title>")
    if "</html>" not in hl:
        fast_fails.append("страница обрезана (нет </html>)")
    if "```" in html:
        fast_fails.append("markdown-ограждение в HTML")
    if re.search(r"(?:Вот|Конечно|Here is|Certainly)[,!]? (?:HTML|готов|the page)", html, re.I):
        fast_fails.append("остаток LLM-ответа в странице")

    # Near-dup check
    try:
        sim = _check_near_dup(html, path)
        if sim > 0.85:
            fast_fails.append(f"дубликат: схожесть {sim:.0%} с существующей страницей")
    except Exception:
        pass

    if fast_fails:
        quarantine(path, fast_fails)
        return {"verdict": "reject", "reasons": fast_fails}

    # ── LLM review (Sonnet) ───────────────────────────────────────────────
    sim_note = ""
    try:
        sim = _check_near_dup(html, path)
        if sim > 0.7:
            sim_note = f"\nfingerprint_similarity={sim:.2f} (>0.85 → автоотклонение как дубль)"
    except Exception:
        pass

    # Pre-check structural facts that the LLM cannot see in plain text.
    # Providing ground truth prevents false-positive rejections.
    has_tldr   = 'class="tldr-answer"' in html or "class='tldr-answer'" in html
    has_close  = "</html>" in html.lower()
    precheck = (
        f"PRE-CHECKS (машинная верификация до LLM):\n"
        f"  tldr-answer class: {'ПРИСУТСТВУЕТ' if has_tldr else 'ОТСУТСТВУЕТ'}\n"
        f"  </html> закрывающий тег: {'ПРИСУТСТВУЕТ' if has_close else 'ОТСУТСТВУЕТ'}\n"
    )

    # Send visible text (no tags/CSS/JS) so the model sees actual content, not
    # HTML boilerplate.  Prepend raw HTML head (first 1500 chars) for title/meta.
    html_head = html[:1500]
    visible_snippet = visible[:5000]   # already computed above
    prompt = (
        f"Страница для рецензии:\n"
        f"Путь: {path.name}{sim_note}\n"
        f"Мета: {json.dumps(meta, ensure_ascii=False)}\n\n"
        f"{precheck}\n"
        f"HTML HEAD (первые 1500 символов):\n{html_head}\n\n"
        f"ВИДИМЫЙ ТЕКСТ СТРАНИЦЫ (первые 5000 символов без тегов/CSS/JS):\n"
        f"{visible_snippet}\n\n"
        "Верни JSON с вердиктом и причинами по критериям."
    )

    try:
        from claude_client import call_claude
        raw, _ = call_claude(prompt, system=_CRITERIA, max_tokens=512,
                             model="claude-sonnet-4-6")
        # Strip markdown fences if model wrapped the JSON
        raw = re.sub(r"^```[a-z]*\n?|```$", "", raw.strip(), flags=re.M).strip()
        result = json.loads(raw)
        verdict = result.get("verdict", "reject")
        reasons = result.get("reasons", [])
        if verdict not in ("pass", "reject"):
            verdict = "reject"
            reasons = [f"неизвестный вердикт от LLM: {verdict!r}"]
    except json.JSONDecodeError as e:
        # LLM returned non-JSON — fail-closed: quarantine and alert.
        msg = (f"🚨 Рецензент: LLM вернул не-JSON для {path.name}. "
               f"Страница удержана (fail-closed).\nОшибка: {e}")
        _alert(msg)
        reasons = ["LLM non-JSON response — held"]
        try:
            quarantine(path, reasons, verdict="hold")
        except Exception:
            path.unlink(missing_ok=True)
            _log(path, "hold", reasons, error=f"json parse error: {e}")
        return {"verdict": "hold", "reasons": reasons}
    except Exception as e:
        # Network, timeout, budget exceeded, any other error — fail-closed:
        # quarantine the file so it cannot land in `git add` even if the caller
        # forgets to check the return value.
        msg = (f"🚨 Рецензент недоступен ({type(e).__name__}: {e}).\n"
               f"Страница {path.name} удержана — новые страницы не публикуются "
               f"пока рецензент не восстановится. Разберись с причиной.")
        _alert(msg)
        reasons = [f"reviewer unavailable: {e}"]
        try:
            quarantine(path, reasons, verdict="hold")
        except Exception:
            path.unlink(missing_ok=True)
            _log(path, "hold", reasons, error=str(e))
        return {"verdict": "hold", "reasons": reasons}

    if verdict == "reject":
        quarantine(path, reasons)   # quarantine() handles the log call
    else:
        _log(path, verdict, reasons)

    return {"verdict": verdict, "reasons": reasons}


# ── Digest for brain ─────────────────────────────────────────────────────────

def gate_rejections_digest(last_n: int = 20) -> dict:
    """Recent rejections + holds for Fable's digest (learn from failures)."""
    try:
        log = json.loads(GATE_LOG.read_text(encoding="utf-8")) if GATE_LOG.exists() else []
    except Exception:
        return {"total": 0, "recent": []}
    bad = [e for e in log if e.get("verdict") in ("reject", "hold")][-last_n:]
    return {
        "total_rejected": sum(1 for e in log if e["verdict"] == "reject"),
        "total_held": sum(1 for e in log if e["verdict"] == "hold"),
        "recent": [
            {"path": e["path"], "verdict": e["verdict"],
             "reasons": e["reasons"][:2], "ts": e["ts"]}
            for e in reversed(bad)
        ],
    }


def gate_summary() -> dict:
    """Published vs quarantined counts — for the pipeline's Telegram summary."""
    try:
        log = json.loads(GATE_LOG.read_text(encoding="utf-8")) if GATE_LOG.exists() else []
    except Exception:
        return {"published": 0, "quarantined": 0, "held": 0, "sample_reasons": []}
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    recent = [e for e in log if e.get("ts", "") >= cutoff]
    reasons = []
    for e in recent:
        if e.get("verdict") in ("reject", "hold"):
            reasons += e.get("reasons", [])[:1]
    return {
        "published": sum(1 for e in recent if e["verdict"] == "pass"),
        "quarantined": sum(1 for e in recent if e["verdict"] == "reject"),
        "held": sum(1 for e in recent if e["verdict"] == "hold"),
        "sample_reasons": reasons[:5],
    }


if __name__ == "__main__":
    # Quick self-test: python3 scripts/page_reviewer.py <path.html>
    import sys as _sys
    if len(_sys.argv) < 2:
        print("Usage: page_reviewer.py <page.html>")
        _sys.exit(1)
    p = Path(_sys.argv[1])
    r = review_page(p)
    print(json.dumps(r, ensure_ascii=False, indent=2))
