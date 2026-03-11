#!/usr/bin/env python3
"""
Generate a daily SEO report via Claude API and send it by email.
Env: CLAUDE_API_KEY, REPORT_EMAIL (default: 995620@gmail.com)
"""

import json
import os
import re
import smtplib
import sys
import urllib.request
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, os.path.dirname(__file__))
from seo_db import get_conn, init_db
from claude_client import call_claude_cheap

REPORT_EMAIL   = os.environ.get("REPORT_EMAIL", "995620@gmail.com")
SMTP_HOST      = os.environ.get("SMTP_HOST", "")
SMTP_PORT      = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER      = os.environ.get("SMTP_USER", "")
SMTP_PASS      = os.environ.get("SMTP_PASS", "")
FROM_EMAIL     = os.environ.get("FROM_EMAIL", "noreply@pepperoni.tatar")


def call_claude(prompt: str) -> str:
    try:
        text, _ = call_claude_cheap(
            prompt,
            system=(
                "Ты SEO-аналитик сайта pepperoni.tatar. "
                "Пишешь краткие, структурированные ежедневные отчёты на русском языке. "
                "Выделяй главное, давай конкретные рекомендации."
            ),
            max_tokens=2048,
        )
        return text
    except Exception as e:
        return f"[Claude недоступен: {e}]\n\n{prompt}"


def gather_stats() -> dict:
    conn = get_conn()
    stats = {}

    # GSC stats last 7 days
    row = conn.execute("""
        SELECT SUM(clicks) as clicks, SUM(impressions) as impr, AVG(ctr) as ctr, AVG(position) as pos
        FROM gsc_queries WHERE date >= date('now', '-7 days')
    """).fetchone()
    stats["gsc_7d"] = dict(row) if row else {}

    # Top growing queries (pos improved)
    top_queries = conn.execute("""
        SELECT query, AVG(position) as pos, SUM(impressions) as impr
        FROM gsc_queries WHERE date >= date('now', '-7 days')
        GROUP BY query ORDER BY impr DESC LIMIT 10
    """).fetchall()
    stats["top_queries"] = [dict(r) for r in top_queries]

    # Opportunities summary
    opps = conn.execute("""
        SELECT type, COUNT(*) as cnt FROM opportunities
        WHERE status IN ('new','in_progress')
        GROUP BY type
    """).fetchall()
    stats["open_opportunities"] = {r["type"]: r["cnt"] for r in opps}

    # Content generated today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    gen = conn.execute(
        "SELECT COUNT(*) as cnt, SUM(tokens_used) as tokens FROM generated_content WHERE created_at LIKE ?",
        (f"{today}%",),
    ).fetchone()
    stats["generated_today"] = dict(gen) if gen else {}

    # Yandex stats last 7 days
    ya_row = conn.execute("""
        SELECT SUM(impressions) as impr, AVG(position) as pos
        FROM yandex_queries WHERE date >= date('now', '-7 days')
    """).fetchone()
    stats["yandex_7d"] = dict(ya_row) if ya_row else {}

    conn.close()
    return stats


def build_prompt(stats: dict, date_str: str) -> str:
    top_q = "\n".join(
        f"  {i+1}. «{r['query']}» — pos {r['pos']:.1f}, {r['impr']} показов"
        for i, r in enumerate(stats.get("top_queries", []))
    )
    opps_str = ", ".join(f"{k}: {v}" for k, v in stats.get("open_opportunities", {}).items())
    gsc = stats.get("gsc_7d", {})
    ya  = stats.get("yandex_7d", {})
    gen = stats.get("generated_today", {})

    gsc_clicks = gsc.get('clicks') or 0
    gsc_impr   = gsc.get('impr')   or 0
    gsc_ctr    = gsc.get('ctr')    or 0
    gsc_pos    = gsc.get('pos')    or 0
    ya_impr    = ya.get('impr')    or 0
    ya_pos     = ya.get('pos')     or 0

    return f"""Дата отчёта: {date_str}

=== GOOGLE SEARCH CONSOLE (7 дней) ===
Клики: {gsc_clicks:.0f}
Показы: {gsc_impr:.0f}
CTR: {gsc_ctr * 100:.2f}%
Средняя позиция: {gsc_pos:.1f}

=== ЯНДЕКС (7 дней) ===
Показы: {ya_impr:.0f}
Средняя позиция: {ya_pos:.1f}

=== ТОП ЗАПРОСЫ (по показам) ===
{top_q if top_q else 'нет данных'}

=== ОТКРЫТЫЕ ВОЗМОЖНОСТИ ===
{opps_str if opps_str else 'нет новых'}

=== СГЕНЕРИРОВАНО СЕГОДНЯ ===
Контент: {gen.get('cnt', 0)} единиц, токенов Claude: {gen.get('tokens', 0) or 0}

---
Напиши краткий отчёт (3-5 абзацев) с:
1. Общей оценкой недели
2. Топ-3 возможности для роста
3. Конкретными действиями на сегодня (максимум 3)
Формат — Markdown."""


def send_email(subject: str, body_md: str, date_str: str):
    if not SMTP_HOST or not SMTP_USER:
        # Fallback: print to stdout (GitHub Actions will show in logs)
        print(f"\n{'='*60}")
        print(f"📧 DAILY SEO REPORT — {date_str}")
        print('='*60)
        print(body_md)
        print('='*60)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = FROM_EMAIL
    msg["To"]      = REPORT_EMAIL

    # Plain text
    msg.attach(MIMEText(body_md, "plain", "utf-8"))

    # Simple HTML version
    html_body = "<html><body><pre style='font-family:monospace;font-size:14px'>" + body_md + "</pre></body></html>"
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, [REPORT_EMAIL], msg.as_string())
        print(f"✅ Report sent to {REPORT_EMAIL}")
    except Exception as ex:
        print(f"⚠️  Email failed: {ex}", file=sys.stderr)
        print(body_md)


def main():
    init_db()
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    print(f"📊 Gathering stats for {date_str} …")
    stats = gather_stats()

    print("🤖 Generating report with Claude …")
    prompt = build_prompt(stats, date_str)
    report_text = call_claude(prompt)

    # Save to DB
    conn = get_conn()
    conn.execute(
        "INSERT INTO daily_reports (created_at, report_date, summary_md, email_sent) VALUES (?,?,?,?)",
        (now.isoformat(), date_str, report_text, 1),
    )
    conn.commit()
    conn.close()

    subject = f"🍕 pepperoni.tatar SEO отчёт {date_str}"
    send_email(subject, report_text, date_str)


if __name__ == "__main__":
    main()
