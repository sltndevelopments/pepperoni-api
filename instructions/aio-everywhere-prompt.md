# Промпт агенту: видимость «Казанских Деликатесов» во всех ИИ

Вставь этот блок целиком в новый чат агента (Cursor / Claude Code). Не ослаблять гейты. Не выдумывать сертификаты, отзывы, клиенты, GTIN.

---

Ты агент-исполнитель репозитория **pepperoni-api** (бренд ООО «Казанские Деликатесы» / Kazan Delicacies).

## Миссия

Сделать так, чтобы покупательский вопрос про халяль-пепперони / сосиски / паттисы / СТМ / казылык / татарскую выпечку / экспорт **называл нас** — во всех перечисленных ИИ, двумя слоями:

1. **Live search** (ассистент ищет веб сейчас) — цитирует `pepperoni.tatar` / `kazandelikates.tatar`.
2. **Knowledge / веса** (без поиска) — знает сущность: юрлицо, Казань, халяль ДУМ РТ, телефон, домены. Не путает с чужим `kazandelikates.ru`.

Владелец сказал явно: **надо быть везде**. Это north star, не «можно потом».

Канон сущности (единственный):
- Юрлицо: ООО «Казанские Деликатесы» / Kazan Delicacies LLC
- Каталог: https://pepperoni.tatar
- Money hub пепперони: https://pepperoni.tatar/pepperoni
- Корп. сайт: https://kazandelikates.tatar
- Тел. +7 987 217-02-02 · info@kazandelikates.tatar
- Адрес: Казань, ул. Аграрная, 2, оф. 7
- Халяль ДУМ РТ #614A/2024, HACCP, ISO 22000:2018, ТР ТС 021/2011
- Никакой свинины. Не сокращать бренд до «KD» в клиентском тексте.
- Источник бренда: `public/brand.txt` + `scripts/brand_system.py::brand_block()`.

Готово = строки в `origin/main` + живой URL / API-ответ / скрин замера, не проза.

## Факт на 2026-08-16/17 (не перепроверять «на глаз» — это уже замерено)

Панель: 12 buyer-intent вопросов (RU + AR + KK + EN). Зачёт = в ответе есть pepperoni.tatar / казанские деликатес / kazandelikates / kazan delicac / пепперони татар / телефон.

| Слой | Результат | Смысл |
|---|---|---|
| Perplexity Sonar (живой веб) | **10/12 (83%)** | Нас находят. Проигрыш: общий «мясо в Залив» (Черкизово/Мираторг) и KK-пепперони (местная Халал Даму). |
| ChatGPT **с поиском** (`gpt-5.6` + Responses `web_search`) | **10/12 (83%)** | Ссылки на pepperoni.tatar / kazandelikates.tatar (`utm_source=openai`). Проигрыш: общий Залив; EN «pepperoni export UAE/KSA» ушёл в Nabil/Amana/SFDA. Арабский близнец того же интента нас взял. |
| Gemini 3.7 Flash **без поиска** | **1/12 (8%)** | Только «деликатесы в Казани», сущность кривая: «ТД / МПК Казанский», сайт **kazandelikates.ru**, без pepperoni.tatar. |
| Claude Sonnet **без поиска** (июнь 2026) | **0%** | Нет в весах. Свежий прогон 16.08 сорвался: Asocks `ruleset` на api.anthropic.com. |
| ChatGPT **без поиска** | не мерили | Ключа нет в `seo-agent.env` / GitHub Secrets; ключ есть в `/opt/kazandel-ai-operator/.env` на VPS. Нужен отдельный прогон Completions **без** `web_search`. |
| Grok, DeepSeek, Kimi, Mistral, Copilot, GLM | **не мерили** | Добавить в панель. |

Вывод, который нельзя потерять: **с поиском мы уже ответ по профильным запросам; в памяти моделей нас почти нет.** Меры должны закрывать оба слоя, не только «ещё лендингов».

Инфра замера:
- Код: `scripts/aio_visibility.py`, леджер `data/aio_visibility.json` (устарел: только 8 и 15 июня).
- GHA: `.github/workflows/aio-visibility.yml` (пн 07:30 UTC). В VPS cron скрипта нет.
- `GEMINI_API_KEY` уже в GitHub Secret + VPS `seo-agent.env`. Gemini с RU VPS: Google `User location is not supported`; Asocks режет `generativelanguage.googleapis.com`. Недельный прогон — **из GHA (США)**, не с Selectel.
- `OPENAI_API_KEY` не прокинут в GHA/seo-agent. Для ChatGPT-search использовали ключ оператора на VPS, гоняли с Mac.
- Незакоммичено локально (на момент промпта): правки `aio_visibility.py` (gemini-3.7-flash, thinking low, proxy chain), `deploy-vps.yml` / `aio-visibility.yml` (прокидка GEMINI). Сначала commit+push этого, иначе GHA останется на старом зонде.

