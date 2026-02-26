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

function getPriceBakery(p, currency) {
  if (currency === 'RUB') {
    return {
      perUnit: parseFloat(p.offers?.pricePerUnit || 0),
      perBox: parseFloat(p.offers?.pricePerBox || 0),
    };
  }
  const rate = p.offers?.exportPrices?.[currency];
  if (!rate) return { perUnit: 0, perBox: 0 };
  return { perUnit: rate, perBox: rate };
}

function escapeXml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function generateCSV(products, lang, currency, withVAT) {
  const isEn = lang === 'en';
  const curLabel = CUR_NAMES[currency]?.[lang] || currency;
  const vatLabel = currency === 'RUB'
    ? (withVAT ? (isEn ? 'incl. VAT' : 'с НДС') : (isEn ? 'excl. VAT' : 'без НДС'))
    : (isEn ? 'excl. VAT' : 'без НДС');

  const headers = isEn
    ? ['SKU', 'Name', 'Original Name (RU)', 'Section', 'Category', 'Weight', `Price ${currency} (${vatLabel})`, 'Price per Unit', 'Price per Box', 'Qty/Box', 'Shelf Life', 'Storage', 'HS Code', 'Meat Type', 'Certification']
    : ['Артикул', 'Название', 'Раздел', 'Категория', 'Вес', `Цена ${curLabel} (${vatLabel})`, 'Цена за шт', 'Цена за короб', 'Кол-во/кор', 'Срок годности', 'Хранение', 'ТН ВЭД', 'Тип мяса', 'Сертификация'];

  const BOM = '\uFEFF';
  let csv = BOM + headers.join(';') + '\n';

  for (const p of products) {
    const isBakery = !!p.offers?.pricePerUnit;
    const price = isBakery ? 0 : getPrice(p, currency, withVAT);
    const bk = isBakery ? getPriceBakery(p, currency) : { perUnit: 0, perBox: 0 };

    const row = isEn
      ? [
          p.sku || '',
          `"${(p.name || '').replace(/"/g, '""')}"`,
          `"${(p.name_ru || p.name || '').replace(/"/g, '""')}"`,
          p.section || '',
          p.category || '',
          p.weight || '',
          isBakery ? '' : price.toFixed(2),
          isBakery ? bk.perUnit.toFixed(2) : '',
          isBakery ? bk.perBox.toFixed(2) : '',
          p.qtyPerBox || '',
          p.shelfLife || '',
          p.storage || '',
          p.hsCode || '',
          p.meatType || '',
          p.certification || 'Halal',
        ]
      : [
          p.sku || '',
          `"${(p.name || '').replace(/"/g, '""')}"`,
          p.section || '',
          p.category || '',
          p.weight || '',
          isBakery ? '' : price.toFixed(2),
          isBakery ? bk.perUnit.toFixed(2) : '',
          isBakery ? bk.perBox.toFixed(2) : '',
          p.qtyPerBox || '',
          p.shelfLife || '',
          p.storage || '',
          p.hsCode || '',
          p.meatType || '',
          p.certification || 'Halal',
        ];
    csv += row.join(';') + '\n';
  }
  return csv;
}

