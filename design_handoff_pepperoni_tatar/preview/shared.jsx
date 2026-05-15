// shared.jsx — i18n strings, ornaments, placeholders, brand data
// shared by all four PEPPERONI.TATAR landing variations.

const T = {
  // Brand
  brand:       { tt: 'PEPPERONI.TATAR', ru: 'PEPPERONI.TATAR', en: 'PEPPERONI.TATAR' },
  brandTag:    { tt: 'Хәләл ит комбинаты',         ru: 'Халяль-мясокомбинат',          en: 'Halal meat manufactory' },
  loc:         { tt: 'Казан · Татарстан',           ru: 'Казань · Татарстан',           en: 'Kazan · Tatarstan' },
  since:       { tt: '2014 елдан бирле',            ru: 'С 2014 года',                  en: 'Since 2014' },

  // Hero
  heroOver:    { tt: 'Татар хәләле — дөнья күләмендә', ru: 'Татарский халяль — для всего мира', en: 'Tatar halal, shipped worldwide' },
  heroH1a:     { tt: 'Пепперони,',                  ru: 'Пепперони,',                   en: 'Pepperoni,' },
  heroH1b:     { tt: 'сосискалар,',                 ru: 'сосиски,',                     en: 'sausages,' },
  heroH1c:     { tt: 'ветчина,',                    ru: 'ветчина,',                     en: 'ham,' },
  heroH1d:     { tt: 'котлет.',                     ru: 'котлеты.',                     en: 'patties.' },
  heroSub:     {
    tt: 'Күмәртә күләмдә фурлар һәм контейнерлар белән җибәрү. 24 SKU. ISO 22000 һәм HACCP сертификатлы хәләл цех Татарстанда.',
    ru: 'Поставки фурами и контейнерами в крупном опте. 24 SKU. Халяль-производство в Татарстане, сертифицированное по ISO 22000 и HACCP.',
    en: 'Wholesale shipments by full truck-loads and 40-ft containers. 24 SKU. Halal manufactory in Tatarstan, ISO 22000 + HACCP certified.',
  },
  ctaWholesale:{ tt: 'Күмәртә сорау →',             ru: 'Оптовый запрос →',             en: 'Request wholesale →' },
  ctaCatalog:  { tt: 'Каталог йөкләү',              ru: 'Скачать каталог',              en: 'Download catalog' },
  ctaContact:  { tt: 'Сату бүлеге',                 ru: 'Отдел продаж',                 en: 'Sales desk' },

  // Stats
  statTons:    { tt: 'тонна / елга',                ru: 'тонн в год',                   en: 'tons / year' },
  statCountries:{tt: 'илгә җибәрелә',               ru: 'стран отгрузки',               en: 'export markets' },
  statSku:     { tt: 'актив SKU',                   ru: 'активных SKU',                 en: 'active SKU' },
  statYears:   { tt: 'ел тәҗрибә',                  ru: 'лет производству',             en: 'yrs of production' },
  statHalal:   { tt: '100% хәләл',                  ru: '100% халяль',                  en: '100% halal' },
  statB2B:     { tt: 'B2B клиентлар',               ru: 'B2B-клиентов',                 en: 'B2B clients' },

  // Section labels
  secProducts: { tt: 'Продукция',                   ru: 'Продукция',                    en: 'Product range' },
  secProcess:  { tt: 'Җитештерү',                   ru: 'Производство',                 en: 'Process' },
  secLogi:     { tt: 'Логистика',                   ru: 'Логистика',                    en: 'Logistics' },
  secCert:     { tt: 'Сертификатлар',               ru: 'Сертификаты',                  en: 'Certifications' },
  secContact:  { tt: 'Контактлар',                  ru: 'Контакты',                     en: 'Contact' },
  secNumbers:  { tt: 'Саннар',                      ru: 'Цифры',                        en: 'By the numbers' },
  secCatalog:  { tt: 'Каталог',                     ru: 'Каталог',                      en: 'Catalogue' },

  // Categories
  catPepperoni:{ tt: 'Пепперони',                   ru: 'Пепперони',                    en: 'Pepperoni' },
  catHotdog:   { tt: 'Хот-дог сосискалары',         ru: 'Сосиски для хот-догов',         en: 'Hot-dog sausages' },
  catHam:      { tt: 'Ветчина',                     ru: 'Ветчина',                      en: 'Ham' },
  catBurger:   { tt: 'Бургер котлеты',              ru: 'Котлеты для бургеров',          en: 'Burger patties' },

  // Process steps
  step1Title:  { tt: 'Сайлап алу',                  ru: 'Отбор сырья',                  en: 'Sourcing' },
  step1Body:   { tt: 'Тик хәләл ит. Берничә хуҗалыктан. Һәр партия — ветеринар тикшерүе.',
                 ru: 'Только халяль-сырьё, у нескольких хозяйств, с ветеринарной приёмкой по каждой партии.',
                 en: 'Halal-only sourcing from vetted farms, with veterinary inspection on every batch.' },
  step2Title:  { tt: 'Җитештерү',                   ru: 'Производство',                 en: 'Production' },
  step2Body:   { tt: 'HACCP контурлы линияләр. 12 000 тонна еллык куәт. Минус 18 °C сакланма зона.',
                 ru: 'Линии под контуром HACCP, мощность 12 000 тонн в год, морозильник −18 °C.',
                 en: 'HACCP-controlled lines, 12,000 tons/year capacity, −18 °C cold storage on-site.' },
  step3Title:  { tt: 'Җибәрү',                      ru: 'Отгрузка',                     en: 'Shipping' },
  step3Body:   { tt: 'Реф-фурлар, 40-фут контейнерлар. Турыдан-туры портларга яки терминалларга.',
                 ru: 'Реф-фуры и 40-футовые контейнеры — напрямую в порты или на терминалы клиента.',
                 en: 'Reefer trucks and 40-ft containers, straight to ports or your terminal.' },

  // Logistics chips
  logiTruck:   { tt: 'Реф-фур',                     ru: 'Реф-фура',                     en: 'Reefer truck' },
  logiContainer:{tt: '40-фут контейнер',            ru: '40-фут контейнер',             en: '40-ft container' },
  logiPallet:  { tt: 'Поддонлы җибәрү',             ru: 'Паллетная отгрузка',           en: 'Palletized lot' },
  logiPort:    { tt: 'Порт-та FOB',                 ru: 'FOB в порту',                  en: 'FOB at port' },

  // Spec labels
  specWeight:  { tt: 'Массасы',                     ru: 'Масса',                        en: 'Net weight' },
  specPack:    { tt: 'Упаковка',                    ru: 'Упаковка',                     en: 'Packaging' },
  specCase:    { tt: 'Кейс',                        ru: 'Короб',                        en: 'Case' },
  specMoq:     { tt: 'MOQ',                         ru: 'MOQ',                          en: 'MOQ' },
  specShelf:   { tt: 'Саклау',                      ru: 'Срок годности',                en: 'Shelf life' },
  specStorage: { tt: 'Температура',                 ru: 'Хранение',                     en: 'Storage' },
  specOrigin:  { tt: 'Чыгыш',                       ru: 'Происхождение',                en: 'Origin' },

  // Misc copy
  badgeHalal:  { tt: 'ХӘЛӘЛ · HALAL · حلال',         ru: 'ХАЛЯЛЬ · HALAL · حلال',         en: 'HALAL · حلال' },
  badgeIso:    { tt: 'ISO 22000',                   ru: 'ISO 22000',                    en: 'ISO 22000' },
  badgeHaccp:  { tt: 'HACCP',                       ru: 'HACCP',                        en: 'HACCP' },
  exportTitle: { tt: 'Без 18 илгә җибәрәбез',       ru: 'Мы поставляем в 18 стран',     en: 'We ship to 18 countries' },
  countries:   { tt: 'РФ · Казахстан · Узбекстан · Кыргызстан · Тажикстан · Әзәрбайҗан · Төркия · ОАЕ · СГА · Малайзия · Индонезия · Сингапур · Бахрейн · Катар · Көвәйт · Гарәбстан · Иордания · Бруней',
                 ru: 'РФ · Казахстан · Узбекистан · Киргизия · Таджикистан · Азербайджан · Турция · ОАЭ · Саудовская Аравия · Малайзия · Индонезия · Сингапур · Бахрейн · Катар · Кувейт · Оман · Иордания · Бруней',
                 en: 'Russia · Kazakhstan · Uzbekistan · Kyrgyzstan · Tajikistan · Azerbaijan · Turkey · UAE · Saudi Arabia · Malaysia · Indonesia · Singapore · Bahrain · Qatar · Kuwait · Oman · Jordan · Brunei' },
  byTheNumbers:{ tt: 'Бер ел эчендә',               ru: 'За один год',                  en: 'In one year of operations' },
  manifestoLine:{ tt: 'Бер ит. Бер сүз. Хәләл.',     ru: 'Одно мясо. Одно слово. Халяль.', en: 'One meat. One word. Halal.' },

  // Form
  formCompany: { tt: 'Компания',                    ru: 'Компания',                     en: 'Company' },
  formCountry: { tt: 'Ил',                          ru: 'Страна',                       en: 'Country' },
  formVolume:  { tt: 'Күләм, тонна / ай',           ru: 'Объём, тонн / мес',            en: 'Volume, tons / mo' },
  formProduct: { tt: 'Кызыксыну',                   ru: 'Интерес',                      en: 'Interested in' },
  formEmail:   { tt: 'Эл-почта',                    ru: 'Email',                        en: 'Email' },
  formSend:    { tt: 'Сорау җибәрү',                ru: 'Отправить запрос',             en: 'Send inquiry' },
};

