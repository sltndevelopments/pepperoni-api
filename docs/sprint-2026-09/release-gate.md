# Release gate: `sprint/post-p0-verification` → `main`

Ответ на «Pepperoni: проверка перед merge и следующий коммерческий спринт» (09.09.2026).
Дата проверки: 2026-09-11. Ветка: `sprint/post-p0-verification`, 11 коммитов поверх `main`
(`219cd8b85 … 4b6e03cb1`). Каждый факт ниже помечен: **локально** (проверено в рабочей копии
или чистом checkout), **опубликовано** (есть в `origin/<ветка>`), **live** (проверено на
prod-адресах), **ожидает** (данных/людей).

## 0. Коротко

| Условие merge | Статус |
|---|---|
| «Sliced beef pepperoni» исправлено в источнике, не руками на VPS | да — `5544c9833`; источники статические файлы `public/.well-known/ai-plugin.json`, `public/ai.json`, `public/en/about.html` + i18n `/pepperoni` (9 локалей) + `faq.html` (копируется в llms). На VPS не трогалось |
| Тест на машинные описания | `scripts/check_product_claims.py` — 15 машинных поверхностей + 239 индексируемых страниц (title, meta, JSON-LD, текст) → **0 FAIL**; блокирующий шаг `sync-vps.sh` |
| «4 прайса, а проверялось 2» | было неполное покрытие: `check_fact_consistency.py` читал только `.md`; теперь все 4 (`.md` + `.txt`, RU/EN) → 62 SKU, 0 расхождений |
| Чистый checkout | `git clone` ветки в `/tmp`, `npm install`, полный этап генерации `sync-vps.sh` (Sheets → карточки → прайсы → llms → sitemap → гейты) — exit 0, зависимостей от untracked нет |
| nginx на VPS = Git | 2 из 3 сниппетов совпадали; `api-products-local.conf` **откатился** сегодняшним деплоем из `main` — причина найдена и устранена (ниже) |
| lead-intake: что и зачем | раздел 3; найден и исправлен дефект (дедуп был на процесс, а не на сервис) |
| 45 с / Indexing API / Яндекс | раздел 4 — два из трёх **не в проде до merge**, токен Яндекса восстановлен и закреплён в секрете |
| Откат | раздел 5 |
| После деплоя | раздел 6 |

Рекомендация: **merge одним релизом** (без выделения lead-intake) — изменения формы проверены
end-to-end локально, рассчитаны на этот релиз (события считаются по `lead_id`, который выдаёт
сервер) и без них аналитика на странице снова начнёт считать попытки как заявки.

## 1. Товарная правда: что было не так и что теперь проверяется

Найдено по классу, не по одному слову. Источник истины — `products.json` (KD-013 нарезка 0,5 кг,
KD-014 батон 0,8 кг, оба «варено-копченый куриный»; KD-012 из конины снят из каталога раньше,
сырокопчёного и «классики говядина+курица» не было никогда).

| Поверхность | Было | Стало | Файл-источник |
|---|---|---|---|
| `ai-plugin.json` `description_for_model` | «supplying sliced beef pepperoni»; «boiled-smoked classic from beef & chicken, dry-cured, horse meat pepperoni»; «meat preparations (diced beef, beef mince)» | «cooked-smoked chicken pepperoni (sliced and whole sticks)»; категории по каталогу | статический `public/.well-known/ai-plugin.json` |
| `ai.json` | «sliced beef pepperoni» | «cooked-smoked chicken pepperoni» | статический |
| `/en/about` meta + 2 абзаца; список категорий | «sliced beef pepperoni»; «cooked-smoked classic, horse meat, dry-cured» | куриный, нарезка и батон | статический |
| `/about` meta + JSON-LD + список | «пепперони из курицы, говядины, конины»; «вар-коп классика, из конины, сырокопчёный» | варёно-копчёный куриный | статический |
| `/pizzeria` meta + hero, `/dlya-horeca` карточка | «из курицы, говядины, конины»; «куриный и из конины» | куриный, нарезка и батон | статический |
| `/pepperoni` FAQ «Из какого мяса…» — 9 локалей + JSON-LD | «В ассортименте также есть пепперони из говядины и из конины» | «Основа — мясо куриное (KD-013, KD-014). Другое сырьё — укажите в заявке, обсудим под заказ» | `data/pepperoni_landing_i18n*.json` → `gen_pepperoni_landing.py` |
| `/faq` JSON-LD → `llms.txt` (4 файла) | «Гибкая рецептура: пепперони из курицы, говядины или конины» | без перечня сырья, «по брифу заказчика» | `public/faq.html` → `gen-llms-full.py` |
| Главная RU/EN, карточка «Кастомизация» | «Пепперони из курицы, говядины или конины» | «Пепперони под ваше меню» | статический |
| `/blog/what-is-halal-pepperoni` RU+EN | статья целиком про сыровяленую говяжье-баранью пепперони «70–80 % / 20–30 %, созревание 3–4 недели» (выдумано), FAQ JSON-LD с теми же числами, title «из говядины» | переписана: халяль = без свинины, сырьё любое халяльное; наш продукт — состав с этикетки, форматы, хранение, сертификаты; FAQ JSON-LD перегенерирован | статический |
| `/blog/pepperoni-iz-kakogo-myasa` | «говяжья, куриная и индюшиная позиции представлены в каталоге» | реальные KD-013/014 | статический |
| 14 статей блога | 69 «мёртвых» пунктов «Читайте также» без ссылок (заголовки удалённых страниц вида «Говяжья пепперони оптом») | удалены | статический |

