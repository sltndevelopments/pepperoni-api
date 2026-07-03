#!/usr/bin/env python3
"""Generate the 7 missing English B2B segment landing pages.

Produces:
  public/en/dlya-azs.html                 (Fuel-station / street-food convenience)
  public/en/dlya-pekaren.html             (Regional bakeries)
  public/en/dlya-setey.html               (Retail chains)
  public/en/dlya-distributorov.html       (Foodservice distributors)
  public/en/dlya-horeca.html              (HoReCa)
  public/en/kontraktnoe-proizvodstvo.html (Private Label / contract manufacturing)
  public/en/dlya-pizzerii.html            (Pizzerias — extra entry point)

URL slugs mirror the RU equivalents so the existing `<link rel="alternate"
hreflang="en">` tags on Russian landings work without further edits.
"""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
EN_DIR = PUBLIC / "en"
EN_DIR.mkdir(parents=True, exist_ok=True)


SEGMENTS = [
    {
        "slug": "dlya-pizzerii",
        "ru_slug": "pepperoni-dlya-pizzerii",
        "chip": "Segment 1 of 7 · Pizzerias & dark kitchens",
        "title": "Halal Pepperoni & Sausages for Pizzerias Wholesale — Manufacturer in Kazan, Russia",
        "h1": "Halal Pepperoni & Sausages for Pizzerias",
        "subtitle": "Pizza-oven-stable pepperoni, classic recipe (beef + chicken) or horse meat. Whole 1 kg sticks, half 0.5 kg sticks, pre-sliced. No pork — Halal certified.",
        "description": "Halal pepperoni for pizzerias and dark kitchens: oven-stable, no curling, classic beef+chicken or horse-meat recipes. Whole 1 kg stick, half stick, pre-sliced. HACCP, Halal #614A/2024. Wholesale, EXW Kazan.",
        "keywords": "halal pepperoni pizzeria, halal pizza topping wholesale, dark kitchen halal pepperoni, oven-stable pepperoni, pork-free pizza pepperoni, halal pizza ingredients Russia",
        "og_title": "Halal Pepperoni for Pizzerias & Dark Kitchens — Wholesale",
        "og_description": "Pizza-oven-stable halal pepperoni. Classic (beef + chicken) or horse meat. Whole sticks, half sticks, pre-sliced.",
        "intro": "Pizzerias and dark kitchens live on consistent topping behaviour: the slice must not curl, must not bleed grease, must hold colour after the oven. Our halal pepperoni is engineered for stone-deck, conveyor, and pan ovens — same diameter, same fat content, same curing depth across every batch, so the slice on a Wednesday lunch tastes like the slice you tested at the contract signing.",
        "case_title": "Case study: «Aslam» pepperoni for OMPK JSC (Ostankino Meat Plant)",
        "case_body": "We produce halal pepperoni under the <strong>«Aslam»</strong> brand for OMPK JSC (Ostankino Meat Plant) — Russia's largest meat producer. The product ships to pizzerias and HoReCa nationwide. This case demonstrates our private-label capacity and recipe consistency at federal scale.",
        "stats": [
            ("Federal", "scale (Aslam / OMPK)"),
            ("3 formats", "whole / half / sliced"),
            ("100%", "halal, pork-free"),
        ],
        "second_case": {
            "title": "Pizzerias of Kazan & Tatarstan",
            "body": "Direct supply to halal-positioned pizza chains in Kazan, Naberezhnye Chelny, Almetyevsk. Spec-locked: one slicer setting, one diameter, one curing depth — chef workflow stays predictable batch to batch.",
        },
        "features_heading": "What pizzerias need — and what we deliver",
        "features": [
            ("🍕", "Oven-stable", "No curling, no grease bleed, holds colour at 280-320°C."),
            ("📏", "Locked diameter", "24-32 mm classic, 38 mm for stuffed crust — your slicer never re-adjusts."),
            ("🇷🇺", "Halal classic & horse meat", "Pork-free product positioned natively for Muslim guests. Horse-meat pepperoni — a unique SKU."),
            ("📦", "Three formats", "Whole 1 kg stick, half 0.5 kg, factory-sliced — pick the labour you want to push to the kitchen."),
            ("❄️", "180-360 day shelf life", "Long shelf life means rare orders, less wastage on slow Mondays."),
            ("📋", "Full document pack", "EAEU declaration, Mercury VSD, Halal certificate, QR traceability."),
        ],
        "items_heading": "Pepperoni SKUs for pizzerias",
        "items": [
            ("Classic Pepperoni (beef & chicken), sliced", "0.5 kg", "274 ₽"),
            ("Classic Pepperoni (beef & chicken), whole stick", "1 kg", "457 ₽"),
            ("Horse-meat Pepperoni, sliced", "0.5 kg", "315 ₽"),
            ("Dry-Cured Pepperoni, sliced", "0.5 kg", "by request"),
            ("Dry-Cured Pepperoni, whole stick", "1 kg", "by request"),
        ],
        "items_note": "Current prices live at <a href=\"/en/\" style=\"color:#0066cc\">/en/</a>. Private-label and custom-format quotations on request.",
        "logistics_heading": "Logistics & terms for pizza chains",
        "logistics": [
            ("Incoterm", "EXW Kazan · transit hub Lyubertsy (Moscow region)"),
            ("Minimum batch", "Discussed — pilot from 1 pallet"),
            ("Cadence", "Weekly or bi-weekly per schedule"),
            ("Payment", "Net 14–30 days after pilot"),
            ("Storage", "180-360 days at -18°C"),
            ("Thawed shelf life", "5 days at +4°C, sealed pack"),
            ("Documents", "EAEU declaration · Mercury VSD · Halal · QR traceability"),
        ],
        "why_heading": "Why pizza chains choose us",
        "why": [
            "<strong>Halal-default product</strong> — works for Muslim and non-Muslim guests alike, no double menu",
            "<strong>Diameter & casing locked</strong> across every batch — slicer settings never drift",
            "<strong>Horse-meat pepperoni</strong> — high-margin unique SKU for premium positioning",
            "<strong>Private Label</strong> — your pizzeria's brand on the box, recipe customisable",
            "<strong>In-house production</strong> in Kazan — no middleman between you and the recipe",
            "<strong>Federal-scale case</strong> — already producing for OMPK / Ostankino",
        ],
        "related": [
            ("/en/kontraktnoe-proizvodstvo", "Private Label / Contract Manufacturing", "Pepperoni under your brand"),
            ("/en/dlya-horeca", "For HoReCa", "Restaurants, hotels, catering"),
            ("/en/dlya-setey", "For Retail Chains", "Slice-ready pepperoni for the shelf"),
            ("/en/dlya-azs", "For Gas Stations", "Pepperoni in the convenience zone"),
            ("/en/pepperoni", "All about pepperoni", "Range, ingredients, certificates"),
            ("/en/kazylyk", "Kazylyk", "Tatar horse-meat sausage"),
        ],
        "cta_heading": "Request a pepperoni sample",
        "cta_lead": "Write to us — we'll send a pizzeria-format short price list, a slicing-spec sheet, and pilot terms.",
        "whatsapp_text": "Hello! I'm interested in halal pepperoni supply for my pizzeria",
        "email_subject": "Halal pepperoni for pizzeria",
    },
    {
        "slug": "dlya-azs",
        "ru_slug": "dlya-azs",
        "chip": "Segment 2 of 7 · Fuel stations & street food",
        "title": "Halal Sausages, Pepperoni & Burger Patties for Gas Stations Wholesale | Kazan Delicacies",
        "h1": "Halal Products for Gas Stations & Street Food",
        "subtitle": "Convenience-zone hot dogs, sandwiches, sausage rolls, burgers. Consistent rotation, same taste across the whole network.",
        "description": "Halal supply for gas stations & street food: hot-dog sausages, pepperoni, burger patties, sausage rolls. Beef, chicken, horse meat. HACCP, Halal #614A/2024. One taste across the entire chain.",
        "keywords": "halal hot dogs for gas stations, halal pepperoni gas station, halal burger patties convenience, halal sausage roll wholesale, halal snacks fuel station",
        "og_title": "Halal Products for Gas Stations & Street Food — Convenience Zone",
        "og_description": "Stable halal supply for fuel-station chains and street food. One taste, full documents, HACCP.",
        "intro": "Gas stations and chain street food live on uniformity: the guest at any point of the network must receive a product that <strong>looks and tastes the same</strong>. We make halal sausages, pepperoni, burger patties and sausage rolls that roll through the network — uninterrupted, one spec, full documents on every shipment.",
        "case_title": "Case study: Tatneft fuel-station network",
        "case_body": "All Tatneft gas stations carry our halal <strong>hot-dog sausages</strong> and <strong>burger patties</strong>. In selected regional stations we also supply our <strong>Tatar pastries</strong> (echpochmak, peremyach, samsa) in the ready-meal category.",
        "stats": [
            ("Whole network", "sausages + patties"),
            ("Regional", "Tatar pastries"),
            ("One taste", "across the chain"),
        ],
        "second_case": {
            "title": "Also: SMARTEN (fuel-station network operator)",
            "body": "We work with the <strong>SMARTEN</strong> fuel-station network — halal products for the convenience zone and street-food line: sausages, pepperoni, burger patties.",
        },
        "features_heading": "What fuel stations need — and what we deliver",
        "features": [
            ("🌭", "One taste across the network", "One recipe, one pack, one label — the guest gets the expected product at any station."),
            ("📦", "Single-piece packaging", "Sausages vacuum-packed individually or by small weight — minimal write-off."),
            ("❄️", "360-day frozen shelf life", "Order once every 2-4 weeks without sorting-out risk."),
            ("📋", "Full document pack per shipment", "EAEU declaration, Mercury VSD, Halal — no DC hold-ups."),
            ("☪️", "Halal & «for everyone»", "Same product fits the Muslim and the non-Muslim guest — no double matrix."),
            ("🚚", "Logistics across Russia", "EXW Kazan or Lyubertsy DC. Regular runs to Volga, Central, Urals."),
        ],
        "items_heading": "SKUs that work at fuel stations",
        "items": [
            ("Classic halal sausages", "~80 g vac-pack", "—"),
            ("Cheese sausages", "~80 g vac-pack", "—"),
            ("Horse-meat sausages", "~80 g vac-pack", "—"),
            ("Boiled-Smoked Pepperoni, sliced", "0.5 kg", "274 ₽"),
            ("Burger patty", "100 g × 3 pcs", "276 ₽"),
            ("Sausage roll", "~100 g/pc", "69 ₽/pc"),
        ],
        "items_note": "Live prices in the <a href=\"/en/\" style=\"color:#0066cc\">catalog</a>. For private label (network-branded hot dog or sausage roll) we put together a separate proposal.",
        "logistics_heading": "Logistics & terms for fuel-station chains",
        "logistics": [
            ("Incoterm", "EXW Kazan · transit hub Lyubertsy (Moscow region)"),
            ("Minimum batch", "Discussed — pilot from 1 pallet"),
            ("Cadence", "Weekly or bi-weekly per schedule"),
            ("Payment", "Net 14–30 days after pilot"),
            ("Storage", "360 days at -18°C"),
            ("Thawed shelf life", "5 days at +4°C, sealed pack"),
            ("Documents", "EAEU declaration · Mercury VSD · Halal · QR traceability"),
        ],
        "why_heading": "Why fuel-station chains choose us",
        "why": [
            "<strong>Halal status</strong> — works for every guest by default",
            "<strong>One price across the network</strong> — no regional markups",
            "<strong>In-house production</strong> in Kazan — no middleman between you and the recipe",
            "<strong>Private Label without a 10-tonne minimum</strong> — pilot from 500 kg/month",
            "<strong>Horse-meat / beef sausages</strong> — high-margin unique SKU for the convenience zone",
            "<strong>Customisation</strong> — spice, diameter, length, packaging adapted to your process",
        ],
        "related": [
            ("/en/kontraktnoe-proizvodstvo", "Private Label", "Under your network brand"),
            ("/en/dlya-setey", "For Retail Chains", "Convenience zone & shelf"),
            ("/en/dlya-horeca", "For HoReCa", "Restaurants, hotels, catering"),
            ("/en/dlya-pizzerii", "For Pizzerias", "Halal pepperoni & toppings"),
            ("/en/pepperoni", "All about pepperoni", "Range, ingredients, certificates"),
            ("/en/kazylyk", "Kazylyk", "Tatar horse-meat sausage"),
        ],
        "cta_heading": "Discuss supply for fuel stations",
        "cta_lead": "Write to us — we'll send a street-food short price list, a sample specification, and pilot terms.",
        "whatsapp_text": "Hello! I'm interested in halal supply for a fuel-station network",
        "email_subject": "Supply for gas stations",
    },
    {
        "slug": "dlya-pekaren",
        "ru_slug": "dlya-pekaren",
        "chip": "Segment 3 of 7 · Regional bakeries",
        "title": "Halal Sausages for Bakeries & Tatar-Pastry Wholesale | Kazan Delicacies",
        "h1": "Halal Sausages & Meat Fillings for Regional Bakeries",
        "subtitle": "Casingless sausages for sausage rolls, beef & chicken mince for echpochmak and samsa, ready Tatar pastries.",
        "description": "Halal supply for regional bakeries: casingless sausages for sausage-in-dough, beef & chicken mince fillings, ready Tatar pastries (echpochmak, samsa, peremyach). HACCP, Halal #614A/2024.",
        "keywords": "halal sausages bakery wholesale, casingless sausage for sausage roll, halal meat fillings echpochmak, samsa filling halal, peremyach wholesale, Tatar pastries bakery",
        "og_title": "Halal Sausages & Fillings for Bakeries — Wholesale",
        "og_description": "Casingless sausages for sausage rolls, meat fillings, ready Tatar pastries. HACCP. Halal default.",
        "intro": "Regional bakery chains run on margins, throughput and zero-fuss sourcing. We supply <strong>halal casingless 45 g sausages</strong> tuned for sausage rolls (no shrinkage, no leakage, predictable dough behaviour), <strong>beef and chicken minces</strong> for echpochmak, samsa and peremyach, and a full line of <strong>ready frozen Tatar pastries</strong> for shops that don't want to bake.",
        "case_title": "Case study: Tatar-pastry chains across Volga",
        "case_body": "Our 45 g casingless «K zavtraku» sausage is the de-facto standard for sausage-in-dough at multiple regional bakery chains. <strong>Frozen ready pastries</strong> — echpochmak, samsa, peremyach, gubadiya — supplied where bakers do not run a hot kitchen.",
        "stats": [
            ("45 g", "casingless sausage"),
            ("4 fillings", "beef, chicken, mince"),
            ("19 SKUs", "ready Tatar pastries"),
        ],
        "second_case": {
            "title": "Tatneft AZS bakery corner",
            "body": "In selected Tatneft fuel-station bakery corners we supply our frozen Tatar pastries — echpochmak, samsa, peremyach — in the ready-meal category alongside hot dogs.",
        },
        "features_heading": "What bakeries need — and what we deliver",
        "features": [
            ("🥐", "Casingless 45 g sausage", "Engineered for sausage rolls — no casing means no shrinkage, no leakage in the dough."),
            ("🥩", "Ready meat fillings", "Beef mince, chicken-skin mince, diced thigh / breast 1×1 cm — drop-in for echpochmak & samsa."),
            ("🥟", "Frozen Tatar pastries", "Echpochmak, samsa, peremyach, gubadiya, elesh, chebureks — for bakeries without a hot kitchen."),
            ("📦", "Long frozen life", "180-360 days at -18°C — fits any DC schedule."),
            ("📋", "Full document pack", "EAEU declaration, Mercury VSD, Halal — clears any regional DC."),
            ("🇷🇺", "Regional delivery", "Volga, Central, Urals — weekly cadence."),
        ],
        "items_heading": "SKUs that work for bakery chains",
        "items": [
            ("«K zavtraku» casingless sausage, 45 g", "0.4 kg pack", "135 ₽"),
            ("Beef mince", "1 kg", "by request"),
            ("Diced chicken thigh 1×1 cm", "1 kg", "by request"),
            ("Echpochmak with beef & potato", "frozen, 100 g", "from 69 ₽/pc"),
            ("Samsa with chicken", "frozen, 120 g", "from 62 ₽/pc"),
            ("Peremyach, fried", "frozen, 100 g", "from 59 ₽/pc"),
        ],
        "items_note": "Current price list in the <a href=\"/en/\" style=\"color:#0066cc\">catalog</a>. For private-label fillings or pastries — bespoke quotation.",
        "logistics_heading": "Logistics & terms for bakery chains",
        "logistics": [
            ("Incoterm", "EXW Kazan · transit hub Lyubertsy"),
            ("Minimum batch", "Discussed — pilot from 1 pallet"),
            ("Cadence", "Weekly per schedule"),
            ("Payment", "Net 14–30 days after pilot"),
            ("Storage", "180-360 days at -18°C"),
            ("Documents", "EAEU declaration · Mercury VSD · Halal · QR traceability"),
        ],
        "why_heading": "Why bakeries pick us",
        "why": [
            "<strong>Casingless 45 g</strong> — the dough-friendly format the market has been asking for",
            "<strong>Halal by default</strong> — broad audience without a special menu",
            "<strong>Tatar-pastry expertise</strong> — we make the pastries you sell, native recipes",
            "<strong>Drop-in mince formats</strong> — beef, chicken, diced — saves butchery time",
            "<strong>Private Label</strong> — your brand on the sausage or pastry pack",
            "<strong>Single supplier</strong> for sausage + filling + ready pastry — fewer SKUs to manage",
        ],
        "related": [
            ("/en/bakery", "Tatar pastry catalog", "All 19 bakery SKUs"),
            ("/en/kontraktnoe-proizvodstvo", "Private Label", "Filling and pastry under your brand"),
            ("/en/dlya-setey", "For Retail Chains", "Frozen pastries on the shelf"),
            ("/en/dlya-horeca", "For HoReCa", "Restaurants, hotels, catering"),
            ("/en/dlya-azs", "For Gas Stations", "Convenience-zone pastries"),
            ("/en/dlya-distributorov", "For Distributors", "Tatar pastry wholesale"),
        ],
        "cta_heading": "Discuss bakery supply",
        "cta_lead": "Write to us — we'll send a bakery-format short price list, casingless-sausage spec sheet, and pilot terms.",
        "whatsapp_text": "Hello! I'm interested in halal bakery supply (sausages, fillings, pastries)",
        "email_subject": "Bakery supply",
    },
    {
        "slug": "dlya-setey",
        "ru_slug": "dlya-setey",
        "chip": "Segment 4 of 7 · Retail chains",
        "title": "Halal Pepperoni, Sausages & Tatar Pastries for Retail Chains | Kazan Delicacies",
        "h1": "Halal Products for Retail Chains",
        "subtitle": "Pepperoni, sausages, kazylyk, Tatar pastries — shelf-ready packaging, EAEU declarations, Mercury VSD, halal certificate.",
        "description": "Halal pepperoni, sausages, kazylyk, Tatar pastries for retail chains: shelf-ready packaging, full document pack, halal #614A/2024. Cases: EuroSpar, Bahetle, Metro, Miratorg.",
        "keywords": "halal retail wholesale, halal pepperoni retail chain, halal Tatar pastry retail, kazylyk retail, EuroSpar Bahetle halal supplier, halal supplier retail Russia",
        "og_title": "Halal Products for Retail Chains — Pepperoni, Sausages, Kazylyk, Pastries",
        "og_description": "Shelf-ready halal product: 77 SKUs, full document pack, retail-grade packaging.",
        "intro": "Retail buyers want one supplier with <strong>a deep matrix</strong>, <strong>retail-grade packaging</strong>, <strong>shelf life that survives DC routing</strong>, and <strong>halal certification</strong> that opens both the Muslim audience and the wider shopper. We supply all 77 SKUs — frozen, chilled, bakery — under one EAEU declaration line, one Mercury VSD process, one document portal.",
        "case_title": "Retail-chain track record",
        "case_body": "Our products are listed in <strong>EuroSpar</strong> and <strong>Bahetle</strong> supermarkets across Kazan, in <strong>Metro Cash &amp; Carry</strong>, and on <strong>Miratorg</strong> shelves (Tatar pastry line). Some assortment goes to regional retail across Volga and Central federal districts.",
        "stats": [
            ("EuroSpar", "Kazan listing"),
            ("Bahetle", "Kazan listing"),
            ("Metro", "Cash & Carry"),
        ],
        "second_case": {
            "title": "Miratorg — Tatar-pastry shelf",
            "body": "We supply our frozen Tatar pastries (chak-chak, gubadiya, echpochmak, samsa) to <strong>Miratorg</strong> retail — under the bakery/national-cuisine shelf line.",
        },
        "features_heading": "What retail chains need — and what we deliver",
        "features": [
            ("🛒", "Retail-grade packaging", "Vacuum or MAP, retail-friendly weight, branded sleeve where required."),
            ("📋", "Full document portal", "EAEU, Mercury VSD, Halal, GTIN, retail-ready barcode."),
            ("📦", "77 SKU matrix", "Frozen + chilled + bakery + ready pastries — one supplier, one DC route."),
            ("❄️", "Long shelf life", "Frozen 180-360 days; chilled 30 days; bakery 60-360 days."),
            ("☪️", "Halal-default", "Opens Muslim audience and works for the general shopper too."),
            ("🚚", "Logistics", "EXW Kazan or Lyubertsy DC. Federal weekly cadence."),
        ],
        "items_heading": "Top retail SKUs",
        "items": [
            ("Boiled-Smoked Pepperoni, classic sliced", "0.5 kg", "274 ₽"),
            ("Kazylyk «Premium» (gift box)", "200 g", "650 ₽"),
            ("Kazylyk «Premium» sliced (gift box)", "100 g", "450 ₽"),
            ("Chak-chak (craft gift box)", "300 g", "by request"),
            ("Echpochmak with beef & potato", "frozen", "from 69 ₽/pc"),
            ("Cheese sausages, vacuum", "0.4 kg", "from 293 ₽"),
        ],
        "items_note": "All 77 SKUs in the <a href=\"/en/\" style=\"color:#0066cc\">catalog</a>. Private-label retail packs (your chain's brand) — quotation on request.",
        "logistics_heading": "Logistics & terms for retail chains",
        "logistics": [
            ("Incoterm", "EXW Kazan · transit hub Lyubertsy"),
            ("Minimum batch", "Pilot from 1 pallet"),
            ("Cadence", "Weekly per schedule"),
            ("Payment", "Net 30–45 days after pilot"),
            ("Storage", "Per SKU — 30 to 360 days"),
            ("Documents", "EAEU · Mercury VSD · Halal · GTIN · QR traceability"),
        ],
        "why_heading": "Why retail chains pick us",
        "why": [
            "<strong>One supplier</strong> for halal sausages + pepperoni + kazylyk + Tatar pastries",
            "<strong>Documents ready before pilot</strong> — no surprises at DC",
            "<strong>Halal certificate</strong> = wider audience without category cannibalisation",
            "<strong>Retail-grade packaging</strong> in MAP or vacuum, GTIN-labelled",
            "<strong>Private Label</strong> available for the whole 77-SKU matrix",
            "<strong>Kazan local production</strong> — short supply chain to Volga & Central DCs",
        ],
        "related": [
            ("/en/kontraktnoe-proizvodstvo", "Private Label", "Retail-pack production under your brand"),
            ("/en/dlya-distributorov", "For Distributors", "Long format, export packaging"),
            ("/en/dlya-azs", "For Gas Stations", "Convenience-zone matrix"),
            ("/en/bakery", "Tatar pastry catalog", "Bakery-shelf items"),
            ("/en/pepperoni", "All about pepperoni", "Recipe, certificates, range"),
            ("/en/kazylyk", "Kazylyk", "Tatar horse-meat sausage"),
        ],
        "cta_heading": "Listing inquiry",
        "cta_lead": "Write to us — we'll send the retail listing pack: short price list, packaging specs, declarations, EAEU document samples.",
        "whatsapp_text": "Hello! I'm a retail-chain buyer interested in halal product listing",
        "email_subject": "Retail listing inquiry",
    },
    {
        "slug": "dlya-distributorov",
        "ru_slug": "dlya-distributorov",
        "chip": "Segment 5 of 7 · Distributors",
        "title": "Become a Distributor of Halal Meat & Tatar Pastries from Kazan, Russia | Kazan Delicacies",
        "h1": "Become a Distributor of Halal Products from Tatarstan",
        "subtitle": "Wide matrix (77 SKUs), export packaging, long shelf life, multi-currency price list, regional exclusivity available.",
        "description": "Become a halal-meat & Tatar-pastry distributor from Kazan: 77 SKUs, export packaging, multi-currency pricing (7 currencies), regional exclusivity. EXW Kazan. Halal #614A/2024.",
        "keywords": "halal distributor Russia, halal meat distributor wholesale, halal pepperoni distributor, halal Tatar pastry wholesale, multi-currency halal supplier, halal export CIS",
        "og_title": "Become a Distributor of Halal Meat & Pastries — Kazan Delicacies",
        "og_description": "77 SKUs, 7 currencies, EXW Kazan, regional exclusivity available. Halal-default supplier.",
        "intro": "Foodservice and retail distributors win on <strong>matrix depth</strong>, <strong>price-list discipline</strong>, and <strong>document availability before the shipment</strong>. We give you 77 halal SKUs from one factory in Kazan, prices in 7 currencies (RUB, USD, KZT, UZS, KGS, BYN, AZN), and a daily-synced API so your sales reps quote from live data, not a quarterly PDF.",
        "case_title": "Distribution track record",
        "case_body": "We're listed by federal foodservice distributors <strong>GFC</strong> and <strong>SweetLife</strong> — covering HoReCa, dark kitchens and convenience retail across Russia. Regional distribution partners cover Volga, Central, Urals and CIS routes.",
        "stats": [
            ("GFC", "federal foodservice"),
            ("SweetLife", "federal foodservice"),
            ("CIS", "Kazakhstan, Uzbekistan, …"),
        ],
        "second_case": {
            "title": "CIS export route",
            "body": "Regular shipments to <strong>Kazakhstan, Uzbekistan, Kyrgyzstan, Belarus, Armenia, Azerbaijan</strong>. HS codes, halal certificate, multi-currency invoicing. EXW Kazan or buyer-arranged transit.",
        },
        "features_heading": "What distributors need — and what we deliver",
        "features": [
            ("📋", "API + daily price sync", "Live JSON on /api/products. Sales reps quote from the same source as the production calendar."),
            ("🌍", "7-currency price list", "RUB, USD, KZT, UZS, KGS, BYN, AZN — exported in XLSX or CSV in one call."),
            ("📦", "Export packaging", "Heavy-duty cardboard, EAEU + Halal labels, GTIN, vacuum or MAP per SKU."),
            ("❄️", "Long shelf life", "Frozen 180-360 days, kazylyk 180 days, bakery up to 360 days — built for the route."),
            ("🤝", "Regional exclusivity", "Available per category and region — discussed before pilot."),
            ("☪️", "Halal everywhere", "One blanket halal certificate (DUM RT #614A/2024) for the whole 77-SKU matrix."),
        ],
        "items_heading": "Distribution-friendly SKUs",
        "items": [
            ("Boiled-Smoked Pepperoni, whole stick", "1 kg", "457 ₽"),
            ("Dry-Cured Pepperoni, whole stick", "1 kg", "by request"),
            ("Kazylyk «Premium» (gift box)", "200 g", "650 ₽"),
            ("Smoked Chicken Breast", "1 kg", "370 ₽"),
            ("Cheese sausages", "0.65 kg × 5", "455 ₽"),
            ("Chak-chak (craft gift box)", "300 g", "by request"),
        ],
        "items_note": "Full live catalog: <a href=\"https://api.pepperoni.tatar/api/products\" style=\"color:#0066cc\">/api/products</a> (no auth). Daily price-list export to your CRM available.",
        "logistics_heading": "Distribution terms",
        "logistics": [
            ("Incoterm", "EXW Kazan · option: buyer-arranged transit to Moscow/CIS"),
            ("Minimum batch", "Pilot from 1 pallet · ramp by region"),
            ("Cadence", "Weekly or bi-weekly"),
            ("Payment", "Net 14–30 days after pilot · prepayment 50% for first export shipment"),
            ("Currencies", "RUB, USD, KZT, UZS, KGS, BYN, AZN"),
            ("Documents", "EAEU · Mercury VSD · Halal · HS codes · COA on request · QR traceability"),
        ],
        "why_heading": "Why distributors choose us",
        "why": [
            "<strong>77 SKUs from one factory</strong> — no juggling 5 suppliers",
            "<strong>API price list</strong> — never quote from a stale PDF again",
            "<strong>Halal default</strong> — opens Muslim audience without dual matrix",
            "<strong>Private Label</strong> on every SKU — your distributor brand on the box",
            "<strong>Federal-scale references</strong> — Tatneft, OMPK/Ostankino, EuroSpar, Bahetle, Metro, Miratorg",
            "<strong>CIS export-ready</strong> — multi-currency invoicing, HS codes",
        ],
        "related": [
            ("/en/kontraktnoe-proizvodstvo", "Private Label", "Distributor-brand production"),
            ("/en/dlya-setey", "For Retail Chains", "Shelf-ready halal matrix"),
            ("/en/dlya-horeca", "For HoReCa", "Restaurants, hotels, catering"),
            ("/en/dlya-azs", "For Gas Stations", "Convenience-zone supply"),
            ("/en/pepperoni", "Pepperoni catalog", "Range, formats, prices"),
            ("/en/bakery", "Bakery catalog", "Tatar pastries wholesale"),
        ],
        "cta_heading": "Distributor partnership inquiry",
        "cta_lead": "Write to us — we'll send the distributor pack: short price list, regional-exclusivity terms, and pilot conditions.",
        "whatsapp_text": "Hello! I'm a distributor interested in halal product partnership",
        "email_subject": "Distributor partnership",
    },
    {
        "slug": "dlya-horeca",
        "ru_slug": "dlya-horeca",
        "chip": "Segment 6 of 7 · HoReCa",
        "title": "Halal Products for HoReCa Wholesale — Restaurants, Hotels, Catering | Kazan Delicacies",
        "h1": "Halal Products for HoReCa, Restaurants & Catering",
        "subtitle": "Pepperoni for pizzerias, hot-dog & grill sausages for dark kitchens, sliced hams & deli, ready Tatar pastries.",
        "description": "Halal supply for HoReCa: pepperoni for pizzerias, hot-dog & grill sausages, burger patties, sliced hams, deli, ready Tatar pastries. HACCP, Halal #614A/2024. EXW Kazan.",
        "keywords": "halal HoReCa wholesale, halal pepperoni restaurant, halal grill sausage HoReCa, halal hotel catering supplier, halal dark kitchen wholesale, halal hot dog restaurant",
        "og_title": "Halal Products for HoReCa & Catering — Wholesale",
        "og_description": "77 halal SKUs for restaurants, hotels, catering and dark kitchens. One supplier, one document pack.",
        "intro": "HoReCa lives on <strong>menu consistency</strong>, <strong>portion economics</strong> and <strong>halal label without extra friction</strong>. We feed pizzerias (oven-stable pepperoni), grill restaurants (premium hot-dog and grill sausages), hotel breakfasts (sliced hams, deli, smoked chicken), and catering kitchens (Tatar pastry sets, kazylyk gift boxes). One supplier, one document portal, one taste across all your touchpoints.",
        "case_title": "Catering & corporate references",
        "case_body": "We supply the corporate canteen of <strong>Kazan Helicopter Plant</strong> (premium beef & lamb sausages for shift catering). Federal foodservice distributors <strong>GFC</strong> and <strong>SweetLife</strong> route our products to HoReCa nationwide.",
        "stats": [
            ("Kazan Helicopter Plant", "corporate catering"),
            ("GFC + SweetLife", "federal foodservice"),
            ("Pizza chains", "Volga & Central"),
        ],
        "second_case": {
            "title": "Hotel breakfast line",
            "body": "Halal sliced ham, smoked chicken breast, boiled chicken fillet, premium kazylyk — ready for buffet breakfast service at halal-positioned hotels in Kazan, Naberezhnye Chelny, Almetyevsk.",
        },
        "features_heading": "What HoReCa needs — and what we deliver",
        "features": [
            ("🍕", "Oven-stable pepperoni", "Locked diameter, locked fat content — slicer stays calibrated."),
            ("🌭", "Premium grill sausages", "7 flavours, 80 g and 130 g, ready for the grill or roller."),
            ("🥪", "Sliced deli ready", "Hams, kazylyk, smoked chicken — pre-sliced for the line."),
            ("🥟", "Tatar pastry sets", "Ready-to-serve frozen sets for catering events."),
            ("📋", "Full document pack", "EAEU, Mercury VSD, Halal, nutrition panel — for every dish you cost-out."),
            ("🤝", "Single supplier", "Frozen + chilled + bakery from one factory — fewer POs, fewer DC trips."),
        ],
        "items_heading": "Top HoReCa SKUs",
        "items": [
            ("Boiled-Smoked Pepperoni, sliced", "0.5 kg", "274 ₽"),
            ("Lamb sausages «With lamb», 80 g × 6", "0.48 kg", "366 ₽"),
            ("Cheese sausages, 130 g × 5", "0.65 kg", "455 ₽"),
            ("Burger patty, fried", "100 g × 3", "276 ₽"),
            ("Chicken ham, sliced", "0.5 kg", "by request"),
            ("Kazylyk «Premium», sliced", "100 g", "450 ₽"),
        ],
        "items_note": "Full HoReCa matrix in the <a href=\"/en/\" style=\"color:#0066cc\">catalog</a>. Portion-pack sizes and private-label HoReCa packs — bespoke quotation.",
        "logistics_heading": "Logistics & terms for HoReCa",
        "logistics": [
            ("Incoterm", "EXW Kazan · transit hub Lyubertsy"),
            ("Minimum batch", "Pilot from 1 pallet"),
            ("Cadence", "Weekly per schedule"),
            ("Payment", "Net 14–30 days after pilot"),
            ("Storage", "Frozen 180-360 days; chilled 30 days"),
            ("Documents", "EAEU · Mercury VSD · Halal · nutrition panel · QR traceability"),
        ],
        "why_heading": "Why HoReCa picks us",
        "why": [
            "<strong>Single halal supplier</strong> for the whole menu",
            "<strong>Federal references</strong> — Kazan Helicopter Plant catering, GFC, SweetLife",
            "<strong>Locked recipe</strong> — pizza slice and grill sausage taste the same every Wednesday",
            "<strong>Portion economics</strong> — vacuum-pack sizes designed for restaurant line work",
            "<strong>Private Label</strong> — for restaurant chains and dark kitchens",
            "<strong>Live API price list</strong> — your purchasing manager always quotes from current data",
        ],
        "related": [
            ("/en/dlya-pizzerii", "For Pizzerias", "Oven-stable pepperoni"),
            ("/en/kontraktnoe-proizvodstvo", "Private Label", "Restaurant-brand production"),
            ("/en/dlya-setey", "For Retail Chains", "Convenience zone & shelf"),
            ("/en/dlya-azs", "For Gas Stations", "Convenience-zone matrix"),
            ("/en/pepperoni", "Pepperoni catalog", "Pizza HoReCa range"),
            ("/en/kazylyk", "Kazylyk", "Tatar horse-meat sausage"),
        ],
        "cta_heading": "HoReCa supply inquiry",
        "cta_lead": "Write to us — we'll send a HoReCa short price list, a portion-pack spec sheet, and pilot terms.",
        "whatsapp_text": "Hello! I'm interested in halal HoReCa supply (pepperoni, sausages, deli)",
        "email_subject": "HoReCa supply",
    },
    {
        "slug": "kontraktnoe-proizvodstvo",
        "ru_slug": "kontraktnoe-proizvodstvo",
        "chip": "Segment 7 of 7 · Private Label / Contract manufacturing",
        "title": "Private Label Halal Sausage, Pepperoni & Pastry Manufacturer — Russia | Kazan Delicacies",
        "h1": "Private Label & Contract Manufacturing — Halal",
        "subtitle": "Sausages, pepperoni, hams, dumplings, Tatar pastries under your brand. Recipe, casing, diameter, packaging — customisable.",
        "description": "Halal private-label / contract manufacturing in Russia: sausages, pepperoni, hams, dumplings, Tatar pastries under your brand. Federal case: «Aslam» pepperoni for OMPK. Halal #614A/2024.",
        "keywords": "halal private label manufacturer, halal contract manufacturing Russia, halal SBM, white-label halal sausage, private label pepperoni, halal pastry private label",
        "og_title": "Private Label Halal Manufacturer — Sausages, Pepperoni, Pastry",
        "og_description": "Recipe, casing, diameter, packaging — customisable under your brand. Federal-scale case: «Aslam» for OMPK.",
        "intro": "Brand owners — retailers, distributors, foodservice operators, e-commerce — come to us when they need <strong>halal product under their own label</strong> without building a meat plant. We provide recipe customisation (spice, fat content, smoke depth), format engineering (casing type, diameter, length, slicing), and packaging design (carton, vacuum, MAP, sleeve) all under one HACCP + Halal certificate.",
        "case_title": "Federal-scale case: «Aslam» pepperoni for OMPK",
        "case_body": "We manufacture halal pepperoni under the <strong>«Aslam»</strong> brand for <strong>OMPK JSC</strong> (Ostankino Meat Plant) — Russia's largest meat producer. Product ships to pizzerias and HoReCa nationwide. This case demonstrates our capacity, recipe stability, and document discipline at federal scale.",
        "stats": [
            ("«Aslam» / OMPK", "federal case"),
            ("500 kg/mo", "minimum pilot"),
            ("4-6 weeks", "from spec to shipment"),
        ],
        "second_case": {
            "title": "Private-label categories we run",
            "body": "Sausages (hot-dog, grill, casingless, breakfast), pepperoni (boiled-smoked, dry-cured), hams (chicken, turkey, beef), boiled & semi-smoked sausages, kazylyk, dumplings (pelmeni, vareniki), echpochmak, samsa, chebureks, chak-chak.",
        },
        "features_heading": "What we customise",
        "features": [
            ("🧪", "Recipe", "Spice mix, fat content, smoke depth, brine, additives — to your spec sheet."),
            ("📏", "Format", "Casing type (natural, collagen, polyamide, cellulose, casingless), diameter, length, slicing pattern."),
            ("📦", "Packaging", "Vacuum, MAP, carton, retail sleeve — your brand, your design, GTIN."),
            ("📋", "Documents", "Full document pack issued under your brand: declaration, halal, Mercury VSD."),
            ("⚖️", "Minimum tier", "Pilot from ~500 kg / month — no 10-tonne entry barrier."),
            ("🕒", "Lead time", "4-6 weeks from approved spec to first pallet shipped."),
        ],
        "items_heading": "Private-label categories",
        "items": [
            ("Hot-dog sausages", "any flavour", "by spec"),
            ("Pepperoni (BC or DC)", "stick or sliced", "by spec"),
            ("Ham (chicken / turkey)", "stick or sliced", "by spec"),
            ("Boiled sausages", "any recipe", "by spec"),
            ("Kazylyk", "gift box or retail", "by spec"),
            ("Tatar pastry", "echpochmak, samsa, …", "by spec"),
        ],
        "items_note": "Send your spec sheet (or describe the target audience and we'll draft one) and we return a sample-pack timeline within 48 h.",
        "logistics_heading": "Contract manufacturing terms",
        "logistics": [
            ("Pilot minimum", "~500 kg / month per SKU"),
            ("Spec → first shipment", "4-6 weeks (recipe approval included)"),
            ("Incoterm", "EXW Kazan · transit hub Lyubertsy · CIS export available"),
            ("Payment", "50% prepayment for the first pilot batch, net 14-30 days thereafter"),
            ("Documents", "Issued under your brand: EAEU · Mercury VSD · Halal · GTIN · nutrition panel"),
            ("IP", "Your recipe is your recipe — NDA on request, exclusivity per category & region available"),
        ],
        "why_heading": "Why brands pick us for private label",
        "why": [
            "<strong>Halal certificate already issued</strong> — no waiting for paperwork",
            "<strong>Federal-scale case</strong> — «Aslam» / OMPK gives buyer confidence",
            "<strong>No 10-tonne barrier</strong> — pilot from 500 kg / month",
            "<strong>Recipe stability</strong> — same spec batch after batch, year after year",
            "<strong>One factory</strong> — sausages, pepperoni, hams, pastry under one roof",
            "<strong>NDA + regional exclusivity</strong> — protected category positioning",
        ],
        "related": [
            ("/en/dlya-setey", "For Retail Chains", "Retail-brand production"),
            ("/en/dlya-distributorov", "For Distributors", "Distributor-brand production"),
            ("/en/dlya-azs", "For Gas Stations", "Network-brand production"),
            ("/en/dlya-pizzerii", "For Pizzerias", "Pizza-chain pepperoni"),
            ("/en/dlya-pekaren", "For Bakeries", "Bakery filling & sausage"),
            ("/en/dlya-horeca", "For HoReCa", "Restaurant-brand production"),
        ],
        "cta_heading": "Discuss private-label production",
        "cta_lead": "Write to us — describe target audience, recipe direction, packaging idea. We respond with a sample-pack timeline in 48 h.",
        "whatsapp_text": "Hello! I'd like to discuss private-label halal production",
        "email_subject": "Private Label / contract manufacturing inquiry",
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
<link rel="alternate" hreflang="ru" href="https://pepperoni.tatar/{ru_slug}">
<link rel="alternate" hreflang="en" href="https://pepperoni.tatar/en/{slug}">
<link rel="alternate" hreflang="x-default" href="https://pepperoni.tatar/en/{slug}">

<meta property="og:type" content="website">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_description}">
<meta property="og:url" content="https://pepperoni.tatar/en/{slug}">
<meta property="og:image" content="https://pepperoni.tatar/og-default.png">
<meta property="og:locale" content="en_US">
<meta property="og:locale:alternate" content="ru_RU">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{og_description}">
<meta name="twitter:image" content="https://pepperoni.tatar/og-default.png">

<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
{{"@type":"ListItem","position":1,"name":"Catalog","item":"https://pepperoni.tatar/en/"}},
{{"@type":"ListItem","position":2,"name":"Buyer segments","item":"https://pepperoni.tatar/en/#segments"}},
{{"@type":"ListItem","position":3,"name":"{h1}","item":"https://pepperoni.tatar/en/{slug}"}}
]}}
</script>

