import ExcelJS from 'exceljs';

const PRODUCTS_URL = 'https://api.pepperoni.tatar/api/products';

const CUR_NAMES = {
  RUB: { ru: 'Рубль (₽)', en: 'Russian Ruble (₽)' },
  USD: { ru: 'Доллар ($)', en: 'US Dollar ($)' },
  KZT: { ru: 'Тенге (₸)', en: 'Kazakhstani Tenge (₸)' },
  UZS: { ru: 'Сум', en: 'Uzbekistani Som' },
  KGS: { ru: 'Сом', en: 'Kyrgyzstani Som' },
  BYN: { ru: 'Бел. рубль (Br)', en: 'Belarusian Ruble (Br)' },
  AZN: { ru: 'Манат (₼)', en: 'Azerbaijani Manat (₼)' },
};

function getPrice(p, currency, withVAT) {
  if (currency === 'RUB') {
    return withVAT
      ? parseFloat(p.offers?.price || 0)
      : parseFloat(p.offers?.priceExclVAT || 0);
  }
  return p.offers?.exportPrices?.[currency] || 0;
}

function generateCSV(products, lang, currency, withVAT) {
  const isEn = lang === 'en';
  const curLabel = CUR_NAMES[currency]?.[lang] || currency;
  const vatLabel = currency === 'RUB'
    ? (withVAT ? (isEn ? 'incl. VAT' : 'с НДС') : (isEn ? 'excl. VAT' : 'без НДС'))
    : (isEn ? 'excl. VAT' : 'без НДС');

  const headers = isEn
    ? ['SKU', 'Name', 'Original Name (RU)', 'Section', 'Category', 'Weight', `Price ${currency} (${vatLabel})`, 'Price/Unit', 'Price/Box', 'Qty/Box', 'Shelf Life', 'Storage', 'HS Code', 'Meat Type', 'Certification']
    : ['Артикул', 'Название', 'Раздел', 'Категория', 'Вес', `Цена ${curLabel} (${vatLabel})`, 'Цена/шт', 'Цена/кор', 'Кол/кор', 'Срок годности', 'Хранение', 'ТН ВЭД', 'Тип мяса', 'Сертификация'];

  const BOM = '\uFEFF';
  let csv = BOM + headers.join(';') + '\n';

  for (const p of products) {
    const isBakery = !!p.offers?.pricePerUnit;
    const price = isBakery ? 0 : getPrice(p, currency, withVAT);
    const ppu = isBakery ? parseFloat(p.offers.pricePerUnit) : 0;
    const ppb = isBakery ? parseFloat(p.offers.pricePerBox) : 0;

    const row = isEn
      ? [p.sku, `"${(p.name||'').replace(/"/g,'""')}"`, `"${(p.name_ru||p.name||'').replace(/"/g,'""')}"`, p.section, p.category, p.weight, isBakery?'':price.toFixed(2), isBakery?ppu.toFixed(2):'', isBakery?ppb.toFixed(2):'', p.qtyPerBox||'', p.shelfLife, p.storage, p.hsCode, p.meatType||'', p.certification||'Halal']
      : [p.sku, `"${(p.name||'').replace(/"/g,'""')}"`, p.section, p.category, p.weight, isBakery?'':price.toFixed(2), isBakery?ppu.toFixed(2):'', isBakery?ppb.toFixed(2):'', p.qtyPerBox||'', p.shelfLife, p.storage, p.hsCode, p.meatType||'', p.certification||'Halal'];
    csv += row.join(';') + '\n';
  }
  return csv;
}