Уже в проде для ИИ-ingest (не путать с «нас знают»):
- https://pepperoni.tatar/llms.txt + `/llms-full.txt` + `/en/llms.txt`
- https://pepperoni.tatar/products-feed.xml (GMC)
- https://pepperoni.tatar/openai-commerce-kazan-delicacies.tsv.gz — **SFTP в OpenAI не живой** (`openai-commerce.env` MISSING)
- MCP: https://api.pepperoni.tatar/api/mcp
- UCP: https://pepperoni.tatar/.well-known/ucp (discovery, без checkout)
- Чеклист заявок: `data/aio-onboarding.md`

## Целевые системы (что делать в каждой)

Различай **поиск** (индекс/grounding) и **память** (дообучение/цитируемые источники). Память не купить лендингом за ночь.

### 1. ChatGPT с поиском
Цель: держать ≥80% панели; закрыть 2 дыры.
- EN export UAE/KSA: усилить канон `/en/pepperoni` + `/en/export` фактами, которые SFDA-стиль запрос может сматчить **без лжи** (не писать, что мы в списке SFDA, если нас там нет). Честно: производитель в Казани, EXW, халяль ДУМ РТ, экспортный хаб. Эскалация владельцу, если нужен claim «одобрен для КСА».
- Общий «мясо в Залив»: либо отдельная страница «что мы экспортируем / чего нет», либо принять, что туши ≠ пепперони. Не притворяться Черкизово.
- Владелец: заявка https://chatgpt.com/merchants + SFTP credentials → `openai-commerce.env` (шаблон `deploy/openai-commerce.env.example`). Агент не выдумывает SFTP.
- Замер: Responses API `tools: [{type: web_search}]`, `tool_choice: web_search`, модель актуальная (сейчас gpt-5.6).

### 2. ChatGPT без поиска
Цель: хоть 1–2 попадания по «Казань + халяль + пепперони» в весах — долгий горизонт.
- Прогнать ту же панель Completions **без** tools; записать в леджер отдельно (`chatgpt_search_score` vs `chatgpt_memory_score`).
- Память кормится повторяемыми внешними источниками: Wikidata, новости, каталоги, YouTube (`data/youtube-aio/`), Wikipedia — **не** править Википедию от имени компании скрыто; владельцу — черновик статьи/карточки, он публикует.
- Исправить ложную сущность: везде канон `.tatar`, не `.ru`. Найти и 301/disavow путаницу `kazandelikates.ru`, если это наше старьё; если чужое — не атаковать, а доминировать правильными URL.

### 3. Claude (Anthropic)
Цель: memory-слой >0; search-слой когда у пользователя есть web.
- Мы генерим контент через Claude, но **он сам себя в веса не записывает**. Нужны внешние цитаты.
- Починить замер: GHA + `ANTHROPIC_PROXY` (сейчас primary Asocks `ruleset` на api.anthropic.com). Не считать 0% при пустом ответе из-за прокси.
- Не возвращать DeepSeek на карточки товаров (уже сжигали халяль-галлюцинациями).

### 4. Perplexity
Цель: не потерять 80%+; добить KK и не врать про Залив.
- Живой поиск нас любит — это рабочий канал.
- Владелец: Typeform Merchants https://perplexity.typeform.com/to/oIcfT8U3 (см. `data/aio-onboarding.md`). Блокер: GTIN ~23%, нет US ship. Не выдумывать штрихкоды.
- Страница/кластер под казахский запрос (уже есть `/en/export/kazakhstan` и `/kk/pepperoni`) — проверить, что они в индексе и в `llms.txt`.

### 5. Grok (xAI / SpaceXAI)
Цель: измерить, затем цитируемость.
- Добавить слой в `aio_visibility.py` (`XAI_API_KEY` / grok-4.6), два режима если API даёт search.
- Индексация: сайт должен быть в обычном вебе; Grok тянет X + веб. Имеет смысл аккуратный X/Twitter-аккаунт бренда с каноном URL — только если владелец подтвердит. Не плодить фейковые аккаунты.
- `llms.txt` + `/pepperoni` как канон.

### 6. Gemini (Google)
Цель: search ≈ Perplexity; memory — починить сущность.
- Замер knowledge: `GEMINI_MODEL=gemini-3.7-flash`, thinkingLevel low (уже в локальном коде).
- Второй замер: **Search grounding** (Google Search tool в generateContent) — это «Gemini с поиском». Сделать отдельно, не смешивать скоры.
- Memory: Google KG / Business Profile / Merchant Center 513449343 уже есть. Проверить, что Knowledge Panel / NAP совпадают с каноном. Wikidata sameAs на pepperoni.tatar.
- Не гонять Gemini с RU VPS.

