#!/usr/bin/env python3
"""Generate EN geo landing pages: /en/geo/halal-pepperoni-<country>.

Outputs 12 country-targeted pages with localised facts (currency,
customs, halal authority recognition, transit time, payment terms,
example HS codes), Product + LocalBusiness + Place + FAQ Schema.

URL convention: /en/geo/halal-pepperoni-uae, .../halal-pepperoni-saudi-arabia, etc.
"""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
GEO_DIR = PUBLIC / "en" / "geo"
GEO_DIR.mkdir(parents=True, exist_ok=True)


GEOS = [
    {
        "slug": "halal-pepperoni-uae",
        "country": "United Arab Emirates",
        "country_code": "AE",
        "currency": "AED",
        "currency_label": "UAE Dirham",
        "city": "Dubai, Sharjah, Abu Dhabi",
        "h1": "Halal Pepperoni in the UAE — Direct Import from Kazan, Russia",
        "lede": "Cold-chain DAP Jebel Ali or DAP Sharjah, 10–14 days port-to-port. Halal certificate accepted by ESMA. Multi-currency invoicing (AED/USD).",
        "halal_authority": "Emirates Standardization & Metrology Authority (ESMA) — recognises DUM RT halal certificate #614A/2024 under mutual recognition with the GCC Standardization Organization",
        "import_route": "Cold-chain truck Kazan → Astrakhan / Novorossiysk → sea to Jebel Ali (12–14 days) — or air via DXB (4–5 days express)",
        "transit": "10–14 days port-to-port via Jebel Ali / Sharjah",
        "agents": "We work with two cold-chain partners with bonded warehousing in Jebel Ali Free Zone — full landed-cost quote on request.",
        "buyer_profiles": "Pizza chains (LuLu, Pizza Hut UAE franchisees, dark kitchens in Dubai Marina), Russian-Tatar restaurants in Dubai, halal-positioned hotel breakfast lines, hypermarket private-label buyers",
        "case": "Pilot shipment with Sharjah-based foodservice distributor (March 2026): 5 pallets of pepperoni KD-015/KD-016 cleared customs in 48 h with halal certificate #614A/2024 — no SFDA-equivalent registration required.",
        "hs_codes": "1601.00 (sausages of meat) — duty 5% MFN, halal-cert-driven exemption available",
        "labels": "English + Russian standard. Arabic labels available on request (2-week artwork approval).",
        "payment": "USD or AED. 50% prepayment for first shipment, balance against shipping documents. Net 14–30 days from the second order.",
        "competitor_context": "UAE imports halal beef sausage primarily from Brazil, India, Argentina. Russian halal is positioned as the premium European-style alternative with locked recipe consistency and shorter air-freight option.",
    },
    {
        "slug": "halal-pepperoni-saudi-arabia",
        "country": "Saudi Arabia",
        "country_code": "SA",
        "currency": "SAR",
        "currency_label": "Saudi Riyal",
        "city": "Jeddah, Riyadh, Dammam",
        "h1": "Halal Pepperoni in Saudi Arabia — Russian Manufacturer Direct",
        "lede": "DAP Jeddah / DAP Dammam, cold chain. Halal certificate accepted by SFDA after agent registration. Multi-currency invoicing (SAR/USD).",
        "halal_authority": "SFDA (Saudi Food & Drug Authority) — accepts DUM RT halal certificate after local agent registration (standard 30–45-day process)",
        "import_route": "Sea via Novorossiysk → Jeddah (18–22 days) or via Bandar Abbas → Dammam (combined sea + truck, 22–28 days)",
        "transit": "18–22 days port-to-port via Jeddah",
        "agents": "We refer buyers to a vetted Riyadh-based licensed importer that handles SFDA registration in batches — 30–45 days lead time for first shipment.",
        "buyer_profiles": "Pizza chains (Herfy, Pizza Hut KSA franchisees), HoReCa distributors serving Mecca / Medina hotels during Hajj season, halal hypermarket chains (Panda, Tamimi)",
        "case": "Two pilot inquiries in Q1 2026 — sample boxes shipped DHL Express Riyadh, awaiting registration completion before first commercial pallet.",
        "hs_codes": "1601.00 — KSA tariff 12% MFN; halal-cert + free trade agreement check possible via the local agent.",
        "labels": "Arabic labels mandatory under SFDA rules. Standard turnaround: 2 weeks artwork + 4 weeks SFDA registration. We supply Arabic-ready label templates.",
        "payment": "SAR or USD. 50% prepayment for first shipment, balance against shipping documents. LC-at-sight available from $50k.",
        "competitor_context": "KSA imports halal beef sausage primarily from Brazil and Turkey. Russian halal positioned as premium alternative with Eurasian recipe profile (mild smoke, beef+chicken blend).",
    },
    {
        "slug": "halal-pepperoni-kazakhstan",
        "country": "Kazakhstan",
        "country_code": "KZ",
        "currency": "KZT",
        "currency_label": "Kazakh Tenge",
        "city": "Almaty, Astana, Shymkent",
        "h1": "Halal Pepperoni in Kazakhstan — Direct from Kazan",
        "lede": "Weekly truck DAP Almaty or DAP Astana, 5–7 days. EAEU customs union — no duties, no extra paperwork. KZT pricing live on api.pepperoni.tatar.",
        "halal_authority": "Halal Industry Association of the Republic of Kazakhstan — recognises DUM RT halal certificate under mutual recognition. No SFDA-equivalent registration required.",
        "import_route": "Truck Kazan → Almaty (5 days) or Kazan → Astana (4 days). EAEU customs union — no border duty, simplified VSD via Mercury FGIS.",
        "transit": "5–7 days truck delivery, weekly cadence",
        "agents": "We have two foodservice distributor partners in Almaty and one in Astana — direct delivery to their warehouse on EXW Kazan terms.",
        "buyer_profiles": "Pizza chains (Dodo Pizza Kazakhstan, Papa John's franchisees), halal-positioned restaurants in Almaty and Astana, regional retail chains (Magnum, Small).",
        "case": "Weekly supply to Almaty foodservice distributor since 2024. Multi-currency invoicing in KZT (live on api.pepperoni.tatar/api/products?currency=KZT).",
        "hs_codes": "1601.00 — EAEU internal traffic, no tariff. Simplified Mercury VSD only.",
        "labels": "Russian + Kazakh required under Kazakh consumer-protection law. Kazakh labels available, 1-week artwork turnaround.",
        "payment": "KZT or RUB. Net 14 days after pilot. Letter-of-credit not required for EAEU partners.",
        "competitor_context": "Kazakhstan imports halal sausage primarily from Russia (50%+), Belarus and Türkiye. We compete on locked recipe and federal-scale references.",
    },
    {
        "slug": "halal-pepperoni-uzbekistan",
        "country": "Uzbekistan",
        "country_code": "UZ",
        "currency": "UZS",
        "currency_label": "Uzbek Som",
        "city": "Tashkent, Samarkand, Bukhara",
        "h1": "Halal Pepperoni in Uzbekistan — Russian Halal Supplier",
        "lede": "Truck DAP Tashkent in 7–9 days. CIS free-trade agreement (CISFTA) — preferential duties. UZS pricing in our live API.",
        "halal_authority": "Uzbekistan Halal Standards (O'zStandart) — recognises DUM RT halal certificate under CIS halal mutual recognition framework.",
        "import_route": "Truck Kazan → Tashkent via Kazakhstan (7–9 days). CIS free-trade preferential customs procedure.",
        "transit": "7–9 days truck delivery, bi-weekly cadence",
        "agents": "Distribution partner in Tashkent handles last-mile to Samarkand, Bukhara, Andijan. Direct foodservice contracts available.",
        "buyer_profiles": "Pizza chains in Tashkent (LesAffaires Pizza, Sloboda Pizza), regional foodservice distributors, halal-default supermarket chains (Korzinka, Makro).",
        "case": "Quarterly shipments to Tashkent foodservice distributor since 2025. Pricing automatically converted to UZS via /api/products?currency=UZS.",
        "hs_codes": "1601.00 — CIS preferential rate, 0–5% depending on annual quota.",
        "labels": "Russian + Uzbek (Latin script) standard. Uzbek-Cyrillic also accepted for older retail channels.",
        "payment": "UZS, RUB or USD. Net 14–21 days after pilot.",
        "competitor_context": "Uzbekistan imports halal sausage primarily from Türkiye, Russia, Belarus. We compete on Eurasian recipe profile and EAEU/CIS-friendly logistics.",
    },
    {
        "slug": "halal-pepperoni-kyrgyzstan",
        "country": "Kyrgyzstan",
        "country_code": "KG",
        "currency": "KGS",
        "currency_label": "Kyrgyz Som",
        "city": "Bishkek, Osh",
        "h1": "Halal Pepperoni in Kyrgyzstan — Wholesale from Russia",
        "lede": "Truck DAP Bishkek in 5–7 days via Almaty. EAEU member — no duty, full Mercury VSD. KGS pricing live.",
        "halal_authority": "Kyrgyz Halal Standards Association — recognises DUM RT halal certificate via EAEU and CIS mutual recognition.",
        "import_route": "Truck Kazan → Bishkek (5–7 days), EAEU internal traffic.",
        "transit": "5–7 days truck delivery, monthly cadence available",
        "agents": "Pilot distributor partnership in Bishkek established Q4 2025. Direct foodservice contracts possible.",
        "buyer_profiles": "Pizza chains in Bishkek, foodservice distributors covering Osh and regional cities, halal-default retail.",
        "case": "Pilot pallet shipped to Bishkek foodservice distributor in November 2025; first repeat order received Feb 2026.",
        "hs_codes": "1601.00 — EAEU internal traffic, 0% duty.",
        "labels": "Russian standard; Kyrgyz labelling welcome on request.",
        "payment": "KGS, RUB or USD. Net 14 days after pilot.",
        "competitor_context": "Kyrgyzstan imports halal sausage primarily from Kazakhstan, Russia, Türkiye. We compete on direct factory pricing.",
    },
    {
        "slug": "halal-pepperoni-belarus",
        "country": "Belarus",
        "country_code": "BY",
        "currency": "BYN",
        "currency_label": "Belarusian Ruble",
        "city": "Minsk, Brest, Gomel",
        "h1": "Halal Pepperoni in Belarus — Wholesale Supply",
        "lede": "Truck DAP Minsk in 4–5 days. Union State (Russia–Belarus) — no border, no duty. BYN pricing live in our API.",
        "halal_authority": "Belarusian Muslim Religious Association — recognises DUM RT halal certificate.",
        "import_route": "Truck Kazan → Minsk (4–5 days), Union State internal traffic, no customs.",
        "transit": "4–5 days truck delivery, weekly cadence available",
        "agents": "Direct foodservice distributor contracts in Minsk. Retail-chain pilots ongoing.",
        "buyer_profiles": "Halal-positioned restaurants in Minsk, pizza chains (Pizzaboom franchise), retail chains (Eurotorg, Hipper).",
        "case": "Weekly Halal pepperoni and bakery supply to a Minsk distributor since Q3 2025.",
        "hs_codes": "1601.00 — Union State internal traffic, no tariff.",
        "labels": "Russian standard; Belarusian (Belaruskaja Latinka or Cyrillic) on request.",
        "payment": "BYN, RUB. Net 14 days after pilot.",
        "competitor_context": "Belarus imports halal sausage primarily from Russia. We compete on locked recipe and federal-scale references (Aslam/OMPK).",
    },
    {
        "slug": "halal-pepperoni-azerbaijan",
        "country": "Azerbaijan",
        "country_code": "AZ",
        "currency": "AZN",
        "currency_label": "Azerbaijani Manat",
        "city": "Baku, Ganja, Sumgait",
        "h1": "Halal Pepperoni in Azerbaijan — Direct from Russian Manufacturer",
        "lede": "Truck DAP Baku in 5–7 days via Dagestan. CIS free trade. AZN pricing live in our API.",
        "halal_authority": "Caucasus Muslims Office — recognises DUM RT halal certificate under bilateral religious-affairs agreement.",
        "import_route": "Truck Kazan → Baku via Dagestan / Yarag-Kazmalyar border (5–7 days). CIS preferential customs.",
        "transit": "5–7 days truck delivery, bi-weekly cadence",
        "agents": "Baku foodservice distributor partnership established 2025.",
        "buyer_profiles": "Pizza chains in Baku (Papa John's franchisees, Yo!Pizza), Russian-themed restaurants, halal-positioned supermarkets (Bazarstore, Bravo).",
        "case": "Bi-weekly Halal pepperoni supply to Baku distributor since Q4 2025. Multi-currency invoicing in AZN.",
        "hs_codes": "1601.00 — CIS preferential rate, 0–5%.",
        "labels": "Russian + Azerbaijani Latin standard.",
        "payment": "AZN, RUB or USD. Net 14 days after pilot.",
        "competitor_context": "Azerbaijan imports halal sausage primarily from Türkiye, Russia, Iran. We compete on locked recipe and Eurasian flavour profile.",
    },
    {
        "slug": "halal-pepperoni-armenia",
        "country": "Armenia",
        "country_code": "AM",
        "currency": "AMD",
        "currency_label": "Armenian Dram",
        "city": "Yerevan, Gyumri",
        "h1": "Halal Pepperoni in Armenia — Russian Halal Supplier",
        "lede": "Truck DAP Yerevan in 7–9 days. EAEU member — no duty, simplified VSD. USD invoicing standard.",
        "halal_authority": "Armenia accepts EAEU-recognised halal certificates; DUM RT #614A/2024 is on the list of accepted authorities.",
        "import_route": "Truck Kazan → Yerevan via Georgia (Verkhny Lars border, 7–9 days). EAEU internal traffic.",
        "transit": "7–9 days truck delivery, monthly cadence",
        "agents": "Yerevan foodservice partner serves Russian-Armenian foodservice and halal-tourism HoReCa segment.",
        "buyer_profiles": "Russian-Armenian foodservice chains, halal-tourism hotels in Yerevan, foreign-cuisine restaurants.",
        "case": "Pilot batches shipped Q1 2026 for Russian-Armenian foodservice distributor.",
        "hs_codes": "1601.00 — EAEU internal traffic, 0% duty.",
        "labels": "Russian + Armenian on request.",
        "payment": "USD or RUB. Net 14 days after pilot.",
        "competitor_context": "Armenia imports halal sausage primarily from Russia, Iran (limited). We compete on document discipline and federal-scale references.",
    },
    {
        "slug": "halal-pepperoni-qatar",
        "country": "Qatar",
        "country_code": "QA",
        "currency": "QAR",
        "currency_label": "Qatari Riyal",
        "city": "Doha",
        "h1": "Halal Pepperoni in Qatar — Russian Manufacturer Direct",
        "lede": "DAP Doha cold-chain, 14–18 days port-to-port. GCC Standardization Organization recognises DUM RT halal certificate.",
        "halal_authority": "Qatar General Organization for Standards & Metrology — recognises GCC-aligned DUM RT halal certificate #614A/2024",
        "import_route": "Sea via Novorossiysk → Hamad Port (14–18 days). Air via DOH possible for sample/express orders.",
        "transit": "14–18 days port-to-port via Hamad Port",
        "agents": "Doha-based foodservice agent handles last-mile to hotel chains and pizzeria networks.",
        "buyer_profiles": "Luxury hotels (Four Seasons, Mondrian, Fairmont), pizza chains (Hot Pizza, Papa John's Qatar), foodservice distributors serving Lusail and Education City.",
        "case": "Quote sent Q1 2026 to a Doha foodservice consolidator covering 5 hotel chains; awaiting final spec sign-off.",
        "hs_codes": "1601.00 — GCC tariff 5% MFN, halal-cert exemption available.",
        "labels": "English + Arabic standard. Russian retail labels also accepted in HoReCa back-of-house.",
        "payment": "USD or QAR. 50% prepayment first shipment, LC-at-sight available from $50k.",
        "competitor_context": "Qatar imports halal beef sausage primarily from Brazil, Türkiye, India. Russian halal positions as premium Eurasian alternative.",
    },
    {
        "slug": "halal-pepperoni-egypt",
        "country": "Egypt",
        "country_code": "EG",
        "currency": "EGP",
        "currency_label": "Egyptian Pound",
        "city": "Cairo, Alexandria",
        "h1": "Halal Pepperoni in Egypt — Direct Import from Russia",
        "lede": "DAP Port Said cold-chain, 12–16 days port-to-port. NFSA-aligned halal certificate. USD invoicing.",
        "halal_authority": "Egyptian National Food Safety Authority (NFSA) — accepts DUM RT halal certificate after local agent registration.",
        "import_route": "Sea via Novorossiysk → Port Said (12–16 days). Bulk cold-container shipments practical from 1 FEU.",
        "transit": "12–16 days port-to-port via Port Said",
        "agents": "Cairo-based foodservice agent handles NFSA registration and last-mile to retail chains.",
        "buyer_profiles": "Pizza chains in Cairo and Alexandria (Pizza King, Mince), 5-star hotels in Sharm El-Sheikh and Hurghada catering to Russian tourists, regional foodservice distributors.",
        "case": "Inquiry pipeline from Cairo foodservice agent Q1 2026 — awaiting NFSA registration for first commercial shipment.",
        "hs_codes": "1601.00 — Egypt tariff 30% MFN. Russian-Egyptian trade agreement provisions may apply.",
        "labels": "Arabic + English mandatory under NFSA. Russian also accepted as supplementary.",
        "payment": "USD or EGP. 50% prepayment first shipment, LC for orders ≥ $30k.",
        "competitor_context": "Egypt imports halal sausage primarily from Brazil, India, Türkiye. Russian halal positions on premium consistency and Russian-tourism HoReCa channel.",
    },
    {
        "slug": "halal-pepperoni-turkey",
        "country": "Turkey",
        "country_code": "TR",
        "currency": "TRY",
        "currency_label": "Turkish Lira",
        "city": "Istanbul, Ankara, Izmir",
        "h1": "Halal Pepperoni in Türkiye — Russian Manufacturer Direct",
        "lede": "Truck DAP Istanbul in 9–12 days via Georgia / Black Sea. Turkish Standards Institution recognises DUM RT halal certificate.",
        "halal_authority": "Türkiye Halal Accreditation Agency (HAK) — Turkish halal authority recognises DUM RT under bilateral cooperation framework.",
        "import_route": "Sea via Novorossiysk → Samsun / Trabzon (5 days sea + truck) or truck via Georgia (9–12 days).",
        "transit": "9–12 days truck or sea+truck delivery",
        "agents": "Istanbul-based foodservice agent for HoReCa segment.",
        "buyer_profiles": "Pizza chains in Istanbul / Ankara, Russian-Turkish foodservice (Antalya, Alanya catering to Russian tourists), halal-positioned restaurants.",
        "case": "Sample shipment Q1 2026 to Istanbul foodservice consolidator. Russian halal positioned as European-style alternative to local Turkish sucuk/sujuk profile.",
        "hs_codes": "1601.00 — Türkiye tariff varies 50–80% MFN; competitive only via specific channels (foodservice imports for hotel chains).",
        "labels": "Turkish + English standard. Russian retail labels also accepted in HoReCa back-of-house.",
        "payment": "TRY or USD. 50% prepayment first shipment.",
        "competitor_context": "Turkish market is dominated by local sucuk producers. Russian halal positions in HoReCa for Russian-tourism segment and niche European-style pizzeria pepperoni.",
    },
    {
        "slug": "halal-pepperoni-malaysia",
        "country": "Malaysia",
        "country_code": "MY",
        "currency": "MYR",
        "currency_label": "Malaysian Ringgit",
        "city": "Kuala Lumpur, Penang, Johor Bahru",
        "h1": "Halal Pepperoni in Malaysia — Russian Halal Manufacturer",
        "lede": "DAP Port Klang cold-chain, 25–30 days port-to-port. JAKIM-recognised halal certificate. USD invoicing.",
        "halal_authority": "Malaysian JAKIM (Department of Islamic Development) recognises DUM RT halal certificate under MOU signed in 2018.",
        "import_route": "Sea via Novorossiysk → Singapore → Port Klang (25–30 days). Air via KUL possible for samples.",
        "transit": "25–30 days port-to-port via Port Klang",
        "agents": "Kuala Lumpur-based foodservice agent handles JAKIM registration and last-mile to Malaysian pizza / HoReCa chains.",
        "buyer_profiles": "Pizza chains in KL (Domino's Malaysia, Pizza Hut Malaysia), 5-star hotels in Penang and Langkawi, halal-default supermarkets (Aeon, Mydin, Tesco Malaysia).",
        "case": "JAKIM recognition allows direct route to MY retail; pilot inquiries from KL foodservice agent Q1 2026.",
        "hs_codes": "1601.00 — Malaysia tariff 20% MFN; JAKIM-recognised origin can unlock preferential treatment via specific bilateral channels.",
        "labels": "Bahasa Malaysia + English + Arabic mandatory under JAKIM standards.",
        "payment": "USD or MYR. 50% prepayment first shipment, LC for orders ≥ $50k.",
        "competitor_context": "Malaysia is the world's largest halal certification market. Russian halal is a niche premium alternative to Brazilian, Australian, NZ halal beef.",
    },
]


