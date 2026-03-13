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

    # GSC stats previous 7 days (8-14 days ago) for WoW comparison
    row_prev = conn.execute("""
        SELECT SUM(clicks) as clicks, SUM(impressions) as impr, AVG(ctr) as ctr, AVG(position) as pos
        FROM gsc_queries WHERE date >= date('now', '-14 days') AND date < date('now', '-7 days')
    """).fetchone()
    stats["gsc_prev_7d"] = dict(row_prev) if row_prev else {}

    # Top queries by impressions last 7 days
    top_queries = conn.execute("""
        SELECT query, AVG(position) as pos, SUM(impressions) as impr, SUM(clicks) as clicks
        FROM gsc_queries WHERE date >= date('now', '-7 days')
        GROUP BY query ORDER BY impr DESC LIMIT 10
    """).fetchall()
    stats["top_queries"] = [dict(r) for r in top_queries]

    # Queries that improved position (week over week) — best growth
    improved = conn.execute("""
        SELECT cur.query,
               cur.pos  AS pos_now,
               prev.pos AS pos_prev,
               (prev.pos - cur.pos) AS improvement
        FROM (
            SELECT query, AVG(position) as pos
            FROM gsc_queries WHERE date >= date('now', '-7 days')
            GROUP BY query
        ) cur
        JOIN (
            SELECT query, AVG(position) as pos
            FROM gsc_queries WHERE date >= date('now', '-14 days') AND date < date('now', '-7 days')
            GROUP BY query
        ) prev ON cur.query = prev.query
        WHERE cur.pos < prev.pos
        ORDER BY improvement DESC LIMIT 5
    """).fetchall()
    stats["improved_queries"] = [dict(r) for r in improved]

    # Queries that dropped in position
    dropped = conn.execute("""
        SELECT cur.query,
               cur.pos  AS pos_now,
               prev.pos AS pos_prev,
               (cur.pos - prev.pos) AS drop_amount
        FROM (
            SELECT query, AVG(position) as pos
            FROM gsc_queries WHERE date >= date('now', '-7 days')
            GROUP BY query
        ) cur
        JOIN (
            SELECT query, AVG(position) as pos
            FROM gsc_queries WHERE date >= date('now', '-14 days') AND date < date('now', '-7 days')
            GROUP BY query
        ) prev ON cur.query = prev.query
        WHERE cur.pos > prev.pos
        ORDER BY drop_amount DESC LIMIT 5
    """).fetchall()
    stats["dropped_queries"] = [dict(r) for r in dropped]

    # Total unique pages indexed in GSC
    pages_count = conn.execute("""
        SELECT COUNT(DISTINCT page) as cnt FROM gsc_queries WHERE date >= date('now', '-7 days')
    """).fetchone()
    stats["pages_in_search"] = (pages_count["cnt"] if pages_count else 0) or 0

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
        SELECT SUM(impressions) as impr, AVG(position) as pos, SUM(clicks) as clicks
        FROM yandex_queries WHERE date >= date('now', '-7 days')
    """).fetchone()
    stats["yandex_7d"] = dict(ya_row) if ya_row else {}

    # Yandex previous 7 days
    ya_prev = conn.execute("""
        SELECT SUM(impressions) as impr, AVG(position) as pos, SUM(clicks) as clicks
        FROM yandex_queries WHERE date >= date('now', '-14 days') AND date < date('now', '-7 days')
    """).fetchone()
    stats["yandex_prev_7d"] = dict(ya_prev) if ya_prev else {}

    conn.close()
    return stats


def _wow(now_val, prev_val, pct=True) -> str:
    """Format week-over-week change as +12% or (нет данных)."""
    try:
        n = float(now_val or 0)
        p = float(prev_val or 0)
        if p == 0:
            return "(нет данных за прош. неделю)"
        delta = n - p
        if pct:
            pct_val = delta / p * 100
            sign = "+" if pct_val >= 0 else ""
            return f"{sign}{pct_val:.1f}%"
        sign = "+" if delta >= 0 else ""
        return f"{sign}{delta:.1f}"
    except Exception:
        return ""


def build_prompt(stats: dict, date_str: str) -> str:
    gsc      = stats.get("gsc_7d", {})
    gsc_prev = stats.get("gsc_prev_7d", {})
    ya       = stats.get("yandex_7d", {})
    ya_prev  = stats.get("yandex_prev_7d", {})
    gen      = stats.get("generated_today", {})

    gsc_clicks = gsc.get('clicks') or 0
    gsc_impr   = gsc.get('impr')   or 0
    gsc_ctr    = gsc.get('ctr')    or 0
    gsc_pos    = gsc.get('pos')    or 0
    ya_impr    = ya.get('impr')    or 0
    ya_clicks  = ya.get('clicks')  or 0
    ya_pos     = ya.get('pos')     or 0
    pages      = stats.get("pages_in_search", 0)

    top_q = "\n".join(
        f"  {i+1}. «{r['query']}» — поз. {r['pos']:.1f}, {r['impr']} показов, {r['clicks']} кликов"
        for i, r in enumerate(stats.get("top_queries", []))
    )

    improved_q = "\n".join(
        f"  ↑ «{r['query']}»: {r['pos_prev']:.1f} → {r['pos_now']:.1f} (+{r['improvement']:.1f})"
        for r in stats.get("improved_queries", [])
    )

    dropped_q = "\n".join(
        f"  ↓ «{r['query']}»: {r['pos_prev']:.1f} → {r['pos_now']:.1f} (-{r['drop_amount']:.1f})"
        for r in stats.get("dropped_queries", [])
    )

    opps_str = ", ".join(f"{k}: {v}" for k, v in stats.get("open_opportunities", {}).items())

    return f"""Дата отчёта: {date_str}

