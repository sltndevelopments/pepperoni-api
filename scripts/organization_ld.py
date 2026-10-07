"""One Organization object for every pepperoni.tatar page.

Identity fields come from public/brand.txt. taxID is omitted: the brand file
has no INN, and a guessed number must not be published.
"""
from __future__ import annotations

import json

ORG_ID = "https://pepperoni.tatar/#organization"

ORGANIZATION = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": ORG_ID,
    "name": "Казанские Деликатесы",
    "legalName": "ООО «Казанские Деликатесы»",
    "url": "https://pepperoni.tatar/",
    "email": "info@kazandelikates.tatar",
    "telephone": "+7 987 217-02-02",
    "address": {
        "@type": "PostalAddress",
        "streetAddress": "ул. Аграрная, 2, оф. 7",
        "addressLocality": "Казань",
        "postalCode": "420061",
        "addressCountry": "RU",
    },
    "sameAs": [
        "https://kazandelikates.tatar",
        "https://www.wikidata.org/wiki/Q141108238",
        "https://www.youtube.com/@kazandelikates",
    ],
}

SAME_AS = set(ORGANIZATION["sameAs"])
SCRIPT = (
    '<script type="application/ld+json">'
    + json.dumps(ORGANIZATION, ensure_ascii=False, separators=(",", ":"))
    + "</script>"
)

# Fields that must agree wherever an Organization states them.
IDENTITY_KEYS = ("name", "legalName", "email", "telephone")
