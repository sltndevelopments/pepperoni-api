// v4-catalog.jsx — "CATALOG"
// White B2B / spec-sheet density. 24 SKU laid out on one page.
// Functional procurement view: filter rail, MOQs, packaging, port terms.

function V4Catalog() {
  const tx = useT();
  const lang = useLang();
  const ink   = '#0C1411';
  const bg    = '#FAFAF7';
  const card  = '#FFFFFF';
  const rule  = 'rgba(12,20,17,0.10)';
  const muted = 'rgba(12,20,17,0.55)';
  const emerald = '#0F4F3D';
  const gold = '#A0823F';

  const wide = { paddingLeft: 56, paddingRight: 56 };
  const catKey = { pep:'catPepperoni', hd:'catHotdog', ham:'catHam', bur:'catBurger' };

  return (
    <div lang={lang} style={{ background: bg, color: ink, width: '100%',
      fontFamily: '"Geist", system-ui, sans-serif', fontSize: 13, lineHeight: 1.5 }}>

      {/* ────────── BANNER strip ────────── */}
      <div style={{ background: emerald, color: '#fff', padding: '8px 56px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.12em',
        textTransform: 'uppercase' }}>
        <span>● B2B-ОТДЕЛ ОТКРЫТ · ПН–СБ 09:00–19:00 KZN</span>
        <span>FOB · CIF · EXW · 18 PORTS</span>
        <span>{tx('badgeHalal')}</span>
      </div>

      {/* ────────── HEADER ────────── */}
      <header style={{ ...wide, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '20px 56px', borderBottom: `1px solid ${rule}`, background: card }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <Wordmark color={ink} size={17} weight={600} />
          <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, color: muted,
            letterSpacing: '0.12em' }}>{tx('brandTag').toUpperCase()}</span>
        </div>
        <nav style={{ display: 'flex', gap: 28, fontSize: 13, color: ink }}>
          <span style={{ fontWeight: 500, borderBottom: `2px solid ${emerald}`, paddingBottom: 2 }}>
            {tx('secCatalog')}
          </span>
          <span style={{ color: muted }}>{tx('secLogi')}</span>
          <span style={{ color: muted }}>{tx('secCert')}</span>
          <span style={{ color: muted }}>{tx('secProcess')}</span>
          <span style={{ color: muted }}>{tx('secContact')}</span>
        </nav>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <LangPills value={lang} ink={ink} muted={muted} />
          <button style={{ padding: '9px 18px', background: emerald, color: '#fff', border: 'none',
            fontFamily: 'inherit', fontSize: 12, cursor: 'pointer', letterSpacing: '0.04em' }}>
            {tx('ctaWholesale')}
          </button>
        </div>
      </header>

      {/* ────────── COMPACT HERO ────────── */}
      <section style={{ ...wide, padding: '56px 56px 44px', borderBottom: `1px solid ${rule}` }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 56, alignItems: 'end' }}>
          <div>
            <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.18em',
              textTransform: 'uppercase', color: gold, marginBottom: 18 }}>
              {tx('secCatalog')} · 2026 · 24 SKU
            </div>
            <h1 style={{ fontWeight: 600, fontSize: 64, lineHeight: 0.98, margin: 0,
              letterSpacing: '-0.035em' }}>
              {lang === 'tt' && <>Татарстаннан хәләл ит — <span style={{ color: emerald }}>күмәртә</span>, контейнерлар белән.</>}
              {lang === 'ru' && <>Халяль из Татарстана — <span style={{ color: emerald }}>оптом</span>, контейнерами.</>}
              {lang === 'en' && <>Halal from Tatarstan — <span style={{ color: emerald }}>at wholesale</span>, by the container.</>}
            </h1>
            <p style={{ marginTop: 22, fontSize: 14, color: muted, lineHeight: 1.6, maxWidth: 660,
              textWrap: 'pretty' }}>{tx('heroSub')}</p>
          </div>
          {/* mini stats */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, background: rule,
            border: `1px solid ${rule}` }}>
            {[
              ['12 000', 'statTons'],
              ['18',     'statCountries'],
              ['24',     'statSku'],
              ['11',     'statYears'],
            ].map(([n, k]) => (
              <div key={k} style={{ background: card, padding: '18px 20px' }}>
                <div style={{ fontSize: 32, fontWeight: 600, letterSpacing: '-0.025em', lineHeight: 1 }}>{n}</div>
                <div style={{ marginTop: 6, fontFamily: '"Geist Mono", monospace', fontSize: 10,
                  letterSpacing: '0.14em', color: muted, textTransform: 'uppercase' }}>{tx(k)}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ────────── CATEGORY TABS ────────── */}
      <section style={{ ...wide, padding: '20px 56px', borderBottom: `1px solid ${rule}`, background: card,
        position: 'sticky', top: 0, zIndex: 2 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 6 }}>
            <button style={{ padding: '8px 14px', background: ink, color: bg, border: 'none',
              fontFamily: 'inherit', fontSize: 12, cursor: 'pointer', letterSpacing: '0.02em' }}>
              {lang === 'tt' ? 'Барысы да' : lang === 'ru' ? 'Все' : 'All'} · 24
            </button>
            {['pep', 'hd', 'ham', 'bur'].map(c => (
              <button key={c} style={{ padding: '8px 14px', background: 'transparent',
                color: muted, border: `1px solid ${rule}`, fontFamily: 'inherit', fontSize: 12,
                cursor: 'pointer', letterSpacing: '0.02em' }}>
                {tx(catKey[c])} · 6
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 14, fontFamily: '"Geist Mono", monospace', fontSize: 11,
            letterSpacing: '0.12em', color: muted, alignItems: 'center' }}>
            <span>SORT · MOQ ↑</span>
            <span>·</span>
            <span>VIEW · GRID</span>
          </div>
        </div>
      </section>

      {/* ────────── CATALOG GRID ────────── */}
      <section style={{ ...wide, padding: '32px 56px 64px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
          {PRODUCTS.map((p, i) => {
            const cat = CATS[p.cat];
            return (
              <article key={p.id} style={{ background: card, border: `1px solid ${rule}`,
                display: 'flex', flexDirection: 'column' }}>
                <Placeholder label={`${p.id}`} ink={ink} bg="#EFEAE1" minH={180} />
                <div style={{ padding: '14px 16px 16px', display: 'flex', flexDirection: 'column',
                  gap: 10, flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 6, height: 6, background: cat.color, borderRadius: 1 }} />
                    <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 10,
                      letterSpacing: '0.14em', color: muted, textTransform: 'uppercase' }}>
                      {tx(cat.key)} · № {String(i + 1).padStart(2, '0')}
                    </span>
                  </div>
                  <div style={{ fontSize: 15, fontWeight: 500, letterSpacing: '-0.01em',
                    color: ink, lineHeight: 1.25 }}>{p.name[lang] || p.name.ru}</div>
                  <div style={{ marginTop: 'auto', display: 'grid', gridTemplateColumns: '1fr 1fr',
                    rowGap: 6, columnGap: 8, fontFamily: '"Geist Mono", monospace', fontSize: 10,
                    color: muted, letterSpacing: '0.06em', borderTop: `1px solid ${rule}`,
                    paddingTop: 10 }}>
                    <span>{tx('specWeight')}</span><span style={{ textAlign: 'right', color: ink }}>{p.w}</span>
                    <span>{tx('specMoq')}</span>   <span style={{ textAlign: 'right', color: ink }}>{p.moq}</span>
                    <span>{tx('specShelf')}</span> <span style={{ textAlign: 'right', color: ink }}>{p.shelf}</span>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {/* ────────── LOGISTICS ────────── */}
      <section style={{ ...wide, padding: '64px 56px', background: '#EFE9D9', borderTop: `1px solid ${rule}` }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 48, alignItems: 'start' }}>
          <div>
            <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.18em',
              textTransform: 'uppercase', color: gold, marginBottom: 16 }}>{tx('secLogi')}</div>
            <h2 style={{ fontSize: 44, fontWeight: 600, letterSpacing: '-0.03em', margin: 0,
              lineHeight: 1 }}>{tx('exportTitle')}</h2>
            <p style={{ marginTop: 18, fontSize: 14, color: muted, lineHeight: 1.6,
              textWrap: 'pretty', maxWidth: 540 }}>
              {tx('countries')}
            </p>
            <div style={{ display: 'flex', gap: 8, marginTop: 26, flexWrap: 'wrap' }}>
              {['EXW Kazan', 'FCA Lamb`s Border', 'FOB St-Petersburg', 'CIF Jebel Ali', 'CIF Port Klang', 'CIF Tanjung Priok'].map(c => (
                <span key={c} style={{ padding: '6px 10px', background: card, border: `1px solid ${rule}`,
                  fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.04em' }}>{c}</span>
              ))}
            </div>
          </div>

          <div style={{ background: card, border: `1px solid ${rule}`, padding: 0 }}>
            <div style={{ padding: '18px 22px', borderBottom: `1px solid ${rule}`,
              display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 500 }}>{tx('formSend')}</span>
              <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 10,
                letterSpacing: '0.14em', color: muted }}>~ 2 H REPLY</span>
            </div>
            <div style={{ padding: '22px', display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                ['formCompany', 'Halal Foods FZE'],
                ['formCountry', 'United Arab Emirates'],
                ['formVolume',  '40 t / mo · containers'],
                ['formProduct', 'Pepperoni · Burger patties'],
                ['formEmail',   'procurement@halalfoods.ae'],
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 10,
                    letterSpacing: '0.14em', color: muted, textTransform: 'uppercase' }}>{tx(k)}</span>
                  <div style={{ padding: '10px 12px', border: `1px solid ${rule}`,
                    background: '#FBFAF6', fontSize: 13 }}>{v}</div>
                </div>
              ))}
              <button style={{ marginTop: 6, padding: '14px 16px', background: emerald, color: '#fff',
                border: 'none', fontFamily: 'inherit', fontSize: 13, cursor: 'pointer',
                letterSpacing: '0.04em' }}>{tx('formSend')} →</button>
            </div>
          </div>
        </div>
      </section>

      {/* ────────── CERTS / FOOTER ────────── */}
      <section style={{ ...wide, padding: '40px 56px', display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', gap: 24, borderTop: `1px solid ${rule}` }}>
        <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
          <HalalSeal size={56} ink={emerald} />
          <div>
            <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.14em',
              textTransform: 'uppercase', color: muted }}>{tx('secCert')}</div>
            <div style={{ marginTop: 4, fontSize: 13 }}>
              {tx('badgeHalal')} · ISO 22000 · HACCP · GMP+ · ROSPOTREBNADZOR
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 20, fontFamily: '"Geist Mono", monospace', fontSize: 11,
          letterSpacing: '0.12em', color: muted }}>
          <span>+7 843 000 00 00</span>
          <span>trade@pepperoni.tatar</span>
          <span>{tx('loc').toUpperCase()}</span>
        </div>
      </section>

      <footer style={{ ...wide, padding: '20px 56px', borderTop: `1px solid ${rule}`,
        display: 'flex', justifyContent: 'space-between',
        fontFamily: '"Geist Mono", monospace', fontSize: 10, letterSpacing: '0.14em',
        color: muted, textTransform: 'uppercase' }}>
        <span>© 2026 PEPPERONI.TATAR LLC</span>
        <span>HALAL CERT. № TR-2024-0118</span>
        <span>v.2026.05</span>
      </footer>
    </div>
  );
}

window.V4Catalog = V4Catalog;
