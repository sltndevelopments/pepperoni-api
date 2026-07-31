# Google Ads для экспортных лендингов KD-013

Операторский handbook владельца «Казанских Деликатесов»: что нажать, в каком порядке и что не трогать.

> Интерфейс Google иногда переименовывает пункты. Русское и английское названия приведены рядом. Любое неизвестное число отмечено `⚠️ взять в аккаунте`: не заменяйте его отраслевым «средним».

## 1. TL;DR — первые 60 минут

1. Откройте Google Tag Manager и контейнер `GTM-W2Q5S8HF`.
2. Нажмите **Preview / Предварительный просмотр** и подключите `https://pepperoni.tatar/pepperoni`.
3. Убедитесь, что Tag Assistant видит `landing_view`, `scroll_depth`, `engaged_time`, `section_view`.
4. Отправьте тестовую форму: должен появиться один `generate_lead`, а лид — прийти в Telegram.
5. В Google Analytics создайте ресурс GA4 и Web stream для `pepperoni.tatar`.
6. Скопируйте `G-…`: `⚠️ взять в аккаунте` — **GA4 → Администратор → Потоки данных → Web**.
7. В GTM создайте Google tag с `G-…`, затем переменные, триггеры и GA4 events по разделу 3.
8. Опубликуйте GTM только после проверки в Preview и GA4 DebugView.
9. В Google Ads откройте **Цели → Конверсии → Сводка** и проверьте существующую конверсию формы.
10. Не создавайте Ads conversion tag на `generate_lead`: код формы уже отправляет эту конверсию.
11. Создайте Primary-конверсии кликов по телефону и WhatsApp.
12. Оставьте вовлечение Secondary: оно не должно обучать ставки вместо лидов.
13. Свяжите GA4 и Google Ads; включите Enhanced Conversions.
14. Создайте по одной Search-кампании на страну, начиная с exact/phrase коммерческих запросов.
15. Выберите **Presence**, а не «Presence or interest», для геотаргетинга.
16. Исключите EEA/UK/Швейцарию: CMP на сайте нет.
17. После первого лида сохраните `gclid` из Telegram вместе с результатом продажи.
18. На первой неделе настройте импорт qualified/sample/contract через Data Manager.

Игнорировать на старте: broad match без данных, Display Expansion, Performance Max «в один клик», Merchant Center, объединение стран и любые автоматические бюджеты без собственной экономики.

## 2. Что готово, а что настраивать

### Уже готово в коде

| Что | Реализация | Результат |
|---|---|---|
| GTM | `GTM-W2Q5S8HF` в `<head>` и `<noscript>` | Единая точка настройки |
| Google Ads | `AW-18346189266` | Базовый Ads tag |
| Метрика | `107064141`, после `window.load` | Дополнительная аналитика |
| Consent Mode v2 | До tags; EEA/UK/CH denied, остальные granted | Полное измерение 8 рынков |
| События | `/assets/gmp-track.js` → `dataLayer` | Готовы для GTM |
| Форма | `/lead-submit` → Flask → Telegram | Лид приходит продажам |
| Конверсия формы | Прямой `gtag('event','conversion', …)` после успеха | Уже отправляется в Ads |
| Enhanced data | `user_data`: телефон/имя/фамилия | Готово для matching |
| Атрибуция | click IDs, UTM, Ads-параметры, хранение 90 дней | Возможен offline import |
| Телефоны | +7/8, +375, +374, +992, +994, +995, +996, +998 | Все 8 стран |
| Локали | RU, EN, KK, UZ, AZ, HY, KA, KY, TG | Страновые страницы |

### Настроить руками

| Задача | Где | Когда |
|---|---|---|
| Создать GA4 property/Web stream | Google Analytics | Сразу |
| Добавить GA4 и events | GTM | Сразу |
| Проверить форму без дубля | Google Ads + Tag Assistant | До запуска |
| Создать phone/WhatsApp conversions | Google Ads + GTM | До запуска |
| Включить Enhanced Conversions | Ads + GTM | До масштабирования |
| Связать Ads и GA4 | GA4 Admin | До аудиторий |
| Настроить offline conversions | Data Manager | Первая неделя |
| Разделить кампании по странам | Google Ads | До масштабирования |
| Подключить Search Console | Search Console | Первая неделя |
| Страновой dashboard | Looker Studio | После первых лидов |

