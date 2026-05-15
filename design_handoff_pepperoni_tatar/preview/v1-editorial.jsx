// v1-editorial.jsx — "EDITORIAL"
// Cream / quiet luxury / Blue Bottle × Aesop × Arabica.
// Pepperoni.tatar treated like a craft good in a curated catalogue.

function V1Editorial() {
  const tx = useT();
  const lang = useLang();
  const cream = '#F4EFE6';
  const ink = '#0C1411';
  const muted = 'rgba(12,20,17,0.55)';
  const rule = 'rgba(12,20,17,0.12)';
  const gold = '#9C7A38';
  const emerald = '#0F4F3D';

  // Pick 4 hero categories
  const heroCats = ['pep', 'hd', 'ham', 'bur'];
  const catKeys = { pep: 'catPepperoni', hd: 'catHotdog', ham: 'catHam', bur: 'catBurger' };
  const wide = { paddingLeft: 80, paddingRight: 80 };

  return (
    <div lang={lang} style={{
      background: cream, color: ink, width: '100%',
      fontFamily: '"Geist", system-ui, sans-serif',
      fontSize: 14, lineHeight: 1.5,
      letterSpacing: '-0.005em',
    }}>
      {/* ────────── NAV ────────── */}
      <header style={{ ...wide, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '32px 80px', borderBottom: `1px solid ${rule}` }}>
        <Wordmark color={ink} size={17} weight={500} />
        <nav style={{ display: 'flex', gap: 38, fontSize: 13, color: muted }}>
          <span>{tx('secProducts')}</span>
          <span>{tx('secProcess')}</span>
          <span>{tx('secLogi')}</span>
          <span>{tx('secCert')}</span>
        </nav>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <LangPills value={lang} ink={ink} muted={muted} />
          <a style={{ fontSize: 13, color: ink, textDecoration: 'underline', textUnderlineOffset: 4 }}>
            {tx('ctaContact')} →
          </a>
        </div>
      </header>

      {/* ────────── HERO ────────── */}
      <section style={{ ...wide, paddingTop: 120, paddingBottom: 80, display: 'grid',
        gridTemplateColumns: '0.9fr 1.1fr', gap: 80, alignItems: 'end' }}>
        <div>
          <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.16em',
            textTransform: 'uppercase', color: muted, marginBottom: 32 }}>
            {String(tx('heroOver')).toUpperCase()}
          </div>
          <h1 style={{
            fontFamily: '"Instrument Serif", "Cormorant Garamond", serif',
            fontWeight: 400, fontSize: 108, lineHeight: 0.92, letterSpacing: '-0.025em',
            margin: 0, color: ink,
          }}>
            <div>{tx('heroH1a')}</div>
            <div style={{ fontStyle: 'italic', color: emerald }}>{tx('heroH1b')}</div>
            <div>{tx('heroH1c')}</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 24 }}>
              <span>{tx('heroH1d')}</span>
              <StarRub size={36} color={gold} />
            </div>
          </h1>
          <p style={{ fontSize: 15, color: muted, lineHeight: 1.55, maxWidth: 420, marginTop: 40, textWrap: 'pretty' }}>
            {tx('heroSub')}
          </p>
          <div style={{ display: 'flex', gap: 20, marginTop: 36, alignItems: 'center' }}>
            <button style={{
              padding: '14px 22px', border: 'none', background: ink, color: cream,
              fontFamily: 'inherit', fontSize: 13, letterSpacing: '0.02em', cursor: 'pointer',
            }}>{tx('ctaWholesale')}</button>
            <a style={{ fontSize: 13, color: ink, textDecoration: 'underline', textUnderlineOffset: 4 }}>
              {tx('ctaCatalog')}
            </a>
          </div>
        </div>

        {/* hero photo card */}
        <div style={{ position: 'relative' }}>
          <Placeholder label="pepperoni · hero shot" ink={ink} bg="#E7DFD0" minH={580} />
          <div style={{ position: 'absolute', top: 24, left: 24, fontFamily: '"Geist Mono", monospace',
            fontSize: 11, letterSpacing: '0.12em', color: ink, background: cream, padding: '4px 8px' }}>
            № 001 · CLASSIC
          </div>
          <div style={{ position: 'absolute', bottom: -32, right: -32 }}>
            <HalalSeal size={112} ink={emerald} />
          </div>
        </div>
      </section>

      {/* ────────── STATS RULE ────────── */}
      <section style={{ ...wide, padding: '56px 80px', borderTop: `1px solid ${rule}`, borderBottom: `1px solid ${rule}` }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 40 }}>
          {[
            ['12,000', 'statTons'],
            ['18',     'statCountries'],
            ['24',     'statSku'],
            ['11',     'statYears'],
          ].map(([num, key]) => (
            <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div style={{ fontFamily: '"Instrument Serif", serif', fontSize: 56, lineHeight: 0.95,
                letterSpacing: '-0.02em' }}>{num}</div>
              <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.14em',
                textTransform: 'uppercase', color: muted }}>{tx(key)}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ────────── PRODUCT GRID ────────── */}
      <section style={{ ...wide, paddingTop: 96, paddingBottom: 96 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 56 }}>
          <h2 style={{ fontFamily: '"Instrument Serif", serif', fontWeight: 400, fontSize: 56,
            margin: 0, letterSpacing: '-0.02em' }}>{tx('secProducts')}</h2>
          <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: muted }}>04 / категории · 24 / SKU</div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 24 }}>
          {heroCats.map((c, i) => {
            const sample = PRODUCTS.filter(p => p.cat === c)[0];
            return (
              <article key={c}>
                <Placeholder label={`${c} · still life`} ink={ink} bg="#E7DFD0" minH={420} />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                  marginTop: 18, paddingBottom: 12, borderBottom: `1px solid ${rule}` }}>
                  <div style={{ fontFamily: '"Instrument Serif", serif', fontSize: 22, letterSpacing: '-0.01em' }}>
                    {tx(catKeys[c])}
                  </div>
                  <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.12em',
                    color: muted }}>{`0${i + 1}`}</div>
                </div>
                <ul style={{ listStyle: 'none', padding: 0, margin: '12px 0 0', display: 'flex',
                  flexDirection: 'column', gap: 4, fontSize: 12, color: muted, lineHeight: 1.7 }}>
                  {PRODUCTS.filter(p => p.cat === c).slice(0, 5).map(p => (
                    <li key={p.id} style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>{p.name[lang] || p.name.ru}</span>
                      <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 10 }}>{p.w}</span>
                    </li>
                  ))}
                  <li style={{ color: ink, marginTop: 4, fontSize: 11, letterSpacing: '0.08em',
                    fontFamily: '"Geist Mono", monospace', textTransform: 'uppercase' }}>
                    +1 {lang === 'en' ? 'more SKU →' : lang === 'tt' ? 'тагы 1 SKU →' : 'ещё 1 SKU →'}
                  </li>
                </ul>
              </article>
            );
          })}
        </div>
      </section>

      {/* ────────── EDITORIAL QUOTE / MANIFESTO ────────── */}
      <section style={{ ...wide, padding: '120px 80px', borderTop: `1px solid ${rule}`,
        display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: 80, alignItems: 'center' }}>
        <div>
          <Tulip size={120} color={gold} />
          <div style={{ marginTop: 24, fontFamily: '"Geist Mono", monospace', fontSize: 11,
            letterSpacing: '0.16em', textTransform: 'uppercase', color: muted }}>
            {tx('manifestoLine')}
          </div>
        </div>
        <blockquote style={{ margin: 0,
          fontFamily: '"Instrument Serif", serif', fontWeight: 400, fontSize: 44, lineHeight: 1.15,
          letterSpacing: '-0.015em', color: ink }}>
          {lang === 'tt' &&
            <>«Без татарның ит сәнгатен — заводлар тизлеге белән сүзсез эшләп бирәбез. <em style={{ color: emerald }}>Хәләл</em>, тулы документ белән, фурлар һәм контейнерлар белән.»</>}
          {lang === 'ru' &&
            <>«Мы делаем татарское мясное ремесло — на скорости заводов, без лишних слов. <em style={{ color: emerald }}>Халяль</em>, под полный документ, фурами и контейнерами.»</>}
          {lang === 'en' &&
            <>“We do Tatar meat-craft at factory speed, with the paperwork. <em style={{ color: emerald }}>Halal</em>, end-to-end, by the truck and the container.”</>}
        </blockquote>
      </section>

      {/* ────────── PROCESS ────────── */}
      <section style={{ ...wide, padding: '96px 80px', background: '#EDE7DA' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 56 }}>
          <h2 style={{ fontFamily: '"Instrument Serif", serif', fontWeight: 400, fontSize: 48,
            margin: 0, letterSpacing: '-0.02em' }}>{tx('secProcess')}</h2>
          <DiamondStrip color={gold} count={26} height={14} />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 48 }}>
          {[1, 2, 3].map(i => (
            <article key={i} style={{ borderTop: `1px solid ${ink}33`, paddingTop: 28 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
                <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11,
                  letterSpacing: '0.14em', color: muted }}>STEP · 0{i}</span>
                <StarRub size={14} color={gold} />
              </div>
              <h3 style={{ fontFamily: '"Instrument Serif", serif', fontWeight: 400, fontSize: 30,
                margin: '0 0 16px', letterSpacing: '-0.01em' }}>{tx(`step${i}Title`)}</h3>
              <p style={{ fontSize: 14, color: muted, lineHeight: 1.55, textWrap: 'pretty' }}>{tx(`step${i}Body`)}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ────────── FOOTER ────────── */}
      <footer style={{ ...wide, padding: '64px 80px 56px', background: ink, color: cream }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr', gap: 48, alignItems: 'start' }}>
          <div>
            <Wordmark color={cream} size={20} weight={500} />
            <div style={{ marginTop: 12, fontSize: 12, color: 'rgba(244,239,230,0.55)' }}>
              {tx('brandTag')} · {tx('loc')}
            </div>
            <div style={{ marginTop: 28, fontFamily: '"Geist Mono", monospace', fontSize: 11,
              letterSpacing: '0.12em', color: 'rgba(244,239,230,0.6)' }}>
              SALES · +7 843 000 00 00 · trade@pepperoni.tatar
            </div>
          </div>
          {['secProducts', 'secLogi', 'secCert'].map(s => (
            <div key={s}>
              <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.14em',
                color: 'rgba(244,239,230,0.5)', marginBottom: 14 }}>{String(tx(s)).toUpperCase()}</div>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8,
                fontSize: 13, color: cream }}>
                <li>—</li><li>—</li><li>—</li>
              </ul>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginTop: 56, paddingTop: 24, borderTop: '1px solid rgba(244,239,230,0.15)',
          fontFamily: '"Geist Mono", monospace', fontSize: 10, letterSpacing: '0.14em',
          color: 'rgba(244,239,230,0.4)' }}>
          <span>© 2026 PEPPERONI.TATAR LLC · {tx('loc').toUpperCase()}</span>
          <span>ISO 22000 · HACCP · HALAL CERT. № TR-2024-0118</span>
        </div>
      </footer>
    </div>
  );
}

window.V1Editorial = V1Editorial;
