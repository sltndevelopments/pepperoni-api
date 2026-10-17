"""One Organization (and LocalBusiness) object for pepperoni.tatar pages.

Identity fields are the public requisites in data/site_facts.json. taxID is
the ИНН — it is published on /about and in legal pages, not guessed.
"""
from __future__ import annotations

import json
from pathlib import Path

from site_facts import certificates_for_api, postal_code, street_address

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
        "streetAddress": street_address(),
        "addressLocality": "Казань",
        "postalCode": postal_code() or "420061",
        "addressCountry": "RU",
    },
    "sameAs": [
        "https://kazandelikates.tatar",
        "https://www.wikidata.org/wiki/Q141108238",
        "https://www.youtube.com/@kazandelikates",
    ],
    "areaServed": [
        {"@type": "Country", "name": name}
        for name in ["Russia"] + list((_FACTS.get("export") or {}).get("current_en") or [])
    ],
}

ORGANIZATION["hasCredential"] = [
    {
        "@type": "EducationalOccupationalCredential",
        "name": item["number"],
        "credentialCategory": "certification",
        "description": item.get("scope_en") or item.get("scope_ru"),
        **({"url": item["verify_url"]} if item.get("verify_url") else {}),
    }
    for item in certificates_for_api()
]

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
