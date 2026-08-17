# Wikidata draft — ООО «Казанские Деликатесы»

**Опубликовано 2026-08-17:** https://www.wikidata.org/wiki/Q141108238
аккаунт `RinatSultanov`. Сайты, ОГРН, тип, страна, Казань, дата регистрации —
на карточке. Телефон/email можно дописать позже (сработал антифлуд).

Реквизиты сверены с ЕГРЮЛ/rusprofile (не с `llms.txt`):
ИНН **1686021074**, ОГРН **1221600096893**, регистрация 28.11.2022,
адрес Казань, ул. Аграрная, 2, офис 7. ИНН `1655504520` в llms — не использовать.

## QuickStatements (один paste)

1. В обычном Safari/Chrome (не браузер Cursor): зайти на
   https://www.wikidata.org и **Log in** (аккаунт Wikimedia).
2. Открыть https://quickstatements.toolforge.org/#/batch
   → разрешить OAuth, если спросит.
3. Вставить блок ниже → **Import V1 commands** → **Run**.
4. Прислать Q-id сюда — пропишем `sameAs`.

```
CREATE
LAST|Len|"Kazan Delicacies"
LAST|Lru|"Казанские Деликатесы"
LAST|Den|"halal meat manufacturer in Kazan, Tatarstan"
LAST|Dru|"производитель халяль мясных изделий в Казани"
LAST|Aen|"Kazan Delicacies LLC"
LAST|Aru|"ООО «Казанские Деликатесы»"
LAST|P31|Q4830453|S854|"https://pepperoni.tatar"|S813|+2026-08-17T00:00:00Z/11
LAST|P31|Q1252971|S854|"https://pepperoni.tatar"|S813|+2026-08-17T00:00:00Z/11
LAST|P1454|Q21191682|S854|"https://www.rusprofile.ru/id/1221600096893"|S813|+2026-08-17T00:00:00Z/11
LAST|P17|Q159|S854|"https://www.rusprofile.ru/id/1221600096893"|S813|+2026-08-17T00:00:00Z/11
LAST|P159|Q900|S854|"https://www.rusprofile.ru/id/1221600096893"|S813|+2026-08-17T00:00:00Z/11
LAST|P1448|ru:"ООО «Казанские Деликатесы»"|S854|"https://www.rusprofile.ru/id/1221600096893"|S813|+2026-08-17T00:00:00Z/11
LAST|P571|+2022-11-28T00:00:00Z/11|S854|"https://www.rusprofile.ru/id/1221600096893"|S813|+2026-08-17T00:00:00Z/11
LAST|P7011|"1221600096893"|S854|"https://www.rusprofile.ru/id/1221600096893"|S813|+2026-08-17T00:00:00Z/11
LAST|P969|"ул. Аграрная, 2, офис 7, Казань"|S854|"https://kazandelikates.tatar"|S813|+2026-08-17T00:00:00Z/11
LAST|P856|"https://pepperoni.tatar"|S854|"https://pepperoni.tatar"|S813|+2026-08-17T00:00:00Z/11
LAST|P856|"https://kazandelikates.tatar"|S854|"https://kazandelikates.tatar"|S813|+2026-08-17T00:00:00Z/11
LAST|P1329|"+7 987 217-02-02"|S854|"https://pepperoni.tatar"|S813|+2026-08-17T00:00:00Z/11
LAST|P968|"info@kazandelikates.tatar"|S854|"https://pepperoni.tatar"|S813|+2026-08-17T00:00:00Z/11
```

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
