import { logVisit } from './stats.js';

const BASE_URL =
  'https://docs.google.com/spreadsheets/d/e/2PACX-1vRWKnx70tXlapgtJsR4rw9WLeQlksXAaXCQzZP1RBh9G7H9lQK4rt0ga9DaJkV28F7q8GDgkRZM3Arj/pub?output=csv';

const SHEETS = [
  { gid: '1087942289', section: 'Заморозка', type: 'standard' },
  { gid: '1589357549', section: 'Охлаждённая продукция', type: 'standard' },
  { gid: '26993021', section: 'Выпечка', type: 'bakery' },
];

function parseCSV(text) {
  const rows = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      if (inQuotes && text[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === ',' && !inQuotes) {
      rows.push(current);
      current = '';
    } else if (ch === '\n' && !inQuotes) {
      rows.push(current);
      current = '';
      rows.push(null);
    } else {
      current += ch;
    }
  }
  if (current) rows.push(current);

  const lines = [];
  let line = [];
  for (const cell of rows) {
    if (cell === null) {
      lines.push(line);
      line = [];
    } else {
      line.push(cell.trim());
    }
  }
  if (line.length) lines.push(line);
  return lines;
}

function toNumber(s) {
  if (!s) return 0;
  return parseFloat(s.replace(/\s/g, '').replace(',', '.')) || 0;
}