## 3. Шаг 1: Google Tag Manager

### 3.1. Проверка контейнера

1. `tagmanager.google.com` → выберите `GTM-W2Q5S8HF`.
2. **Preview** → URL `https://pepperoni.tatar/pepperoni` → **Connect**.
3. В Tag Assistant найдите `Consent Initialization`, `Initialization`, `Container Loaded`, затем `landing_view`.
4. Прокрутите страницу: проверьте `scroll_depth` и `section_view`.
5. Оставьте вкладку видимой 15 секунд: проверьте `engaged_time`.
6. Откройте и запустите видео: проверьте `video_open`, затем `video_start`.
7. В Data Layer каждого события проверьте `page_lang`, `page_country`, `product_sku: KD-013`, `page_type: export_landing`.
8. Отправьте тестовую форму и проверьте один `generate_lead` плюс Telegram.

### 3.2. Создание GA4

1. `analytics.google.com` → **Администратор → Создать → Ресурс**.
2. Название: `Pepperoni Export`.
3. Часовой пояс: `⚠️ взять решение владельца`; далее применять его и в offline uploads.
4. Валюта: `⚠️ взять основную отчётную валюту аккаунта Ads`.
5. **Сбор и изменение данных → Потоки данных → Добавить поток → Web**.
6. URL: `https://pepperoni.tatar`; имя: `pepperoni.tatar`.
7. Скопируйте Measurement ID `G-…`: `⚠️ взять в карточке потока`.

### 3.3. Базовый tag

В новом GTM прежний GA4 Configuration tag называется **Google tag**.

1. GTM → **Tags → New → Google tag**.
2. Имя: `GA4 - Google tag - All Pages`.
3. Tag ID: `⚠️ G-… взять в GA4 Web stream`.
4. Trigger: **Initialization — All Pages**.
5. Сохраните, пока не публикуйте.

### 3.4. Data Layer Variables

Для каждой строки: **Variables → User-Defined → New → Data Layer Variable**, Version 2.

| Имя GTM | Data Layer Variable Name |
|---|---|
| `DLV - page_lang` | `page_lang` |
| `DLV - page_country` | `page_country` |
| `DLV - product_sku` | `product_sku` |
| `DLV - page_type` | `page_type` |
| `DLV - ecomm_prodid` | `ecomm_prodid` |
| `DLV - ecomm_pagetype` | `ecomm_pagetype` |
| `DLV - ecomm_totalvalue` | `ecomm_totalvalue` |
| `DLV - currency` | `currency` |
| `DLV - attribution_source` | `attribution_source` |
| `DLV - percent_scrolled` | `percent_scrolled` |
| `DLV - engagement_seconds` | `engagement_seconds` |
| `DLV - section_name` | `section_name` |
| `DLV - selected_country` | `selected_country` |
| `DLV - selected_language` | `selected_language` |
| `DLV - video_title` | `video_title` |
| `DLV - video_id` | `video_id` |
| `DLV - video_percent` | `video_percent` |
| `DLV - event_label` | `event_label` |
| `DLV - user_data` | `user_data` |
| `DLV - attribution` | `attribution` |

### 3.5. Custom Event triggers и GA4 tags

Для каждой строки:

1. **Triggers → New → Custom Event**.
2. Event name — ровно из таблицы; **All Custom Events**.
3. Имя trigger: `CE - <event>`.
4. **Tags → New → Google Analytics: GA4 Event**.
5. Configuration tag: `GA4 - Google tag - All Pages`.
6. Event name — GA4 name из таблицы.
7. Всегда передавайте `page_lang`, `page_country`, `product_sku`, `page_type`.
8. Добавьте указанные специальные параметры и соответствующий trigger.