async function generateXLSX(products, lang, currency, withVAT) {
  const isEn = lang === 'en';
  const curLabel = CUR_NAMES[currency]?.[lang] || currency;
  const vatLabel = currency === 'RUB'
    ? (withVAT ? (isEn ? 'incl. VAT' : 'с НДС') : (isEn ? 'excl. VAT' : 'без НДС'))
    : (isEn ? 'excl. VAT' : 'без НДС');

  const wb = new ExcelJS.Workbook();
  wb.creator = 'Kazan Delicacies';
  wb.created = new Date();

  // ── Sheet 1: Catalog ───────────────────────────────────────────────────────
  const ws = wb.addWorksheet(isEn ? 'Catalog' : 'Каталог');

  const headers = isEn
    ? ['SKU', 'Name', 'Original (RU)', 'Section', 'Category', 'Weight', `Price ${currency} (${vatLabel})`, 'Price/Unit', 'Price/Box', 'Qty/Box', 'Shelf Life', 'Storage', 'HS Code', 'Meat Type', 'Cert.']
    : ['Артикул', 'Название', 'Раздел', 'Категория', 'Вес', `Цена ${curLabel} (${vatLabel})`, 'Цена/шт', 'Цена/кор', 'Кол/кор', 'Годность', 'Хранение', 'ТН ВЭД', 'Мясо', 'Серт.'];

  // Fix 1: dynamic merge width based on actual header count
  const totalCols = headers.length;
  const lastCol = String.fromCharCode(64 + totalCols);

  const titleRow = ws.addRow([isEn ? 'Kazan Delicacies — Halal Product Catalog' : 'Казанские Деликатесы — Каталог халяль продукции']);
  titleRow.font = { bold: true, size: 14, color: { argb: 'FF1B7A3D' } };
  titleRow.height = 22;
  ws.mergeCells(`A1:${lastCol}1`);

  ws.addRow([
    `${isEn ? 'Currency' : 'Валюта'}: ${curLabel} (${vatLabel})`,
    '',
    `${isEn ? 'Date' : 'Дата'}: ${new Date().toISOString().split('T')[0]}`,
    '',
    `${isEn ? 'Contact' : 'Контакт'}: info@kazandelikates.tatar`,
    '',
    '+7 987 217-02-02',
  ]);

  ws.addRow([]);

  const headerRow = ws.addRow(headers);
  headerRow.eachCell((cell) => {
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1B7A3D' } };
    cell.font = { bold: true, color: { argb: 'FFFFFFFF' }, size: 11 };
    cell.alignment = { horizontal: 'center', vertical: 'middle' };
    cell.border = { bottom: { style: 'thin', color: { argb: 'FF0D5C2E' } } };
  });
  headerRow.height = 18;

  // Fix 2: freeze top 4 rows (title + info + blank + headers)
  ws.views = [{ state: 'frozen', xSplit: 0, ySplit: 4, topLeftCell: 'A5' }];

  // Fix 3: autoFilter on header row
  ws.autoFilter = { from: 'A4', to: `${lastCol}4` };

  let currentSection = '';
  let dataRowIndex = 0;

  for (const p of products) {
    if (p.section !== currentSection) {
      currentSection = p.section;
      const sectionRow = ws.addRow([currentSection]);
      sectionRow.font = { bold: true, size: 11, color: { argb: 'FF1B7A3D' } };
      sectionRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFE8F5EC' } };
      // Fix 1: dynamic merge for section rows
      ws.mergeCells(`A${sectionRow.number}:${lastCol}${sectionRow.number}`);
      sectionRow.height = 16;
    }

    const isBakery = !!p.offers?.pricePerUnit;
    const rawPrice = isBakery ? null : getPrice(p, currency, withVAT);
    const rawPpu = isBakery ? parseFloat(p.offers.pricePerUnit) : null;
    const rawPpb = isBakery ? parseFloat(p.offers.pricePerBox) : null;

    // Fix 4: null → '' for empty prices
    const price = rawPrice !== null ? rawPrice : '';
    const ppu   = rawPpu   !== null ? rawPpu   : '';
    const ppb   = rawPpb   !== null ? rawPpb   : '';

    const row = isEn
      ? [p.sku, p.name, p.name_ru || p.name, p.section, p.category, p.weight, price, ppu, ppb, p.qtyPerBox || '', p.shelfLife, p.storage, p.hsCode, p.meatType || '', p.certification || 'Halal']
      : [p.sku, p.name, p.section, p.category, p.weight, price, ppu, ppb, p.qtyPerBox || '', p.shelfLife, p.storage, p.hsCode, p.meatType || '', p.certification || 'Halal'];

    const dataRow = ws.addRow(row);

    // Fix 6: zebra striping on data rows
    dataRowIndex++;
    const bgColor = dataRowIndex % 2 === 0 ? 'FFFFFFFF' : 'FFF5F5F5';
    dataRow.eachCell({ includeEmpty: true }, (cell) => {
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: bgColor } };
    });

    const priceCol = isEn ? 7 : 6;
    [priceCol, priceCol + 1, priceCol + 2].forEach((col) => {
      const cell = dataRow.getCell(col);
      if (cell.value !== '' && typeof cell.value === 'number') {
        cell.numFmt = '#,##0.00';
      }
    });
  }

  ws.columns.forEach((col) => {
    let maxLen = 10;
    col.eachCell({ includeEmpty: false }, (cell) => {
      const len = String(cell.value || '').length;
      if (len > maxLen) maxLen = len;
    });
    col.width = Math.min(maxLen + 2, 40);
  });

  // Fix 5: Sheet 2 — Contacts
  const wsContacts = wb.addWorksheet(isEn ? 'Contacts' : 'Контакты');
  const contactData = isEn
    ? [
        ['Kazan Delicacies — Contact Information'],
        [],
        ['Company', 'Kazan Delicacies (LLC «Kazanskie Delikatesy»)'],
        ['Address', 'ul. Agrarnaya 2, office 7, Kazan, Republic of Tatarstan, 420061, Russia'],
        ['Phone', '+7 987 217-02-02'],
        ['Email', 'info@kazandelikates.tatar'],
        ['Website', 'https://pepperoni.tatar'],
        ['Catalog API', 'https://api.pepperoni.tatar/api/products'],
        [],
        ['Certifications', ''],
        ['Halal', 'DUM RT Certificate №614А/2024'],
        ['Food Safety', 'ISO 22000:2018'],
        ['HACCP', 'HACCP certified'],
        ['Technical', 'TR CU 021/2011'],
        [],
        ['Working hours', 'Mon–Fri 9:00–18:00 MSK'],
        ['WhatsApp', 'https://wa.me/79872170202'],
      ]
    : [
        ['Казанские Деликатесы — Контактная информация'],
        [],
        ['Компания', 'ООО «Казанские Деликатесы»'],
        ['Адрес', 'г. Казань, ул. Аграрная, д. 2, оф. 7, Республика Татарстан, 420061'],
        ['Телефон', '+7 987 217-02-02'],
        ['Email', 'info@kazandelikates.tatar'],
        ['Сайт', 'https://pepperoni.tatar'],
        ['API каталога', 'https://api.pepperoni.tatar/api/products'],
        [],
        ['Сертификаты', ''],
        ['Халяль', 'Сертификат ДУМ РТ №614А/2024'],
        ['Пищевая безопасность', 'ISO 22000:2018'],
        ['ХАССП', 'Сертифицировано по ХАССП'],
        ['Технический регламент', 'ТР ТС 021/2011'],
        [],
        ['Режим работы', 'Пн–Пт 9:00–18:00 МСК'],
        ['WhatsApp', 'https://wa.me/79872170202'],
      ];

  contactData.forEach((rowData, i) => {
    const r = wsContacts.addRow(rowData);
    if (i === 0) {
      r.font = { bold: true, size: 14, color: { argb: 'FF1B7A3D' } };
      wsContacts.mergeCells(`A1:B1`);
    } else if (rowData.length === 2 && rowData[1] === '') {
      r.font = { bold: true, size: 11, color: { argb: 'FF1B7A3D' } };
    } else if (rowData.length === 2) {
      r.getCell(1).font = { bold: true };
    }
  });
  wsContacts.getColumn(1).width = 28;
  wsContacts.getColumn(2).width = 55;

  return wb.xlsx.writeBuffer();
}

