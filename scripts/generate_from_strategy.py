#!/usr/bin/env python3
"""
Strategy executor (HANDS) — generates blog articles and Private Label / OEM /
White Label pages from the brain's data/strategy.json directive, using cheap
DeepSeek Flash. Idempotent: skips pages that already exist on disk.

Run frequently (e.g. hourly) from seo-worker.sh. Safe no-op if no strategy.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from claude_client import call_claude, CONTENT_MODEL
from blog_template import BLOG_ARTICLE_OUTPUT_RULES_RU, wrap_generated_blog

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
STRATEGY_FILE = DATA / "strategy.json"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
YEAR = datetime.now().year

MAX_BLOG = int(os.environ.get("MAX_STRATEGY_BLOG", "4"))
MAX_PL   = int(os.environ.get("MAX_STRATEGY_PL", "4"))
MAX_TOKENS = int(os.environ.get("STRATEGY_MAX_TOKENS", "7000"))

# Canonical contacts (single source of truth; never invent others)
PHONE_DISPLAY = "+7 987 217-02-02"
PHONE_TEL     = "+79872170202"
EMAIL         = "info@kazandelikates.tatar"
ADDR_RU       = "г. Казань, ул. Аграрная, 2, оф. 7"
CONTACTS_RULE = (
    f"Контакты используй СТРОГО такие: телефон {PHONE_DISPLAY} (tel:{PHONE_TEL}), "
    f"email {EMAIL}, адрес {ADDR_RU}. НИКОГДА не выдумывай 8-800 и другие адреса/email."
)


def slugify(text: str) -> str:
    t = re.sub(r"[^a-z0-9\-]+", "-", text.lower())
    return re.sub(r"-+", "-", t).strip("-")[:80]


def clean_html(html: str) -> str:
    html = re.sub(r"^```html?\s*\n?", "", html.strip(), flags=re.IGNORECASE)
    html = re.sub(r"\n?```\s*$", "", html.strip())
    return html.strip()


def load_strategy() -> dict:
    try:
        return json.loads(STRATEGY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


_BLOG_EXISTING_CACHE: list[dict] | None = None


def _blog_existing() -> list[dict]:
    global _BLOG_EXISTING_CACHE
    if _BLOG_EXISTING_CACHE is None:
        from blog_topic_dedup import scan_blog
        _BLOG_EXISTING_CACHE = scan_blog("ru")
    return _BLOG_EXISTING_CACHE


def prep_blog(topic: dict) -> dict | None:
    """Build a batch-ready request for one blog topic (None → skip)."""
    slug = topic.get("slug") or slugify(topic.get("title_ru", ""))
    if not slug:
        return None
    out = PUBLIC / "blog" / f"{slug}.html"
    if out.exists():
        return None
    title = topic.get("title_ru", slug)
    # Near-duplicate gate (normalized slug / commercial key / title overlap)
    from blog_topic_dedup import is_near_duplicate
    is_dup, reason = is_near_duplicate(slug, title, _blog_existing())
    if is_dup:
        print(f"  ⏭ blog skip near-dup /blog/{slug}: {reason}")
        _mark_queue(slug, "skipped_dup")
        return None
    intent = topic.get("intent", "информационный")
    from brand_system import brand_block
    system = brand_block("ru") + "\n\n" + (
        "Ты эксперт мясной/пищевой промышленности и SEO-автор для pepperoni.tatar "
        "(Казанские Деликатесы, халяль производитель). Пишешь экспертно, без воды, "
        "без упоминания свинины."
    )
    prompt = f"""Напиши {intent} SEO-статью: «{title}».
{BLOG_ARTICLE_OUTPUT_RULES_RU.format(date=TODAY)}