| Trigger | dataLayer event | GA4 event | Дополнительные параметры |
|---|---|---|---|
| `CE - landing_view` | `landing_view` | `view_item` | `ecomm_prodid`, `ecomm_pagetype`, `ecomm_totalvalue`, `currency`, `attribution_source` |
| `CE - scroll_depth` | `scroll_depth` | `scroll_depth` | `percent_scrolled` |
| `CE - engaged_time` | `engaged_time` | `engaged_time` | `engagement_seconds` |
| `CE - section_view` | `section_view` | `section_view` | `section_name` |
| `CE - select_country` | `select_country` | `select_country` | `selected_country`, `selected_language` |
| `CE - video_open` | `video_open` | `video_open` | `video_title`, `video_id` |
| `CE - video_start` | `video_start` | `video_start` | `video_title`, `video_id` |
| `CE - video_progress` | `video_progress` | `video_progress` | `video_title`, `video_id`, `video_percent` |
| `CE - video_complete` | `video_complete` | `video_complete` | `video_title`, `video_id` |
| `CE - generate_lead` | `generate_lead` | `generate_lead` | `attribution` |
| `CE - click_phone` | `click_phone` | `click_phone` | `event_label` |
| `CE - click_email` | `click_email` | `click_email` | `event_label` |
| `CE - click_messenger` | `click_messenger` | `click_messenger` | `event_label` |
| `CE - download_price` | `download_price` | `download_price` | `event_label` |

`landing_view` использует рекламные `ecomm_*` параметры. Полноценный GA4 ecommerce `items` можно добавить позже; запуск ради этого не задерживать.

### 3.6. Публикация

1. **Preview** → повторите просмотр, scroll, видео, форму.
2. У каждого события должен сработать один GA4 Event tag.
3. GA4 → **Администратор → DebugView** → найдите события.
4. Проверьте, что `generate_lead` один.
5. GTM → **Submit → Publish and Create Version**.
6. После публикации проверьте GA4 Realtime без Preview.

## 4. Шаг 2: Google Ads конверсии

| Действие | Роль | Статус | Value |
|---|---|---|---|
| Успешная форма | Лид | **Primary** | `⚠️ взять из экономики продаж` |
| `click_phone` | Контакт | **Primary** | `⚠️ взять из своей статистики` |
| `click_messenger`/WhatsApp | Контакт | **Primary** | `⚠️ взять из своей статистики` |
| `click_email` | Слабее | Secondary сначала | `⚠️ взять из своей статистики` |
| `download_price` | Интерес | Secondary | `⚠️ утвердить владельцу` |
| `video_complete` | Вовлечение | Secondary | `⚠️ условное значение` |
| `section_view: price` | Вовлечение | Secondary | `⚠️ условное значение` |
| `scroll_depth: 90` | Вовлечение | Secondary | `⚠️ условное значение` |
| `engaged_time: 60/120` | Вовлечение | Secondary | `⚠️ условное значение` |

Не делайте вовлечение Primary: Smart Bidding начнёт покупать дешёвые просмотры вместо лидов.

### 4.1. Ценности

1. Ads → **Цели → Конверсии → Сводка → действие → Настройки → Ценность**.
2. Для лида: `⚠️ средняя маржа сделки × вероятность сделки после лида — взять из учёта`.
3. Для phone/WhatsApp: `⚠️ взять фактическую вероятность к квалифицированному лиду`.
4. Secondary можно оценивать относительной стабильной шкалой: `⚠️ утвердить владельцу`.
5. Не называйте условную ценность выручкой и не меняйте шкалу еженедельно.

Последовательные values помогают Smart Bidding различать сильные и слабые сигналы.

### 4.2. Критическое предупреждение о дубле

После успеха `/assets/lead-form.js` уже вызывает:

```javascript
gtag('event', 'conversion', {send_to:'AW-18346189266'});
```

И отдельно отправляет `generate_lead` в `dataLayer`. Если создать GTM Ads Conversion tag на `generate_lead`, один лид может считаться дважды.

Правильно:

- код не менять;
- `generate_lead` через GTM отправлять в GA4;
- второй Ads Conversion tag для него **не создавать**;
- Ads tags в GTM создавать только для отдельных phone/WhatsApp conversion actions.

Проверка формы: **Ads → Цели → Конверсии → Сводка** → найдите website action от `AW-18346189266`; имя/label `⚠️ взять в аккаунте`; откройте **Диагностика** и найдите тест.

### 4.3. Phone и WhatsApp