Гейт `check_product_claims.py` выводит allowed-мясо из каталога (сегодня `chicken`) и валит
сборку на любой другой привязке мяса/способа вяления к слову «пепперони». Два не-падающих
класса выводятся владельцу:

- **CUSTOM** (1) — `/blog/private-label-kolbasnyh-izdeliy`: «…деликатесы из птицы или говядины»
  в контексте СТМ. Плюс сохранены как есть (внутри СТМ-разделов, требуют слова владельца):
  `pl.items[0]` лендинга `/pepperoni` «Сырьё: курица, говядина, конина или миксы» в 9 локалях,
  и в `ai-plugin.json` — «Private Label … dumplings (pelmeni, vareniki)» и «retail listings in
  EuroSpar, Bahetle, Metro, Miratorg; Aslam for OMPK; Tatneft; SMARTEN». **Вопрос владельцу:**
  можем ли мы реально выпускать пепперони из говядины/конины под СТМ и пельмени; подтверждены
  ли клиенты — если нет, убрать.
- **GENERIC** (6) — фразы о пепперони как классе продукта в `/blog/pepperoni-iz-kakogo-myasa`
  («пепперони производят из говядины, курицы, индейки и конины — в зависимости от
  производителя»). Не ложь, но статья устарела по акценту; в списке 6 обновлений.

Не тронуто (осознанно): `scripts/fix_invented_pepperoni.py` — одноразовый патчер июля с уже
устаревшей «правдой» (KD-012). Не запускать; кандидат на удаление отдельным коммитом.

## 2. Чистый checkout

```
git clone --branch sprint/post-p0-verification https://github.com/sltndevelopments/pepperoni-api.git /tmp/pep-clean
npm install --omit=dev                    # 186 packages
DATA_DIR=/tmp/pep-clean-data bash <этап 1 sync-vps.sh>   # до публикации products.json
→ exit 0
  sync-sheets: 62 SKU, lastSynced 2026-09-11
  fix_pages 260 / 0 repaired · qa_pages 260 / 0 FAIL · index policy OK
  fact consistency: 62 SKU, 4 price lists → 0
  product claims: 239 pages + 15 machine surfaces → 0 FAIL
```

Единственный `[warn]`: `check_stale_counts` (известные «77 SKU» в старых og-картинках — не
блокирует, в бэклоге). Все скрипты и nginx-сниппеты, на которые ссылается `deploy-vps.yml`
и `apply_nginx_*.sh`, есть в дереве (проверено циклом по ссылкам: 14 скриптов, 7 сниппетов).

После прогона в клоне изменено 179 файлов — те же, что «дрейфуют» на VPS каждые 10 минут:
`lastSynced`, курсы валют в `exportPrices`, `add-perf-hints` в карточках, штампы версий
ассетов, `daily_ledger.json`. Это штатная перегенерация, а не зависимость от локальных файлов.

## 3. lead-intake: что меняется и как проверено