const TRANSLATIONS = {
  'сосиски гриль для хот-догов': 'Grill Sausages for Hot Dogs',
  'сосиски «из говядины» (80 г × 6 шт)': 'Beef Sausages (80g × 6 pcs)',
  'сосиски «два мяса» (80 г × 6 шт)': 'Two-Meat Sausages (80g × 6 pcs)',
  'сосиски «три перца с сыром» (80 г × 6 шт)': 'Three Peppers & Cheese Sausages (80g × 6 pcs)',
  'сосиски «куриные» (80 г × 6 шт)': 'Chicken Sausages (80g × 6 pcs)',
  'сосиски «с бараниной» (80 г × 6 шт)': 'Lamb Sausages (80g × 6 pcs)',
  'сосиски «с травами» (130 г × 5 шт)': 'Herb Sausages (130g × 5 pcs)',
  'сосиски «с сыром» (130 г × 5 шт)': 'Cheese Sausages (130g × 5 pcs)',
  'котлеты для бургеров': 'Burger Patties',
  'котлета говяжья прожаренная (100 г × 3 шт)': 'Fried Beef Patty (100g × 3 pcs)',
  'котлета говяжья прожаренная (150 г × 2 шт)': 'Fried Beef Patty (150g × 2 pcs)',
  'топпинги': 'Toppings',
  'ветчина из курицы в батоне': 'Chicken Ham (whole)',
  'ветчина из курицы в нарезке': 'Chicken Ham (sliced)',
  'ветчина из индейки в батоне': 'Turkey Ham (whole)',
  'ветчина из индейки в нарезке': 'Turkey Ham (sliced)',
  'пепперони вар-коп из конины': 'Boiled-Smoked Pepperoni (horse meat)',
  'пепперони вар-коп классика': 'Boiled-Smoked Pepperoni Classic (beef & chicken)',
  'пепперони вар-коп классика целый батон': 'Boiled-Smoked Pepperoni Classic (whole stick, beef & chicken)',
  'пепперони сырокопчёный в нарезке': 'Dry-Cured Pepperoni (sliced, beef & chicken)',
  'пепперони сырокопчёный целый батон': 'Dry-Cured Pepperoni (whole stick, beef & chicken)',
  'грудка куриная варено-копченая': 'Smoked Chicken Breast',
  'филе куриное варное': 'Boiled Chicken Fillet',
  'мясные заготовки': 'Meat Preparations',
  'фарш говяжий': 'Beef Mince',
  'фарш из куриной кожи': 'Chicken Skin Mince',
  'филе бедра куриного в кубике 1х1 см': 'Diced Chicken Thigh (1×1 cm)',
  'филе грудки куриной в кубике 1х1 см': 'Diced Chicken Breast (1×1 cm)',
  'говядина 1 сорт в кубике 1х1 см': 'Diced Beef Grade 1 (1×1 cm)',
  'сосиски, сардельки': 'Sausages & Frankfurters',
  'сосиски «к завтраку»': 'Breakfast Sausages',
  'сосиски «к завтраку» (без оболочки) \nдля «сосиски в тесте»': 'Breakfast Sausages (skinless, for pigs-in-blankets)',
  'сосиски «нежные»': 'Tender Sausages',
  'сосиски «казанские с молоком»': 'Kazan Milk Sausages',
  'сосиски «с сыром»': 'Cheese Sausages',
  'сосиски «из говядины»': 'Beef Sausages',
  'сосиски "из говядины"': 'Beef Sausages',
  'сосиски в/с премиум': 'Premium Sausages',
  'сосиски в/с сочные': 'Juicy Sausages',
  'сардельки «буинские»': 'Buinsk Frankfurters',
  'сардельки «буинские"': 'Buinsk Frankfurters',
  'вареные': 'Boiled Sausages',
  'вареная «из говядины»': 'Boiled Beef Sausage',
  'вареная ассорти': 'Boiled Assorted Sausage',
  'вареная нежная': 'Boiled Tender Sausage',
  'ветчины': 'Hams',
  'ветчина из индейки': 'Turkey Ham',
  'ветчина мраморная с говядиной': 'Marbled Beef Ham',
  'ветчина из курицы': 'Chicken Ham',
  'ветчина филейная': 'Fillet Ham',
  'копченые': 'Smoked Meats',
  'сервелат ханский': 'Khan Cervelat',
  'сервелат по-татарски в/к': 'Tatar-Style Smoked Cervelat',
  'полукопченая из индейки': 'Semi-Smoked Turkey Sausage',
  'полукопченая из говядины': 'Semi-Smoked Beef Sausage',
  'колбаски с сыром': 'Cheese Sausage Links',
  'грудка куриная': 'Chicken Breast',
  'филе куриное': 'Chicken Fillet',
  'в/к рамазан': 'Ramazan Smoked Sausage',
  'в/к рамазан (половинка)': 'Ramazan Smoked Sausage (half)',
  'в/к мраморная': 'Marbled Smoked Sausage',
  'в/к мраморная (половинка)': 'Marbled Smoked Sausage (half)',
  'в/к филейный': 'Fillet Smoked Sausage',
  'в/к филейный (половинка)': 'Fillet Smoked Sausage (half)',
  'в/к княжеская': 'Knyazheskaya Smoked Sausage',
  'в/к княжеская (половинка)': 'Knyazheskaya Smoked Sausage (half)',
  'премиум казылык': 'Premium Kazylyk',
  'казылык «премиум» в подарочной упаковке': 'Kazylyk Premium (gift box, horse meat)',
  'казылык «премиум» в нарезке в подарочной упаковке': 'Kazylyk Premium Sliced (gift box, horse meat)',
  'национальная татарская выпечка': 'Traditional Tatar Pastries',
  'губадия с кортом': 'Gubadiya with Kort (Tatar layered pie)',
  'чебурек жареный': 'Fried Cheburek',
  'перемяч жареный': 'Fried Peremyach (Tatar meat pie)',
  'самса с курицей': 'Chicken Samsa',
  'эчпочмак с говядиной и картофелем': 'Echpochmak with Beef & Potato (Tatar triangle pie)',
  'самса с говядиной': 'Beef Samsa',
  'элеш с курицей и картофелем': 'Elesh with Chicken & Potato (Tatar pie)',
  'чак-чак в пластиковой упаковке': 'Chak-Chak (plastic pack)',
  'чак-чак в крафтовой подарочной упаковке': 'Chak-Chak (craft gift box)',
  'классическая выпечка': 'Classic Pastries',
  'сочник с творогом': 'Cottage Cheese Sochnik',
  'пирожок печеный с картофелем': 'Baked Potato Pie',
  'сырник': 'Syrnik (cottage cheese pancake)',
  'пирожок с яблоком': 'Apple Pie',
  'пирожок с зеленым луком и яйцом': 'Spring Onion & Egg Pie',
  'маффин апельсиновый': 'Orange Muffin',
  'сосиска в тесте': 'Sausage Roll',
  'пирожок с вишней': 'Cherry Pie',
  'круассан с шоколадом и орехами': 'Chocolate & Nut Croissant',
  'маффин шоколадный': 'Chocolate Muffin',
};