1. Ads → **Цели → Конверсии → + Создать → Сайт**.
2. Домен `pepperoni.tatar` → ручная настройка → категория **Контакт**.
3. Имена: `Export - Phone click`, `Export - WhatsApp click`.
4. Value: `⚠️ взять из экономики`; Count: **One**.
5. Окно: `⚠️ взять в настройках действующей KZ-кампании и сверить с циклом`.
6. Attribution: **Data-driven**, если доступно; иначе `⚠️ взять доступное в аккаунте`.
7. **Tag setup → Use Google Tag Manager** → скопируйте ID/Label.
8. В GTM создайте Ads Conversion Tracking tags с triggers `CE - click_phone` и `CE - click_messenger`.
9. Если `click_messenger` шире WhatsApp, фильтр trigger: `DLV - event_label contains wa.me` либо фактический href из Preview.

### 4.4. Enhanced Conversions

`user_data` уже содержит телефон/имя/фамилию. Не отправляйте их как обычные GA4 parameters.

1. Ads → **Цели → Конверсии → Настройки → Enhanced conversions**.
2. Включите и примите Customer Data Terms.
3. GTM → **Tags → New → Google Ads User-Provided Data Event**.
4. Conversion Tracking ID: `AW-18346189266`.
5. Источник user-provided data: `DLV - user_data`.
6. Trigger: `CE - generate_lead`.
7. Preview: user-data tag срабатывает, второй Ads conversion tag — нет.
8. Publish → Ads → действие формы → **Диагностика**.

В 2026 Google объединяет Enhanced Conversions for web/leads. Этот tag улучшает сопоставление, но не должен создавать второй conversion hit.

## 5. Шаг 3: офлайн-конверсии — главное для B2B

Петля:

1. Google добавляет `gclid`/`gbraid`/`wbraid`.
2. Страница хранит click IDs, UTM и Ads-параметры 90 дней.
3. `gclid`, source, campaign, keyword попадают в Telegram-карточку.
4. Менеджер отмечает qualified → sample requested → contract.
5. Результат загружается в Ads.
6. Smart Bidding учится на покупателях, а не на «интересующихся».

### 5.1. Создать actions

1. Ads → **Цели → Конверсии → + Создать → Conversions offline**.
2. Создайте `Export - Qualified lead`, `Export - Sample requested`, `Export - Contract`.
3. Count: **One**.
4. Value каждого: `⚠️ взять из CRM/управленческого учёта`.
5. Currency: `⚠️ взять валюту аккаунта Ads`.
6. Включите Enhanced Conversions и примите terms.
7. Для первого теста выберите **Skip and set up later**, затем подключите Sheets через Data Manager.

### 5.2. Формат upload

| Google Click ID | Conversion Name | Conversion Time | Conversion Value | Conversion Currency |
|---|---|---|---|---|
| `⚠️ gclid из Telegram` | `⚠️ точное имя action` | `⚠️ фактическое время с поясом` | `⚠️ из учёта` | `⚠️ валюта Ads` |

Формат времени:

```text
yyyy-mm-dd hh:mm:ss+hh:mm
```

Указывайте момент бизнес-события, тот же согласованный часовой пояс и загружайте в пределах 90 дней после рекламного клика.

### 5.3. Ручной тест и регулярный импорт

1. Ads → **Цели → Конверсии → Uploads**.
2. Скачайте свежий template: `⚠️ взять в аккаунте`.
3. Заполните без изменения заголовков.
4. **Preview** → исправьте время, currency, name, `gclid` → **Apply**.
5. На следующий день проверьте диагностику.
6. Для регулярной работы: **Инструменты → Data Manager → Connect product → Google Sheets → Direct connection → Conversions**.
7. Сопоставьте колонки и задайте расписание: `⚠️ выбрать по ритму отдела продаж`.
8. После автоматизации не загружайте те же строки вручную.

Передавайте и `gclid`, и first-party данные, когда они доступны. Для новой автоматизации используйте Data Manager/Data Manager API, а не legacy Ads API upload.

## 6. Шаг 4: кампании по 8 странам

