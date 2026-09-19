# 1С УНФ — OData клиент (только чтение)

Читающий клиент к `http://192.168.11.40/unf/odata/standard.odata/` (OData 3.0,
HTTP Basic, realm `1C:Enterprise 8.5`).

## Только чтение — механически, не на словах

1С — источник данных, не приёмник. В базу ничего не пишется, ничего не
проводится, никакие файлы не трогаются. Это закреплено гейтом в тестах, а не
договорённостью:

| Тест | Что ловит |
|---|---|
| `test_transport_issues_get` | реальный `Request` уходит как GET и без тела |
| `test_every_request_is_get_without_body` | по AST: любой `Request` — GET, без `data=` |
| `test_no_write_verb_literals_in_module` | появление литерала POST/PUT/PATCH/DELETE/MERGE |
| `test_public_api_has_no_mutating_methods` | публичный метод вида `create*`/`update*`/`delete*`/`save*` |
| `test_module_never_writes_to_disk` | по AST: `open()`, `os.remove`, `write_text`, … |

Гейт проверен мутациями: подмена `GET`→`POST`, добавление `data=` в запрос,
публичный `delete_row()` и запись на диск — каждая роняет тесты.

Если чтения окажется мало и понадобится запись — это отдельное решение
владельца, а не правка клиента: снимать гейт молча нельзя.

Рекомендация по доступу: у учётной записи `Odata.user` в 1С стоит оставить
только право чтения. Тогда запись невозможна и на стороне сервера, а не только
на стороне клиента.

## Требование к сети

1С живёт в LAN `192.168.11.0/24` и доступна **только через WireGuard**. Клиент
намеренно ходит мимо `HTTPS_PROXY`: прокси в эту подсеть не маршрутизирует, и
запрос через него превращается в таймаут.

Из-за этого **из remote-сессии Claude Code (claude.ai/code) подключиться нельзя** —
там разрешён только HTTP(S) через прокси, сырой UDP до WG-эндпоинта не проходит,
handshake остаётся `0 B received`. Запускать нужно с машины, где туннель поднят.

```bash
sudo wg-quick up wg0
sudo wg show wg0        # received > 0 — туннель живой; 0 B — нет смысла идти дальше
```

## Проверка соединения

```bash
export ODATA_USER='...' ODATA_PASSWORD='...'
python3 -m integrations.onec.odata
```

Коды возврата: `0` — связь есть, `1` — сеть/авторизация, `2` — не заданы креды.

## Использование

```python
from datetime import datetime
from integrations.onec.odata import ODataClient

client = ODataClient()                       # ODATA_URL / ODATA_USER / ODATA_PASSWORD
for row in client.sales(datetime(2026, 7, 1), datetime(2026, 8, 1)):
    ...
```

Пагинация через `$top`/`$skip` внутри `iter_all()` — регистры отдают тысячи
строк, поэтому методы возвращают итератор, а не список. `orderby` передаётся по
умолчанию: без стабильной сортировки страницы могут дублировать или терять
строки на изменяющейся таблице.

Произвольный запрос:

```python
client.get("Catalog_Номенклатура", filter="DeletionMark eq false", top=100)
```

Кириллица в именах сущностей кодируется автоматически; пробелы в `$filter`
уходят как `%20`, а не `+` (1С не декодирует `+` как пробел).

## Не подтверждено на живой базе

Имена сущностей в константах `ENTITY_*` взяты из постановки задачи и **ещё не
сверены с реальными `$metadata`**:

| Константа | Значение |
|---|---|
| `ENTITY_COUNTERPARTIES` | `Catalog_Контрагенты` |
| `ENTITY_SALES` | `AccumulationRegister_Продажи_RecordType` |
| `ENTITY_CUSTOMER_ORDERS` | `Document_ЗаказПокупателя` |
| `ENTITY_ORDER_FULFILMENT` | `AccumulationRegister_ЗаказыПокупателей_RecordType` |

Первый живой запуск: снять `$metadata`, сверить имена сущностей и полей
(`Period`, `Date`, `Posted`, `RecordType`, `IsFolder`, `DeletionMark`) и
поправить константы. До сверки числа из этих выборок в отчёты не пускать.

```bash
python3 -c "
from integrations.onec.odata import ODataClient
print(ODataClient().metadata())
" > unf-metadata.xml
```

Клиент печатает `$metadata` в stdout; файл создаёт редирект, то есть вы, а не
код.

## Тесты

```bash
python3 -m unittest integrations.onec.tests.test_odata
```

40 тестов на моках, сеть не нужна. Из них 5 — гейт «только чтение».
