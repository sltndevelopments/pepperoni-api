#!/usr/bin/env python3
"""Generate 6 EN keyword-targeted product landing pages.

Each page has its own H1 / meta / Schema.org Product + FAQPage, but
they share a Python template (the same look-and-feel as the existing
RU sales pages).

Outputs:
  public/en/halal-sliced-pepperoni-for-pizza
  public/en/beef-halal-pepperoni
  public/en/halal-pepperoni-for-pizzerias
  public/en/wholesale-halal-pepperoni-supplier
  public/en/halal-pepperoni-russia
  public/en/halal-pepperoni-export

(Trailing .html added by file system; Vercel `cleanUrls: true` serves them at /en/<slug>.)
"""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
EN_DIR = PUBLIC / "en"


# Pull one-off product photos from public/products.json so the FAQ cards
# show real pictures, not placeholders.
def get_product_images() -> dict:
    data = json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))
    by_sku = {p["sku"]: p for p in data.get("products", [])}
    pick = {
        "sliced": by_sku.get("KD-015") or {},   # boiled-smoked pepperoni sliced
        "stick":  by_sku.get("KD-016") or {},   # boiled-smoked pepperoni whole stick
        "horse":  by_sku.get("KD-014") or {},   # horse-meat pepperoni
        "dry":    by_sku.get("KD-027") or {},   # dry-cured pepperoni
    }
    return pick


