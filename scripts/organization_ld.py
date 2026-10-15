"""One Organization (and LocalBusiness) object for pepperoni.tatar pages.

Identity fields are the public requisites in data/site_facts.json. taxID is
the ИНН — it is published on /about and in legal pages, not guessed.
"""
from __future__ import annotations

import json
from pathlib import Path

ORG_ID = "https://pepperoni.tatar/#organization"
LOCAL_ID = "https://pepperoni.tatar/#localbusiness"

_FACTS = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "site_facts.json")
    .read_text(encoding="utf-8")
)
_CO = _FACTS["company"]

ORGANIZATION = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": ORG_ID,
    "name": "Казанские Деликатесы",
    "legalName": _CO["legal_name_ru"],
    "taxID": _CO["inn"],
    "url": "https://pepperoni.tatar/",
    "email": _CO["email"],
    "telephone": _CO["phone"],
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

LOCAL_BUSINESS = {
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    "@id": LOCAL_ID,
    "name": "Казанские Деликатесы",
    "legalName": _CO["legal_name_ru"],
    "taxID": _CO["inn"],
    "url": "https://pepperoni.tatar/",
    "email": _CO["email"],
    "telephone": _CO["phone"],
    "address": dict(ORGANIZATION["address"]),
    "parentOrganization": {"@id": ORG_ID},
}

SAME_AS = set(ORGANIZATION["sameAs"])
SCRIPT = (
    '<script type="application/ld+json">'
    + json.dumps(ORGANIZATION, ensure_ascii=False, separators=(",", ":"))
    + "</script>"
)
LOCAL_SCRIPT = (
    "<!-- localbusiness-ld:start -->"
    '<script type="application/ld+json">'
    + json.dumps(LOCAL_BUSINESS, ensure_ascii=False, separators=(",", ":"))
    + "</script>"
    "<!-- localbusiness-ld:end -->"
)

# Fields that must agree wherever an Organization states them.
# taxID is published on LocalBusiness and /about; older Organization blocks
# without it are still valid as long as they do not contradict the ИНН.
IDENTITY_KEYS = ("name", "legalName", "email", "telephone")
