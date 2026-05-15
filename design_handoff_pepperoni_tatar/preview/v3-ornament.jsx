// v3-ornament.jsx — "ORNAMENT"
// Tatar geometric pattern as the graphic hero · emerald + gold.
// Theatrical luxury, Gentle Monster gallery + manuscript cover.

function V3Ornament() {
  const tx = useT();
  const lang = useLang();
  const emerald = '#0F4F3D';
  const emeraldDeep = '#093729';
  const gold = '#C9A961';
  const goldDeep = '#A0823F';
  const cream = '#F4EFE6';
  const ink = '#0C1411';
  const onEm = 'rgba(244,239,230,0.75)';

  const wide = { paddingLeft: 80, paddingRight: 80 };

  // 8-point star rendered larger as a backdrop element
  const HugeStar = ({ size = 460 }) => {
    const c = size / 2, r = size * 0.46;
    return (
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block' }}>
        <g fill="none" stroke={gold} strokeWidth={1.2}>
          <circle cx={c} cy={c} r={r * 0.98} />
          <rect x={c - r} y={c - r} width={r * 2} height={r * 2} />
          <rect x={c - r} y={c - r} width={r * 2} height={r * 2} transform={`rotate(45 ${c} ${c})`} />
          <rect x={c - r * 0.72} y={c - r * 0.72} width={r * 1.44} height={r * 1.44} />
          <rect x={c - r * 0.72} y={c - r * 0.72} width={r * 1.44} height={r * 1.44} transform={`rotate(45 ${c} ${c})`} />
          <circle cx={c} cy={c} r={r * 0.55} />
          <circle cx={c} cy={c} r={r * 0.32} />
        </g>
        <text x={c} y={c + 8} textAnchor="middle" fill={gold}
          fontFamily="'Noto Naskh Arabic', serif" fontSize={size * 0.16}>حلال</text>
      </svg>
    );
  };

  return (
    <div lang={lang} style={{ background: emerald, color: cream, width: '100%',
      fontFamily: '"Geist", system-ui, sans-serif', fontSize: 14, lineHeight: 1.5 }}>

      {/* ────────── NAV ────────── */}
      <header style={{ ...wide, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '28px 80px', borderBottom: `1px solid ${gold}55` }}>
        <Wordmark color={cream} size={17} weight={500} />
        <nav style={{ display: 'flex', gap: 36, fontSize: 12, color: onEm,
          fontFamily: '"Geist Mono", monospace', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
          <span>{tx('secProducts')}</span>
          <span>{tx('secProcess')}</span>
          <span>{tx('secLogi')}</span>
          <span>{tx('secCert')}</span>
        </nav>
        <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
          <LangPills value={lang} ink={cream} muted={onEm} />
          <button style={{ padding: '9px 18px', background: gold, color: emeraldDeep,
            border: 'none', fontFamily: 'inherit', fontSize: 12, letterSpacing: '0.04em',
            cursor: 'pointer', fontWeight: 500 }}>{tx('ctaWholesale')}</button>
        </div>
      </header>

      {/* ornamental band */}
      <div style={{ padding: '14px 80px', borderBottom: `1px solid ${gold}33` }}>
        <DiamondStrip color={gold} count={56} height={10} opacity={0.6} />
      </div>

      {/* ────────── HERO ────────── */}
      <section style={{ position: 'relative', padding: '88px 80px 80px', textAlign: 'center', overflow: 'hidden' }}>
        {/* corner stars */}
        <div style={{ position: 'absolute', top: 60, left: 80 }}><StarRub size={28} color={gold} /></div>
        <div style={{ position: 'absolute', top: 60, right: 80 }}><StarRub size={28} color={gold} /></div>
        <div style={{ position: 'absolute', bottom: 60, left: 80 }}><StarRub size={28} color={gold} /></div>
        <div style={{ position: 'absolute', bottom: 60, right: 80 }}><StarRub size={28} color={gold} /></div>

        <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.22em',
          color: gold, textTransform: 'uppercase', marginBottom: 32 }}>
          {tx('brandTag')} · {tx('loc')} · {tx('since')}
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 36 }}>
          <HugeStar size={420} />
        </div>

        <h1 style={{ margin: '0 auto', fontWeight: 600, fontSize: 132, lineHeight: 0.95,
          letterSpacing: '-0.04em', maxWidth: 1200, color: cream }}>
          <span>PEPPERONI</span>
          <span style={{ color: gold }}>.</span>
          <span style={{ color: gold, fontFamily: '"Instrument Serif", serif', fontWeight: 400,
            fontStyle: 'italic' }}>tatar</span>
        </h1>

        <p style={{ margin: '36px auto 0', maxWidth: 680, fontSize: 16, color: onEm, lineHeight: 1.6,
          textWrap: 'pretty' }}>
          {tx('heroSub')}
        </p>

        <div style={{ display: 'flex', gap: 16, justifyContent: 'center', marginTop: 40 }}>
          <button style={{ padding: '14px 24px', background: gold, color: emeraldDeep,
            border: 'none', fontFamily: 'inherit', fontSize: 13, letterSpacing: '0.04em',
            cursor: 'pointer', fontWeight: 500 }}>{tx('ctaWholesale')}</button>
          <button style={{ padding: '14px 24px', background: 'transparent', color: cream,
            border: `1px solid ${gold}77`, fontFamily: 'inherit', fontSize: 13, letterSpacing: '0.04em',
            cursor: 'pointer' }}>{tx('ctaCatalog')}</button>
        </div>
      </section>

      {/* ornament band */}
      <div style={{ padding: '14px 80px', background: emeraldDeep }}>
        <DiamondStrip color={gold} count={56} height={10} opacity={0.6} />
      </div>

      {/* ────────── STATS ────────── */}
      <section style={{ ...wide, padding: '64px 80px', background: emeraldDeep }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 24 }}>
          {[
            ['12 000', 'statTons'],
            ['18',     'statCountries'],
            ['24',     'statSku'],
            ['100%',   'statHalal'],
          ].map(([n, k], i) => (
            <div key={k} style={{ padding: '0 8px', borderLeft: i === 0 ? 'none' : `1px solid ${gold}33`,
              display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
              <StarRub size={14} color={gold} />
              <div style={{ fontFamily: '"Instrument Serif", serif', fontSize: 76, fontWeight: 400,
                lineHeight: 1, letterSpacing: '-0.025em', marginTop: 16, color: gold }}>{n}</div>
              <div style={{ marginTop: 10, fontFamily: '"Geist Mono", monospace', fontSize: 11,
                letterSpacing: '0.14em', color: onEm, textTransform: 'uppercase' }}>{tx(k)}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ────────── PRODUCT GALLERY ────────── */}
      <section style={{ background: cream, color: ink, padding: '120px 80px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 56 }}>
          <h2 style={{ fontFamily: '"Instrument Serif", serif', fontWeight: 400, fontSize: 64,
            margin: 0, letterSpacing: '-0.02em', color: ink }}>{tx('secProducts')}</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, color: 'rgba(12,20,17,0.55)' }}>
            <Tulip size={32} color={goldDeep} />
            <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.14em' }}>
              04 / категории · 24 / SKU
            </span>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 24 }}>
          {['pep', 'hd', 'ham', 'bur'].map((c, i) => {
            const catKey = { pep:'catPepperoni', hd:'catHotdog', ham:'catHam', bur:'catBurger' }[c];
            const featured = PRODUCTS.filter(p => p.cat === c)[0];
            return (
              <article key={c} style={{
                background: '#fff', border: `1px solid ${goldDeep}33`,
                padding: 4, display: 'flex', flexDirection: 'column',
              }}>
                <div style={{ position: 'relative', border: `1px solid ${goldDeep}33` }}>
                  <Placeholder label={`${c} · still life`} ink={ink} bg="#EFE9DA" minH={360} />
                  <div style={{ position: 'absolute', top: 12, left: 12, fontFamily: '"Geist Mono", monospace',
                    fontSize: 10, letterSpacing: '0.14em', color: goldDeep, padding: '4px 8px',
                    background: cream }}>№ 0{i + 1}</div>
                  <div style={{ position: 'absolute', bottom: 12, right: 12 }}>
                    <StarRub size={20} color={goldDeep} />
                  </div>
                </div>
                <div style={{ padding: '24px 18px 22px', textAlign: 'center' }}>
                  <div style={{ fontFamily: '"Instrument Serif", serif', fontSize: 26, letterSpacing: '-0.01em' }}>
                    {tx(catKey)}
                  </div>
                  <div style={{ marginTop: 4, fontFamily: '"Geist Mono", monospace', fontSize: 10,
                    letterSpacing: '0.16em', color: goldDeep, textTransform: 'uppercase' }}>
                    6 SKU · от {featured.moq}
                  </div>
                  <div style={{ marginTop: 18, height: 1, background: `${goldDeep}33` }} />
                  <div style={{ marginTop: 16, fontSize: 12, color: 'rgba(12,20,17,0.6)',
                    fontStyle: 'italic', textWrap: 'balance' }}>
                    {featured.name[lang] || featured.name.ru}, {featured.w}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {/* ────────── HALAL SEAL CENTERPIECE ────────── */}
      <section style={{ padding: '120px 80px', textAlign: 'center', background: cream, color: ink,
        borderTop: `1px solid ${goldDeep}33`, borderBottom: `1px solid ${goldDeep}33` }}>
        <HalalSeal size={180} ink={emerald} />
        <h2 style={{ marginTop: 36, fontFamily: '"Instrument Serif", serif', fontWeight: 400, fontSize: 56,
          letterSpacing: '-0.02em', margin: '36px 0 14px' }}>
          {tx('manifestoLine')}
        </h2>
        <p style={{ margin: '0 auto', maxWidth: 580, color: 'rgba(12,20,17,0.6)', fontSize: 15,
          lineHeight: 1.6, textWrap: 'pretty' }}>
          {lang === 'tt' && 'Татарстан Диния Нәзарәте раслаган. Һәр партиягә хәләл сертификат. ISO 22000 һәм HACCP — һәр конвейерда.'}
          {lang === 'ru' && 'Сертификат ДУМ Татарстана на каждую партию. ISO 22000 и HACCP — на каждой линии.'}
          {lang === 'en' && 'Certified by the Spiritual Board of Tatarstan. Halal certificate per batch. ISO 22000 + HACCP on every line.'}
        </p>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 14, marginTop: 28 }}>
          {['ХӘЛӘЛ', 'ISO 22000', 'HACCP', 'GMP+', 'ROSPOTREBNADZOR'].map(b => (
            <span key={b} style={{ padding: '8px 14px', border: `1px solid ${goldDeep}55`,
              fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.14em',
              color: goldDeep }}>{b}</span>
          ))}
        </div>
      </section>

      {/* ────────── PROCESS ────────── */}
      <section style={{ ...wide, padding: '120px 80px', background: emerald }}>
        <div style={{ textAlign: 'center', marginBottom: 64 }}>
          <span style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, letterSpacing: '0.22em',
            color: gold, textTransform: 'uppercase' }}>{tx('byTheNumbers')}</span>
          <h2 style={{ fontFamily: '"Instrument Serif", serif', fontWeight: 400, fontSize: 64,
            letterSpacing: '-0.02em', margin: '14px 0 0', color: cream }}>{tx('secProcess')}</h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 32 }}>
          {[1, 2, 3].map(i => (
            <article key={i} style={{ border: `1px solid ${gold}44`, padding: 32 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ width: 56, height: 56, background: gold, color: emeraldDeep,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transform: 'rotate(45deg)' }}>
                  <span style={{ transform: 'rotate(-45deg)', fontFamily: '"Instrument Serif", serif',
                    fontSize: 26 }}>{i}</span>
                </div>
                <StarRub size={20} color={gold} />
              </div>
              <h3 style={{ marginTop: 24, fontFamily: '"Instrument Serif", serif', fontWeight: 400,
                fontSize: 32, letterSpacing: '-0.01em', color: cream }}>{tx(`step${i}Title`)}</h3>
              <p style={{ marginTop: 14, color: onEm, fontSize: 14, lineHeight: 1.6, textWrap: 'pretty' }}>
                {tx(`step${i}Body`)}
              </p>
            </article>
          ))}
        </div>
      </section>

      {/* ornament band */}
      <div style={{ padding: '14px 80px', background: emeraldDeep }}>
        <DiamondStrip color={gold} count={56} height={10} opacity={0.6} />
      </div>

      {/* ────────── FOOTER ────────── */}
      <footer style={{ background: emeraldDeep, color: cream, padding: '64px 80px 40px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr', gap: 48 }}>
          <div>
            <Wordmark color={cream} size={22} weight={500} />
            <div style={{ marginTop: 12, fontSize: 13, color: onEm }}>{tx('brandTag')}</div>
            <div style={{ marginTop: 24, fontFamily: '"Geist Mono", monospace', fontSize: 11,
              letterSpacing: '0.12em', color: gold }}>+7 843 000 00 00<br/>trade@pepperoni.tatar</div>
          </div>
          {['secProducts', 'secLogi', 'secCert'].map(s => (
            <div key={s}>
              <div style={{ fontFamily: '"Geist Mono", monospace', fontSize: 11, color: gold,
                letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 14 }}>{tx(s)}</div>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0,
                display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13, color: cream }}>
                <li>—</li><li>—</li><li>—</li>
              </ul>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 56, paddingTop: 24, borderTop: `1px solid ${gold}33`,
          display: 'flex', justifyContent: 'space-between',
          fontFamily: '"Geist Mono", monospace', fontSize: 10, letterSpacing: '0.14em',
          color: onEm, textTransform: 'uppercase' }}>
          <span>© 2026 PEPPERONI.TATAR LLC · {tx('loc').toUpperCase()}</span>
          <span>ISO 22000 · HACCP · HALAL № TR-2024-0118</span>
        </div>
      </footer>
    </div>
  );
}

window.V3Ornament = V3Ornament;