Требования к содержанию:
- canonical /blog/{slug}
- 700-900 слов, 4× H2, заключение с cta-block
- Контекстные ссылки: /pepperoni, /pepperoni-optom, /private-label
- CTA: tel:{PHONE_TEL}, mailto:{EMAIL}
- {CONTACTS_RULE}
- НЕ упоминать свинину"""
    return {"out": out, "label": f"blog: /blog/{slug}", "query": title,
            "system": system, "prompt": prompt}


def prep_pl(topic: dict) -> dict | None:
    """Build a batch-ready request for one PL/OEM topic (None → skip)."""
    lang = topic.get("lang", "ru")
    slug = topic.get("slug") or slugify(topic.get("title", ""))
    if not slug:
        return None
    out_dir = PUBLIC / ("private-label" if lang == "ru" else f"{lang}/private-label")
    out = out_dir / f"{slug}.html"
    if out.exists():
        return None
    title = topic.get("title", slug)
    angle = topic.get("angle", "")
    from brand_system import brand_block
    if lang == "ru":
        system = brand_block("ru") + "\n\n" + (
            "Ты B2B-эксперт по контрактному производству (Private Label / СТМ / OEM) "
            "халяль мясных изделий и выпечки для pepperoni.tatar (Казанские Деликатесы). "
            "Пишешь убедительно для закупщиков сетей, дистрибьюторов, маркетплейсов."
        )
        prompt = f"""Напиши коммерческую посадочную страницу по услуге Private Label / СТМ / OEM: «{title}».
Угол: {angle}
Верни ТОЛЬКО валидный HTML5 (lang="ru"), без объяснений.
Требования:
- <head>: <title> (до 65 симв.), <meta description> (до 160), canonical /private-label/{slug}
- Schema.org Service + Organization JSON-LD
- Bootstrap 5 CDN, <h1> с услугой
- ОБЯЗАТЕЛЬНО первым видимым блоком после <h1> вставь прямой ответ закупщику:
  <div class="tldr-answer"> … 2-3 предложения: что это за продукт/услуга, для кого, ключевые условия (MOQ, сроки, халяль-сертификат). Это первые ~150 слов страницы. …</div>