// Translate helper. Falls back to RU if a key/lang is missing.
function t(key, lang) {
  const row = T[key];
  if (!row) return key;
  return row[lang] || row.ru || row.en || key;
}
const LangCtx = React.createContext('ru');
const useLang = () => React.useContext(LangCtx);
const useT = () => { const l = useLang(); return (k) => t(k, l); };

// 24 SKUs as flat array. Names are kept in Russian (with English mirror) —
// these are commodity products and the buyer market reads them either way.
const PRODUCTS = [
  // Pepperoni — 6
  { id: 'pep-classic',   cat: 'pep', name: { tt: 'Пепперони классик',   ru: 'Пепперони классик',   en: 'Pepperoni Classic'   }, w: '2.5 кг', moq: '500 кг', shelf: '120 д' },
  { id: 'pep-spicy',     cat: 'pep', name: { tt: 'Пепперони ачы',       ru: 'Пепперони острый',    en: 'Pepperoni Spicy'     }, w: '2.5 кг', moq: '500 кг', shelf: '120 д' },
  { id: 'pep-beef',      cat: 'pep', name: { tt: 'Пепперони сыер ите',  ru: 'Пепперони из говядины', en: 'Pepperoni Beef'    }, w: '2.5 кг', moq: '500 кг', shelf: '120 д' },
  { id: 'pep-smoked',    cat: 'pep', name: { tt: 'Пепперони төтенле',   ru: 'Пепперони копчёный',  en: 'Pepperoni Smoked'    }, w: '2.5 кг', moq: '500 кг', shelf: '120 д' },
  { id: 'pep-mini',      cat: 'pep', name: { tt: 'Пепперони мини',      ru: 'Пепперони мини',      en: 'Pepperoni Mini'      }, w: '1.0 кг', moq: '300 кг', shelf: '90 д'  },
  { id: 'pep-sticks',    cat: 'pep', name: { tt: 'Пепперони таяклар',   ru: 'Пепперони палочки',   en: 'Pepperoni Sticks'    }, w: '0.5 кг', moq: '200 кг', shelf: '90 д'  },
  // Hot-dog — 6
  { id: 'hd-classic',    cat: 'hd',  name: { tt: 'Хот-дог классик',     ru: 'Хот-дог классик',     en: 'Hot-dog Classic'     }, w: '1.0 кг', moq: '500 кг', shelf: '45 д'  },
  { id: 'hd-cheese',     cat: 'hd',  name: { tt: 'Хот-дог сырлы',       ru: 'Хот-дог с сыром',     en: 'Hot-dog Cheese'      }, w: '1.0 кг', moq: '500 кг', shelf: '45 д'  },
  { id: 'hd-smoked',     cat: 'hd',  name: { tt: 'Хот-дог төтенле',     ru: 'Хот-дог копчёный',    en: 'Hot-dog Smoked'      }, w: '1.0 кг', moq: '500 кг', shelf: '60 д'  },
  { id: 'hd-mini',       cat: 'hd',  name: { tt: 'Хот-дог мини',        ru: 'Хот-дог мини',        en: 'Hot-dog Mini'        }, w: '0.8 кг', moq: '300 кг', shelf: '45 д'  },
  { id: 'hd-bavaria',    cat: 'hd',  name: { tt: 'Бавария',             ru: 'Бавария',             en: 'Bavarian'            }, w: '1.0 кг', moq: '400 кг', shelf: '45 д'  },
  { id: 'hd-vienna',     cat: 'hd',  name: { tt: 'Вена',                ru: 'Вена',                en: 'Vienna'              }, w: '1.0 кг', moq: '400 кг', shelf: '45 д'  },
  // Ham — 6
  { id: 'h-smoked',      cat: 'ham', name: { tt: 'Ветчина төтенле',     ru: 'Ветчина копчёная',    en: 'Smoked Ham'          }, w: '3.0 кг', moq: '600 кг', shelf: '90 д'  },
  { id: 'h-pressed',     cat: 'ham', name: { tt: 'Прессланган ветчина', ru: 'Ветчина прессованная', en: 'Pressed Ham'        }, w: '3.0 кг', moq: '600 кг', shelf: '60 д'  },
  { id: 'h-beef',        cat: 'ham', name: { tt: 'Сыер ите ветчина',    ru: 'Ветчина из говядины', en: 'Beef Ham'            }, w: '3.0 кг', moq: '600 кг', shelf: '90 д'  },
  { id: 'h-pastrami',    cat: 'ham', name: { tt: 'Пастрами',            ru: 'Пастрами',            en: 'Pastrami'            }, w: '2.0 кг', moq: '400 кг', shelf: '60 д'  },
  { id: 'h-carved',      cat: 'ham', name: { tt: 'Ветчина кисәкләргә',  ru: 'Ветчина в нарезке',   en: 'Carved Ham'          }, w: '0.5 кг', moq: '300 кг', shelf: '45 д'  },
  { id: 'h-pepper',      cat: 'ham', name: { tt: 'Кара борычлы ветчина',ru: 'Ветчина с чёрным перцем', en: 'Black-pepper Ham'}, w: '2.5 кг', moq: '500 кг', shelf: '60 д'  },
  // Burger patties — 6
  { id: 'b-100',         cat: 'bur', name: { tt: 'Бургер котлет 100 гр',ru: 'Котлета 100 г',       en: 'Burger Patty 100 g'  }, w: '2.4 кг', moq: '600 кг', shelf: '180 д' },
  { id: 'b-150',         cat: 'bur', name: { tt: 'Бургер премиум 150 гр',ru: 'Котлета премиум 150 г', en: 'Premium Patty 150 g'}, w: '3.0 кг', moq: '600 кг', shelf: '180 д' },
  { id: 'b-smash',       cat: 'bur', name: { tt: 'Смэш котлет 80 гр',   ru: 'Смэш-котлета 80 г',   en: 'Smashburger 80 g'    }, w: '1.6 кг', moq: '400 кг', shelf: '180 д' },
  { id: 'b-spicy',       cat: 'bur', name: { tt: 'Ачы бургер котлеты',  ru: 'Острая котлета',      en: 'Spicy Beef Patty'    }, w: '2.4 кг', moq: '500 кг', shelf: '180 д' },
  { id: 'b-slider',      cat: 'bur', name: { tt: 'Слайдер мини',        ru: 'Слайдер-мини',        en: 'Mini Slider'         }, w: '1.6 кг', moq: '400 кг', shelf: '180 д' },
  { id: 'b-wagyu',       cat: 'bur', name: { tt: 'Хәләл вагю',          ru: 'Халяль-вагю',         en: 'Halal Wagyu'         }, w: '1.2 кг', moq: '200 кг', shelf: '180 д' },
];