| Страна | Landing URL | Язык страницы | Languages в Ads |
|---|---|---|---|
| Казахстан | `https://pepperoni.tatar/kk/pepperoni` | kk | Kazakh + Russian |
| Узбекистан | `https://pepperoni.tatar/uz/pepperoni` | uz | Uzbek + Russian |
| Азербайджан | `https://pepperoni.tatar/az/pepperoni` | az | Azerbaijani + Russian |
| Армения | `https://pepperoni.tatar/hy/pepperoni` | hy | Armenian + Russian |
| Грузия | `https://pepperoni.tatar/ka/pepperoni` | ka | Georgian + Russian + English |
| Кыргызстан | `https://pepperoni.tatar/ky/pepperoni` | ky | Kyrgyz + Russian |
| Беларусь | `https://pepperoni.tatar/pepperoni` | ru | Russian |
| Таджикистан | `https://pepperoni.tatar/tg/pepperoni` | tg | Tajik + Russian |

Ads language — язык интерфейса/контента пользователя, не только запроса. Поэтому Russian нужен почти во всех экспортных кампаниях. `/en/pepperoni` — английская страница для международного трафика, второй вариант для Грузии и `x-default`.

### Создание

1. **Кампании → + Новая → Лиды → Search**.
2. Goals: форма, phone, WhatsApp; Secondary убрать из campaign-specific goals.
3. Networks: Display выключить; Search Partners сначала выключить для чистой диагностики.
4. Location: одна страна; option: **Presence**.
5. Languages: по таблице.
6. Budget: `⚠️ взять утверждённый бюджет страны`.
7. Bidding: `⚠️ выбрать по фактическому объёму conversion history`; не ставить выдуманный target CPA.
8. Ad groups: wholesale, pizza/HoReCa, halal, private label.
9. Matches: exact и phrase.
10. Добавьте negative list, RSA и assets.

Одна страна = одна кампания: иначе общий бюджет скрывает, какой рынок работает. Performance Max/Demand Gen добавлять только после накопления проверенных Primary и offline conversions.

## 7. Шаг 5: ключи и объявления

Перед добавлением: **Инструменты → Планировщик ключевых слов → Найти новые**, выбрать страну/язык. Частотность и CPC: `⚠️ взять в аккаунте`.

| Рынок | Локальные seed-запросы | Русские seed-запросы |
|---|---|---|
| KZ | `халал пепперони көтерме`, `пиццаға арналған пепперони` | `пепперони оптом казахстан`, `халяль пепперони для пиццы` |
| UZ | `halol pepperoni ulgurji`, `pizza uchun pepperoni` | `пепперони оптом узбекистан`, `халяль пепперони для пиццы` |
| AZ | `halal pepperoni topdan`, `pizza üçün pepperoni` | `пепперони оптом азербайджан`, `халяль пепперони поставщик` |
| AM | `հալալ պեպպերոնի մեծածախ`, `պեպպերոնի պիցցայի համար` | `пепперони оптом армения`, `куриный пепперони поставщик` |
| GE | `ჰალალ პეპერონი საბითუმო`, `პეპერონი პიცისთვის` | `пепперони оптом грузия`, `халяль пепперони horeca` |
| KG | `халал пепперони дүң`, `пицца үчүн пепперони` | `пепперони оптом кыргызстан`, `пепперони для пиццерии` |
| BY | — | `пепперони оптом беларусь`, `куриный пепперони для пиццы`, `халяль колбаса horeca` |
| TJ | `пепперони ҳалол яклухт`, `пепперони барои пицца` | `пепперони оптом таджикистан`, `халяль пепперони поставщик` |

### Минус-слова

**Инструменты → Общая библиотека → Списки минус-слов → +**:

```text
рецепт, рецепты, своими руками, как приготовить, домашняя
купить 1 кг, розница, рядом, доставка еды, пицца доставка
вакансия, вакансии, работа, зарплата, стажировка
бесплатно, скачать, фото, картинка
свинина, свиной, сало, шпик, алкоголь, кошер, кошерный
```

Добавляйте локальные переводы после Search Terms. Halal-критические negatives обязательны. Не минусуйте `колбаса`, `пицца`, `курица`, `halal`, `оптом`, `поставщик`.

### RSA 1 — halal и документы

Заголовки: `Пепперони куриный Halal оптом`; `Halal ДУМ РТ № 614A/2024`; `KD-013 для пиццы и HoReCa`; `HACCP и ISO 22000:2018`; `Документы для экспорта`; `Упаковка 0,5 кг`; `EXW Казань`; `Цена в WhatsApp`.

Описания:

- Куриный варено-копчёный пепперони KD-013. Halal, HACCP, ISO 22000:2018, ТР ТС 021/2011.
- Вакуумная упаковка 0,5 кг. Экспортные документы и связь с производителем через WhatsApp.