- Секции: что такое СТМ/OEM, что можем (колбасы, мясо, ВСЯ выпечка), этапы запуска, MOQ/сроки, сертификаты (Халяль ДУМ РТ #614A/2024, HACCP, ISO 22000:2018, ТР ТС 021/2011), FAQ (5), CTA-форма
- ОБЯЗАТЕЛЬНА секция «Сценарий применения»: как покупатель использует сам ПРОДУКТ в своём процессе (например для котлет — жарка на гриле/контактном гриле, роллерный гриль, конвектомат, слайсер; для сосисок — роллер, гриль, фритюр; для казылыка — нарезка слайсером, подача, хранение). Описывай применение продукта у клиента, НЕ только запуск СТМ.
- Кнопка «Получить расчёт СТМ» → tel:{PHONE_TEL}
- Контекстные ссылки: /private-label, /pepperoni-optom, /dlya-distributorov
- Футер: © 2022–{YEAR} Казанские Деликатесы, {ADDR_RU}, {PHONE_DISPLAY}
- {CONTACTS_RULE}
- ЗАПРЕЩЕНО: анонимные «кейсы партнёров» и любые непроверяемые цифры результата (проценты экономии, «топ продаж», сроки вывода, число точек), если нет названия компании и подтверждения. Не выдумывай кейсы, отзывы, рейтинги, награды. Вместо кейсов — фактические условия сотрудничества.
- НЕ упоминать свинину, 450-650 слов
- ОБЯЗАТЕЛЬНО закончи документ тегами </body></html>; сократи FAQ, если не хватает лимита"""
    else:
        system = brand_block("en") + "\n\n" + (
            "You are a B2B expert in contract manufacturing (Private Label / White "
            "Label / OEM) of HALAL meat products and bakery for pepperoni.tatar "
            "(Kazan Delicacies). Write persuasively for export buyers (GCC, CIS)."
        )
        prompt = f"""Write a commercial landing page for the Private Label / White Label / OEM service: "{title}".
Angle: {angle}
Return ONLY valid HTML5 (lang="{lang}"), no explanations.
Requirements:
- <head>: <title> (<=65 chars), <meta description> (<=160), canonical /{lang}/private-label/{slug}
- Schema.org Service + Organization JSON-LD
- Bootstrap 5 CDN, <h1>, sections: what is OEM/White Label, capabilities (sausages, meat, ALL bakery), launch steps, MOQ/lead time, certifications (Halal DUM RT, HACCP, ISO 22000), cases, FAQ (5), CTA form
- "Request OEM quote" button → tel:{PHONE_TEL}
- Footer with contacts: {PHONE_DISPLAY}, {EMAIL}
- Use EXACTLY these contacts, never invent others. No pork mentions. 450-650 words
- You MUST finish with </body></html>; shorten the FAQ if the token limit is near."""
    return {"out": out, "label": f"PL/OEM [{lang}]: /private-label/{slug}",
            "query": title,
            "system": system, "prompt": prompt}


def _mark_queue(slug: str, status: str) -> None:
    """Mark a blog_topic_queue entry done/skipped_dup after executor runs."""
    qpath = DATA / "blog_topic_queue.json"
    if not qpath.exists() or not slug:
        return
    try:
        q = json.loads(qpath.read_text(encoding="utf-8"))
        changed = False
        for t in q.get("topics") or []:
            if t.get("slug") == slug and t.get("status") == "pending":
                t["status"] = status
                t["updated_at"] = TODAY
                changed = True
        if changed:
            q["updated_at"] = datetime.now(timezone.utc).isoformat()
            qpath.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    except Exception as e:
        print(f"  ⚠️  queue update {slug}: {e}", file=sys.stderr)


def _write_page(prep: dict, html: str) -> bool:
    """Write page and run the quality gate synchronously. Returns True only if published.

    Temp-file flow: write to data/tmp/ → reviewer → on pass move to public/;
    on fail/crash delete temp so public/ is never polluted with bad content.
    """
    import shutil as _shutil
    html = clean_html(html)
    final_out: Path = prep["out"]
    if "/blog/" in final_out.as_posix():
        lang = "en" if "/en/blog/" in final_out.as_posix() else "ru"
        html = wrap_generated_blog(lang, final_out.stem, html, TODAY)
    elif "<html" not in html.lower():
        return False
    tmp_dir = ROOT / "data" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / final_out.name
    tmp_path.write_text(html, encoding="utf-8")

    # ── Quality gate (synchronous — before git add sees this file) ────────────
    try:
        import page_reviewer
        review = page_reviewer.review_page(
            tmp_path,
            meta={"label": prep.get("label", ""), "action": prep.get("action", "")},
        )
    except Exception as _rev_exc:
        # Reviewer module crashed — fail-closed: delete temp, never publish.
        tmp_path.unlink(missing_ok=True)
        try:
            import page_reviewer as _pr
            _pr._alert(f"🚨 Рецензент упал (strategy): {_rev_exc}\n"
                       f"Страница {final_out.name} удержана.")
            _pr._log(tmp_path, "hold", [], error=str(_rev_exc))
        except Exception:
            pass
        print(f"  🚨 {prep['label']}: рецензент упал — удержан", file=sys.stderr)
        return False

    if review["verdict"] != "pass":
        # review_page() may have already quarantined the temp; ensure it's gone.
        tmp_path.unlink(missing_ok=True)
        reasons = "; ".join(review["reasons"][:2])
        print(f"  🚧 {prep['label']}: {review['verdict']} — {reasons}")
        return False

    # Gate passed — move to final public/ destination.
    final_out.parent.mkdir(parents=True, exist_ok=True)
    _shutil.move(str(tmp_path), str(final_out))
    try:
        from experiment_registry import start
        start(
            query=prep.get("query") or final_out.stem.replace("-", " "),
            page="/" + final_out.relative_to(PUBLIC).as_posix().removesuffix(".html"),
            hypothesis="Approved demand-backed page should gain commercial clicks or inquiries",
            change_type=f"new_{prep.get('action', 'page')}",
            baseline={"position": None, "impressions": 0, "clicks": 0, "inquiries": 0},
        )
    except Exception as e:
        # Publication is already gated and approved; registry failure is visible
        # but must not corrupt or silently delete the page.
        print(f"  ⚠️ experiment registry: {e}", file=sys.stderr)

    print(f"  ✓ {prep['label']}")
    if prep.get("action") == "blog_post":
        _mark_queue(final_out.stem, "done")
    return True


def _generate_one(prep: dict) -> str:
    """Synchronous single-page generation — used for owner-approved rebuilds."""
    try:
        html, _ = call_claude(prep["prompt"], system=prep.get("system", ""),
                              max_tokens=MAX_TOKENS, effort="medium",
                              model=CONTENT_MODEL)
        return html
    except Exception as e:
        print(f"  ✗ _generate_one {prep.get('label','?')}: {e}", file=sys.stderr)
        return ""


def _approval_key(prep: dict) -> str:
    """Stable approval key derived from the output path."""
    label = prep.get("label", "")
    action = prep.get("action", "new_page")
    slug = re.sub(r"[^a-z0-9-]", "", str(prep["out"].stem).lower())[:60]
    return f"{action}:{slug}"


def main():
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")):
        print("❌ ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1
    strat = load_strategy()
    if not strat:
        print("ℹ️  No strategy.json — nothing to execute.")
        return 0
    try:
        from strategy_control import execution_allowed
        allowed, blockers = execution_allowed()
        if not allowed:
            print("⏸ Strategy executor blocked: " + "; ".join(blockers))
            return 0
    except Exception as e:
        print(f"⏸ Strategy executor fail-closed: control plane unavailable ({e})")
        return 0

    print(f"🛠  Executing strategy ({strat.get('generated_at','?')})")

    # Pages are gated automatically by page_reviewer (fail-closed) inside
    # _write_page(). No human approval step needed.
    preps = []
    for t in (strat.get("new_blog_topics") or [])[:MAX_BLOG]:
        try:
            p = prep_blog(t)
            if p:
                p["action"] = "blog_post"
                preps.append(p)
        except Exception as e:
            print(f"  ✗ blog prep error: {e}", file=sys.stderr)
    for t in (strat.get("pl_oem_topics") or [])[:MAX_PL]:
        try:
            p = prep_pl(t)
            if p:
                p["action"] = "pl_page"
                preps.append(p)
        except Exception as e:
            print(f"  ✗ PL prep error: {e}", file=sys.stderr)

    # Every new page requires explicit owner approval before any LLM spend.
    from approvals import request_new_page
    approved_preps = []
    for prep in preps[:3]:
        key = _approval_key(prep)
        prep["approval_key"] = key
        status = request_new_page(
            key=key,
            title=prep["label"],
            detail="Новая коммерческая/экспертная страница из outcome-очереди",
            action=prep.get("action", "new_page"),
            payload={"path": str(prep["out"].relative_to(ROOT))},
            requested_by="site-brain",
        )
        if status == "approved":
            approved_preps.append(prep)
        else:
            print(f"  ⏳ {prep['label']}: approval={status}")
    preps = approved_preps

    if not preps:
        print("✅ Strategy executor done: nothing new to generate")
        return 0

    made = 0
    quarantined = 0
    # Cron job, nobody waits → Batch API (−50%). Fall back to sync calls.
    use_batch = os.environ.get("WORKER_BATCH", "1") != "0" and len(preps) >= 2
    if use_batch:
        try:
            from claude_client import call_claude_batch
            items = [{"custom_id": f"w{i}", "prompt": p["prompt"],
                      "system": p["system"], "max_tokens": MAX_TOKENS,
                      "effort": "medium"}
                     for i, p in enumerate(preps)]
            out = call_claude_batch(items)
            for i, p in enumerate(preps):
                res = out.get(f"w{i}") or {}
                if res.get("ok"):
                    if _write_page(p, res["text"]):
                        made += 1
                        from approvals import mark_executed
                        mark_executed(p["approval_key"], success=True)
                    else:
                        quarantined += 1
                        from approvals import mark_executed
                        mark_executed(
                            p["approval_key"], success=False,
                            note="rejected or held by page gate",
                        )
                else:
                    print(f"  ✗ {p['label']}: {res.get('error','no result')}",
                          file=sys.stderr)
            print(f"✅ Strategy executor done (batch): {made} published, "
                  f"{quarantined} quarantined/held by gate")
            return 0
        except Exception as e:
            print(f"⚠️  batch failed ({e}) — falling back to sync", file=sys.stderr)

    for p in preps:
        try:
            html, _ = call_claude(p["prompt"], system=p["system"],
                                  max_tokens=MAX_TOKENS, effort="medium",
                                  model=CONTENT_MODEL)
            if _write_page(p, html):
                made += 1
                from approvals import mark_executed
                mark_executed(p["approval_key"], success=True)
            else:
                quarantined += 1
                from approvals import mark_executed
                mark_executed(
                    p["approval_key"], success=False,
                    note="rejected or held by page gate",
                )
        except Exception as e:
            print(f"  ✗ {p['label']}: {e}", file=sys.stderr)

    print(f"✅ Strategy executor done: {made} published, "
          f"{quarantined} quarantined/held by gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
