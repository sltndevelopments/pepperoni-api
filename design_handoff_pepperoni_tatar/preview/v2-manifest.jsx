// v2-manifest.jsx — "MANIFEST"
// Tesla / Bang-Olufsen / industrial spec sheet.
// Black canvas, gigantic type, monospace metrics, emerald accent.

function V2Manifest() {
  const tx = useT();
  const lang = useLang();
  const ink   = '#FAFAF7';
  const bg    = '#070908';
  const carbon= '#11140F';
  const emerald = '#1F8A60';
  const gold    = '#C9A961';
  const muted = 'rgba(250,250,247,0.45)';
  const rule  = 'rgba(250,250,247,0.12)';

  const wide = { paddingLeft: 64, paddingRight: 64 };

  return (
    <div lang={lang} style={{
      background: bg, color: ink, width: '100%',
      fontFamily: '"Geist", system-ui, sans-serif', fontSize: 14, lineHeight: 1.5,
    }}>
      {/* ────────── NAV ────────── */}
      <header style={{ ...wide, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '22px 64px', borderBottom: `1px solid ${rule}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Wordmark color={ink} size={15} weight={600} />
          <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 10, letterSpacing: '0.18em',
            color: emerald, padding: '3px 7px', border: `1px solid ${emerald}77` }}>● ONLINE · KZN-01</span>
        </div>
        <nav style={{ display: 'flex', gap: 28, fontSize: 12, color: muted,
          fontFamily: '"Geist Mono", monospace', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          <span>{tx('secProducts')}</span>
          <span>{tx('secProcess')}</span>
          <span>{tx('secLogi')}</span>
          <span>{tx('secCert')}</span>
        </nav>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <LangPills value={lang} ink={ink} muted={muted} />
          <button style={{ padding: '9px 16px', border: 'none', background: emerald, color: '#fff',
            fontFamily: 'inherit', fontSize: 12, letterSpacing: '0.04em', cursor: 'pointer' }}>
            {tx('ctaWholesale')}
          </button>
        </div>
      </header>

      {/* ────────── HERO ────────── */}
      <section style={{ position: 'relative', padding: '110px 64px 0', minHeight: 760, overflow: 'hidden' }}>
        {/* corner annotations */}
        <div style={{ position: 'absolute', top: 28, left: 64, fontFamily: '"Geist Mono", monospace',
          fontSize: 11, color: muted, letterSpacing: '0.14em' }}>BLOCK · 01 / HERO</div>
        <div style={{ position: 'absolute', top: 28, right: 64, fontFamily: '"Geist Mono", monospace',
          fontSize: 11, color: muted, letterSpacing: '0.14em' }}>55.7887° N · 49.1221° E</div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 40, alignItems: 'end' }}>
          <h1 style={{
            margin: 0, fontWeight: 700, fontSize: 196, lineHeight: 0.86,
            letterSpacing: '-0.05em', textTransform: 'uppercase',
          }}>
            <div>PEPPERONI</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 18 }}>
              <span style={{ color: emerald }}>.</span><span>TATAR</span>
            </div>
          </h1>
          <div style={{ textAlign: 'right', minWidth: 280 }}>
            <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.14em',
              color: muted, textTransform: 'uppercase', marginBottom: 14 }}>{tx('heroOver')}</div>
            <div style={{ fontSize: 14, color: ink, lineHeight: 1.5, maxWidth: 360, marginLeft: 'auto',
              textWrap: 'pretty' }}>
              {tx('heroSub')}
            </div>
            <div style={{ display: 'flex', gap: 14, justifyContent: 'flex-end', marginTop: 28 }}>
              <button style={{ padding: '13px 22px', border: `1px solid ${ink}`, background: 'transparent',
                color: ink, fontFamily: 'inherit', fontSize: 12, cursor: 'pointer', letterSpacing: '0.04em' }}>
                {tx('ctaCatalog')}
              </button>
              <button style={{ padding: '13px 22px', border: 'none', background: ink, color: bg,
                fontFamily: 'inherit', fontSize: 12, cursor: 'pointer', letterSpacing: '0.04em' }}>
                {tx('ctaWholesale')}
              </button>
            </div>
          </div>
        </div>

        {/* spec rail */}
        <div style={{ marginTop: 88, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
          borderTop: `1px solid ${rule}`, borderBottom: `1px solid ${rule}` }}>
          {[
            ['12 000', 'statTons'],
            ['18',     'statCountries'],
            ['24',     'statSku'],
            ['100%',   'statHalal'],
          ].map(([n, k], i) => (
            <div key={k} style={{ padding: '32px 28px',
              borderLeft: i === 0 ? 'none' : `1px solid ${rule}` }}>
              <div style={{ fontSize: 64, fontWeight: 600, letterSpacing: '-0.04em', lineHeight: 1 }}>
                {n}
              </div>
              <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, color: muted,
                letterSpacing: '0.14em', textTransform: 'uppercase', marginTop: 10 }}>{tx(k)}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ────────── PRODUCT MATRIX ────────── */}
      <section style={{ ...wide, padding: '120px 64px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 56 }}>
          <h2 style={{ fontSize: 56, fontWeight: 700, letterSpacing: '-0.035em', margin: 0,
            textTransform: 'uppercase' }}>{tx('secProducts')}</h2>
          <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, color: muted,
            letterSpacing: '0.14em' }}>04 LINES · 24 SKU</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr', gap: 1, background: rule,
          border: `1px solid ${rule}` }}>
          {['pep', 'hd', 'ham', 'bur'].map((c, i) => {
            const catKey = { pep:'catPepperoni', hd:'catHotdog', ham:'catHam', bur:'catBurger' }[c];
            const skus = PRODUCTS.filter(p => p.cat === c);
            const featured = i === 0;
            return (
              <article key={c} style={{ background: carbon, padding: 28, minHeight: featured ? 520 : 520,
                display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.14em',
                    color: muted }}>MODEL · 0{i + 1}</span>
                  {featured && <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 10,
                    color: emerald, letterSpacing: '0.18em', padding: '3px 7px', border: `1px solid ${emerald}77` }}>
                    ● FLAGSHIP</span>}
                </div>
                <h3 style={{ marginTop: 14, marginBottom: featured ? 24 : 18, fontSize: featured ? 38 : 26,
                  fontWeight: 600, letterSpacing: '-0.025em', lineHeight: 1.05 }}>{tx(catKey)}</h3>
                <Placeholder label={`${c} · render`} ink={ink} bg="#1A1D17" minH={featured ? 220 : 180} />
                <div style={{ marginTop: 'auto', paddingTop: 18,
                  fontFamily: '"Geist Mono", monospace', fontSize: 11, color: muted, lineHeight: 1.7 }}>
                  {skus.slice(0, 4).map(p => (
                    <div key={p.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        color: 'rgba(250,250,247,0.7)' }}>{p.name[lang] || p.name.ru}</span>
                      <span>{p.w}</span>
                    </div>
                  ))}
                  <div style={{ marginTop: 10, color: emerald, letterSpacing: '0.12em' }}>
                    + {skus.length - 4} {lang === 'en' ? 'more →' : lang === 'tt' ? 'тагы →' : 'ещё →'}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {/* ────────── MANIFESTO ────────── */}
      <section style={{ ...wide, padding: '60px 64px 120px' }}>
        <div style={{ borderTop: `1px solid ${rule}`, paddingTop: 60 }}>
          <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.16em',
            color: emerald, textTransform: 'uppercase', marginBottom: 28 }}>
            BLOCK · 04 / MANIFEST
          </div>
          <p style={{ fontSize: 72, fontWeight: 600, letterSpacing: '-0.035em', lineHeight: 1.02,
            margin: 0, maxWidth: 1180, textWrap: 'pretty' }}>
            {lang === 'tt' && <>«Без — Татарстаннан килгән <span style={{ color: emerald }}>хәләл индустриясе</span>. Бер ит, бер сүз. Тулы документ, реф-фурлар, көн саен.»</>}
            {lang === 'ru' && <>«Мы — <span style={{ color: emerald }}>халяль-индустрия</span> из Татарстана. Одно мясо. Одно слово. Полный документ, реф-фуры, каждый день.»</>}
            {lang === 'en' && <>“We are <span style={{ color: emerald }}>halal industry</span>, out of Tatarstan. One meat. One word. Full docs, reefer trucks, every day.”</>}
          </p>
        </div>
      </section>

      {/* ────────── LOGISTICS ────────── */}
      <section style={{ ...wide, padding: '0 64px 120px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 64, alignItems: 'start' }}>
          <div>
            <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.16em',
              color: muted, textTransform: 'uppercase' }}>BLOCK · 05 / LOGISTICS</span>
            <h2 style={{ fontSize: 56, fontWeight: 700, letterSpacing: '-0.035em', margin: '14px 0 24px',
              textTransform: 'uppercase' }}>{tx('exportTitle')}</h2>
            <p style={{ fontSize: 15, color: 'rgba(250,250,247,0.7)', maxWidth: 460, lineHeight: 1.55,
              textWrap: 'pretty' }}>{tx('countries')}</p>

            <div style={{ marginTop: 36, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1,
              background: rule, border: `1px solid ${rule}` }}>
              {[
                ['logiTruck',     '20 t'],
                ['logiContainer', '24 t'],
                ['logiPallet',    '0.5–5 t'],
                ['logiPort',      'FOB / CIF'],
              ].map(([k, v]) => (
                <div key={k} style={{ padding: '20px 22px', background: carbon,
                  display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontSize: 14 }}>{tx(k)}</span>
                  <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, color: emerald }}>{v}</span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ position: 'relative' }}>
            <Placeholder label="export map · 18 markets" ink={ink} bg="#1A1D17" minH={460} />
            <div style={{ position: 'absolute', top: 16, right: 16, padding: '6px 10px',
              background: emerald, color: '#fff', fontFamily: '"Geist Mono", monospace', fontSize: 10,
              letterSpacing: '0.14em' }}>LIVE · 14 IN TRANSIT</div>
          </div>
        </div>
      </section>

      {/* ────────── BIG CTA ────────── */}
      <section style={{ ...wide, padding: '0 64px 0' }}>
        <div style={{ background: emerald, color: '#fff', padding: '72px 64px',
          display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 48, alignItems: 'center' }}>
          <div>
            <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.18em',
              opacity: 0.8, marginBottom: 14 }}>BLOCK · 06 / TRADE DESK</div>
            <h3 style={{ fontSize: 56, fontWeight: 700, letterSpacing: '-0.035em', margin: 0,
              textTransform: 'uppercase', lineHeight: 1 }}>
              {lang === 'tt' && <>Сату бүлеге белән<br/>тоташыгыз →</>}
              {lang === 'ru' && <>Свяжитесь с<br/>отделом продаж →</>}
              {lang === 'en' && <>Speak to<br/>our trade desk →</>}
            </h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, fontFamily: '"Geist Mono", monospace',
            fontSize: 13, letterSpacing: '0.04em' }}>
            <div>+7 843 000 00 00</div>
            <div>trade@pepperoni.tatar</div>
            <div>WhatsApp · Telegram</div>
            <button style={{ marginTop: 14, padding: '14px 22px', background: '#fff', color: emerald,
              border: 'none', fontFamily: 'inherit', fontSize: 13, letterSpacing: '0.04em', cursor: 'pointer' }}>
              {tx('formSend')} →
            </button>
          </div>
        </div>
      </section>

      {/* ────────── FOOTER ────────── */}
      <footer style={{ ...wide, padding: '40px 64px', display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', fontFamily: '"Geist Mono", monospace', fontSize: 10, letterSpacing: '0.14em',
        color: muted, textTransform: 'uppercase' }}>
        <span>© 2026 PEPPERONI.TATAR LLC</span>
        <span>ISO 22000 · HACCP · HALAL CERT. № TR-2024-0118</span>
        <span>{tx('loc').toUpperCase()}</span>
      </footer>
    </div>
  );
}

window.V2Manifest = V2Manifest;