const CATEGORY_TRANSLATIONS = {
  'Сосиски гриль для хот-догов': 'Grill Sausages for Hot Dogs',
  'Котлеты для бургеров': 'Burger Patties',
  'Топпинги': 'Toppings',
  'Мясные заготовки': 'Meat Preparations',
  'Сосиски, сардельки': 'Sausages & Frankfurters',
  'Вареные': 'Boiled Sausages',
  'Ветчины': 'Hams',
  'Копченые': 'Smoked Meats',
  'Премиум Казылык': 'Premium Kazylyk',
  'Национальная татарская выпечка': 'Traditional Tatar Pastries',
  'Классическая выпечка': 'Classic Pastries',
  'Готовые блюда': 'Ready Meals',
};

const SECTION_TRANSLATIONS = {
  'Заморозка': 'Frozen Products',
  'Охлаждённая продукция': 'Refrigerated Products',
  'Выпечка': 'Bakery',
};

const MEAT_TR = {
  'говядина, курица': 'beef, chicken',
  'конина': 'horse meat',
  'говядина': 'beef',
  'курица': 'chicken',
  'индейка': 'turkey',
  'баранина': 'lamb',
};

const SHELF_TR_MAP = {
  '30 суток': '30 days', '60 суток': '60 days',
  '180 суток': '180 days', '360 суток': '360 days',
};

const STORAGE_TR_MAP = {
  '–18°C': '–18°C', '0-6 ˚C': '0–6°C', '0-6°C': '0–6°C',
  '0-12 ˚C': '0–12°C', 'до +18°C': 'up to +18°C',
};

const DESC_TR = {
  'пепперони вар-коп классика': 'Boiled-smoked classic pepperoni from beef and chicken. Halal. Thermostable — does not curl when baked.',
  'пепперони вар-коп классика целый батон': 'Boiled-smoked classic pepperoni, whole stick, from beef and chicken. Halal.',
  'пепперони вар-коп из конины': 'Boiled-smoked pepperoni from horse meat. Halal.',
  'пепперони сырокопчёный в нарезке': 'Dry-cured pepperoni, sliced, from beef and chicken. Halal.',
  'пепперони сырокопчёный целый батон': 'Dry-cured pepperoni, whole stick, from beef and chicken. Halal.',
};

function translateProduct(product) {
  const key = product.name.toLowerCase().trim();
  const translated = { ...product };
  translated.name_ru = product.name;
  translated.name = TRANSLATIONS[key] || product.name;
  if (product.category) {
    translated.category_ru = product.category;
    translated.category = CATEGORY_TRANSLATIONS[product.category] || product.category;
  }
  if (product.section) {
    translated.section_ru = product.section;
    translated.section = SECTION_TRANSLATIONS[product.section] || product.section;
  }
  if (product.shelfLife) {
    translated.shelfLife = SHELF_TR_MAP[product.shelfLife] || product.shelfLife.replace('суток', 'days');
  }
  if (product.storage) {
    translated.storage = STORAGE_TR_MAP[product.storage] || product.storage;
  }
  if (product.meatType) {
    translated.meatType = MEAT_TR[product.meatType] || product.meatType;
  }
  if (product.description) {
    translated.description = DESC_TR[key] || product.description;
  }
  if (product.weight) {
    translated.weight = product.weight.replace(' г', ' g').replace(' кг', ' kg');
  }
  return translated;
}

const PHOTO_MAP = {};