**Зачем в этом релизе.** До 09.09 сайт считал `generate_lead` по факту отправки формы
(попытка), а клики по телефону/мессенджеру считались дважды (inline-слушатель + `lead-form.js`).
Чтобы «одна заявка → одно событие», серверу нужно сообщать странице, что заявка *принята*, и
уметь узнавать повтор. Без серверной части клиентские правки бессмысленны, поэтому это один релиз.

**Сервер `infra/scripts/lead_intake_server.py`** (diff `origin/main...HEAD`, +70/−4):

- каждая принятая заявка получает `lead_id` (12 hex), он же уходит в сообщение группе (`🆔`);
- `client_ref` (токен заполнения формы из браузера, ≤64 симв.) — повтор с тем же токеном в
  течение 6 ч отвечает `ok, lead_id (тот же), duplicate: true` и **не отправляется** в группу;
- **исправлено 11.09:** хранилище дедупа было словарём в памяти процесса, а unit запускает
  `gunicorn --workers 2` → повтор, попавший во второй воркер, доставлялся бы дважды. Перенесено
  в sqlite (`LEAD_DEDUP_DB`, по умолчанию `/var/www/pepperoni/data/lead_dedup.sqlite`; unit
  работает от root, каталог доступен; при любой ошибке дедупа — warning и заявка проходит);
- из лога убран телефон (`Lead delivered: lead_id=… page=… exp=…`);
- `TELEGRAM_API_BASE` (env) — только для тестов против mock.

Не менялось: rate-limit 5/10 мин/IP (в памяти процесса → фактически до 10 при 2 воркерах —
известно, достаточно для «очевидного спама»), honeypot `company` (200 без `lead_id` → страница
не считает успех), обязательный `consent`, валидация телефона RU/KZ + 7 экспортных кодов,
обрезка полей (`name` 120, `phone` 32, `message` 1000, `page` 300), CORS только на свои origin.
Honeypot и rate-limit логируют IP — как и раньше.

**Клиент `public/assets/lead-form.js`:** `client_ref` через `crypto.randomUUID()`, событие
`lead_submit_success`/`generate_lead` только при `lead_id` без `duplicate`, и один раз на
`lead_id` в `sessionStorage`; в GA4 `transaction_id = lead_id`; `form_submit` = попытка.
Inline-дубли Metrika-целей убраны из главной и 124 карточек (`95044aaee`).

**Проверка end-to-end (локально, 2 воркера gunicorn + mock Telegram, 2026-09-11):**

```
health                 {"configured":true,"ok":true}
без consent            400 consent_required
телефон 12345          400 invalid_phone
honeypot company=spam  200 {"ok":true}            (без lead_id → событие не считается)
+998 90 123 45 67      200 lead_id
валидная заявка        200 lead_id=8bb01c8b7f42 → доставлена в mock 1 раз
тот же client_ref ×6   2× {duplicate:true, lead_id=8bb01c8b7f42}, 4× 429 → в mock всё ещё 1
имя 500 символов       200 (обрезано до 120)
свежий IP ×7           200 ×6, затем 429
🆔 в каждом сообщении  9/9
телефон/имя в логе     0 вхождений
```

Не проверено live: реальная доставка в группу продаж после деплоя — п. 6.

## 4. Статус трёх прежних заданий

| Задание | В ветке | В проде (`main` на VPS, 11.09 06:40) |
|---|---|---|
| Снять задержку базовой аналитики 45 с | `255f97fce`: gtm/ym грузятся через `requestIdleCallback` (timeout 1,5 с) или по первому взаимодействию — без 45-секундного таймера | **не снята**: `curl https://pepperoni.tatar/` → `setTimeout(loadAnalytics,45000` присутствует |
| Не слать обычные страницы в Google Indexing API | `219cd8b85`: `gsc-index.py` отказывает без флага `--i-have-jobposting-or-broadcastevent-pages`, вызовы убраны из `seo-agent-vps.sh`, `nudge_google_after_seo.sh`, `gsc-index.yml` | **продолжается**: cron из `main` сегодня 05:30 отправил **102 URL** (`data/gsc_submitted.json`: 09-05 32, 09-06 99, 09-09 34, 09-11 102). Прекратится с первым деплоем после merge |
| Интеграция Яндекс Вебмастера | скрипты не менялись | **восстановлена 11.09 и закреплена**: токен, поставленный руками 09.09, был **перезаписан** сегодняшним деплоем (workflow пишет `seo-agent.env` из GitHub Secrets; секрет `YANDEX_WM_TOKEN` датировался 2026-03-11 → API отвечал `INVALID_OAUTH_TOKEN`). Секрет обновлён (`updated_at 2026-09-11T06:33Z`, `gh secret set` PAT-ом агента с VPS), env восстановлен, `GET /v4/user` → 200 `user_id 238539242`. Токен получен от владельца в чате 09.09 — второй присланный токен без scope, не использован |