### 7. DeepSeek
Цель: измерить (chat + reasoner/v4-flash). Не использовать как writer карточек.
- Слой в зонде через `DEEPSEEK_API_KEY` (уже в secrets), модель `deepseek-v4-flash` / pro. Есть Anthropic-совместимый endpoint.
- Китайские + глобальные веса: нужны EN/ZH факты на сайте без выдуманных region-claim. Канон `/en/pepperoni`.
- Peak/off-peak цены с 2026-08-16 — для bulk замера не критично.

### 8. Kimi (Moonshot)
Цель: измерить API Moonshot; цитируемость EN/ZH/RU.
- Ключ запросить у владельца, если нет. Панель + `/en` + llms.txt.
- Китайский индекс ≠ Google. Проверить, что сайт открывается без Cloudflare proxy (уже DNS-only, это плюс).

### 9. Mistral (Le Chat)
Цель: измерить; Европа/EN.
- La Plateforme API. Слой в зонде.
- Акцент EN money hub + экспортные факты. Copilot-подобная цитируемость из веба, если Le Chat ищет.

### 10. Copilot (Microsoft / Bing)
Цель: попасть в ответы Bing Copilot по RU/EN запросам.
- Это **индекс Bing**, не OpenAI-память. IndexNow ключ уже в env. Проверить IndexNow + Bing Webmaster: канон `/pepperoni`, sitemap, 200, не noindex.
- Замер: либо Bing API, либо ручной протокол (владелец) + агент фиксирует URL выдачи. Не подделывать.

### 11. GLM (Zhipu)
Цель: измерить bigmodel.cn API; CN/EN.
- Ключ у владельца. Не генерить ими карточки. Только зонд + EN/ZH канон на сайте.

## Порядок работ (агент, без ожидания «идеального плана»)

P0 — замерный контур (иначе слепые «меры»):
1. Закоммитить и запушить текущие правки AIO (Gemini 3.7 + секреты в workflow). Не коммитить ключи.
2. Расширить `aio_visibility.py`: отдельные поля `*_search` / `*_memory` для ChatGPT, Gemini, Claude; плюс слоты grok/deepseek/kimi/mistral/glm/copilot (skip если нет ключа). Леджер не смешивать со старыми 0% при fail прокси.
3. Прогнать панель: ChatGPT memory, Claude memory (через рабочий прокси/GHA), DeepSeek, остальное по ключам. Отчёт таблицей.
4. Вернуть weekly GHA живым: GEMINI + OPENAI (search+memory) + PPLX + Anthropic. `OPENAI_API_KEY` в GitHub Secrets — эскалация владельцу, ключ оператора в git не копировать.

P1 — live-search дыры (контент + индекс, гейт `fix_pages.py` → `qa_pages.py`):
5. EN export UAE/KSA: канонический ответ на `/en/pepperoni` и связанном export URL — кто мы, EXW Kazan, халяль какой сертификат, чего нет (SFDA — только если правда).
6. KK/KZ: живые URL из llms.txt реально отвечают на казахский интент.
7. Bing/IndexNow проверка для Copilot.
8. После SEO-правок money-URL: `python3 scripts/gen-llms-full.py` затем `bash scripts/nudge_google_after_seo.sh`.

P2 — память моделей (медленно, эскалация владельцу на публичные реестры):
9. Черновик Wikidata item + sameAs pepperoni.tatar / kazandelikates.tatar / телефон / адрес. Публикацию — владелец.
10. Инвентаризация `kazandelikates.ru` vs `.tatar`.
11. YouTube AIO (`data/youtube-aio/`) — что уже залито, что нет; не плодить фейковые просмотры.
12. Заявки Merchants: OpenAI + Perplexity — чеклист владельцу, не нажимать формы за него, если нет явного «отправь».

## Запрещено

- Ослаблять `page_reviewer.py`, `data/invariants.json`, `deploy_check.py`.
- Генерить карточки DeepSeek/Kimi/GLM «потому что дешево».
- Выдумывать SFDA/ESMA/одобрение Саудовской/ОАЭ, клиентские кейсы, рейтинги.
- Свинина, шпик, «бекон» не говяжий/куриный халяль.
- `reset --hard` на VPS руками; rsync как канал кода.
- Коммитить API-ключи. Gemini-ключ уже светился в чате — не печатать; ротация на усмотрение владельца.

## Формат отчёта

Таблица: система × search × memory × что сделано × blocker (ключ / владелец / гейт). Хеш коммита + grep/тест. По SEO — вывод nudge.

Читай: `CLAUDE.md`, `AGENTS.md`, `data/aio-onboarding.md`, `public/llms.txt`, `.cursor/rules/pepperoni-brand.mdc`.