const CATS = {
  pep: { color: '#C24A2F', key: 'catPepperoni' },
  hd:  { color: '#D8A24E', key: 'catHotdog' },
  ham: { color: '#A24565', key: 'catHam' },
  bur: { color: '#3C5B3A', key: 'catBurger' },
};

// ───────── Ornaments (composed from primitives only) ─────────

// Rub el Hizb — 8-point star made of two overlapping squares rotated 45°.
function StarRub({ size = 64, color = '#C9A961', stroke = 0, bg = 'transparent' }) {
  const s = size, c = s / 2, r = s * 0.45;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${s} ${s}`} style={{ display: 'block' }}>
      {bg !== 'transparent' && <rect width={s} height={s} fill={bg} />}
      <g fill={stroke ? 'none' : color} stroke={stroke ? color : 'none'} strokeWidth={stroke}>
        <rect x={c - r} y={c - r} width={r * 2} height={r * 2} transform={`rotate(0 ${c} ${c})`} />
        <rect x={c - r} y={c - r} width={r * 2} height={r * 2} transform={`rotate(45 ${c} ${c})`} />
      </g>
    </svg>
  );
}

// Tulip — Tatar national motif. 3 overlapping circles (3 petals) on a triangular stem.
function Tulip({ size = 80, color = '#C9A961', stroke = 0 }) {
  const s = size; const fill = stroke ? 'none' : color;
  const sw = stroke ? stroke : 0;
  return (
    <svg width={size} height={size * 1.4} viewBox={`0 0 ${s} ${s * 1.4}`} style={{ display: 'block' }}>
      <g fill={fill} stroke={color} strokeWidth={sw} strokeLinejoin="round">
        {/* stem */}
        <rect x={s * 0.48} y={s * 0.55} width={s * 0.04} height={s * 0.7} />
        {/* leaves */}
        <ellipse cx={s * 0.32} cy={s * 0.95} rx={s * 0.2} ry={s * 0.08} transform={`rotate(-30 ${s * 0.32} ${s * 0.95})`} />
        <ellipse cx={s * 0.68} cy={s * 0.95} rx={s * 0.2} ry={s * 0.08} transform={`rotate(30 ${s * 0.68} ${s * 0.95})`} />
        {/* three petals */}
        <circle cx={s * 0.30} cy={s * 0.45} r={s * 0.18} />
        <circle cx={s * 0.70} cy={s * 0.45} r={s * 0.18} />
        <circle cx={s * 0.50} cy={s * 0.32} r={s * 0.22} />
        {/* base */}
        <rect x={s * 0.35} y={s * 0.45} width={s * 0.30} height={s * 0.18} />
      </g>
    </svg>
  );
}

// Repeating diamond strip — a horizontal border of rotated squares.
function DiamondStrip({ height = 18, color = '#C9A961', count = 40, gap = 8, opacity = 1 }) {
  const items = Array.from({ length: count });
  return (
    <div style={{ display: 'flex', gap, alignItems: 'center', height, opacity }}>
      {items.map((_, i) => (
        <div key={i} style={{ width: height * 0.55, height: height * 0.55, background: color, transform: 'rotate(45deg)', flex: '0 0 auto' }} />
      ))}
    </div>
  );
}

// Tile of small Rub-el-Hizb stars — used as a textured panel background.
function StarTile({ color = '#C9A961', cell = 36, opacity = 0.18, rows = 8, cols = 16 }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, ${cell}px)`, gridAutoRows: `${cell}px`, opacity }}>
      {Array.from({ length: rows * cols }).map((_, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <StarRub size={cell * 0.55} color={color} />
        </div>
      ))}
    </div>
  );
}