export default async function handler(req, res) {
  try {
    const lang = req.query.lang || 'ru';
    const format = req.query.format || 'xlsx';
    const currency = req.query.currency || (lang === 'en' ? 'USD' : 'RUB');
    const withVAT = currency === 'RUB' ? (req.query.vat !== 'false') : false;

    const apiUrl = `${PRODUCTS_URL}?lang=${lang}`;
    const response = await fetch(apiUrl);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const data = await response.json();
    const products = data.products || [];

    const company = lang === 'en' ? 'Kazan_Delicacies' : 'Kazanskie_Delikatesy';
    const vatSuffix = currency === 'RUB' ? (withVAT ? '_VAT' : '_noVAT') : '';

    if (format === 'csv') {
      const csv = generateCSV(products, lang, currency, withVAT);
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader('Content-Disposition', `attachment; filename="${company}_${currency}${vatSuffix}.csv"`);
      res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
      res.status(200).send(csv);
    } else if (format === 'xlsx' || format === 'excel') {
      const buffer = await generateXLSX(products, lang, currency, withVAT);
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', `attachment; filename="${company}_${currency}${vatSuffix}.xlsx"`);
      res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
      res.status(200).send(Buffer.from(buffer));
    } else {
      res.status(400).json({ error: 'Supported formats: csv, xlsx' });
    }
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
}