HEAD_TPL = """<!DOCTYPE html>
<html lang="en">
<head>
<link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
<link rel="dns-prefetch" href="https://www.googletagmanager.com">
<link rel="preconnect" href="https://mc.yandex.ru" crossorigin>
<link rel="dns-prefetch" href="https://mc.yandex.ru">
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);}})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="content-language" content="en">
<link rel="icon" type="image/png" sizes="32x32" href="/images/icon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/images/icon-16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/images/icon-180.png">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="manifest" href="/manifest.json">
<link rel="llms" href="/en/llms.txt" type="text/plain" title="LLM instructions (English)">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="keywords" content="{keywords}">
<meta name="robots" content="index, follow">
<meta name="geo.region" content="{country_code}">
<meta name="geo.placename" content="{city}">
<link rel="canonical" href="https://pepperoni.tatar/en/geo/{slug}">
<link rel="alternate" hreflang="en" href="https://pepperoni.tatar/en/geo/{slug}">
<link rel="alternate" hreflang="x-default" href="https://pepperoni.tatar/en/geo/{slug}">

<meta property="og:type" content="website">
<meta property="og:title" content="{h1}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="https://pepperoni.tatar/en/geo/{slug}">
<meta property="og:image" content="https://pepperoni.tatar/og-default-en.png">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{h1}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="https://pepperoni.tatar/og-default-en.png">

<script type="application/ld+json">{org_jsonld}</script>
<script type="application/ld+json">{place_jsonld}</script>
<script type="application/ld+json">{faq_jsonld}</script>
<script type="application/ld+json">{breadcrumb_jsonld}</script>

<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.75}}
.container{{max-width:840px;margin:0 auto;padding:36px 22px}}
nav{{font-size:.85rem;color:#888;margin-bottom:18px}}
nav a{{color:#0066cc;text-decoration:none}}
.flag-line{{display:inline-block;background:#fef3c7;color:#92400e;padding:4px 10px;border-radius:4px;font-size:.72rem;font-weight:700;margin-bottom:10px;letter-spacing:.5px;text-transform:uppercase}}
h1{{font-size:1.85rem;font-weight:700;margin-bottom:10px;line-height:1.25}}
h2{{font-size:1.2rem;font-weight:700;margin:30px 0 12px;color:#1b7a3d}}
p{{margin-bottom:12px}}
.lede{{color:#555;font-size:1.04rem;margin-bottom:10px}}
.badge{{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.82rem;font-weight:600;margin:4px 6px 4px 0}}
.badge-outline{{background:transparent;border:1.5px solid #1b7a3d;color:#1b7a3d}}
.fact-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin:14px 0}}
.fact{{background:#fff;border-left:3px solid #1b7a3d;padding:12px 14px;border-radius:4px;font-size:.9rem}}
.fact .label{{font-size:.72rem;text-transform:uppercase;letter-spacing:.5px;color:#888;margin-bottom:4px}}
.spec-table{{width:100%;border-collapse:collapse;margin:12px 0;background:#fff;border:1px solid #e5e5e5;border-radius:8px;overflow:hidden}}
.spec-table td{{padding:10px 14px;border-bottom:1px solid #eee;font-size:.92rem;vertical-align:top}}
.spec-table td:first-child{{color:#666;width:34%}}
.spec-table tr:last-child td{{border-bottom:0}}
.faq details{{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:14px 18px;margin:8px 0}}
.faq summary{{cursor:pointer;font-weight:600;font-size:.95rem;color:#1a1a1a;list-style:none}}
.faq summary::-webkit-details-marker{{display:none}}
.faq summary::before{{content:"+ ";color:#1b7a3d;font-weight:700;margin-right:4px}}
.faq details[open] summary::before{{content:"− "}}
.faq p{{margin:10px 0 0;color:#444;font-size:.92rem}}
.cta{{background:#1b7a3d;color:#fff;display:inline-block;padding:12px 26px;border-radius:8px;text-decoration:none;font-weight:600;font-size:.95rem;margin:8px 8px 0 0}}
.cta-outline{{background:transparent;border:2px solid #1b7a3d;color:#1b7a3d}}
.related{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin:14px 0}}
.related a{{display:block;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:12px;text-decoration:none;color:#1a1a1a;font-size:.88rem}}
.related strong{{display:block;margin-bottom:3px}}
footer{{text-align:center;color:#aaa;font-size:.85rem;padding-top:30px;margin-top:32px;border-top:1px solid #eee}}
footer a{{color:#888;text-decoration:none}}
</style>
</head>
<body>
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<div class="container">
<div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid #eee;font-size:.9rem">
  <a href="/en/" style="color:#0066cc;text-decoration:none;font-weight:600">Catalog</a>
  <a href="/en/pepperoni" style="color:#0066cc;text-decoration:none">Pepperoni</a>
  <a href="/en/about" style="color:#0066cc;text-decoration:none">About</a>
  <a href="/en/halal-pepperoni-export" style="color:#0066cc;text-decoration:none">Export</a>
  <a href="/en/faq" style="color:#0066cc;text-decoration:none">FAQ</a>
  <a href="/" style="color:#888;margin-left:auto;text-decoration:none">🇷🇺 RU</a>
</div>
<nav aria-label="Breadcrumb">
  <a href="/en/">Catalog</a> &rsaquo; <a href="/en/halal-pepperoni-export">Export</a> &rsaquo; <span>{country}</span>
</nav>

<span class="flag-line">Export market · {country}</span>
<h1>{h1}</h1>
<p class="lede">{lede}</p>
<div>
  <span class="badge">HALAL #614A/2024</span>
  <span class="badge badge-outline">HACCP + ISO 22000</span>
  <span class="badge badge-outline">{currency} pricing live</span>
  <span class="badge badge-outline">EXW Kazan</span>
</div>

<div class="fact-grid">
  <div class="fact"><div class="label">Currency</div>{currency} · {currency_label}</div>
  <div class="fact"><div class="label">Cities served</div>{city}</div>
  <div class="fact"><div class="label">Transit time</div>{transit}</div>
  <div class="fact"><div class="label">HS code</div>{hs_codes}</div>
</div>

<h2>Halal authority recognition in {country}</h2>
<p>{halal_authority}</p>

<h2>Import route &amp; logistics</h2>
<p>{import_route}</p>
<p><strong>Local agent:</strong> {agents}</p>

<h2>Typical buyer profile in {country}</h2>
<p>{buyer_profiles}</p>

<h2>Case &amp; pipeline</h2>
<p>{case}</p>

<h2>Documents &amp; labelling for {country}</h2>
<table class="spec-table"><tbody>
  <tr><td>Halal certificate</td><td>#614A/2024 (DUM RT) — accepted</td></tr>
  <tr><td>HS codes</td><td>{hs_codes}</td></tr>
  <tr><td>Labels</td><td>{labels}</td></tr>
  <tr><td>Payment terms</td><td>{payment}</td></tr>
  <tr><td>Currency invoicing</td><td>{currency} (live in API), USD, RUB</td></tr>
  <tr><td>EAEU declaration</td><td>Yes, included with shipment</td></tr>
  <tr><td>Mercury VSD (FGIS)</td><td>Yes — electronic, attached to consignment</td></tr>
  <tr><td>COA / Nutrition panel</td><td>On request, per SKU</td></tr>
</tbody></table>

<h2>Market context</h2>
<p>{competitor_context}</p>

<h2>FAQ — frequently asked by {country} buyers</h2>
<div class="faq">
  <details><summary>Will my halal authority accept your certificate?</summary><p>{halal_authority}</p></details>
  <details><summary>What's the transit time to {city}?</summary><p>{transit}.</p></details>
  <details><summary>Can you invoice in {currency}?</summary><p>Yes — {currency} ({currency_label}) pricing is live in our API at api.pepperoni.tatar/api/products?currency={currency}. We can also invoice in USD or RUB depending on your accounting setup.</p></details>
  <details><summary>What's the minimum first order?</summary><p>1 pallet (≈500 kg of mixed SKUs) for a pilot. Subsequent orders scale per agreed cadence (weekly / bi-weekly / monthly).</p></details>
  <details><summary>Can you handle private label for {country}?</summary><p>Yes — from 500 kg/month per SKU. Recipe, casing, diameter, packaging, brand fully customisable. Federal-scale reference: «Aslam» pepperoni for OMPK / Ostankino.</p></details>
</div>

<h2>Get a quote for {country}</h2>
<p>Send an email or WhatsApp and we'll respond within one working day with a personalised price list ({currency} or your preferred currency) and pilot terms for {country}.</p>
<a href="tel:+79872170202" class="cta">📞 +7 987 217-02-02</a>
<a href="mailto:info@kazandelikates.tatar?subject={email_subject}" class="cta cta-outline">📧 info@kazandelikates.tatar</a>
<a href="https://wa.me/79872170202?text={whatsapp_text}" class="cta cta-outline">💬 WhatsApp</a>

<h2>See also</h2>
<div class="related">
  <a href="/en/halal-pepperoni-export"><strong>Halal Pepperoni Export</strong>All markets overview</a>
  <a href="/en/wholesale-halal-pepperoni-supplier"><strong>Wholesale Supplier</strong>MOQ, payment, lead time</a>
  <a href="/en/halal-pepperoni-russia"><strong>Halal pepperoni from Russia</strong>Origin & certificates</a>
  <a href="/en/halal-pepperoni-for-pizzerias"><strong>Pizzeria range</strong>All formats</a>
  <a href="/en/beef-halal-pepperoni"><strong>Beef recipe</strong>Ingredients & origin</a>
  <a href="/en/about"><strong>About Kazan Delicacies</strong>Company profile</a>
</div>

<footer>
  <p><a href="/en/">← Catalog</a> &middot; <a href="/en/about">About</a> &middot; <a href="/en/halal-pepperoni-export">Export</a> &middot; <a href="/en/faq">FAQ</a> &middot; <a href="/en/privacy">Privacy</a></p>
  <p>&copy; <a href="https://kazandelikates.tatar">Kazan Delicacies</a> &middot; <a href="https://pepperoni.tatar/en/">pepperoni.tatar/en</a></p>
</footer>
</div>
<script>(function(m,e,t,r,i,k,a){{m[i]=m[i]||function(){{(m[i].a=m[i].a||[]).push(arguments)}};m[i].l=1*new Date();for(var j=0;j<document.scripts.length;j++){{if(document.scripts[j].src===r)return}}k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a);}})(window,document,'script','https://mc.yandex.ru/metrika/tag.js','ym');ym(107064141,'init',{{clickmap:true,trackLinks:true,accurateTrackBounce:true,ecommerce:'dataLayer'}});</script>
</body>
</html>
"""


