/**
 * Общие заголовки «свежесть данных» для API ответов.
 */

export function setDataHeaders(res) {
  const now = new Date();
  const dateVersion = now.toISOString().split('T')[0];
  res.setHeader('X-Data-Version', dateVersion);
  res.setHeader('X-Data-Source', 'Google Sheets');
  res.setHeader('X-Last-Sync', now.toISOString());
}
