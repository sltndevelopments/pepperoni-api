// v6-apple.jsx — "APPLE"
// Pure Apple.com aesthetic: black canvas, precision typography, product-as-hero.
// SF Pro spirit × halal meat craftsmanship.

function V6Apple() {
  const tx = useT();
  const lang = useLang();

  // Apple palette
  const black   = '#000000';
  const white   = '#f5f5f7';
  const gray    = '#86868b';
  const grayLight = '#a1a1a6';
  const cardBg  = '#ffffff';
  const cardBorder = 'rgba(0,0,0,0.06)';
  const rule    = 'rgba(255,255,255,0.16)';
  const ruleDark = 'rgba(0,0,0,0.08)';
  const accent  = '#0071e3';  // Apple blue
  const accentDark = '#0066cc';
  const green   = '#1d9b5c';  // halal green accent alternative
  const heroText = '#f5f5f7';

  const wide = { paddingLeft: 'max(24px, 8vw)', paddingRight: 'max(24px, 8vw)' };

  return (
    <div lang={lang} style={{
      background: black, color: white, width: '100%',
      fontFamily: '"Geist", -apple-system, "SF Pro Display", "Helvetica Neue", sans-serif',
      fontSize: 17, lineHeight: 1.47059, fontWeight: 400,
      letterSpacing: '-0.022em',
      WebkitFontSmoothing: 'antialiased',
      MozOsxFontSmoothing: 'grayscale',
    }}>
      {/* ────────── NAV · frosted glass ────────── */}
      <nav style={{
        position: 'sticky', top: 0, zIndex: 100,
        background: 'rgba(0,0,0,0.8)',
        backdropFilter: 'saturate(180%) blur(20px)',
        WebkitBackdropFilter: 'saturate(180%) blur(20px)',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        height: 48, display: 'flex', alignItems: 'center',
      }}>
        <div style={{ ...wide, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          width: '100%', maxWidth: 1280, margin: '0 auto' }}>
          <div style={{ fontSize: 16, fontWeight: 500, color: white, letterSpacing: '-0.02em' }}>
            PEPPERONI<span style={{ opacity: 0.4, margin: '0 0.5px' }}>·</span>TATAR
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 24, fontSize: 12,
            fontWeight: 400, letterSpacing: '-0.01em', color: grayLight }}>
            <span style={{ cursor: 'pointer' }}>{tx('secProducts')}</span>
            <span style={{ cursor: 'pointer' }}>{tx('secProcess')}</span>
            <span style={{ cursor: 'pointer' }}>{tx('secLogi')}</span>
            <span style={{ cursor: 'pointer' }}>{tx('secCert')}</span>
            <span style={{ cursor: 'pointer' }}>{tx('ctaContact')}</span>
            <div style={{ display: 'flex', gap: 8, marginLeft: 4 }}>
              <LangPills value={lang} ink={white} muted={gray} size="sm" />
            </div>
            <button style={{
              padding: '6px 16px', background: accent, color: white,
              border: 'none', borderRadius: 980, fontSize: 12, fontWeight: 500,
              letterSpacing: '-0.01em', cursor: 'pointer', fontFamily: 'inherit',
            }}>{tx('ctaWholesale')}</button>
          </div>
        </div>
      </nav>

      {/* ────────── HERO · black canvas ────────── */}
      <section style={{
        background: black, color: white,
        padding: '120px 0 0', textAlign: 'center',
      }}>
        <div style={{ ...wide, maxWidth: 1280, margin: '0 auto' }}>
          <div style={{
            fontSize: 17, fontWeight: 400, color: grayLight,
            letterSpacing: '-0.01em', marginBottom: 16,
          }}>
            {tx('brandTag')} · {tx('since')}
          </div>

          <h1 style={{
            margin: 0, fontSize: 'clamp(56px, 8vw, 112px)', fontWeight: 600,
            letterSpacing: '-0.045em', lineHeight: 1.04, color: white,
          }}>
            PEPPERONI<span style={{ color: accent }}>.</span>TATAR
          </h1>

          <p style={{
            margin: '24px auto 0', maxWidth: 560, fontSize: 21, fontWeight: 400,
            letterSpacing: '-0.016em', lineHeight: 1.381, color: grayLight,
          }}>
            {lang === 'tt' && 'Татар хәләл ите — Apple төгәллеге белән.'}
            {lang === 'ru' && 'Татарский халяль — с точностью Apple.'}
            {lang === 'en' && 'Tatar halal, engineered to Apple precision.'}
          </p>

          <p style={{
            margin: '10px auto 0', maxWidth: 500, fontSize: 14,
            color: gray, lineHeight: 1.5,
          }}>
            {tx('heroSub')}
          </p>

          <div style={{ display: 'flex', gap: 14, justifyContent: 'center', marginTop: 32 }}>
            <button style={{
              padding: '12px 28px', background: accent, color: white,
              border: 'none', borderRadius: 980, fontSize: 15, fontWeight: 500,
              letterSpacing: '-0.01em', cursor: 'pointer', fontFamily: 'inherit',
              minWidth: 120,
            }}>{tx('ctaWholesale')}</button>
            <button style={{
              padding: '12px 28px', background: 'transparent', color: accent,
              border: '1px solid rgba(255,255,255,0.25)', borderRadius: 980,
              fontSize: 15, fontWeight: 400, letterSpacing: '-0.01em',
              cursor: 'pointer', fontFamily: 'inherit',
            }}>{tx('ctaCatalog')}</button>
          </div>

          {/* hero product image */}
          <div style={{ marginTop: 80 }}>
            <Placeholder label="PEPPERONI · hero product" ink={white} bg="#1a1a1a"
              minH={560} style={{ maxWidth: 1024, margin: '0 auto' }} />
          </div>
        </div>
      </section>

      {/* ────────── STATS · black band ────────── */}
      <section style={{
        background: black, padding: '60px 0 80px',
      }}>
        <div style={{ ...wide, maxWidth: 960, margin: '0 auto',
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20 }}>
          {[
            ['12 000', 'statTons'],
            ['18',     'statCountries'],
            ['24',     'statSku'],
            ['11',     'statYears'],
          ].map(([n, k]) => (
            <div key={k} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 48, fontWeight: 600, letterSpacing: '-0.03em',
                color: white, lineHeight: 1 }}>{n}</div>
              <div style={{ marginTop: 8, fontSize: 12, color: gray, letterSpacing: '0',
                textTransform: 'uppercase' }}>{tx(k)}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ────────── PRODUCTS · light gray ────────── */}
      <section style={{
        background: white, color: black, padding: '120px 0',
      }}>
        <div style={{ ...wide, maxWidth: 1280, margin: '0 auto' }}>
          <h2 style={{
            margin: '0 0 8px', fontSize: 'clamp(40px, 5vw, 64px)',
            fontWeight: 600, letterSpacing: '-0.03em', lineHeight: 1.08,
            textAlign: 'center',
          }}>
            {lang === 'tt' && 'Продукция.'}
            {lang === 'ru' && 'Продукция.'}
            {lang === 'en' && 'Product range.'}
          </h2>
          <p style={{
            textAlign: 'center', fontSize: 17, color: gray, margin: '8px 0 64px',
            letterSpacing: '-0.016em',
          }}>
            {lang === 'tt' && '24 SKU · 4 категория'}
            {lang === 'ru' && '24 SKU · 4 категории'}
            {lang === 'en' && '24 SKU · 4 categories'}
          </p>

          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20,
          }}>
            {['pep', 'hd', 'ham', 'bur'].map((c, i) => {
              const catKey = { pep:'catPepperoni', hd:'catHotdog', ham:'catHam', bur:'catBurger' }[c];
              const skus = PRODUCTS.filter(p => p.cat === c);
              const featured = skus[0];
              return (
                <article key={c} style={{
                  background: cardBg,
                  borderRadius: 18,
                  overflow: 'hidden',
                  boxShadow: '0 0 0 1px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.04)',
                  display: 'flex', flexDirection: 'column',
                }}>
                  <Placeholder label={c} ink={black} bg="#f2f2f2" minH={240} />
                  <div style={{ padding: '24px 24px 28px', display: 'flex',
                    flexDirection: 'column', gap: 6, flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 400, color: gray,
                      letterSpacing: '0', textTransform: 'uppercase' }}>
                      {`0${i + 1}`} · 6 SKU
                    </div>
                    <h3 style={{
                      fontSize: 24, fontWeight: 600, letterSpacing: '-0.02em',
                      margin: '0 0 4px', lineHeight: 1.15,
                    }}>{tx(catKey)}</h3>
                    <div style={{
                      fontSize: 14, color: gray, letterSpacing: '-0.01em',
                      lineHeight: 1.4,
                    }}>
                      {featured.name[lang] || featured.name.ru} · {featured.w}
                    </div>
                    <div style={{ marginTop: 'auto', paddingTop: 16 }}>
                      <span style={{
                        fontSize: 14, color: accent, fontWeight: 500,
                        letterSpacing: '-0.01em', cursor: 'pointer',
                      }}>
                        {lang === 'en' ? 'View details →' : lang === 'tt' ? 'Тулырак →' : 'Подробнее →'}
                      </span>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      {/* ────────── PROCESS · black ────────── */}
      <section style={{
        background: black, color: white, padding: '120px 0',
      }}>
        <div style={{ ...wide, maxWidth: 960, margin: '0 auto' }}>
          <h2 style={{
            margin: '0 0 8px', fontSize: 'clamp(40px, 5vw, 64px)',
            fontWeight: 600, letterSpacing: '-0.03em', lineHeight: 1.08,
            textAlign: 'center',
          }}>
            {lang === 'tt' && 'Ничек эшләнә.'}
            {lang === 'ru' && 'Как это сделано.'}
            {lang === 'en' && 'How it\'s made.'}
          </h2>

          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 28,
            marginTop: 80,
          }}>
            {[1, 2, 3].map(i => (
              <div key={i} style={{
                borderTop: `1px solid ${rule}`, paddingTop: 28,
              }}>
                <div style={{
                  fontSize: 40, fontWeight: 600, letterSpacing: '-0.03em',
                  color: accent, lineHeight: 1, marginBottom: 16,
                }}>
                  {`0${i}`}
                </div>
                <h3 style={{
                  fontSize: 28, fontWeight: 600, letterSpacing: '-0.025em',
                  margin: '0 0 12px', lineHeight: 1.15,
                  color: white,
                }}>{tx(`step${i}Title`)}</h3>
                <p style={{
                  fontSize: 15, color: grayLight, letterSpacing: '-0.012em',
                  lineHeight: 1.5,
                }}>{tx(`step${i}Body`)}</p>
              </div>
            ))}
          </div>

          {/* certification badges */}
          <div style={{
            display: 'flex', justifyContent: 'center', gap: 20, marginTop: 80,
            flexWrap: 'wrap',
          }}>
            {['HALAL · حلال', 'ISO 22000', 'HACCP', 'GMP+', 'ТР ТС 021/2011'].map(b => (
              <span key={b} style={{
                padding: '10px 20px', borderRadius: 980,
                border: '1px solid rgba(255,255,255,0.15)',
                fontSize: 12, fontWeight: 400, color: grayLight,
                letterSpacing: '0',
              }}>{b}</span>
            ))}
          </div>
        </div>
      </section>

      {/* ────────── LOGISTICS · light gray ────────── */}
      <section style={{
        background: white, color: black, padding: '120px 0',
      }}>
        <div style={{ ...wide, maxWidth: 1280, margin: '0 auto',
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 80, alignItems: 'center' }}>
          <div>
            <div style={{
              fontSize: 12, fontWeight: 400, color: gray,
              letterSpacing: '0', textTransform: 'uppercase', marginBottom: 12,
            }}>{tx('secLogi')}</div>
            <h2 style={{
              fontSize: 'clamp(40px, 5vw, 56px)', fontWeight: 600,
              letterSpacing: '-0.03em', lineHeight: 1.08, margin: '0 0 20px',
            }}>
              {lang === 'tt' && '18 илгә.'}
              {lang === 'ru' && 'В 18 стран.'}
              {lang === 'en' && 'To 18 countries.'}
            </h2>
            <p style={{
              fontSize: 17, color: gray, letterSpacing: '-0.016em',
              lineHeight: 1.47, marginBottom: 32,
            }}>
              {tx('countries')}
            </p>
            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16,
            }}>
              {[
                ['logiTruck', '20 t'],
                ['logiContainer', '24 t'],
                ['logiPallet', '0.5–5 t'],
                ['logiPort', 'FOB / CIF'],
              ].map(([k, v]) => (
                <div key={k} style={{
                  padding: '20px', borderRadius: 14,
                  background: cardBg,
                  boxShadow: '0 0 0 1px rgba(0,0,0,0.04), 0 2px 6px rgba(0,0,0,0.03)',
                }}>
                  <div style={{ fontSize: 14, fontWeight: 500, letterSpacing: '-0.01em' }}>
                    {tx(k)}
                  </div>
                  <div style={{ fontSize: 17, fontWeight: 600, color: accent,
                    letterSpacing: '-0.01em', marginTop: 4 }}>{v}</div>
                </div>
              ))}
            </div>
          </div>

          <Placeholder label="export · 18 markets" ink={black} bg="#f2f2f2" minH={420}
            style={{ borderRadius: 18 }} />
        </div>
      </section>

      {/* ────────── CTA · black ────────── */}
      <section style={{
        background: black, color: white, padding: '100px 0',
        textAlign: 'center',
      }}>
        <div style={{ ...wide, maxWidth: 640, margin: '0 auto' }}>
          <h2 style={{
            fontSize: 'clamp(40px, 5vw, 56px)', fontWeight: 600,
            letterSpacing: '-0.03em', lineHeight: 1.08, margin: '0 0 16px',
          }}>
            {lang === 'tt' && 'Сезнең белән эшләргә әзер.'}
            {lang === 'ru' && 'Готовы работать с вами.'}
            {lang === 'en' && 'Ready to work with you.'}
          </h2>
          <p style={{
            fontSize: 17, color: gray, letterSpacing: '-0.016em',
            lineHeight: 1.47, marginBottom: 28,
          }}>
            {tx('ctaContact')} · +7 843 000 00 00 · trade@pepperoni.tatar
          </p>
          <div style={{ display: 'flex', gap: 14, justifyContent: 'center' }}>
            <button style={{
              padding: '14px 32px', background: accent, color: white,
              border: 'none', borderRadius: 980, fontSize: 15, fontWeight: 500,
              letterSpacing: '-0.01em', cursor: 'pointer', fontFamily: 'inherit',
            }}>{tx('formSend')} →</button>
            <button style={{
              padding: '14px 32px', background: 'transparent', color: accent,
              border: '1px solid rgba(255,255,255,0.25)', borderRadius: 980,
              fontSize: 15, fontWeight: 400, letterSpacing: '-0.01em',
              cursor: 'pointer', fontFamily: 'inherit',
            }}>{tx('ctaCatalog')}</button>
          </div>
        </div>
      </section>

      {/* ────────── FOOTER · Apple-style ────────── */}
      <footer style={{
        background: white, color: 'rgba(0,0,0,0.56)', padding: '24px 0 32px',
        fontSize: 12, letterSpacing: '-0.01em',
      }}>
        <div style={{ ...wide, maxWidth: 1024, margin: '0 auto' }}>
          <div style={{
            borderBottom: `1px solid ${ruleDark}`, paddingBottom: 16, marginBottom: 16,
            lineHeight: 1.4,
          }}>
            © 2014–2026 PEPPERONI.TATAR LLC. {tx('brandTag')}. {tx('loc')}.
            ISO 22000 · HACCP · HALAL CERT. № TR-2024-0118.
          </div>
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 32,
          }}>
            <div>
              <div style={{ fontWeight: 500, color: 'rgba(0,0,0,0.88)', marginBottom: 10 }}>
                {tx('secProducts')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <span>{tx('catPepperoni')}</span>
                <span>{tx('catHotdog')}</span>
                <span>{tx('catHam')}</span>
                <span>{tx('catBurger')}</span>
              </div>
            </div>
            <div>
              <div style={{ fontWeight: 500, color: 'rgba(0,0,0,0.88)', marginBottom: 10 }}>
                {tx('secLogi')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <span>{tx('logiTruck')}</span>
                <span>{tx('logiContainer')}</span>
                <span>{tx('logiPallet')}</span>
                <span>{tx('logiPort')}</span>
              </div>
            </div>
            <div>
              <div style={{ fontWeight: 500, color: 'rgba(0,0,0,0.88)', marginBottom: 10 }}>
                {tx('secCert')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <span>{tx('badgeHalal')}</span>
                <span>{tx('badgeIso')}</span>
                <span>{tx('badgeHaccp')}</span>
                <span>ТР ТС 021/2011</span>
              </div>
            </div>
            <div>
              <div style={{ fontWeight: 500, color: 'rgba(0,0,0,0.88)', marginBottom: 10 }}>
                {tx('ctaContact')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <span>+7 843 000 00 00</span>
                <span>trade@pepperoni.tatar</span>
                <span>WhatsApp · Telegram</span>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

window.V6Apple = V6Apple;