=== GOOGLE (последние 7 дней vs предыдущие 7) ===
Клики:          {gsc_clicks:.0f}  {_wow(gsc_clicks, gsc_prev.get('clicks'))}
Показы:         {gsc_impr:.0f}  {_wow(gsc_impr, gsc_prev.get('impr'))}
CTR:            {gsc_ctr * 100:.2f}%  {_wow(gsc_ctr, gsc_prev.get('ctr'))}
Средняя позиция:{gsc_pos:.1f}  {_wow(gsc_pos, gsc_prev.get('pos'), pct=False)} (чем меньше — тем лучше)
Страниц в поиске: {pages}

=== ЯНДЕКС (последние 7 дней vs предыдущие 7) ===
Клики:          {ya_clicks:.0f}  {_wow(ya_clicks, ya_prev.get('clicks'))}
Показы:         {ya_impr:.0f}  {_wow(ya_impr, ya_prev.get('impr'))}
Средняя позиция:{ya_pos:.1f}  {_wow(ya_pos, ya_prev.get('pos'), pct=False)} (чем меньше — тем лучше)

=== ТОП ЗАПРОСЫ (по показам, 7 дней) ===
{top_q if top_q else 'нет данных'}

=== ЗАПРОСЫ, КОТОРЫЕ ВЫРОСЛИ В ПОЗИЦИИ ===
{improved_q if improved_q else 'нет данных (нужно 2 недели истории)'}

=== ЗАПРОСЫ, КОТОРЫЕ УПАЛИ В ПОЗИЦИИ ===
{dropped_q if dropped_q else 'нет данных (нужно 2 недели истории)'}

=== ОТКРЫТЫЕ ВОЗМОЖНОСТИ ===
{opps_str if opps_str else 'нет новых'}

=== СГЕНЕРИРОВАНО СЕГОДНЯ ===
Контент: {gen.get('cnt', 0)} единиц, токенов Claude: {gen.get('tokens', 0) or 0}

---
На основе этих данных напиши структурированный отчёт на русском языке:

## 📈 Растёт ли сайт?
Сравни текущую неделю с прошлой: клики, показы, позиции. Дай однозначный вердикт: растём / стоим / падаем и почему.

## 🔑 Топ-3 возможности роста
Конкретные запросы или страницы, где можно улучшить результат.

## ⚠️ Что требует внимания
Запросы, которые упали. Что с ними делать.

## ✅ Действия на сегодня (максимум 3)
Конкретные, выполнимые задачи.

Формат — Markdown. Будь конкретен, используй цифры из данных выше."""


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

    subject = f"🍕 pepperoni.tatar | SEO Growth Digest {date_str}"
    send_email(subject, report_text, date_str)


if __name__ == "__main__":
    main()