<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.8}}
.container{{max-width:820px;margin:0 auto;padding:40px 24px}}
nav{{font-size:.85rem;color:#888;margin-bottom:32px}}
nav a{{color:#0066cc;text-decoration:none}}
h1{{font-size:2rem;font-weight:700;margin-bottom:8px;line-height:1.25}}
h2{{font-size:1.3rem;font-weight:700;margin:36px 0 12px;color:#1b7a3d}}
h3{{font-size:1.05rem;font-weight:600;margin:20px 0 8px}}
p{{margin-bottom:14px}}
.segment-chip{{display:inline-block;background:#fef3c7;color:#92400e;padding:4px 10px;border-radius:4px;font-size:.75rem;font-weight:700;margin-bottom:10px;letter-spacing:.5px;text-transform:uppercase}}
.badge{{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;margin:6px 4px 20px 0;letter-spacing:.5px}}
.badge-outline{{background:transparent;border:1.5px solid #1b7a3d;color:#1b7a3d}}
.hero-subtitle{{color:#666;font-size:1.05rem;margin-bottom:4px}}
.card{{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:24px;margin:16px 0}}
.card-accent{{border-left:4px solid #1b7a3d}}
.grid-2{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin:16px 0}}
.feat-card{{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:16px}}
.feat-card .icon{{font-size:1.6rem;margin-bottom:6px}}
.feat-card .title{{font-weight:600;font-size:.9rem}}
.feat-card .desc{{font-size:.82rem;color:#666;margin-top:4px}}
.prices-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin:16px 0}}
.price-card{{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:16px;text-align:center}}
.price-card .name{{font-size:.85rem;font-weight:600;margin-bottom:4px}}
.price-card .weight{{font-size:.75rem;color:#888}}
.price-card .price{{font-size:1.4rem;font-weight:700;color:#1b7a3d;margin-top:8px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;margin:18px 0}}
.stat{{background:#f0f9f3;border-left:3px solid #1b7a3d;padding:12px 14px;border-radius:4px}}
.stat .num{{font-size:1.4rem;font-weight:700;color:#1b7a3d;line-height:1}}
.stat .lbl{{font-size:.78rem;color:#444;margin-top:4px}}
table{{width:100%;border-collapse:collapse;margin:12px 0}}
th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid #eee;font-size:.9rem}}
th{{background:#f5f5f5;font-weight:600}}
ul{{margin:8px 0 14px 24px}}
li{{margin-bottom:4px}}
.spec-value{{font-weight:600;color:#1b7a3d}}
.cta{{background:#1b7a3d;color:#fff;display:inline-block;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;margin:8px 8px 8px 0;font-size:.95rem}}
.cta:hover{{background:#15652f}}
.cta-outline{{background:transparent;border:2px solid #1b7a3d;color:#1b7a3d}}
.cta-outline:hover{{background:#1b7a3d;color:#fff}}
footer{{text-align:center;color:#aaa;font-size:.85rem;padding-top:32px;margin-top:32px;border-top:1px solid #eee}}
footer a{{color:#888;text-decoration:none}}
@media(max-width:600px){{.grid-2,.prices-grid,.stats{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<div class="container">
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #eee;font-size:.9rem">
  <a href="/en/" style="color:#0066cc;text-decoration:none;font-weight:600">Catalog</a>
  <a href="/en/pepperoni" style="color:#0066cc;text-decoration:none">Pepperoni</a>
  <a href="/en/about" style="color:#0066cc;text-decoration:none">About</a>
  <a href="/en/delivery" style="color:#0066cc;text-decoration:none">Delivery</a>
  <a href="/en/faq" style="color:#0066cc;text-decoration:none">FAQ</a>
  <a href="/" style="color:#888;text-decoration:none;margin-left:auto">🇷🇺 RU</a>
</div>
<nav aria-label="Breadcrumb">
  <a href="/en/">Catalog</a> &rsaquo; <a href="/en/#segments">Buyer segments</a> &rsaquo; <span>{h1}</span>
</nav>

<span class="segment-chip">{chip}</span>
<h1>{h1}</h1>
<p class="hero-subtitle">{subtitle}</p>
<span class="badge">HALAL #614A/2024</span>
<span class="badge badge-outline">HACCP + ISO 22000:2018</span>
<span class="badge badge-outline">Weekly shipments</span>
<span class="badge badge-outline">EXW Kazan / Lyubertsy DC</span>

<p>{intro}</p>

<div class="card card-accent">
  <h3 style="margin-top:0">{case_title}</h3>
  <p style="margin-bottom:8px">{case_body}</p>
  <div class="stats">
{stats_html}
  </div>
</div>

<div class="card">
  <h3 style="margin-top:0">{second_case_title}</h3>
  <p>{second_case_body}</p>
</div>

<h2>{features_heading}</h2>
<div class="grid-2">
{features_html}
</div>

<h2>{items_heading}</h2>
<div class="prices-grid">
{items_html}
</div>
<p style="font-size:.85rem;color:#666"><em>{items_note}</em></p>

<h2>{logistics_heading}</h2>
<div class="card">
  <table>
    <tbody>
{logistics_html}
    </tbody>
  </table>
</div>

<h2>{why_heading}</h2>
<div class="card">
  <ul style="list-style:none;margin-left:0">
{why_html}
  </ul>
</div>

<h2>See also</h2>
<div class="grid-2">
{related_html}
</div>

<h2>{cta_heading}</h2>
<p>{cta_lead}</p>
<a href="tel:+79872170202" class="cta">📞 +7 987 217-02-02</a>
<a href="mailto:info@kazandelikates.tatar?subject={email_subject_url}" class="cta cta-outline">📧 info@kazandelikates.tatar</a>
<a href="https://wa.me/79872170202?text={whatsapp_text_url}" class="cta cta-outline">💬 WhatsApp</a>

<footer>
  <p><a href="/en/">← Catalog</a> &middot; <a href="/en/pepperoni">Pepperoni</a> &middot; <a href="/en/about">About</a> &middot; <a href="/en/delivery">Delivery</a> &middot; <a href="/en/faq">FAQ</a></p>
  <p>&copy; <a href="https://kazandelikates.tatar">Kazan Delicacies</a> &middot; <a href="https://pepperoni.tatar/en/">pepperoni.tatar</a></p>
</footer>
</div>
<script>(function(m,e,t,r,i,k,a){{m[i]=m[i]||function(){{(m[i].a=m[i].a||[]).push(arguments)}};m[i].l=1*new Date();for(var j=0;j<document.scripts.length;j++){{if(document.scripts[j].src===r)return}}k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a);}})(window,document,'script','https://mc.yandex.ru/metrika/tag.js','ym');ym(107064141,'init',{{clickmap:true,trackLinks:true,accurateTrackBounce:true,ecommerce:'dataLayer'}});</script><noscript><div><img src='https://mc.yandex.ru/watch/107064141' style='position:absolute;left:-9999px' alt='' width="1" height="1" loading="lazy" /></div></noscript>
</body>
</html>
"""


from urllib.parse import quote


def render(seg: dict) -> str:
    stats_html = "\n".join(
        f'    <div class="stat"><div class="num">{n}</div><div class="lbl">{l}</div></div>'
        for n, l in seg["stats"]
    )
    features_html = "\n".join(
        f'  <div class="feat-card"><div class="icon">{ic}</div><div class="title">{t}</div><div class="desc">{d}</div></div>'
        for ic, t, d in seg["features"]
    )
    items_html = "\n".join(
        f'  <div class="price-card"><div class="name">{n}</div><div class="weight">{w}</div><div class="price">{p}</div></div>'
        for n, w, p in seg["items"]
    )
    logistics_html = "\n".join(
        f'      <tr><td>{k}</td><td class="spec-value">{v}</td></tr>'
        for k, v in seg["logistics"]
    )
    why_html = "\n".join(
        f'    <li>✅ {x}</li>' for x in seg["why"]
    )
    related_html = "\n".join(
        f'  <a href="{href}" style="display:block;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:14px;text-decoration:none;color:#1a1a1a;font-size:.9rem"><strong>{title}</strong><br><span style="color:#666;font-size:.82rem">{desc}</span></a>'
        for href, title, desc in seg["related"]
    )
    return HEAD_TPL.format(
        slug=seg["slug"],
        ru_slug=seg["ru_slug"],
        chip=seg["chip"],
        title=seg["title"],
        description=seg["description"],
        keywords=seg["keywords"],
        og_title=seg["og_title"],
        og_description=seg["og_description"],
        h1=seg["h1"],
        subtitle=seg["subtitle"],
        intro=seg["intro"],
        case_title=seg["case_title"],
        case_body=seg["case_body"],
        stats_html=stats_html,
        second_case_title=seg["second_case"]["title"],
        second_case_body=seg["second_case"]["body"],
        features_heading=seg["features_heading"],
        features_html=features_html,
        items_heading=seg["items_heading"],
        items_html=items_html,
        items_note=seg["items_note"],
        logistics_heading=seg["logistics_heading"],
        logistics_html=logistics_html,
        why_heading=seg["why_heading"],
        why_html=why_html,
        related_html=related_html,
        cta_heading=seg["cta_heading"],
        cta_lead=seg["cta_lead"],
        email_subject_url=quote(seg["email_subject"]),
        whatsapp_text_url=quote(seg["whatsapp_text"]),
    )


def main():
    for seg in SEGMENTS:
        out = EN_DIR / f"{seg['slug']}.html"
        out.write_text(render(seg), encoding="utf-8")
        print(f"OK {out}  ({len(out.read_text())} bytes)")


if __name__ == "__main__":
    main()