def build_org_jsonld():
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": "https://pepperoni.tatar/#organization",
        "name": "Kazan Delicacies",
        "alternateName": "Казанские Деликатесы",
        "url": "https://kazandelikates.tatar",
        "logo": "https://pepperoni.tatar/images/logo.png",
        "email": "info@kazandelikates.tatar",
        "telephone": "+79872170202",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "ul. Agrarnaya, 2",
            "addressLocality": "Kazan",
            "addressRegion": "Tatarstan",
            "postalCode": "420059",
            "addressCountry": "RU",
        },
        "hasCredential": {
            "@type": "EducationalOccupationalCredential",
            "name": "Halal",
            "identifier": "614A/2024",
            "recognizedBy": {
                "@type": "Organization",
                "name": "Muslim Spiritual Board of Tatarstan",
                "url": "https://dumrt.ru",
            },
        },
    }, ensure_ascii=False)


def build_place_jsonld(geo):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "ServiceArea",
        "@id": f"https://pepperoni.tatar/en/geo/{geo['slug']}#service-area",
        "name": f"Halal pepperoni supply to {geo['country']}",
        "url": f"https://pepperoni.tatar/en/geo/{geo['slug']}",
        "serviceArea": {
            "@type": "Country",
            "name": geo["country"],
            "identifier": geo["country_code"],
        },
        "areaServed": geo["country"],
        "provider": {"@id": "https://pepperoni.tatar/#organization"},
        "availableLanguage": ["en", "ru"],
    }, ensure_ascii=False)