### RSA 2 — для пиццы

Заголовки: `Пепперони для пиццерий`; `Слайсы остаются ровными в печи`; `Диаметр 50–55 мм`; `Куриный пепперони Halal`; `Поставка для HoReCa`; `KD-013 от производителя`; `Запросить образец`; `Обсудить в WhatsApp`.

Описания:

- Термостабильный пепперони: слайсы сохраняют плоскую форму в печи. Диаметр 50–55 мм.
- Для пиццерий, дистрибьюторов и HoReCa. Упаковка 0,5 кг, условия EXW Казань.

### RSA 3 — экспорт/private label

Заголовки: `Пепперони на экспорт`; `Срок хранения 360 дней`; `Хранение при –18°C`; `Private Label для партнёров`; `HS Code 1601 00`; `Цена производителя`; `Поставка EXW Казань`; `Экспортный отдел`.

Описания:

- KD-013: куриный halal пепперони, вакуум 0,5 кг. Срок хранения 360 дней при –18°C.
- Экспортная поставка и private label. Запросите документы, цену и условия у производителя.

Локальные RSA переводить профессионально. Не закреплять все headlines. Ad Strength полезен как подсказка, но не равен продажам.

### Assets

**Кампании → Объявления и объекты → Assets → +**:

- sitelinks «Цена», «FAQ», «Private Label» → anchors `⚠️ взять из адресной строки страницы`;
- call asset `+7 987 217-02-02`;
- callouts `Halal`, `0,5 кг`, `360 дней при –18°C`, `Диаметр 50–55 мм`;
- structured snippet — только подтверждённые сертификаты;
- lead form asset — только если он попадает в тот же процесс атрибуции.

Для иностранцев основной канал — WhatsApp `79274297220`. Номер российский: не скрывать это и явно предлагать WhatsApp.

## 8. Шаг 6: аудитории и ремаркетинг

1. GA4 → **Администратор → Связи с продуктами → Google Ads → Связать**.
2. Ads account: `⚠️ взять в аккаунте`.
3. GA4 → **Администратор → Отображение данных → Аудитории → Новая → Специальная**.
4. Условие — event name + parameter; срок участия `⚠️ выбрать по B2B-циклу`.

| Аудитория | Включить | Исключить |
|---|---|---|
| Video watchers | `video_percent >= 50` или `video_complete` | — |
| Price viewers | `section_view`, `section_name=price` | — |
| 90% readers | `scroll_depth`, `percent_scrolled=90` | — |
| Engaged | `engaged_time`, `engagement_seconds>=60` | — |
| Form abandoners | глубокое вовлечение/контакт | `generate_lead` |
| Private label | `section_name=private_label` | — |

Чтобы параметры были доступны: **GA4 → Администратор → Специальные определения** → event-scoped dimensions для `section_name`, `percent_scrolled`, `engagement_seconds`, `video_percent`, `page_country`, `page_lang`.

Не регистрируйте телефон, имя, email, `gclid` или PII как GA4 dimensions.

`ecomm_prodid`, `ecomm_pagetype`, `ecomm_totalvalue` дают товарный контекст для динамического ремаркетинга. Merchant Center не нужен для одного B2B wholesale-оффера. Он имеет смысл при поддерживаемом онлайн-каталоге с ценой, наличием, доставкой и сценарием покупки; сейчас это отвлечение.

## 9. Шаг 7: Google Marketing Platform — триаж

| Инструмент | Решение |
|---|---|
| Google Ads | Обязательно: трафик, bidding, offline goals |
| GTM | Обязательно: единая настройка |
| GA4 | Обязательно: воронка, аудитории, ремаркетинг |
| Search Console | Обязательно: индексирование и hreflang 9 локалей |
| Looker Studio | Полезно: одна страница «страна × лиды × этапы» |
| Merchant Center | Ситуативно: только при реальном e-commerce feed |
| Campaign Manager 360 | Не нужен: enterprise ad serving/атрибуция |
| Display & Video 360 | Не нужен: enterprise programmatic и лишняя инфраструктура |
| Search Ads 360 | Не нужен: крупные multi-engine портфели, не 8 Search-кампаний |
| Google Optimize | Закрыт; использовать Ads Experiments или сторонний A/B tool |

