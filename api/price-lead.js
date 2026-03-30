/**
 * POST /api/price-lead — захват контакта при скачивании прайса.
 *
 * Env (Vercel → Settings → Environment Variables):
 *   TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (или TELEGRAM_LEADS_CHAT_ID) — уведомление в Telegram
 *   GOOGLE_APPS_SCRIPT_LEAD_URL (или PRICE_LEAD_WEBHOOK_URL) — URL веб-приложения Google Apps Script
 *
 * Тело JSON: { contact, lang?, format?, currency?, vat?, page? }
 *
 * Пример Google Apps Script (развернуть как веб-приложие, доступ: «Все»):
 *   function doPost(e) {
 *     const sh = SpreadsheetApp.openById('SHEET_ID').getSheetByName('Leads');
 *     const d = JSON.parse(e.postData.contents);
 *     sh.appendRow([new Date(), d.contact, d.lang, d.format, d.currency, d.page || '']);
 *     return ContentService.createTextOutput(JSON.stringify({ok:true})).setMimeType(ContentService.MimeType.JSON);
 *   }
 */

function parseBody(req) {
  const raw = req.body;
  if (raw == null) return {};
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw);
    } catch {
      return {};
    }
  }
  if (typeof raw === 'object') return raw;
  return {};
}

export default async function handler(req, res) {
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    return res.status(204).end();
  }

  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST, OPTIONS');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');

  try {
    const body = parseBody(req);
    const contact = String(body.contact || '')
      .trim()
      .replace(/[\u0000-\u001F\u007F]/g, '')
      .slice(0, 200);

    if (!contact || contact.length < 4) {
      return res.status(400).json({ error: 'contact_too_short' });
    }

    const payload = {
      ts: new Date().toISOString(),
      contact,
      lang: String(body.lang || '').slice(0, 8),
      format: String(body.format || '').slice(0, 12),
      currency: String(body.currency || '').slice(0, 8),
      vat: body.vat != null ? String(body.vat).slice(0, 8) : '',
      page: String(body.page || '').slice(0, 500),
      ua: String(req.headers['user-agent'] || '').slice(0, 400),
    };

    const tgToken = process.env.TELEGRAM_BOT_TOKEN;
    const tgChat = process.env.TELEGRAM_CHAT_ID || process.env.TELEGRAM_LEADS_CHAT_ID;
    const sheetUrl = process.env.GOOGLE_APPS_SCRIPT_LEAD_URL || process.env.PRICE_LEAD_WEBHOOK_URL;

    const tasks = [];

    if (tgToken && tgChat) {
      const text =
        `📥 Прайс-лист (лид)\n` +
        `Контакт: ${contact}\n` +
        `Язык: ${payload.lang || '—'} · Формат: ${payload.format || '—'} · Валюта: ${payload.currency || '—'}\n` +
        (payload.page ? `Страница: ${payload.page}\n` : '') +
        `Время: ${payload.ts}`;

      tasks.push(
        fetch(`https://api.telegram.org/bot${tgToken}/sendMessage`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chat_id: tgChat,
            text: text.slice(0, 4090),
            disable_web_page_preview: true,
          }),
        }).then((r) => (r.ok ? null : r.text().catch(() => '')))
      );
    }

    if (sheetUrl) {
      tasks.push(
        fetch(sheetUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }).then((r) => (r.ok ? null : r.text().catch(() => '')))
      );
    }

    await Promise.all(tasks);

    const saved = Boolean((tgToken && tgChat) || sheetUrl);
    return res.status(200).json({ ok: true, saved });
  } catch {
    return res.status(500).json({ error: 'server_error' });
  }
}
