const PRODUCTS_URL = 'https://api.pepperoni.tatar/api/products';

export default async function handler(req, res) {
  try {
    const lang = req.query.lang || 'ru';
    const format = req.query.format || 'csv';

    const apiUrl = `${PRODUCTS_URL}?lang=${lang}`;
    const response = await fetch(apiUrl);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const data = await response.json();
    const products = data.products || [];

    if (format === 'csv') {
      const isEn = lang === 'en';
      const headers = isEn
        ? ['SKU', 'Name', 'Original Name (RU)', 'Section', 'Category', 'Weight', 'Price RUB (incl. VAT)', 'Price RUB (excl. VAT)', 'Price per Unit', 'Price per Box', 'Qty per Box', 'Shelf Life', 'Storage', 'HS Code', 'Meat Type', 'Certification']
        : ['Артикул', 'Название', 'Раздел', 'Категория', 'Вес', 'Цена с НДС (₽)', 'Цена без НДС (₽)', 'Цена за шт', 'Цена за короб', 'Кол-во в коробе', 'Срок годности', 'Хранение', 'ТН ВЭД', 'Тип мяса', 'Сертификация'];

      const BOM = '\uFEFF';
      let csv = BOM + headers.join(';') + '\n';

      for (const p of products) {
        const o = p.offers || {};
        const row = isEn
          ? [
              p.sku || '',
              `"${(p.name || '').replace(/"/g, '""')}"`,
              `"${(p.name_ru || '').replace(/"/g, '""')}"`,
              p.section || '',
              p.category || '',
              p.weight || '',
              o.price || '',
              o.priceExclVAT || '',
              o.pricePerUnit || '',
              o.pricePerBox || '',
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
              o.price || '',
              o.priceExclVAT || '',
              o.pricePerUnit || '',
              o.pricePerBox || '',
              p.qtyPerBox || '',
              p.shelfLife || '',
              p.storage || '',
              p.hsCode || '',
              p.meatType || '',
              p.certification || 'Halal',
            ];
        csv += row.join(';') + '\n';
      }

      const filename = isEn
        ? 'Kazan_Delicacies_Catalog.csv'
        : 'Kazanskie_Delikatesy_Katalog.csv';

      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
      res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
      res.status(200).send(csv);
    } else {
      res.status(400).json({ error: 'Supported formats: csv. Use ?format=csv' });
    }
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
}
