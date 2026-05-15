// v5-earth.jsx — "BUTCHER BLOCK"
// Warm terracotta / natural oak / farm-to-fork halal.
// Premium butcher shop meets Scandinavian simplicity.

function V5Earth() {
  const tx = useT();
  const lang = useLang();
  const cream    = '#FBF9F4';
  const ink      = '#1C1008';
  const muted    = 'rgba(28,16,8,0.5)';
  const rule     = 'rgba(28,16,8,0.08)';
  const terracotta = '#C4643E';
  const terracottaLight = '#F3EAE0';
  const sage     = '#7A8B5E';
  const sageMuted = 'rgba(122,139,94,0.25)';
  const espresso = '#120A05';
  const cardBg   = '#FFFFFF';

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
        padding: '24px 80px', borderBottom: `1px solid ${rule}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <Wordmark color={ink} size={17} weight={600} />
          <span style={{ width: 1, height: 18, background: rule }} />
          <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 10, letterSpacing: '0.14em',
            color: terracotta, textTransform: 'uppercase' }}>{tx('brandTag')}</span>
        </div>
        <nav style={{ display: 'flex', gap: 32, fontSize: 13, color: muted }}>
          <span>{tx('secProducts')}</span>
          <span>{tx('secProcess')}</span>
          <span>{tx('secLogi')}</span>
          <span>{tx('secCert')}</span>
        </nav>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <LangPills value={lang} ink={ink} muted={muted} />
          <button style={{ padding: '10px 20px', background: terracotta, color: '#fff',
            border: 'none', fontFamily: 'inherit', fontSize: 12, letterSpacing: '0.04em',
            cursor: 'pointer', borderRadius: 3, fontWeight: 500 }}>{tx('ctaWholesale')}</button>
        </div>
      </header>

      {/* ────────── HERO ────────── */}
      <section style={{ ...wide, padding: '110px 80px 80px', display: 'grid',
        gridTemplateColumns: '1fr 1fr', gap: 72, alignItems: 'center' }}>
        <div>
          <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.16em',
            textTransform: 'uppercase', color: terracotta, marginBottom: 28 }}>
            {tx('brandTag')} · {tx('loc')} · {tx('since')}
          </div>
          <h1 style={{
            margin: 0, fontWeight: 700, fontSize: 96, lineHeight: 0.94,
            letterSpacing: '-0.04em', color: ink,
          }}>
            <div>{tx('heroH1a')}</div>
            <div style={{ color: terracotta }}>{tx('heroH1b')}</div>
            <div>{tx('heroH1c')}</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 20 }}>
              <span>{tx('heroH1d')}</span>
              <span style={{ width: 28, height: 2, background: terracotta, alignSelf: 'center' }} />
            </div>
          </h1>
          <p style={{ fontSize: 15, color: muted, lineHeight: 1.6, maxWidth: 440, marginTop: 34, textWrap: 'pretty' }}>
            {tx('heroSub')}
          </p>
          <div style={{ display: 'flex', gap: 16, marginTop: 34, alignItems: 'center' }}>
            <button style={{
              padding: '15px 26px', border: 'none', background: ink, color: cream,
              fontFamily: 'inherit', fontSize: 13, letterSpacing: '0.03em', cursor: 'pointer',
              borderRadius: 3, fontWeight: 500,
            }}>{tx('ctaWholesale')}</button>
            <button style={{
              padding: '15px 26px', border: `1px solid ${rule}`, background: 'transparent',
              color: ink, fontFamily: 'inherit', fontSize: 13, letterSpacing: '0.03em',
              cursor: 'pointer', borderRadius: 3,
            }}>{tx('ctaCatalog')}</button>
          </div>
        </div>

        <div style={{ position: 'relative' }}>
          <Placeholder label="pepperoni · butcher block" ink={ink} bg="#EDE3D7" minH={520} ratio="4/5" />
          <div style={{ position: 'absolute', top: 16, left: 16, fontFamily: '"Geist Mono", monospace',
            fontSize: 10, letterSpacing: '0.14em', color: cream, background: terracotta,
            padding: '5px 10px', borderRadius: 2 }}>
            № 001 · 24 SKU
          </div>
          <div style={{ position: 'absolute', bottom: -1, left: 0, right: 0, height: 3, background: terracotta }} />
        </div>
      </section>

      {/* ────────── STATS ────────── */}
      <section style={{ ...wide, padding: '48px 80px', borderTop: `1px solid ${rule}`,
        borderBottom: `1px solid ${rule}`, background: terracottaLight }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 28 }}>
          {[
            ['12 000', 'statTons'],
            ['18',     'statCountries'],
            ['24',     'statSku'],
            ['11',     'statYears'],
            ['100%',   'statHalal'],
          ].map(([num, key]) => (
            <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-start' }}>
              <div style={{ fontWeight: 700, fontSize: 44, letterSpacing: '-0.03em', lineHeight: 1,
                color: ink }}>{num}</div>
              <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 10, letterSpacing: '0.14em',
                textTransform: 'uppercase', color: muted }}>{tx(key)}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ────────── PRODUCTS ────────── */}
      <section style={{ ...wide, padding: '120px 80px 96px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 56 }}>
          <h2 style={{ fontWeight: 700, fontSize: 56, letterSpacing: '-0.035em', margin: 0,
            color: ink }}>
            {tx('secProducts')}
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ width: 32, height: 1, background: terracotta }} />
            <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.14em',
              color: muted, textTransform: 'uppercase' }}>04 lines · 24 SKU</span>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20 }}>
          {['pep', 'hd', 'ham', 'bur'].map((c, i) => {
            const catKey = { pep:'catPepperoni', hd:'catHotdog', ham:'catHam', bur:'catBurger' }[c];
            const { color } = CATS[c];
            const skus = PRODUCTS.filter(p => p.cat === c);
            const featured = skus[0];
            return (
              <article key={c} style={{
                background: cardBg, border: `1px solid ${rule}`,
                display: 'flex', flexDirection: 'column', overflow: 'hidden',
              }}>
                <div style={{ position: 'relative' }}>
                  <Placeholder label={`${c} · still life`} ink={ink} bg="#F3EBE0" minH={300} />
                  <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: 3,
                    background: color }} />
                  <div style={{ position: 'absolute', top: 12, right: 12, fontFamily: '"Geist Mono", monospace',
                    fontSize: 10, letterSpacing: '0.14em', color: cream, background: ink,
                    padding: '3px 8px', borderRadius: 2 }}>
                    {`0${i + 1}`}
                  </div>
                </div>
                <div style={{ padding: '22px 20px 24px', display: 'flex', flexDirection: 'column',
                  gap: 12, flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 6, height: 6, background: color, borderRadius: 1, flexShrink: 0 }} />
                    <h3 style={{ fontWeight: 600, fontSize: 22, letterSpacing: '-0.02em', margin: 0,
                      color: ink }}>{tx(catKey)}</h3>
                  </div>
                  <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 10,
                    letterSpacing: '0.12em', color: terracotta, textTransform: 'uppercase' }}>
                    6 SKU · from {featured.moq}
                  </div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: '4px 0 0',
                    display: 'flex', flexDirection: 'column', gap: 5, fontSize: 12, color: muted,
                    lineHeight: 1.6 }}>
                    {skus.slice(0, 4).map(p => (
                      <li key={p.id} style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>{p.name[lang] || p.name.ru}</span>
                        <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 10,
                          color: ink }}>{p.w}</span>
                      </li>
                    ))}
                  </ul>
                  <div style={{ marginTop: 'auto', paddingTop: 14, borderTop: `1px solid ${rule}`,
                    fontFamily: '"Geist Mono", monospace', fontSize: 10, letterSpacing: '0.1em',
                    color: sage, textTransform: 'uppercase' }}>
                    +{skus.length - 4} {lang === 'en' ? 'more →' : lang === 'tt' ? 'тагы →' : 'ещё →'}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {/* ────────── MANIFESTO / QUOTE ────────── */}
      <section style={{ ...wide, padding: '110px 80px', background: terracottaLight,
        borderTop: `1px solid ${rule}`, borderBottom: `1px solid ${rule}`,
        display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: 64, alignItems: 'center' }}>
        <div>
          <HalalSeal size={140} ink={terracotta} stroke={2} />
          <div style={{ marginTop: 22, fontFamily: '"Geist Mono", monospace', fontSize: 11,
            letterSpacing: '0.16em', textTransform: 'uppercase', color: terracotta }}>
            {tx('manifestoLine')}
          </div>
        </div>
        <blockquote style={{ margin: 0, fontWeight: 600, fontSize: 44, lineHeight: 1.12,
          letterSpacing: '-0.025em', color: ink }}>
          {lang === 'tt' &&
            <>«Безнең ит — Татарстан туфрагыннан. <span style={{ color: terracotta }}>Хәләл</span>, саф, документлы. Һәр килограммда — 11 ел тәҗрибә.»</>}
          {lang === 'ru' &&
            <>«Наше мясо — из почвы Татарстана. <span style={{ color: terracotta }}>Халяль</span>, честное, с документами. В каждом килограмме — 11 лет опыта.»</>}
          {lang === 'en' &&
            <>“Our meat comes from Tatarstan soil. <span style={{ color: terracotta }}>Halal</span>, honest, fully documented. 11 years of craft in every kilo.”</>}
        </blockquote>
      </section>

      {/* ────────── PROCESS ────────── */}
      <section style={{ ...wide, padding: '120px 80px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 64 }}>
          <div>
            <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: terracotta, marginBottom: 14 }}>{tx('byTheNumbers')}</div>
            <h2 style={{ fontWeight: 700, fontSize: 56, letterSpacing: '-0.035em', margin: 0 }}>
              {tx('secProcess')}
            </h2>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {['ISO 22000', 'HACCP', 'ХӘЛӘЛ'].map(b => (
              <span key={b} style={{ padding: '6px 12px', border: `1px solid ${terracotta}44`,
                fontFamily: '"Geist Mono", monospace', fontSize: 10, letterSpacing: '0.12em',
                color: terracotta, borderRadius: 2 }}>{b}</span>
            ))}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 32 }}>
          {[1, 2, 3].map(i => (
            <article key={i} style={{ borderTop: `2px solid ${terracotta}`, paddingTop: 32 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
                <div style={{ width: 44, height: 44, borderRadius: '50%', background: terracotta,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontWeight: 600, fontSize: 18 }}>{i}</div>
                <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 10,
                  letterSpacing: '0.14em', color: muted, textTransform: 'uppercase' }}>
                  STAGE · 0{i}
                </span>
              </div>
              <h3 style={{ fontWeight: 600, fontSize: 30, letterSpacing: '-0.02em', margin: '0 0 16px',
                lineHeight: 1.15 }}>{tx(`step${i}Title`)}</h3>
              <p style={{ fontSize: 14, color: muted, lineHeight: 1.6, textWrap: 'pretty' }}>
                {tx(`step${i}Body`)}
              </p>
            </article>
          ))}
        </div>
      </section>

      {/* ────────── LOGISTICS ────────── */}
      <section style={{ ...wide, padding: '96px 80px', background: cardBg, borderTop: `1px solid ${rule}` }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 64, alignItems: 'start' }}>
          <div>
            <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: terracotta, marginBottom: 16 }}>{tx('secLogi')}</div>
            <h2 style={{ fontWeight: 700, fontSize: 48, letterSpacing: '-0.03em', margin: '0 0 22px',
              lineHeight: 1.05 }}>{tx('exportTitle')}</h2>
            <p style={{ fontSize: 14, color: muted, lineHeight: 1.6, maxWidth: 500, textWrap: 'pretty' }}>
              {tx('countries')}
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, background: rule,
              marginTop: 32 }}>
              {[
                ['logiTruck',     '20 t',    sage],
                ['logiContainer', '24 t',    terracotta],
                ['logiPallet',    '0.5–5 t', sage],
                ['logiPort',      'FOB/CIF', terracotta],
              ].map(([k, v, accent]) => (
                <div key={k} style={{ padding: '18px 22px', background: cream,
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 500, fontSize: 14 }}>{tx(k)}</span>
                  <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 12,
                    color: accent, letterSpacing: '0.06em' }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
          <Placeholder label="export map · 18 markets" ink={ink} bg="#EDE3D7" minH={420} />
        </div>
      </section>

      {/* ────────── CTA BANNER ────────── */}
      <section style={{ ...wide, padding: '0 80px 0' }}>
        <div style={{ background: ink, color: cream, padding: '72px 64px',
          display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 48, alignItems: 'center',
          borderRadius: 2 }}>
          <div>
            <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.18em',
              color: terracotta, textTransform: 'uppercase', marginBottom: 14 }}>
              {tx('ctaContact')}
            </div>
            <h3 style={{ fontWeight: 700, fontSize: 56, letterSpacing: '-0.035em', margin: 0,
              lineHeight: 1, color: cream }}>
              {lang === 'tt' && <>Бер адым калды.<br/>Языгыз безгә →</>}
              {lang === 'ru' && <>Остался один шаг.<br/>Напишите нам →</>}
              {lang === 'en' && <>One step away.<br/>Write to us →</>}
            </h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12,
            fontFamily: '"Geist Mono", monospace', fontSize: 13, letterSpacing: '0.04em' }}>
            <div style={{ color: 'rgba(251,249,244,0.7)' }}>+7 843 000 00 00</div>
            <div style={{ color: terracotta }}>trade@pepperoni.tatar</div>
            <div style={{ color: 'rgba(251,249,244,0.5)' }}>WhatsApp · Telegram</div>
            <button style={{ marginTop: 10, padding: '14px 22px', background: terracotta, color: '#fff',
              border: 'none', fontFamily: 'inherit', fontSize: 13, letterSpacing: '0.04em',
              cursor: 'pointer', borderRadius: 3, fontWeight: 500 }}>
              {tx('formSend')} →
            </button>
          </div>
        </div>
      </section>

      {/* ────────── FOOTER ────────── */}
      <footer style={{ ...wide, padding: '72px 80px 48px', background: espresso, color: cream }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr', gap: 48, alignItems: 'start' }}>
          <div>
            <Wordmark color={cream} size={22} weight={600} />
            <div style={{ marginTop: 14, fontSize: 13, color: 'rgba(251,249,244,0.6)' }}>
              {tx('brandTag')} · {tx('loc')}
            </div>
            <div style={{ marginTop: 28, fontFamily: '"Geist Mono", monospace', fontSize: 11,
              letterSpacing: '0.12em', color: terracotta }}>
              +7 843 000 00 00<br/>trade@pepperoni.tatar
            </div>
          </div>
          {['secProducts', 'secLogi', 'secCert'].map(s => (
            <div key={s}>
              <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.14em',
                textTransform: 'uppercase', color: 'rgba(251,249,244,0.4)', marginBottom: 14 }}>
                {tx(s)}
              </div>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0,
                display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                <li style={{ color: 'rgba(251,249,244,0.6)' }}>—</li>
                <li style={{ color: 'rgba(251,249,244,0.6)' }}>—</li>
                <li style={{ color: 'rgba(251,249,244,0.6)' }}>—</li>
              </ul>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 56, paddingTop: 24, borderTop: '1px solid rgba(251,249,244,0.1)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          fontFamily: '"Geist Mono", monospace', fontSize: 10, letterSpacing: '0.14em',
          color: 'rgba(251,249,244,0.35)', textTransform: 'uppercase' }}>
          <span>© 2026 PEPPERONI.TATAR LLC · {tx('loc').toUpperCase()}</span>
          <span>ISO 22000 · HACCP · HALAL CERT. № TR-2024-0118</span>
        </div>
      </footer>
    </div>
  );
}

window.V5Earth = V5Earth;