// Halal seal — stamp-style circular badge with multilingual word.
function HalalSeal({ size = 120, ink = '#0F4F3D', stroke = 2 }) {
  const s = size, c = s / 2;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${s} ${s}`}>
      <circle cx={c} cy={c} r={s / 2 - stroke} fill="none" stroke={ink} strokeWidth={stroke} />
      <circle cx={c} cy={c} r={s / 2 - stroke * 4} fill="none" stroke={ink} strokeWidth={1} />
      <g transform={`translate(${c} ${c})`}>
        <text textAnchor="middle" y="-14" fontFamily="'Noto Naskh Arabic', serif" fontSize={s * 0.32} fill={ink}>حلال</text>
        <text textAnchor="middle" y="22" fontFamily="'Geist Mono', monospace" fontSize={s * 0.10} letterSpacing="2" fill={ink}>HALAL · ХӘЛӘЛ</text>
        <text textAnchor="middle" y="36" fontFamily="'Geist Mono', monospace" fontSize={s * 0.075} letterSpacing="1" fill={ink}>ISO 22000 · HACCP</text>
      </g>
    </svg>
  );
}

// Striped placeholder — calls out where a real photo/render belongs.
function Placeholder({ label = 'product shot', ink = '#0C1411', bg = '#EFEAE1', minH = 240, ratio, style = {} }) {
  const stripes = `repeating-linear-gradient(135deg, ${bg} 0px, ${bg} 14px, ${ink}0F 14px, ${ink}0F 16px)`;
  const aspectRatio = ratio || undefined;
  return (
    <div style={{
      position: 'relative', width: '100%', minHeight: minH, aspectRatio,
      background: stripes, color: ink,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: '"Geist Mono", ui-monospace, monospace', fontSize: 11, letterSpacing: '0.12em',
      textTransform: 'uppercase', overflow: 'hidden', ...style,
    }}>
      <span style={{ padding: '6px 10px', background: bg, border: `1px solid ${ink}22`, borderRadius: 2 }}>
        ⌬ {label}
      </span>
    </div>
  );
}

// Language pill control. The active button is filled with `ink`.
function LangPills({ value, onChange, ink = '#0C1411', muted = 'rgba(12,20,17,0.5)', size = 'sm' }) {
  const pad = size === 'sm' ? '4px 10px' : '8px 14px';
  const fs  = size === 'sm' ? 11 : 13;
  return (
    <div style={{ display: 'inline-flex', gap: 0, fontFamily: '"Geist Mono", monospace', fontSize: fs, letterSpacing: '0.08em' }}>
      {['tt', 'ru', 'en'].map((l, i) => (
        <button key={l}
          onClick={() => onChange && onChange(l)}
          style={{
            padding: pad, border: `1px solid ${ink}33`,
            borderLeftWidth: i === 0 ? 1 : 0,
            background: value === l ? ink : 'transparent',
            color: value === l ? '#fff' : muted,
            cursor: 'pointer', textTransform: 'uppercase',
            fontFamily: 'inherit', fontSize: 'inherit', letterSpacing: 'inherit',
            transition: 'background .12s, color .12s',
          }}>
          {l}
        </button>
      ))}
    </div>
  );
}

// Decorative band background made of CSS gradients — a rope of dots/dashes.
function OrnamentBand({ color = '#C9A961', height = 22, opacity = 0.7 }) {
  return (
    <div style={{
      height, opacity,
      backgroundImage: [
        `radial-gradient(circle, ${color} 1.5px, transparent 2px)`,
        `radial-gradient(circle, ${color} 2.5px, transparent 3px)`,
      ].join(','),
      backgroundSize: '12px 12px, 36px 36px',
      backgroundPosition: '0 50%, 6px 50%',
      backgroundRepeat: 'repeat-x',
    }} />
  );
}

// Brand wordmark — kept as plain styled text so it edits cleanly. Two
// weights stitched together with a thin dot, so "PEPPERONI.TATAR" reads
// as a single composed mark.
function Wordmark({ color = '#0C1411', size = 18, weight = 600 }) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'baseline', gap: 0, color,
      fontFamily: '"Geist", system-ui, sans-serif', fontSize: size, fontWeight: weight,
      letterSpacing: '-0.02em' }}>
      <span>PEPPERONI</span>
      <span style={{ opacity: 0.5, margin: '0 1px' }}>.</span>
      <span style={{ fontWeight: weight + 100 }}>TATAR</span>
    </div>
  );
}

Object.assign(window, {
  T, t, LangCtx, useLang, useT,
  PRODUCTS, CATS,
  StarRub, Tulip, DiamondStrip, StarTile, HalalSeal,
  Placeholder, LangPills, OrnamentBand, Wordmark,
});
