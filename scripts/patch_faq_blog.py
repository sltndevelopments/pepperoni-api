#!/usr/bin/env python3
"""
Add FAQPage Schema + visible FAQ section to existing blog articles
that were created before FAQ generation was added to prompts.

Uses Claude API to generate relevant Q&A based on actual article content.
Run: CLAUDE_API_KEY=... python scripts/patch_faq_blog.py
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

PUBLIC     = Path(__file__).parent.parent / "public"
API_KEY    = os.environ.get("CLAUDE_API_KEY", "")
MODEL      = "claude-sonnet-4-5"
MAX_TOKENS = 800


def call_claude(system: str, prompt: str) -> str:
    if not API_KEY:
        raise RuntimeError("CLAUDE_API_KEY not set")
    body = json.dumps({
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                data = json.loads(r.read())
                return data["content"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            if e.code == 529 or e.code == 429:
                time.sleep(30)
                continue
            raise
    raise RuntimeError("Claude API failed after 3 attempts")


def extract_text(html: str, max_chars: int = 3000) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>",  "", text, flags=re.DOTALL)
    text = re.sub(r"<nav[^>]*>.*?</nav>",       "", text, flags=re.DOTALL)
    text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def generate_faq(article_text: str, lang: str) -> list[tuple[str, str]]:
    if lang == "ru":
        system = (
            "Ты SEO-эксперт. Генерируешь FAQ для статей блога о халяль мясной продукции. "
            "Вопросы должны быть реальными — те, что задают покупатели B2B, HoReCa, оптовики. "
            "Отвечай ТОЛЬКО валидным JSON, без объяснений."
        )
        prompt = (
            f"На основе этой статьи создай 4 вопроса и ответа для FAQ блока.\n\n"
            f"Статья:\n{article_text}\n\n"
            f"Верни строго JSON массив: "
            f'[{{"q": "вопрос", "a": "ответ 1-3 предложения"}}, ...]\n'
            f"Вопросы начинаются с: Как, Где, Что, Можно ли, Сколько, Чем, Почему."
        )
    else:
        system = (
            "You are an SEO expert. You generate FAQ sections for blog articles about halal meat products. "
            "Questions must be real — what B2B buyers, HoReCa operators, and wholesalers actually ask. "
            "Reply ONLY with valid JSON, no explanations."
        )
        prompt = (
            f"Based on this article, create 4 questions and answers for a FAQ block.\n\n"
            f"Article:\n{article_text}\n\n"
            f"Return strictly a JSON array: "
            f'[{{"q": "question", "a": "answer 1-3 sentences"}}, ...]\n'
            f"Questions start with: How, What, Where, Can, Which, Why, How much."
        )

    raw = call_claude(system, prompt)
    # Extract JSON from response
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON array in response: {raw[:200]}")
    items = json.loads(m.group())
    return [(item["q"], item["a"]) for item in items if "q" in item and "a" in item]


def build_faq_schema(qa: list[tuple[str, str]]) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in qa
        ],
    }
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(schema, ensure_ascii=False, indent=2)
        + "\n</script>"
    )


def build_faq_html(qa: list[tuple[str, str]], lang: str) -> str:
    heading = "Часто задаваемые вопросы" if lang == "ru" else "Frequently Asked Questions"
    items = "\n".join(
        f'<details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    )
    return (
        f'\n<section class="faq-section">'
        f'<h2>{heading}</h2>\n{items}\n</section>\n'
    )


def patch_article(path: Path, lang: str) -> bool:
    html = path.read_text(encoding="utf-8")

    if "FAQPage" in html:
        return False  # already done

    text = extract_text(html)
    if len(text) < 200:
        print(f"    ⚠️  Too short, skipping: {path.name}")
        return False

    try:
        qa = generate_faq(text, lang)
    except Exception as e:
        print(f"    ❌ Claude error: {e}")
        return False

    if not qa:
        print(f"    ⚠️  No FAQ generated for {path.name}")
        return False

    # Inject schema into <head>
    schema_block = build_faq_schema(qa)
    html = html.replace("</head>", schema_block + "\n</head>", 1)

    # Inject visible FAQ section before CTA block or before </main>
    faq_html = build_faq_html(qa, lang)
    if '<div class="cta-block">' in html:
        html = html.replace('<div class="cta-block">', faq_html + '<div class="cta-block">', 1)
    elif "</main>" in html:
        html = html.replace("</main>", faq_html + "</main>", 1)

    # Add FAQ CSS if not present
    if ".faq-section" not in html:
        faq_css = """
.faq-section{max-width:800px;margin:2rem auto;padding:0 20px}
.faq-section h2{font-size:1.4rem;color:var(--green,#1b7a3d);margin-bottom:1rem}
.faq-section details{border:1px solid var(--border,#e5e5e5);border-radius:8px;margin-bottom:.6rem;padding:.8rem 1rem}
.faq-section details[open]{border-color:var(--green,#1b7a3d)}
.faq-section summary{font-weight:600;cursor:pointer;list-style:none;color:var(--text,#1a1a1a)}
.faq-section summary::after{content:' +';color:var(--green,#1b7a3d)}
.faq-section details[open] summary::after{content:' −'}
.faq-section p{margin-top:.6rem;color:var(--muted,#555);line-height:1.6}
"""
        html = html.replace("</style>", faq_css + "</style>", 1)

    path.write_text(html, encoding="utf-8")
    return True


def main():
    if not API_KEY:
        print("❌ CLAUDE_API_KEY not set")
        sys.exit(1)

    ru_files = [f for f in sorted((PUBLIC / "blog").glob("*.html")) if "FAQPage" not in f.read_text()]
    en_files = [f for f in sorted((PUBLIC / "en" / "blog").glob("*.html")) if "FAQPage" not in f.read_text()]

    print(f"📝 Articles needing FAQ: {len(ru_files)} RU + {len(en_files)} EN")

    total = 0
    for path in ru_files:
        print(f"  [RU] {path.name[:50]}", end=" ... ", flush=True)
        ok = patch_article(path, "ru")
        print("✅" if ok else "skip")
        if ok:
            total += 1
        time.sleep(1.5)

    for path in en_files:
        print(f"  [EN] {path.name[:50]}", end=" ... ", flush=True)
        ok = patch_article(path, "en")
        print("✅" if ok else "skip")
        if ok:
            total += 1
        time.sleep(1.5)

    print(f"\n🎉 Done: {total} articles patched with FAQ Schema + HTML block")


if __name__ == "__main__":
    main()