function generateExcelXML(products, lang, currency, withVAT) {
  const isEn = lang === 'en';
  const curLabel = CUR_NAMES[currency]?.[lang] || currency;
  const vatLabel = currency === 'RUB'
    ? (withVAT ? (isEn ? 'incl. VAT' : 'с НДС') : (isEn ? 'excl. VAT' : 'без НДС'))
    : (isEn ? 'excl. VAT' : 'без НДС');

  const headers = isEn
    ? ['SKU', 'Name', 'Original (RU)', 'Section', 'Category', 'Weight', `Price ${currency} (${vatLabel})`, 'Price/Unit', 'Price/Box', 'Qty/Box', 'Shelf Life', 'Storage', 'HS Code', 'Meat Type', 'Cert']
    : ['Артикул', 'Название', 'Раздел', 'Категория', 'Вес', `Цена ${curLabel} (${vatLabel})`, 'Цена/шт', 'Цена/кор', 'Кол-во/кор', 'Годность', 'Хранение', 'ТН ВЭД', 'Мясо', 'Серт.'];

  const sheetName = isEn ? 'Kazan Delicacies Catalog' : 'Каталог Казанские Деликатесы';

  let xml = `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
<Styles>
 <Style ss:ID="header"><Font ss:Bold="1" ss:Size="11"/><Interior ss:Color="#1B7A3D" ss:Pattern="Solid"/><Font ss:Color="#FFFFFF" ss:Bold="1"/></Style>
 <Style ss:ID="num"><NumberFormat ss:Format="0.00"/></Style>
 <Style ss:ID="title"><Font ss:Bold="1" ss:Size="14"/></Style>
</Styles>
<Worksheet ss:Name="${escapeXml(sheetName)}">
<Table>
`;

  xml += `<Row><Cell ss:StyleID="title"><Data ss:Type="String">${isEn ? 'Kazan Delicacies — Halal Product Catalog' : 'Казанские Деликатесы — Каталог халяль продукции'}</Data></Cell></Row>\n`;
  xml += `<Row><Cell><Data ss:Type="String">${isEn ? 'Currency' : 'Валюта'}: ${curLabel} (${vatLabel})</Data></Cell><Cell><Data ss:Type="String">${isEn ? 'Date' : 'Дата'}: ${new Date().toISOString().split('T')[0]}</Data></Cell></Row>\n`;
  xml += '<Row></Row>\n';

  xml += '<Row>';
  for (const h of headers) {
    xml += `<Cell ss:StyleID="header"><Data ss:Type="String">${escapeXml(h)}</Data></Cell>`;
  }
  xml += '</Row>\n';

  for (const p of products) {
    const isBakery = !!p.offers?.pricePerUnit;
    const price = isBakery ? 0 : getPrice(p, currency, withVAT);
    const bk = isBakery ? getPriceBakery(p, currency) : { perUnit: 0, perBox: 0 };

    const cells = isEn
      ? [
          { t: 'String', v: p.sku || '' },
          { t: 'String', v: p.name || '' },
          { t: 'String', v: p.name_ru || p.name || '' },
          { t: 'String', v: p.section || '' },
          { t: 'String', v: p.category || '' },
          { t: 'String', v: p.weight || '' },
          { t: 'Number', v: isBakery ? '' : price.toFixed(2) },
          { t: 'Number', v: isBakery ? bk.perUnit.toFixed(2) : '' },
          { t: 'Number', v: isBakery ? bk.perBox.toFixed(2) : '' },
          { t: 'String', v: p.qtyPerBox || '' },
          { t: 'String', v: p.shelfLife || '' },
          { t: 'String', v: p.storage || '' },
          { t: 'String', v: p.hsCode || '' },
          { t: 'String', v: p.meatType || '' },
          { t: 'String', v: p.certification || 'Halal' },
        ]
      : [
          { t: 'String', v: p.sku || '' },
          { t: 'String', v: p.name || '' },
          { t: 'String', v: p.section || '' },
          { t: 'String', v: p.category || '' },
          { t: 'String', v: p.weight || '' },
          { t: 'Number', v: isBakery ? '' : price.toFixed(2) },
          { t: 'Number', v: isBakery ? bk.perUnit.toFixed(2) : '' },
          { t: 'Number', v: isBakery ? bk.perBox.toFixed(2) : '' },
          { t: 'String', v: p.qtyPerBox || '' },
          { t: 'String', v: p.shelfLife || '' },
          { t: 'String', v: p.storage || '' },
          { t: 'String', v: p.hsCode || '' },
          { t: 'String', v: p.meatType || '' },
          { t: 'String', v: p.certification || 'Halal' },
        ];

    xml += '<Row>';
    for (const c of cells) {
      if (c.v === '' || c.v === undefined) {
        xml += '<Cell><Data ss:Type="String"></Data></Cell>';
      } else if (c.t === 'Number' && !isNaN(parseFloat(c.v))) {
        xml += `<Cell ss:StyleID="num"><Data ss:Type="Number">${c.v}</Data></Cell>`;
      } else {
        xml += `<Cell><Data ss:Type="String">${escapeXml(c.v)}</Data></Cell>`;
      }
    }
    xml += '</Row>\n';
  }

  xml += `</Table>
</Worksheet>
</Workbook>`;
  return xml;
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
      const filename = `${company}_${currency}${vatSuffix}.csv`;
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
      res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
      res.status(200).send(csv);
    } else if (format === 'xlsx' || format === 'excel') {
      const xml = generateExcelXML(products, lang, currency, withVAT);
      const filename = `${company}_${currency}${vatSuffix}.xls`;
      res.setHeader('Content-Type', 'application/vnd.ms-excel; charset=utf-8');
      res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
      res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
      res.status(200).send(xml);
    } else {
      res.status(400).json({ error: 'Supported formats: csv, xlsx. Params: lang (ru/en), currency (RUB/USD/KZT/UZS/KGS/BYN/AZN), vat (true/false), format (csv/xlsx)' });
    }
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
}