Вывод: два пункта требуют именно merge; третий закрыт и больше не откатится деплоем.

## 5. Откат

Состояние до релиза сохранено: `main` = `3d8701fe7` (автокоммит SEO-агента 11.09 05:30, на
VPS то же). Откат сайта и скриптов — `git revert -m 1 <merge-commit>` в `main` + push (деплой
сделает `reset --hard`); **не** `reset --hard` руками на VPS.

| Слой | Откат | Проверка |
|---|---|---|
| Страницы/данные | revert merge-коммита → деплой | `curl -s https://pepperoni.tatar/ \| grep -c 45000` вернётся к 1 (признак старой версии) |
| lead-intake | тот же revert; деплой сам делает `systemctl restart pepperoni-lead-intake` и `curl /lead-health`. Если сервис не поднялся: `journalctl -u pepperoni-lead-intake -n 50`; ручной старт старого кода не нужен — revert возвращает файл | `curl -s http://127.0.0.1:5002/lead-health` → `{"ok":true}` |
| nginx | `apply_nginx_*` идемпотентны и кладут бэкапы vhost в `/etc/nginx/disabled-vhosts/*.bak.*`; откат сниппета = `install` предыдущей версии из `git show 3d8701fe7:deploy/nginx/<file>` (для `api-products-local.conf` — версия 2 строк заголовка + `/api/products`) → `nginx -t && systemctl reload nginx` | `curl -sI https://api.pepperoni.tatar/api/products \| grep X-Data-Source` |
| Яндекс-токен | не откатывать; при проблемах — новый токен в секрет `YANDEX_WM_TOKEN`, не в env на VPS | `GET https://api.webmaster.yandex.net/v4/user` → 200 |
| `lead_dedup.sqlite` | удалить файл — сервис создаст заново; потеря = только дедуп за 6 ч | — |

Необратимого в релизе нет: Indexing API не «отзывается», удалений страниц нет. Redirect-карты
(`deploy/nginx/*redirects*.conf`, `51f3763ad`) входят в релиз; откат — тем же revert, деплой
переустановит прежние сниппеты через `apply_nginx_trust_reset.sh`.

## 6. После разрешённого деплоя (кто проверяет: агент, результаты — в этот файл)

1. **Версия**: на VPS `git rev-parse HEAD` == merge-коммит; `ls scripts/apply_nginx_api_products.sh` tracked (`git status --porcelain` пусто для него).
2. **Контент**: `/`, `/en/`, `/sosiski-dlya-hotdog`, `/products/kd-013`, `/en/products/kd-013`, `/blog/what-is-halal-pepperoni`, 4 прайса → 200; `check_fact_consistency.py` на VPS → 0.
3. **Поиск**: `python3 scripts/verify_sitemap_live.py` → 239 URL 200, hreflang 0 расхождений; контрольные 301: `/en` → `/en/`, `/geo/...` (топ-3 из `redirect-review.csv`).
4. **Машинные описания**: `curl -s https://api.pepperoni.tatar/.well-known/ai-plugin.json | grep -c "beef pepperoni"` → **0**; `/llms.txt`, `/openapi.yaml`, `/robots.txt` → 200 `X-Data-Source: vps-local`; `https://api.pepperoni.tatar/about` → 301 (HTML-копии нет).
5. **Измерение**: согласованная тестовая заявка с `/sosiski-dlya-hotdog` (имя «Тест релиза 11.09», телефон владельца) → ответ `lead_id`; **менеджер подтверждает сообщение с 🆔 в группе** — ответ 200 доказательством не считается. Повторная отправка той же формы → `duplicate:true`, второго сообщения нет. В Metrika/GA4 DebugView: один `lead_submit_success`, один `generate_lead` с `transaction_id`; клик по телефону → один `click_phone`.
6. **Наблюдение 48 ч**: `journalctl -u pepperoni-lead-intake` без `delivery_failed`; `data/gsc_submitted.json` без новых записей; дальнейшие массовые изменения — после этого.
7. `bash scripts/nudge_google_after_seo.sh` (sitemap Google + Yandex `--hot` + IndexNow) — вывод сюда.

