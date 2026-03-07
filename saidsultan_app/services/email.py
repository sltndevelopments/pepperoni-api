"""
Отправка HTML-писем через SMTP.
"""
from typing import List

import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import get_settings


def _build_html_report(brand: str, scan_results: list, advice: List[str]) -> str:
    """Формирует HTML-отчёт для письма."""
    rows = ""
    for i, r in enumerate(scan_results, 1):
        status = "✅ Упоминание есть" if r.get("mentioned") else "❌ Нет упоминания"
        prompt = (r.get("prompt", "") or "")[:100]
        answer = (r.get("answer", "") or "")[:300]
        rows += f"""
        <tr>
            <td>{i}</td>
            <td>{status}</td>
            <td>{prompt}...</td>
            <td>{answer}...</td>
        </tr>
        """
    steps_html = "".join(f"<li>{s}</li>" for s in (advice or [])[:5])
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: system-ui, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1>Отчёт по видимости: {brand}</h1>
        <h2>Результаты сканирования ИИ</h2>
        <table style="width:100%; border-collapse: collapse;">
            <tr style="background: #333; color: #fff;">
                <th style="padding: 8px;">#</th>
                <th style="padding: 8px;">Статус</th>
                <th style="padding: 8px;">Промпт</th>
                <th style="padding: 8px;">Ответ ИИ</th>
            </tr>
            {rows}
        </table>
        <h2>Что делать (5 действий)</h2>
        <ol>{steps_html}</ol>
        <p style="color: #666; font-size: 12px;">Saidsultan AI Visibility Platform © 2026</p>
    </body>
    </html>
    """


async def send_report_email(brand: str, to_email: str, scan_results: list, advice: List[str]) -> None:
    """Отправляет HTML-отчёт на указанный email."""
    settings = get_settings()
    if not all([settings.smtp_host, settings.smtp_user, settings.smtp_password]):
        raise ValueError("SMTP не настроен. Задайте SMTP_HOST, SMTP_USER, SMTP_PASSWORD в .env")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Отчёт по видимости: {brand}"
    msg["From"] = settings.smtp_user
    msg["To"] = to_email

    html = _build_html_report(brand, scan_results, advice)
    msg.attach(MIMEText(html, "html", "utf-8"))

    use_tls = settings.smtp_port == 465
    start_tls = settings.smtp_port == 587
    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        use_tls=use_tls,
        start_tls=start_tls,
    )


async def send_lead_email(name: str, phone: str, brand: str = "") -> None:
    """Отправляет заявку на email администратора."""
    settings = get_settings()
    if not all([settings.smtp_host, settings.smtp_user, settings.smtp_password]):
        raise ValueError("SMTP не настроен. Задайте SMTP_HOST, SMTP_USER, SMTP_PASSWORD в .env")

    to_email = (settings.admin_email or "").strip() or settings.smtp_user
    if not to_email:
        raise ValueError("Укажите ADMIN_EMAIL или SMTP_USER в .env")

    body = f"Новая заявка с saidsultan.com\n\nИмя: {name}\nТелефон: {phone}\nБренд: {brand or '—'}\n"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Заявка: {name} — {brand or 'без бренда'}"
    msg["From"] = settings.smtp_user
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain", "utf-8"))

    use_tls = settings.smtp_port == 465
    start_tls = settings.smtp_port == 587
    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        use_tls=use_tls,
        start_tls=start_tls,
    )
