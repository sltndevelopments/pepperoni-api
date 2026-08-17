# Wikidata draft — ООО «Казанские Деликатесы»

Публикует **владелец** (не агент). Черновик фактов из `public/brand.txt`.
Не выдумывать ИНН/ОГРН, если их нет в этом файле.

## Label / description

| lang | label | description |
|---|---|---|
| ru | Казанские Деликатесы | производитель халяль мясных изделий в Казани |
| en | Kazan Delicacies | halal meat manufacturer in Kazan, Tatarstan |
| tt | Казанский Деликатеслар | *(если подтверждаешь татарский лейбл — поправь)* |

## Suggested statements

| prop | value | note |
|---|---|---|
| instance of (P31) | business / food manufacturer | Q4830453 enterprise, or food manufacturer if a closer class exists |
| official name (P1448) | ООО «Казанские Деликатесы» | ru |
| official name (P1448) | Kazan Delicacies LLC | en |
| country (P17) | Russia | |
| headquarters location (P159) | Kazan | |
| located on street (P669) | Agrarnaya Street | + house 2, office 7 if qualifiers allowed |
| official website (P856) | https://pepperoni.tatar | catalog |
| official website (P856) | https://kazandelikates.tatar | corporate |
| phone (P1329) | +7 987 217-02-02 | |
| email (P968) | info@kazandelikates.tatar | |
| YouTube channel (P2397) | kazandelikates | https://www.youtube.com/@kazandelikates |
| certification | Halal DUM RT #614A/2024 | only if a suitable property exists; do not invent a certificate item |

## sameAs after publish

Когда появится Q-id, добавить в Organization JSON-LD `sameAs` на money hub
(`/pepperoni`, `/en/pepperoni`) в `scripts/gen_pepperoni_landing.py` и в
`scripts/gen-index.py`.

## Не писать

- kazandelikates.ru (нам не принадлежит, DNS не резолвится)
- SFDA / ESMA listing
- свинина, выдуманные клиенты, рейтинги