def build_faq_jsonld(geo):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": f"Will my halal authority in {geo['country']} accept your certificate?",
             "acceptedAnswer": {"@type": "Answer", "text": geo["halal_authority"]}},
            {"@type": "Question", "name": f"What's the transit time to {geo['city']}?",
             "acceptedAnswer": {"@type": "Answer", "text": geo["transit"]}},
            {"@type": "Question", "name": f"Can you invoice in {geo['currency']}?",
             "acceptedAnswer": {"@type": "Answer", "text": f"Yes — {geo['currency']} ({geo['currency_label']}) pricing is live in our API at api.pepperoni.tatar/api/products?currency={geo['currency']}. USD and RUB also available."}},
            {"@type": "Question", "name": "What's the minimum first order?",
             "acceptedAnswer": {"@type": "Answer", "text": "1 pallet (≈500 kg of mixed SKUs) for a pilot. Subsequent orders scale per agreed cadence."}},
            {"@type": "Question", "name": f"Can you handle private label for {geo['country']}?",
             "acceptedAnswer": {"@type": "Answer", "text": "Yes — from 500 kg/month per SKU. Recipe, casing, diameter, packaging, brand customisable. Federal-scale reference: «Aslam» pepperoni for OMPK / Ostankino."}},
        ],
    }, ensure_ascii=False)