function addPhoto(product) {
  const key = product.name.toLowerCase().trim();
  const photoId = PHOTO_MAP[key];
  if (photoId) {
    product.image = `https://drive.google.com/thumbnail?id=${photoId}&sz=w800`;
    product.imageOriginal = `https://drive.google.com/uc?id=${photoId}`;
  }
  return product;
}

const ENRICHMENTS = {
  'пепперони вар-коп классика': { meatType: 'говядина, курица', description: 'Пепперони варёно-копчёный классический из говядины и курицы. Халяль. Термостабильный — не скручивается при запекании.' },
  'пепперони вар-коп классика целый батон': { meatType: 'говядина, курица', description: 'Пепперони варёно-копчёный классический из говядины и курицы, целый батон. Халяль.' },
  'пепперони вар-коп из конины': { meatType: 'конина', description: 'Пепперони варёно-копчёный из конины. Халяль.' },
  'пепперони сырокопчёный в нарезке': { meatType: 'говядина, курица', description: 'Пепперони сырокопчёный в нарезке из говядины и курицы. Халяль.' },
  'пепперони сырокопчёный целый батон': { meatType: 'говядина, курица', description: 'Пепперони сырокопчёный из говядины и курицы, целый батон. Халяль.' },
};

function enrich(product) {
  const key = product.name.toLowerCase();
  const data = ENRICHMENTS[key];
  if (data) {
    product.meatType = data.meatType;
    product.description = data.description;
  }
  return product;
}

function buildStandard(lines, section, startIdx) {
  let category = '';
  const products = [];
  let idx = startIdx;

  for (const cols of lines) {
    if (!cols || cols.length < 3) continue;
    const name = cols[0];
    if (!name || name === 'Наименование' || name === 'Номенклатура' || name.startsWith('ООО')) continue;

    const priceVAT = toNumber(cols[2]);
    const priceNoVAT = toNumber(cols[3]);

    if (priceVAT === 0 && priceNoVAT === 0) {
      if (name && !cols[1]) category = name;
      continue;
    }

    idx++;
    const weight = cols[1] || '';
    const shelfLife = cols[4] || '';
    const storage = cols[5] || '';
    const hsCode = cols[6] || '';

    const prices = {};
    if (toNumber(cols[7])) prices.USD = toNumber(cols[7]);
    if (toNumber(cols[8])) prices.KZT = toNumber(cols[8]);
    if (toNumber(cols[9])) prices.UZS = toNumber(cols[9]);
    if (toNumber(cols[10])) prices.KGS = toNumber(cols[10]);
    if (toNumber(cols[11])) prices.BYN = toNumber(cols[11]);
    if (toNumber(cols[12])) prices.AZN = toNumber(cols[12]);

    products.push({
      name,
      sku: `KD-${String(idx).padStart(3, '0')}`,
      section,
      category: category || section,
      weight,
      brand: 'Казанские Деликатесы',
      certification: 'Halal',
      offers: {
        url: 'https://pepperoni.tatar',
        priceCurrency: 'RUB',
        price: priceVAT.toFixed(2),
        priceExclVAT: priceNoVAT.toFixed(2),
        availability: 'https://schema.org/InStock',
        exportPrices: prices,
        deliveryTerms: 'EXW Kazan Russia',
      },
      shelfLife,
      storage,
      hsCode,
    });
  }

  return { products, nextIdx: idx };
}

