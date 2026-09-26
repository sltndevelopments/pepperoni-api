# Public customer-reference inventory — 2026-09-26

No public copy was changed. Nothing was added to `data/evidence_registry.json`.

Registry check: none of Татнефть, SMARTEN, EuroSpar, Бэхетле, Metro, Мираторг, Aslam / ОМПК has an entry. Nearby registry ids that are **not** these names: `gfc_pepperoni_240111`, `sweet_life_pepperoni_118665`.

`Needs owner classification` is YES wherever the sentence mixes roles. One shelf mention is not a contract, and the Aslam line is a private-label project, not a pepperoni purchase.

| Entity | File/URL | Exact current claim | Implied relationship | Evidence registry entry | Needs owner classification |
|---|---|---|---|---|---|
| Татнефть | `public/index.html` | «Кейс: сеть АЗС Татнефть + SMARTEN» | petrol-station network, labeled as a case | no | YES |
| SMARTEN | `public/index.html` | same sentence | petrol-station operator, labeled as a case | no | YES |
| EuroSpar, Бэхетле, Metro, Мираторг | `public/index.html` | «EuroSpar, Бэхетле, Metro, Мираторг» under retail chains | retail listing / chain presence, labeled as a case | no | YES |
| Aslam / ОМПК | `public/index.html` | «Кейс: линейка „Аслам“ для ОМПК» | private-label / STM project | no | YES |
| Татнефть, SMARTEN | `public/about.html` | «Сеть АЗС „Татнефть“ & SMARTEN. Поставки халяльных сосисок…» | supply to petrol stations | no | YES |
| EuroSpar, Бэхетле, Metro, Мираторг | `public/about.html` | «Присутствие на халяль-полках супермаркетов» | retail listing, not a stated contract | no | YES |
| Aslam / ОМПК | `public/about.html` | «контрактное производство линейки традиционных колбас под маркой „Aslam“ для АО „ОМПК“ … (пепперони в этой линейке нет)» | STM project for the customer's brand; explicitly not pepperoni | no | YES |
| Aslam / ОМПК, Татнефть, СМАРТЕН, EuroSpar, Бэхетле, Metro, Мираторг | `public/cases.html` meta | one description lists STM, petrol stations, retailers and distributors together | mixed; page calls all of them cases/clients | no | YES |
| Татнефть | `public/pizzeria.html` | «Партнёрство с „Татнефть“»; «поставляется на все АЗС сети» | supply / partnership | no | YES |
| Metro | `public/pizzeria.html` | «в федеральную сеть Metro Cash & Carry» | retail or wholesale-club listing | no | YES |
| Татнефть, SMARTEN, EuroSpar, Metro, Бэхетле | `public/sosiski-dlya-hotdog.html` | hot-dog sausages and burger patties supplied to Tatneft; other names listed as where product also goes | petrol-station supply plus retail listing, one sentence | no | YES |
| Татнефть, ОМПК, EuroSpar, Metro | `public/kontraktnoe-proizvodstvo.html` | link label «Кейсы и клиенты: Татнефть, ОМПК, EuroSpar, Metro» | treats petrol, STM and retail as one client list | no | YES |
| Aslam / ОМПК | `public/kontraktnoe-proizvodstvo.html` description | «Кейс — „Aslam“ для ОМПК» | STM project | no | YES |
| EuroSpar, Бэхетле | `public/dlya-setey.html` | «Кейсы: EuroSpar и „Бэхетле“ в Казани»; products «постоянно» on shelf | retail listing in Kazan | no | YES |
| Metro, Мираторг | `public/dlya-setey.html` | «Федеральные сети»; «продукция представлена» | retail listing, not a named contract | no | YES |
| All of the above | `public/llms-full.txt` | «Федеральные кейсы: сеть АЗС Татнефть, СМАРТЕН, EuroSpar, Бахетле, Metro Cash & Carry, Мираторг; контрактная линейка … „Аслам“ для ОМПК» | one sentence mixes cases and one STM project | no | YES |
| EuroSpar, Бэхетле, Татнефть, Metro, Мираторг | `public/llms-full.txt` FAQ copy | «представлена в супермаркетах EuroSpar и „Бэхетле“ … на всех АЗС „Татнефть“ … в Metro … на полках „Мираторг“» | retail listing and petrol-station presence | no | YES |
| Same cluster | `public/en/llms-full.txt`, `public/en/index.html`, `public/en/about.html`, `public/en/cases.html` | English equivalents of the sentences above | same mix of roles | no | YES |
| Tatneft, Aslam/OMPK, the retail names | `submission/kb-company.txt` | «Федеральные кейсы» plus the Aslam line «не пепперони» | same mix | no | YES |

English pages repeat the Russian claims. They are not a second set of facts.

Not rewritten in this sprint: `data/ab_tests.json`, `data/experiments.json`, and any sales-intel files.
