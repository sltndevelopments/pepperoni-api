# Independent B2B authority program

The program converts verified company facts into third-party records. It does
not manufacture mentions. The machine-readable state is
`data/authority_program.json`; published proof is admitted to
`data/evidence_registry.json` only after verification.

## Monthly target

- Five newly published independent domains.
- At least one international domain.
- One domain counts once per cycle, even if it contains several SKU pages.
- Updates on an existing domain are useful but do not count as a new domain.
- An application, email, negotiation or paid placement is not a published node.

## Weekly operating loop

1. Sales or management confirms that outreach has a real commercial,
   certification or editorial basis.
2. The owner sends the approved entity template and only the evidence relevant
   to that target.
3. When a public page appears, record its URL, publication date, domain,
   supported claims and screenshot/PDF if available.
4. A reviewer checks that the page is crawlable and does not introduce a false
   importer, customer, certification, MOQ, shipment or country-approval claim.
5. Add the verified node to `data/evidence_registry.json` and the program
   scoreboard. Re-run `scripts/authority_program_check.py`.
6. Review citation pickup in the fixed AI panel at the next 30-day checkpoint.

## Evidence package

Use the same package for every target:

- legal name: ООО «Казанские Деликатесы»;
- English name: Kazan Delicacies LLC;
- location: Kazan, Republic of Tatarstan, Russia;
- B2B catalog: <https://pepperoni.tatar/>;
- corporate site: <https://kazandelikates.tatar/>;
- contact: +7 987 217-02-02, info@kazandelikates.tatar;
- product facts: only the selected record in `public/products.json`;
- credentials: only active entries in `data/evidence_registry.json`.

Never attach an unsupported client list, market-access claim, universal MOQ,
lead time or capacity statement.

## Outreach briefs

### DUM RT registry

Ask the registry owner to add “Kazan Delicacies LLC”, the B2B catalog URL and a
plain manufacturer description. Do not ask for JAKIM, SFDA, GSO or GCC wording.
This improves an existing node and does not count as a new domain.

### Distributor or B2B retailer

Proceed only when sales confirms a real listing or onboarding route. Supply the
current SKU name, article, pack, storage, halal status and approved image. A
public product or brand page is the acceptance criterion.

### Trade publication

Pitch an owned asset: a documented product test, a certification update, or a
small disclosed catalog study. The article must be editorially useful without
“best manufacturer” language. A paid advertorial must be disclosed and is not
treated as independent editorial proof.

### International importer or catalog

Submit the supplier pack only with destination-specific requirements supplied
by the prospective importer. Until a public SKU or supplier record exists,
describe the work as an application—not a partnership, shipment or local
availability.

## Acceptance checklist

- Public HTTPS URL and independent registrable domain.
- Page names the correct entity and links to a canonical site page.
- Every material claim has a dated source.
- No fake review, rating, award, customer or stock statement.
- No unsupported JAKIM, SFDA, GSO, GCC, country approval or importer claim.
- Domain was not already counted in the current cycle.
- International status is based on the publisher/importer domain and page, not
  on a self-authored geo landing.