def build_breadcrumb_jsonld(geo):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Catalog", "item": "https://pepperoni.tatar/en/"},
            {"@type": "ListItem", "position": 2, "name": "Export", "item": "https://pepperoni.tatar/en/halal-pepperoni-export"},
            {"@type": "ListItem", "position": 3, "name": geo["country"], "item": f"https://pepperoni.tatar/en/geo/{geo['slug']}"},
        ],
    }, ensure_ascii=False)


def render(geo):
    title = f"{geo['h1']} — Wholesale, Direct Import, Halal #614A/2024"
    keywords = f"halal pepperoni {geo['country'].lower()}, halal pepperoni import {geo['country'].lower()}, russian halal pepperoni {geo['country'].lower()}, halal supplier {geo['country'].lower()}, halal pepperoni {geo['city'].split(',')[0].lower().strip()}"
    description = f"{geo['lede']} HALAL #614A/2024 (DUM RT). HACCP + ISO 22000. Direct factory pricing in {geo['currency']} live at api.pepperoni.tatar/api/products."
    return HEAD_TPL.format(
        slug=geo["slug"],
        title=title,
        description=description,
        keywords=keywords,
        country=geo["country"],
        country_code=geo["country_code"],
        currency=geo["currency"],
        currency_label=geo["currency_label"],
        city=geo["city"],
        h1=geo["h1"],
        lede=geo["lede"],
        halal_authority=geo["halal_authority"],
        import_route=geo["import_route"],
        transit=geo["transit"],
        agents=geo["agents"],
        buyer_profiles=geo["buyer_profiles"],
        case=geo["case"],
        hs_codes=geo["hs_codes"],
        labels=geo["labels"],
        payment=geo["payment"],
        competitor_context=geo["competitor_context"],
        org_jsonld=build_org_jsonld(),
        place_jsonld=build_place_jsonld(geo),
        faq_jsonld=build_faq_jsonld(geo),
        breadcrumb_jsonld=build_breadcrumb_jsonld(geo),
        email_subject=quote(f"Halal pepperoni inquiry — {geo['country']}"),
        whatsapp_text=quote(f"Hi, I'm a buyer in {geo['country']} interested in halal pepperoni — please send a quote in {geo['currency']}."),
    )


def main():
    for geo in GEOS:
        out = GEO_DIR / f"{geo['slug']}.html"
        out.write_text(render(geo), encoding="utf-8")
        print(f"OK {out}  ({out.stat().st_size//1024} KB)")


if __name__ == "__main__":
    main()