function buildBakery(lines, section, startIdx) {
  let category = '';
  const products = [];
  let idx = startIdx;

  for (const cols of lines) {
    if (!cols || cols.length < 4) continue;
    const name = cols[0];
    if (!name || name === 'Наименование' || name.startsWith('ООО')) continue;

    const pricePerUnit = toNumber(cols[3]);
    const pricePerBox = toNumber(cols[4]);

    if (pricePerUnit === 0 && pricePerBox === 0) {
      if (name && !cols[1]) category = name;
      continue;
    }

    idx++;
    const weightGrams = cols[1] || '';
    const qtyPerBox = cols[2] || '';
    const priceBoxNoVAT = toNumber(cols[5]);
    const shelfLife = cols[6] || '';
    const storage = cols[7] || '';
    const hsCode = cols[8] || '';

    const prices = {};
    if (toNumber(cols[9])) prices.USD = toNumber(cols[9]);
    if (toNumber(cols[10])) prices.KZT = toNumber(cols[10]);
    if (toNumber(cols[11])) prices.UZS = toNumber(cols[11]);
    if (toNumber(cols[12])) prices.KGS = toNumber(cols[12]);
    if (toNumber(cols[13])) prices.BYN = toNumber(cols[13]);
    if (toNumber(cols[14])) prices.AZN = toNumber(cols[14]);

    products.push({
      name,
      sku: `KD-${String(idx).padStart(3, '0')}`,
      section,
      category: category || section,
      weight: weightGrams ? `${weightGrams} г` : '',
      qtyPerBox: qtyPerBox || '',
      brand: 'Казанские Деликатесы',
      certification: 'Halal',
      offers: {
        url: 'https://pepperoni.tatar',
        priceCurrency: 'RUB',
        pricePerUnit: pricePerUnit.toFixed(2),
        pricePerBox: pricePerBox.toFixed(2),
        pricePerBoxExclVAT: priceBoxNoVAT.toFixed(2),
        availability: 'https://schema.org/InStock',
        exportPrices: prices,
        deliveryTerms: 'EXW Kazan Russia',
      },
      shelfLife,
      storage,
      hsCode,
    });
  }

  return { products, nextIdx: idx };
}

export default async function handler(req, res) {
  try {
    logVisit(req);
    const fetches = SHEETS.map((s) =>
      fetch(`${BASE_URL}&gid=${s.gid}`).then((r) => r.text())
    );
    const csvs = await Promise.all(fetches);

    let allProducts = [];
    let idx = 0;

    for (let i = 0; i < SHEETS.length; i++) {
      const lines = parseCSV(csvs[i]);
      const sheet = SHEETS[i];
      let result;

      if (sheet.type === 'bakery') {
        result = buildBakery(lines, sheet.section, idx);
      } else {
        result = buildStandard(lines, sheet.section, idx);
      }

      allProducts = allProducts.concat(result.products.map(p => addPhoto(enrich(p))));
      idx = result.nextIdx;
    }

    const { search, section, category, sku, lang } = req.query || {};
    let filtered = lang === 'en'
      ? allProducts.map(translateProduct)
      : allProducts;

    if (search) {
      const q = search.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          (p.category && p.category.toLowerCase().includes(q)) ||
          (p.sku && p.sku.toLowerCase().includes(q)) ||
          (p.description && p.description.toLowerCase().includes(q)) ||
          (p.meatType && p.meatType.toLowerCase().includes(q))
      );
    }
    if (section) {
      const s = section.toLowerCase();
      filtered = filtered.filter((p) => p.section && p.section.toLowerCase().includes(s));
    }
    if (category) {
      const c = category.toLowerCase();
      filtered = filtered.filter((p) => p.category && p.category.toLowerCase().includes(c));
    }
    if (sku) {
      filtered = filtered.filter((p) => p.sku && p.sku.toUpperCase() === sku.toUpperCase());
    }

    const result = {
      '@context': 'https://schema.org',
      '@type': 'DataCatalog',
      name: 'Полный каталог — Казанские Деликатесы',
      url: 'https://api.pepperoni.tatar/api/products',
      publisher: {
        '@type': 'Organization',
        name: 'Казанские Деликатесы',
        url: 'https://kazandelikates.tatar',
        address: '420061, Казань, ул Аграрная, 2, оф 7',
        phone: '+79872170202',
        email: 'info@kazandelikates.tatar',
      },
      dateModified: new Date().toISOString(),
      source: 'Google Sheets (live sync — 3 sheets)',
      sections: SHEETS.map((s) => s.section),
      totalProducts: filtered.length,
      filters: { search: search || null, section: section || null, category: category || null, sku: sku || null },
      products: filtered,
    };

    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.status(200).json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
}