PAGES = [
    {
        "slug": "halal-sliced-pepperoni-for-pizza",
        "title": "Halal Sliced Pepperoni for Pizza Wholesale — Kazan Delicacies",
        "h1": "Halal Sliced Pepperoni for Pizza",
        "subtitle": "Pre-sliced, oven-stable, 0.5 kg vacuum packs. No curling, locked diameter, halal #614A/2024.",
        "description": "Halal sliced pepperoni for pizza wholesale: 0.5 kg vacuum packs, pre-sliced, oven-stable (280–320 °C), no curling. Beef & chicken classic. HACCP. EXW Kazan, Russia. Used by federal pizza chains.",
        "keywords": "halal sliced pepperoni for pizza, halal pizza topping wholesale, pre-sliced halal pepperoni, halal beef pepperoni sliced, pork-free pizza topping",
        "intent": "buyer wants sliced halal pepperoni ready to use on pizzas — wholesale volume, oven-stable",
        "primary_sku": "KD-015",
        "primary_name": "Boiled-Smoked Pepperoni Classic (sliced, beef & chicken)",
        "primary_price_rub": "274",
        "primary_price_usd": "3.37",
        "primary_weight": "0.5 kg",
        "primary_pack": "Vacuum-packed",
        "primary_storage": "−18 °C, 180 days frozen; +4 °C, 5 days after opening",
        "primary_diameter": "38 mm",
        "primary_yield": "≈ 80 slices per pack (depending on slice thickness)",
        "specs": [
            ("SKU", "KD-015"),
            ("Format", "Pre-sliced, vacuum-packed"),
            ("Net weight", "0.5 kg per pack"),
            ("Stick diameter", "38 mm (slice ≈ 36 mm)"),
            ("Recipe", "Beef + chicken, no pork"),
            ("Halal", "Certified #614A/2024 by DUM RT"),
            ("HACCP", "Yes, ISO 22000:2018"),
            ("Cooking", "Oven-stable to 320 °C — no curling, no grease bleed"),
            ("Shelf life", "180 days frozen at −18 °C"),
            ("Minimum order", "1 pallet for pilot · ramp by category"),
        ],
        "faqs": [
            ("Is this pepperoni really halal?", "Yes. We hold halal certificate #614A/2024 from the Halal Standards Committee of the Muslim Spiritual Board of the Republic of Tatarstan (DUM RT). Zero pork, zero pork derivatives. Certificate copies are sent with every shipment and on request via info@kazandelikates.tatar."),
            ("Will the slice curl in a stone-deck oven?", "No. The product is engineered for stone-deck, conveyor, and pan ovens at 280–320 °C. Curling and grease bleed are eliminated by recipe formulation, not by curing time."),
            ("What's the slice yield per pack?", "Around 80 slices per 0.5 kg pack depending on slice thickness. Most pizzerias settle on 1.6–1.8 mm, giving 75–85 slices."),
            ("Can I order under my own brand?", "Yes — private label (СТМ / SBM / white-label) starts from 500 kg/month. We did this for OMPK / Ostankino (their 'Aslam' brand)."),
            ("What's the lead time for first shipment?", "4–6 weeks for a custom recipe; 1–2 weeks for our stock SKU."),
            ("Do you ship to UAE / Kazakhstan / Uzbekistan / Saudi Arabia?", "Yes. We ship EXW Kazan and the buyer arranges transit. Multi-currency invoicing (USD, KZT, UZS, KGS, BYN, AZN, RUB). Halal certificate accepted for all GCC and CIS markets."),
        ],
        "related_links": [
            ("/en/halal-pepperoni-for-pizzerias", "Halal Pepperoni for Pizzerias", "All formats + case studies"),
            ("/en/beef-halal-pepperoni", "Beef Halal Pepperoni", "Recipe deep-dive"),
            ("/en/wholesale-halal-pepperoni-supplier", "Wholesale Supplier", "Terms, MOQ, payment"),
            ("/en/products/kd-015", "KD-015 product card", "Full specs"),
            ("/en/dlya-pizzerii", "Buyer guide for pizzerias", "Range, formats, photos"),
            ("/en/kontraktnoe-proizvodstvo", "Private Label", "СТМ / white-label"),
        ],
    },
    {
        "slug": "beef-halal-pepperoni",
        "title": "Beef Halal Pepperoni — Wholesale Manufacturer, Russia | Kazan Delicacies",
        "h1": "Beef Halal Pepperoni (Beef & Chicken Recipe)",
        "subtitle": "Classic boiled-smoked pepperoni made from beef and chicken — no pork, no horse. Whole 1 kg sticks and 0.5 kg pre-sliced packs.",
        "description": "Beef halal pepperoni wholesale from Kazan: classic recipe (beef + chicken, no pork), boiled-smoked, whole 1 kg stick or 0.5 kg sliced. Halal certificate #614A/2024. HACCP + ISO 22000. Used by federal pizza chains, retail (EuroSpar, Bahetle), Aslam/OMPK private label.",
        "keywords": "beef halal pepperoni, halal beef pepperoni manufacturer, pork-free pepperoni Russia, halal pepperoni beef chicken, halal pepperoni recipe, halal pepperoni wholesale",
        "intent": "buyer specifically wants the beef-based halal pepperoni recipe and asks for ingredients / certificates",
        "primary_sku": "KD-016",
        "primary_name": "Boiled-Smoked Pepperoni Classic (whole stick, beef & chicken)",
        "primary_price_rub": "457",
        "primary_price_usd": "5.62",
        "primary_weight": "1.0 kg",
        "primary_pack": "Vacuum-packed whole stick",
        "primary_storage": "−18 °C, 180 days frozen; +4 °C, 10 days after opening",
        "primary_diameter": "38 mm",
        "primary_yield": "≈ 160 slices per stick (1.8 mm thickness)",
        "specs": [
            ("SKU", "KD-016 (stick) / KD-015 (sliced)"),
            ("Recipe", "High-quality beef (≥50%), chicken meat, spices, curing salts, natural smoke"),
            ("Protein content", "≥ 18 g per 100 g"),
            ("Fat", "≤ 32 g per 100 g"),
            ("Halal", "DUM RT certificate #614A/2024 — pork-free, no pork derivatives, no alcohol"),
            ("HACCP", "Yes, ISO 22000:2018"),
            ("Smoking", "Natural beechwood smoke, 6 h"),
            ("Shelf life", "180 days frozen / 30 days chilled vac-pack"),
            ("Minimum order", "1 pallet pilot · 500 kg/month for private label"),
            ("Available formats", "Whole 1 kg stick · 0.5 kg sliced · custom slice thickness for HoReCa"),
        ],
        "faqs": [
            ("What's exactly in the beef halal pepperoni?", "High-quality beef (≥50%), poultry meat, water, table salt, curing salt mix (sodium nitrite), natural beech smoke, spice mix (paprika, garlic, white pepper, ground cardamom). No pork, no pork derivatives, no alcohol, no MSG. Allergen statement: contains spices. Full nutrition and allergens panel on the EAEU declaration."),
            ("Is the beef sourced from halal-slaughtered cattle?", "Yes. We only purchase from suppliers with valid halal certificates issued by Russian or international halal authorities. The chain of custody is documented and audited annually by DUM RT."),
            ("Why beef + chicken, not 100% beef?", "100% beef gives a denser, drier slice — most pizzerias prefer the slightly softer mouthfeel of a beef/chicken blend that still curls well on the pizza. 100% beef on request, 4–6 week lead time."),
            ("Can you do a kosher version?", "No — we hold a halal certificate, not a kosher one. We can however certify pork-free + alcohol-free + gluten-free on request."),
            ("What's the price by the tonne?", "Wholesale price drops 8–12% on orders ≥ 1 tonne and 15–18% on ≥ 5 tonnes monthly. Live pricing via /api/products. Private-label pricing on request."),
            ("Do you sell horse-meat pepperoni too?", "Yes — KD-014 (boiled-smoked pepperoni, horse meat) and KD-027 (dry-cured pepperoni). Both halal. See /en/halal-pepperoni-for-pizzerias."),
        ],
        "related_links": [
            ("/en/halal-sliced-pepperoni-for-pizza", "Sliced halal pepperoni", "Ready-to-use pizza topping"),
            ("/en/halal-pepperoni-for-pizzerias", "All pepperoni formats", "Stick, sliced, dry-cured"),
            ("/en/wholesale-halal-pepperoni-supplier", "Wholesale terms", "MOQ, payment, lead time"),
            ("/en/halal-pepperoni-russia", "Halal pepperoni from Russia", "Geo & certificates"),
            ("/en/products/kd-016", "KD-016 product card", "Full specs"),
            ("/en/dlya-pizzerii", "Buyer guide", "Sales segments"),
        ],
    },
    {
        "slug": "halal-pepperoni-for-pizzerias",
        "title": "Halal Pepperoni for Pizzerias — All Formats Wholesale | Kazan Delicacies",
        "h1": "Halal Pepperoni for Pizzerias — All Formats",
        "subtitle": "Whole 1 kg sticks, 0.5 kg sliced, dry-cured premium, horse-meat unique SKU. Locked diameter, halal-default, pizzeria-tested.",
        "description": "Halal pepperoni catalog for pizzerias: 3 formats × 2 recipes (classic beef+chicken, horse meat), boiled-smoked or dry-cured. Whole 1 kg, 0.5 kg sliced. Federal-scale references (Aslam/OMPK). Live pricing in 7 currencies.",
        "keywords": "halal pepperoni for pizzerias, pizzeria halal pepperoni wholesale, halal pizza chain supplier, halal pepperoni stick, halal pepperoni slice, oven-stable halal pepperoni",
        "intent": "pizzeria buyer evaluating all pepperoni options at once",
        "primary_sku": "KD-016",
        "primary_name": "Boiled-Smoked Pepperoni Classic (whole stick)",
        "primary_price_rub": "457",
        "primary_price_usd": "5.62",
        "primary_weight": "1.0 kg",
        "primary_pack": "Vacuum-packed whole stick",
        "primary_storage": "−18 °C, 180 days frozen",
        "primary_diameter": "38 mm",
        "primary_yield": "≈ 160 slices per stick",
        "specs": [
            ("Available SKUs", "KD-014 (horse-meat, sliced) · KD-015 (classic, sliced) · KD-016 (classic, whole) · KD-027 (dry-cured, sliced) · KD-028 (dry-cured, whole)"),
            ("Recipes", "Classic beef+chicken · Horse meat · Dry-cured"),
            ("Formats", "Whole 1 kg stick · 0.5 kg pre-sliced · custom slice thickness"),
            ("Diameter", "38 mm (classic) · 36 mm (dry-cured)"),
            ("Oven behaviour", "Stable at 280–320 °C; no curling; no grease bleed"),
            ("Halal", "Certificate #614A/2024, DUM RT — all SKUs"),
            ("Federal references", "Aslam (OMPK / Ostankino), EuroSpar, Bahetle, Metro, Miratorg, Tatneft AZS"),
            ("Logistics", "EXW Kazan or DC Lyubertsy (Moscow region)"),
            ("MOQ", "1 pallet for pilot, 500 kg/mo for private label"),
            ("Lead time", "1–2 weeks stock, 4–6 weeks private label"),
        ],
        "faqs": [
            ("Which pepperoni SKU works best in a stone-deck oven at 300 °C?", "KD-015 (sliced) or KD-016 (whole, sliced in-house) — the classic beef+chicken recipe is engineered for stone deck. KD-027/028 (dry-cured) is denser and better for cold cuts or as a premium topping on artisan pizzas."),
            ("Do you carry a true Italian-style dry-cured pepperoni?", "Yes — KD-027/028 (dry-cured, 25-day curing, beef+chicken). It mimics the Italian Salame Pepperoni profile but is fully halal and pork-free."),
            ("Why is horse-meat pepperoni interesting for a pizzeria?", "Two reasons: (1) it's a distinct premium SKU for the menu — unique flavour, talking point with guests; (2) horse meat in Russia is the natural halal alternative to wild boar/pork notes — many Muslim guests specifically ask for it."),
            ("Can you supply at federal scale?", "Yes. We manufacture 'Aslam' branded pepperoni for OMPK JSC (Ostankino Meat Plant) — Russia's largest meat producer. The product ships to pizzerias nationwide under their distribution."),
            ("Is there a private-label option?", "Yes. From 500 kg/month per SKU. Recipe, casing, diameter, slice thickness, packaging, brand all customisable. NDA + regional exclusivity on request."),
            ("What documents do I get with the shipment?", "EAEU declaration, Mercury VSD (FGIS), halal certificate, nutrition panel, QR-traceability label, packing list."),
        ],
        "related_links": [
            ("/en/halal-sliced-pepperoni-for-pizza", "Sliced format", "Ready-to-use"),
            ("/en/beef-halal-pepperoni", "Beef recipe deep-dive", "Ingredients & origin"),
            ("/en/wholesale-halal-pepperoni-supplier", "Wholesale terms", "MOQ, payment"),
            ("/en/halal-pepperoni-russia", "Halal pepperoni from Russia", "Geographic context"),
            ("/en/halal-pepperoni-export", "Export to GCC / CIS", "Documents, HS codes"),
            ("/en/dlya-pizzerii", "Buyer guide for pizzerias", "Full B2B context"),
        ],
    },
    {
        "slug": "wholesale-halal-pepperoni-supplier",
        "title": "Wholesale Halal Pepperoni Supplier — Russia / CIS / GCC | Kazan Delicacies",
        "h1": "Wholesale Halal Pepperoni Supplier",
        "subtitle": "Direct from Kazan factory: 7-currency pricing, EXW Kazan, pilot from 1 pallet, private label from 500 kg/month.",
        "description": "Wholesale halal pepperoni supplier from Kazan, Russia. 5 pepperoni SKUs (whole / sliced / horse meat / dry-cured), live pricing in 7 currencies, EXW Kazan, federal-scale references (Aslam/OMPK). Halal #614A/2024 + HACCP.",
        "keywords": "wholesale halal pepperoni supplier, halal pepperoni B2B Russia, halal pepperoni distributor, halal pepperoni manufacturer wholesale, halal meat supplier Kazan",
        "intent": "B2B buyer evaluating us as a wholesale supplier — wants MOQ, payment, lead time, documents",
        "primary_sku": "KD-016",
        "primary_name": "Halal Pepperoni Catalog Entry SKU",
        "primary_price_rub": "457",
        "primary_price_usd": "5.62",
        "primary_weight": "1.0 kg",
        "primary_pack": "Vacuum-packed whole stick",
        "primary_storage": "−18 °C, 180 days frozen",
        "primary_diameter": "38 mm",
        "primary_yield": "≈ 160 slices per stick",
        "specs": [
            ("Production capacity", "Up to 60 tonnes / month, scalable in 2 weeks"),
            ("Catalog depth", "5 pepperoni SKUs + 72 other halal meat & bakery SKUs"),
            ("MOQ", "Pilot from 1 pallet (∼500 kg). Private label from 500 kg/month/SKU"),
            ("Lead time", "1–2 weeks stock SKU · 4–6 weeks private label / custom recipe"),
            ("Incoterms", "EXW Kazan (default) · CPT / DAP CIS on agreement"),
            ("Currencies", "RUB (with/without VAT), USD, KZT, UZS, KGS, BYN, AZN"),
            ("Payment", "As per contract after pilot · 50 % prepayment for first export shipment"),
            ("Documents", "EAEU declaration, Mercury VSD, Halal cert, nutrition panel, HS codes, COA on request, QR-traceability"),
            ("Federal references", "OMPK (Aslam), Tatneft AZS, SMARTEN, EuroSpar, Bahetle, Metro, Miratorg, GFC, SweetLife"),
            ("API for distributors", "Live JSON at api.pepperoni.tatar/api/products, daily-synced 7-currency price list"),
        ],
        "faqs": [
            ("What's the smallest pilot order I can place?", "One pallet (≈ 500 kg of mixed SKUs). We treat the first order as a pilot — full payment up-front, document pack issued, and you decide whether to scale into a regular cadence."),
            ("Do you work on deferred payment terms?", "Yes — after a successful pilot. The first shipment is prepaid 100 %. From the second shipment onward, payment terms are as per contract and negotiable based on volume."),
            ("How do I get a live price list?", "Three ways. (1) Open https://api.pepperoni.tatar/api/products — JSON, no auth. (2) Download CSV/XLSX from the catalog UI, choose your currency and VAT preference. (3) Email info@kazandelikates.tatar — we send a personalised price list in your currency within one working day."),
            ("Is regional exclusivity available?", "Yes, for distributors. Exclusivity is set per category × region, negotiated before pilot, formalised in a distribution agreement."),
            ("What's your production capacity if I need 10 tonnes / month?", "10 tonnes/month is within standard capacity — we can confirm slot within 1 week. Above 30 tonnes/month, give us 4 weeks of lead time for scheduling."),
            ("Do you have a sales rep speaking English / Arabic?", "English yes (direct correspondence). Arabic via a partner translator in Kazan and one in UAE for face-to-face meetings with GCC buyers."),
        ],
        "related_links": [
            ("/en/dlya-distributorov", "For Distributors", "Regional exclusivity"),
            ("/en/kontraktnoe-proizvodstvo", "Private Label", "СТМ / white-label"),
            ("/en/halal-pepperoni-export", "Export to CIS / GCC", "Documents, HS codes"),
            ("/en/halal-pepperoni-russia", "Halal pepperoni from Russia", "Geographic context"),
            ("/en/halal-pepperoni-for-pizzerias", "All formats", "Pizzeria-focused"),
            ("/en/about", "About Kazan Delicacies", "Company profile"),
        ],
    },
    {
        "slug": "halal-pepperoni-russia",
        "title": "Halal Pepperoni from Russia — Kazan-Made, Federal Brand | Kazan Delicacies",
        "h1": "Halal Pepperoni from Russia (Made in Kazan, Tatarstan)",
        "subtitle": "Manufactured in Kazan, the Muslim capital of the Russian Federation. Halal #614A/2024 from DUM RT — the most respected halal authority in Russia.",
        "description": "Halal pepperoni from Russia, made in Kazan, Tatarstan — the Muslim capital of the Russian Federation. Halal cert #614A/2024 from DUM RT, HACCP + ISO 22000. Federal supplier to Tatneft AZS, Aslam/OMPK, Bahetle, EuroSpar.",
        "keywords": "halal pepperoni Russia, halal meat Russia, Kazan halal manufacturer, halal pepperoni Tatarstan, DUM RT halal certificate, halal Russia export",
        "intent": "user searching by origin (Russia / Kazan) and wants assurance of authenticity / halal credentials",
        "primary_sku": "KD-016",
        "primary_name": "Halal Pepperoni from Russia (KD-016)",
        "primary_price_rub": "457",
        "primary_price_usd": "5.62",
        "primary_weight": "1.0 kg",
        "primary_pack": "Vacuum-packed whole stick",
        "primary_storage": "−18 °C, 180 days frozen",
        "primary_diameter": "38 mm",
        "primary_yield": "≈ 160 slices per stick",
        "specs": [
            ("Manufacturer", "Kazan Delicacies LLC (ООО «Казанские Деликатесы»)"),
            ("Tax ID (INN)", "1655504520"),
            ("Address", "Russia, Tatarstan, Kazan, Agrarnaya St. 2 (420059)"),
            ("Founded", "2022 (Halal-default product line)"),
            ("Halal authority", "DUM RT (Muslim Spiritual Board of the Republic of Tatarstan) — federally recognised"),
            ("Halal certificate", "#614A/2024 — covers all 77 SKUs"),
            ("Food safety", "HACCP + ISO 22000:2018"),
            ("Production facility", "20 000 m² in Kazan, dedicated halal line, no pork on premises"),
            ("Federal-scale references", "Aslam (OMPK / Ostankino), Tatneft, SMARTEN, EuroSpar, Bahetle, Metro, Miratorg"),
            ("Logistics", "EXW Kazan · CIS export via Lyubertsy DC"),
        ],
        "faqs": [
            ("Why Kazan specifically?", "Kazan is the historic capital of the Republic of Tatarstan — home to the largest Muslim community in central Russia (≈ 2 million) and the seat of the Russian Muslim Spiritual Board. Halal food production has been an unbroken tradition here for centuries; the regulatory and supply infrastructure for halal meat is the most mature in Russia."),
            ("How does DUM RT halal certification compare to Saudi/Malaysian halal?", "DUM RT (Muslim Spiritual Board of the Republic of Tatarstan) is recognised by the GCC Standardisation Organization and by Malaysian JAKIM through mutual recognition agreements. Our halal certificate #614A/2024 is accepted in UAE, Saudi Arabia, Kuwait, Bahrain, Kazakhstan, Uzbekistan, Kyrgyzstan, and Belarus."),
            ("Is the product 100 % made in Russia?", "Yes. Cattle and poultry are sourced from halal-certified farms in Tatarstan and neighbouring regions (Mari El, Bashkortostan). Meat processing, smoking, packaging and labelling all happen in our Kazan facility."),
            ("Why not import from Turkey or UAE?", "Many of our GCC and CIS buyers specifically prefer Russian halal because (1) Russian wheat-fed beef has a distinct flavour profile that Italian-style pizza pepperoni benefits from, (2) Russian production economics give a 15–25% price advantage vs. Turkish equivalents, (3) the long-tradition halal infrastructure in Tatarstan is comparable to anywhere in the GCC."),
            ("Are you on the Russian export-promotion list?", "Yes. We participate in Russian Export Center (REC) trade missions to UAE (annual), Kazakhstan, Uzbekistan, and Saudi Arabia."),
            ("Can I visit the factory?", "Yes — pre-arranged factory tours are welcome. Halal-authority joint audits also welcome. Contact info@kazandelikates.tatar to schedule."),
        ],
        "related_links": [
            ("/en/about", "About Kazan Delicacies", "Full company profile"),
            ("/en/halal-pepperoni-export", "Export terms", "GCC / CIS / Africa"),
            ("/en/wholesale-halal-pepperoni-supplier", "Wholesale supplier", "B2B terms"),
            ("/en/halal-pepperoni-for-pizzerias", "Pizzeria range", "All formats"),
            ("/en/beef-halal-pepperoni", "Beef recipe", "Ingredients & origin"),
            ("/en/faq", "FAQ", "Common questions"),
        ],
    },
    {
        "slug": "halal-pepperoni-export",
        "title": "Halal Pepperoni Export — GCC / UAE / Saudi Arabia / CIS | Kazan Delicacies",
        "h1": "Halal Pepperoni Export from Russia",
        "subtitle": "Direct factory export to UAE, Saudi Arabia, Kazakhstan, Uzbekistan, Kyrgyzstan, Belarus, Azerbaijan. Multi-currency invoicing, HS code 1601, halal cert accepted in all GCC.",
        "description": "Halal pepperoni export from Russia: GCC (UAE, Saudi Arabia, Qatar, Kuwait, Bahrain), CIS (Kazakhstan, Uzbekistan, Kyrgyzstan, Belarus, Azerbaijan, Armenia), Africa, Malaysia. HS code 1601, halal #614A/2024, multi-currency invoicing.",
        "keywords": "halal pepperoni export, halal pepperoni UAE, halal pepperoni Saudi Arabia, halal export Russia, halal pepperoni Kazakhstan, halal pepperoni Uzbekistan, halal export GCC",
        "intent": "international buyer evaluating cross-border supply from a Russian halal manufacturer",
        "primary_sku": "KD-016",
        "primary_name": "Halal Pepperoni Export SKU (KD-016)",
        "primary_price_rub": "457",
        "primary_price_usd": "5.62",
        "primary_weight": "1.0 kg",
        "primary_pack": "Vacuum-packed, export carton (16 sticks/box)",
        "primary_storage": "−18 °C, 180 days frozen, cold-chain transit",
        "primary_diameter": "38 mm",
        "primary_yield": "≈ 160 slices per stick",
        "specs": [
            ("Markets served", "UAE, Saudi Arabia, Qatar, Kuwait, Bahrain, Oman, Kazakhstan, Uzbekistan, Kyrgyzstan, Belarus, Azerbaijan, Armenia, Egypt, Turkey, Malaysia"),
            ("HS code", "1601 (sausages of meat) · 1602 (other prepared meat) · 1905 (bakery)"),
            ("Halal certificate", "#614A/2024 by DUM RT — accepted by GCC, Malaysia, CIS, Africa"),
            ("Languages on label", "Russian + English standard · Arabic / Kazakh / Uzbek labels available"),
            ("Currencies", "USD, KZT, UZS, KGS, BYN, AZN, RUB"),
            ("Incoterms", "EXW Kazan default · CPT / DAP on agreement · FCA Moscow available"),
            ("Cold-chain partners", "FM Logistic, Atlas Air-Bridge (UAE), DHL Halal Cold Chain"),
            ("Documents pack", "EAEU declaration, halal certificate, HS code, COA, nutrition panel, packing list, MSDS for chilled, QR traceability"),
            ("Lead time to UAE/KSA", "10–14 days port-to-port via DAP Sharjah / DAP Jebel Ali"),
            ("First-shipment payment", "50 % prepayment, 50 % against shipping documents"),
        ],
        "faqs": [
            ("Is your halal certificate accepted in UAE?", "Yes — Halal certificate #614A/2024 issued by DUM RT is on the GCC Standardisation Organization's list of recognised foreign halal authorities. ESMA (UAE) accepts shipments under this certificate. We also support GAC (Saudi) audits on request."),
            ("Do you ship to Saudi Arabia?", "Yes. Cold-chain DAP Jeddah / DAP Dammam. SFDA registration of the halal certificate done by the buyer's local agent — we provide the apostilled certificate and product specs."),
            ("What's the lead time to Kazakhstan / Uzbekistan?", "5–7 days truck delivery to Almaty / Tashkent. Weekly cadence available — we already supply foodservice distributors in both markets."),
            ("Will you handle import customs?", "We ship EXW Kazan by default. For UAE / KSA we can arrange CPT or DAP via our cold-chain partners. For CIS, weekly truck departures from Kazan with all shipping documents handled by our logistics team."),
            ("Do you have Arabic / Kazakh / Uzbek labels?", "Yes — on request for export orders. Standard turnaround for label artwork approval: 2 weeks."),
            ("Can I get a small sample first?", "Yes. Sample boxes (5 kg mix of pepperoni/sausages) are sent by DHL Express to your address for $200 + courier. Approval triggers a pilot pallet order at standard wholesale price."),
        ],
        "related_links": [
            ("/en/halal-pepperoni-russia", "Halal pepperoni from Russia", "Origin & certificates"),
            ("/en/wholesale-halal-pepperoni-supplier", "Wholesale supplier", "B2B terms"),
            ("/en/dlya-distributorov", "For Distributors", "Regional exclusivity"),
            ("/en/kontraktnoe-proizvodstvo", "Private Label", "White-label export"),
            ("/en/about", "About Kazan Delicacies", "Manufacturer profile"),
            ("/en/halal-pepperoni-for-pizzerias", "Product range", "All pepperoni SKUs"),
        ],
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
<link rel="canonical" href="https://pepperoni.tatar/en/{slug}">
<link rel="alternate" hreflang="en" href="https://pepperoni.tatar/en/{slug}">
<link rel="alternate" hreflang="x-default" href="https://pepperoni.tatar/en/{slug}">

<meta property="og:type" content="product.group">
<meta property="og:title" content="{h1}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="https://pepperoni.tatar/en/{slug}">
<meta property="og:image" content="https://pepperoni.tatar/og-pepperoni-en.png">
<meta property="og:locale" content="en_US">
<meta property="og:locale:alternate" content="ru_RU">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{h1}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="https://pepperoni.tatar/og-pepperoni-en.png">

<script type="application/ld+json">{product_jsonld}</script>
<script type="application/ld+json">{faq_jsonld}</script>
<script type="application/ld+json">{breadcrumb_jsonld}</script>

<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.75}}
.container{{max-width:880px;margin:0 auto;padding:36px 22px}}
nav{{font-size:.85rem;color:#888;margin-bottom:18px}}
nav a{{color:#0066cc;text-decoration:none}}
h1{{font-size:1.9rem;font-weight:700;margin-bottom:10px;line-height:1.25}}
h2{{font-size:1.25rem;font-weight:700;margin:30px 0 12px;color:#1b7a3d}}
h3{{font-size:1rem;font-weight:600;margin:16px 0 8px}}
p{{margin-bottom:12px}}
.hero-subtitle{{color:#555;font-size:1.04rem;margin-bottom:8px}}
.badges{{margin:8px 0 18px}}
.badge{{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.82rem;font-weight:600;margin:4px 6px 4px 0}}
.badge-outline{{background:transparent;border:1.5px solid #1b7a3d;color:#1b7a3d}}
.product-card{{background:#fff;border:1px solid #e5e5e5;border-radius:12px;padding:20px;margin:14px 0;display:flex;gap:18px;flex-wrap:wrap;align-items:flex-start}}
.product-card .photo{{flex:0 0 220px;background:#f6f6f6;border-radius:10px;aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;overflow:hidden}}
.product-card .photo img{{width:100%;height:100%;object-fit:cover}}
.product-card .info{{flex:1;min-width:220px}}
.product-card h3{{margin-top:0;font-size:1.1rem}}
.price-block{{font-size:1.5rem;color:#1b7a3d;font-weight:700;margin:8px 0}}
.price-block small{{display:block;font-size:.85rem;color:#666;font-weight:400}}
.spec-table{{width:100%;border-collapse:collapse;margin:12px 0;background:#fff;border:1px solid #e5e5e5;border-radius:8px;overflow:hidden}}
.spec-table td{{padding:10px 14px;border-bottom:1px solid #eee;font-size:.92rem;vertical-align:top}}
.spec-table td:first-child{{color:#666;width:38%}}
.spec-table td:last-child{{color:#1a1a1a;font-weight:500}}
.spec-table tr:last-child td{{border-bottom:0}}
.faq{{margin:6px 0}}
.faq details{{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:14px 18px;margin:8px 0}}
.faq details[open]{{border-color:#1b7a3d}}
.faq summary{{cursor:pointer;font-weight:600;font-size:.96rem;color:#1a1a1a;list-style:none}}
.faq summary::-webkit-details-marker{{display:none}}
.faq summary::before{{content:"+ ";color:#1b7a3d;font-weight:700;margin-right:4px}}
.faq details[open] summary::before{{content:"− "}}
.faq p{{margin:10px 0 0;color:#444;font-size:.92rem;line-height:1.65}}
.grid-2{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin:12px 0}}
.grid-2 a{{display:block;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:14px;text-decoration:none;color:#1a1a1a;font-size:.9rem}}
.grid-2 a:hover{{border-color:#1b7a3d}}
.grid-2 strong{{display:block;color:#1a1a1a;margin-bottom:3px}}
.grid-2 span{{color:#666;font-size:.82rem}}
.cta-row{{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}}
.cta{{background:#1b7a3d;color:#fff;display:inline-block;padding:12px 26px;border-radius:8px;text-decoration:none;font-weight:600;font-size:.95rem}}
.cta:hover{{background:#15652f}}
.cta-outline{{background:transparent;border:2px solid #1b7a3d;color:#1b7a3d}}
.cta-outline:hover{{background:#1b7a3d;color:#fff}}
footer{{text-align:center;color:#aaa;font-size:.85rem;padding-top:30px;margin-top:32px;border-top:1px solid #eee}}
footer a{{color:#888;text-decoration:none}}
@media(max-width:600px){{.product-card{{flex-direction:column}}.product-card .photo{{width:100%;flex:none}}}}
</style>
</head>
<body>
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<div class="container">
<div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid #eee;font-size:.9rem">
  <a href="/en/" style="color:#0066cc;text-decoration:none;font-weight:600">Catalog</a>
  <a href="/en/pepperoni" style="color:#0066cc;text-decoration:none">Pepperoni</a>
  <a href="/en/about" style="color:#0066cc;text-decoration:none">About</a>
  <a href="/en/delivery" style="color:#0066cc;text-decoration:none">Delivery</a>
  <a href="/en/faq" style="color:#0066cc;text-decoration:none">FAQ</a>
  <a href="/" style="color:#888;margin-left:auto;text-decoration:none">🇷🇺 RU</a>
</div>
<nav aria-label="Breadcrumb">
  <a href="/en/">Catalog</a> &rsaquo; <a href="/en/pepperoni">Pepperoni</a> &rsaquo; <span>{h1}</span>
</nav>

<h1>{h1}</h1>
<p class="hero-subtitle">{subtitle}</p>
<div class="badges">
  <span class="badge">HALAL #614A/2024</span>
  <span class="badge badge-outline">HACCP + ISO 22000</span>
  <span class="badge badge-outline">No pork</span>
  <span class="badge badge-outline">EXW Kazan</span>
</div>

<div class="product-card">
  <div class="photo"><img src="{primary_image}" alt="{primary_name}" loading="lazy"></div>
  <div class="info">
    <h3>{primary_name}</h3>
    <div class="price-block">{primary_price_rub} ₽ <small>or ${primary_price_usd} USD · {primary_weight} · {primary_pack}</small></div>
    <p><strong>Diameter:</strong> {primary_diameter} · <strong>Yield:</strong> {primary_yield}<br><strong>Storage:</strong> {primary_storage}</p>
    <div class="cta-row">
      <a href="tel:+79872170202" class="cta">📞 +7 987 217-02-02</a>
      <a href="mailto:info@kazandelikates.tatar?subject={email_subject}" class="cta cta-outline">📧 Request quote</a>
      <a href="https://wa.me/79872170202?text={whatsapp_text}" class="cta cta-outline">💬 WhatsApp</a>
    </div>
  </div>
</div>

<h2>Specifications</h2>
<table class="spec-table"><tbody>
{specs_html}
</tbody></table>

<h2>Frequently Asked Questions</h2>
<div class="faq">
{faq_html}
</div>

<h2>See also</h2>
<div class="grid-2">
{related_html}
</div>

<h2>Get a quote</h2>
<p>Send an email or WhatsApp and we'll respond within one working day with a personalised price list (your currency, with/without VAT) and pilot terms.</p>
<div class="cta-row">
  <a href="tel:+79872170202" class="cta">📞 +7 987 217-02-02</a>
  <a href="mailto:info@kazandelikates.tatar?subject={email_subject}" class="cta cta-outline">📧 info@kazandelikates.tatar</a>
  <a href="https://wa.me/79872170202?text={whatsapp_text}" class="cta cta-outline">💬 WhatsApp</a>
</div>

<footer>
  <p><a href="/en/">← Catalog</a> &middot; <a href="/en/pepperoni">Pepperoni</a> &middot; <a href="/en/about">About</a> &middot; <a href="/en/delivery">Delivery</a> &middot; <a href="/en/faq">FAQ</a> &middot; <a href="/en/privacy">Privacy</a></p>
  <p>&copy; <a href="https://kazandelikates.tatar">Kazan Delicacies</a> &middot; <a href="https://pepperoni.tatar/en/">pepperoni.tatar/en</a></p>
</footer>
</div>
<script>(function(m,e,t,r,i,k,a){{m[i]=m[i]||function(){{(m[i].a=m[i].a||[]).push(arguments)}};m[i].l=1*new Date();for(var j=0;j<document.scripts.length;j++){{if(document.scripts[j].src===r)return}}k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a);}})(window,document,'script','https://mc.yandex.ru/metrika/tag.js','ym');ym(107064141,'init',{{clickmap:true,trackLinks:true,accurateTrackBounce:true,ecommerce:'dataLayer'}});</script>
</body>
</html>
"""


def build_product_jsonld(page, primary_image):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "Product",
        "@id": f"https://pepperoni.tatar/en/{page['slug']}#product",
        "name": page["h1"],
        "description": page["description"],
        "image": [primary_image, "https://pepperoni.tatar/og-pepperoni-en.png"],
        "sku": page["primary_sku"],
        "brand": {"@type": "Brand", "name": "Kazan Delicacies"},
        "manufacturer": {
            "@type": "Organization",
            "name": "Kazan Delicacies LLC",
            "url": "https://kazandelikates.tatar",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "ul. Agrarnaya, 2",
                "addressLocality": "Kazan",
                "addressRegion": "Tatarstan",
                "postalCode": "420059",
                "addressCountry": "RU",
            },
        },
        "countryOfOrigin": "RU",
        "hasCertification": {
            "@type": "Certification",
            "name": "Halal",
            "identifier": "614A/2024",
            "issuedBy": {
                "@type": "Organization",
                "name": "Muslim Spiritual Board of the Republic of Tatarstan (DUM RT)",
                "url": "https://dumrt.ru",
            },
        },
        "offers": {
            "@type": "Offer",
            "url": f"https://pepperoni.tatar/en/{page['slug']}",
            "priceCurrency": "RUB",
            "price": page["primary_price_rub"],
            "availability": "https://schema.org/InStock",
            "itemCondition": "https://schema.org/NewCondition",
            "seller": {"@type": "Organization", "name": "Kazan Delicacies"},
            "shippingDetails": {
                "@type": "OfferShippingDetails",
                "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "RU"},
                "shippingOrigin": {
                    "@type": "DefinedRegion",
                    "addressLocality": "Kazan",
                    "addressCountry": "RU",
                },
                "shippingRate": {"@type": "MonetaryAmount", "value": "0.00", "currency": "RUB"},
            },
        },
    }, ensure_ascii=False)


def build_faq_jsonld(faqs):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in faqs
        ],
    }, ensure_ascii=False)


def build_breadcrumb_jsonld(slug, h1):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Catalog", "item": "https://pepperoni.tatar/en/"},
            {"@type": "ListItem", "position": 2, "name": "Pepperoni", "item": "https://pepperoni.tatar/en/pepperoni"},
            {"@type": "ListItem", "position": 3, "name": h1, "item": f"https://pepperoni.tatar/en/{slug}"},
        ],
    }, ensure_ascii=False)


def render(page, product_images):
    sku = page["primary_sku"]
    img_pick = product_images.get("sliced", {})
    if sku == "KD-016":
        img_pick = product_images.get("stick", {})
    elif sku == "KD-014":
        img_pick = product_images.get("horse", {})
    elif sku == "KD-027":
        img_pick = product_images.get("dry", {})
    primary_image = (
        img_pick.get("imageMain")
        or img_pick.get("image")
        or "https://pepperoni.tatar/og-pepperoni-en.png"
    )

    specs_html = "\n".join(
        f"  <tr><td>{k}</td><td>{v}</td></tr>"
        for k, v in page["specs"]
    )
    faq_html = "\n".join(
        f'  <details><summary>{q}</summary><p>{a}</p></details>'
        for q, a in page["faqs"]
    )
    related_html = "\n".join(
        f'  <a href="{href}"><strong>{title}</strong><span>{desc}</span></a>'
        for href, title, desc in page["related_links"]
    )

    return HEAD_TPL.format(
        slug=page["slug"],
        title=page["title"],
        description=page["description"],
        keywords=page["keywords"],
        h1=page["h1"],
        subtitle=page["subtitle"],
        primary_image=primary_image,
        primary_name=page["primary_name"],
        primary_price_rub=page["primary_price_rub"],
        primary_price_usd=page["primary_price_usd"],
        primary_weight=page["primary_weight"],
        primary_pack=page["primary_pack"],
        primary_storage=page["primary_storage"],
        primary_diameter=page["primary_diameter"],
        primary_yield=page["primary_yield"],
        specs_html=specs_html,
        faq_html=faq_html,
        related_html=related_html,
        product_jsonld=build_product_jsonld(page, primary_image),
        faq_jsonld=build_faq_jsonld(page["faqs"]),
        breadcrumb_jsonld=build_breadcrumb_jsonld(page["slug"], page["h1"]),
        email_subject=quote(f"Inquiry: {page['h1']}"),
        whatsapp_text=quote(f"Hi, I'm interested in {page['h1'].lower()} — please send a quote."),
    )


def main():
    product_images = get_product_images()
    EN_DIR.mkdir(parents=True, exist_ok=True)
    for page in PAGES:
        out = EN_DIR / f"{page['slug']}.html"
        out.write_text(render(page, product_images), encoding="utf-8")
        print(f"OK {out}  ({out.stat().st_size//1024} KB)")


if __name__ == "__main__":
    main()