## 7. Что это не решает (честно)

- Отсутствие бренд-запросов и заявок — не техническая проблема; результат следующего этапа
  измеряется одной работающей категорией (`/sosiski-dlya-hotdog`), обновлёнными профилями и
  подтверждёнными обращениями, а не служебными файлами.
- Открытый API и manifests не заставят ИИ рекомендовать компанию; они лишь перестали врать.

## 8. Журнал фактического выпуска (2026-09-11)

**Отклонение от рекомендованного порядка.** Рекомендация была: сначала техническая ветка, промежуточная
проверка, затем пилот. Фактически по указанию владельца («сделай как должно быть») техническая ветка
(`sprint/post-p0-verification`, 12 коммитов) и пилот (`commercial/sosiski-hotdog`, 2 коммита) были влиты
в `main` **одним** merge-коммитом `8332c31b5` и задеплоены вместе; следом `bb5765212` (EN JSON-LD USD из
`products.json`, 0 расхождений). Промежуточной проверки между техническим релизом и пилотом не было —
вместо неё выполнена пост-фактум проверка одного состояния (ниже). Откат остаётся одним revert
merge-коммита (§5).

**Проверено live после деплоя `bb5765212` (07:10 UTC):**

| Пункт §6 | Результат |
|---|---|
| 1. Версия | VPS `/var/www/pepperoni/repo` HEAD = `bb5765212` = `origin/main` |
| 2. Контент | `/sosiski-dlya-hotdog`, `/en/sosiski-dlya-hotdog` → 200, title/форма/цены на месте |
| 4. Машинные описания | `api.pepperoni.tatar/.well-known/ai-plugin.json`: `X-Data-Source: vps-local`, `beef pepperoni` = 0, `chicken pepperoni` = 1 |
| 7. nudge | GSC sitemap ✅ (оба хоста); Yandex sitemap 429 (месячная квота 10/10 до 2026-09-30); Yandex recrawl 8 hot URL + `/sosiski-dlya-hotdog`, `/en/sosiski-dlya-hotdog` ✅ (осталось 80/150); IndexNow ✅ |
| 5. Тестовая заявка | **не выполнена** — только с разрешения владельца и согласованным с менеджером контактом (§6 п.5). Mock-тест ≠ доставка |
| 3. verify_sitemap_live | ожидает |
| 6. Наблюдение 48 ч | идёт |

**Спорные товары KD-006/KD-007** — информационный карантин с 2026-09-11 (`data/spec_holds.json`,
`scripts/apply_spec_holds.py` в `sync-vps.sh` шаг 1a, блокирующая проверка `--check`). Поле состава
убрано из карточек RU/EN, `products.json`/API, `llms.txt`; вместо него пометка «Спецификация уточняется…».
Позиции исключены из подбора на `/sosiski-dlya-hotdog` (страница: 6 позиций + явная пометка о двух
скрытых); URL карточек сохранены; исходные значения — `data/spec_holds_raw-2026-09-11.json`.
Задание технологу — `technologist-questions.md`, раздел внизу.

**Пред-релизные проверки пилота (локально, mock-intake на :3011, viewport 390×844):**
нет горизонтального скролла (`scrollWidth` 390), сетка 1 колонка, таблица сравнения скроллится внутри
обёртки; выбор 3 SKU → снятие 1 → в сообщении ровно выбранные 2; сервер 500 → «Не удалось отправить.
Позвоните…», кнопка снова активна, `generate_lead` = 0, «Спасибо» не показано; тройной клик по кнопке →
1 POST, 1 `lead_id`, 1 `generate_lead`, `sessionStorage` хранит id. Цены: 290 ₽ / 6 шт = 48,33 ₽/шт
(поле `offers.pricePerPiece`, не из названия), 290 / 0,48 кг = 604 ₽/кг; дата данных 2026-09-06
(`lastSynced`, не дата сборки). Canonical/hreflang без `.html`, `127.0.0.1`/`localhost` в страницах = 0.