Dashboard: Ads + GA4; фильтр `page_type=export_landing`; строки — страна/кампания; показатели — cost, clicks, lead, phone, WhatsApp, qualified, sample, contract.

## 10. Что мерить и когда решать

| Этап | Метрика | Источник |
|---|---|---|
| Реклама | Search terms, расход, клики | Ads |
| Лид | Cost per lead | Ads Primary |
| Качество | Lead → qualified | Telegram/CRM + offline |
| Интерес | Lead → sample request | Продажи |
| Продажа | Sample → contract | CRM/учёт |
| Экономика | Cost/value per contract | Ads + offline |

1. Не судить страну по одному лиду или нескольким дням.
2. Порог данных/срок: `⚠️ определить по собственному циклу и допустимому CPL`.
3. На тонких данных проверять search terms, показы и форму, а не «окупаемость».
4. Первые недели длинного B2B-цикла показывают лиды, не revenue.
5. Не выключать страну до разметки качества менеджером.
6. Лиды есть, но слабые — менять keys/ads/offline goals, а не только bid.
7. Масштабировать после подтверждения следующего этапа воронки.

## 11. Юридические и политические ограничения

1. Проверяйте локальные правила рекламы, маркировки и импорта еды/мяса: `⚠️ юридическую оценку взять у специалиста/импортёра`.
2. Не обещайте медицинские эффекты, лечение или непроверенные превосходства.
3. Halal claim подтверждать только: **Halal ДУМ РТ № 614A/2024**.
4. Допустимы HACCP, ISO 22000:2018, ТР ТС 021/2011, декларация ЕАЭС N RU D-RU.PA07.V.69731/23.
5. Кошер-сертификата нет; свинина, шпик, сало и алкоголь недопустимы.
6. Проверяйте **Google Ads Policy Manager** перед каждой страной.
7. CMP/banner сейчас нет.
8. Consent Mode оставляет EEA/UK/CH storage/user-data/personalization/analytics в `denied`.
9. Ни одна из 8 стран не EEA, поэтому там измерение полное.
10. EEA/UK/CH исключить из targeting.
11. До рекламы там установить Google Consent Mode-compatible CMP и получить корректное согласие.
12. PII не передавать в GA4, URL и dashboards; только в предназначенный Enhanced Conversions механизм.

## 12. Чек-лист запуска страны

```text
[ ] Отдельная Search-кампания
[ ] География — одна страна; option — Presence
[ ] EEA/UK/CH исключены
[ ] Локальный язык + Russian; для Грузии также English
[ ] URL соответствует стране и языку
[ ] Mobile/desktop страница открывается
[ ] GTM Preview видит события
[ ] GA4 DebugView получает события
[ ] Тестовая форма создаёт один generate_lead
[ ] Лид приходит в Telegram
[ ] В Telegram видны source/campaign/keyword/gclid
[ ] Второй Ads tag на generate_lead НЕ создан
[ ] Phone/WhatsApp — Primary
[ ] Engagement — Secondary
[ ] Enhanced Conversions диагностируются
[ ] На старте только exact/phrase
[ ] Общие и локальные negatives добавлены
[ ] RSA соответствует landing
[ ] Sitelinks/callouts/call/WhatsApp добавлены
[ ] Бюджет утверждён владельцем
[ ] Bid strategy основана на данных аккаунта
[ ] Offline actions qualified/sample/contract созданы
[ ] Менеджер сохраняет gclid и outcome
[ ] Назначен ответственный за Data Manager import
[ ] После запуска проверены spend/search terms/form
```

Сверка claims: KD-013 — «Пепперони варено-копчёный куриный», halal, вакуум 0,5 кг, диаметр 50–55 mm, 360 дней при –18°C, HS 1601 00, barcode 4680638720318, термостабильный. Цена 274 ₽ / 249,09 ₽ без НДС за 0,5 кг, EXW Казань. Reference за 0,5 кг: USD 3.21; KZT 1524.77; UZS 38810.2; KGS 280.53; BYN 9.2; AZN 5.45. Контакты: +7 987 217-02-02, info@kazandelikates.tatar, WhatsApp 79274297220. Перед ценой в объявлении актуальность: `⚠️ подтвердить владельцу`.
