"""Avito product-chat worker backed by pepperoni.tatar catalog and lead group.

The worker intentionally owns only product chats. Recruitment chats remain for
human operators. Leads are persisted before Telegram delivery so a network
failure cannot silently discard a customer's phone number.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)

AVITO_API = "https://api.avito.ru"
TOKEN_URL = f"{AVITO_API}/token"
PHONE_RE = re.compile(r"(?<!\d)(?:\+7|8|7)[\s().-]*\d{3}[\s().-]*\d{3}[\s.-]*\d{2}[\s.-]*\d{2}(?!\d)")
WORD_RE = re.compile(r"[а-яёa-z0-9]{3,}", re.I)

INTRO = (
    "Здравствуйте! Чтобы менеджер связался с вами, пришлите, пожалуйста:\n"
    "1. Город\n"
    "2. Телефон\n"
    "3. Имя"
)
LEAD_THANKS = "Спасибо! Сейчас с вами свяжется менеджер."
LEAD_FAILED = "Не удалось передать заявку менеджеру. Пожалуйста, попробуйте позже."


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, dict) and isinstance(content.get("text"), str):
        return content["text"].strip()
    return ""


def _normalize_phone(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 10:
        return "+7" + digits
    if len(digits) == 11 and digits[0] in {"7", "8"}:
        return "+7" + digits[1:]
    return None


def _phones_from(messages: Iterable[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    found: list[tuple[str, dict[str, Any]]] = []
    for message in messages:
        for raw in PHONE_RE.findall(_message_text(message)):
            phone = _normalize_phone(raw)
            if phone:
                found.append((phone, message))
    return found


def _listing(chat: dict[str, Any]) -> tuple[str, str]:
    value = ((chat.get("context") or {}).get("value") or {})
    if not isinstance(value, dict):
        return "—", ""
    return str(value.get("title") or "—").strip(), str(value.get("url") or "").strip()


def _is_recruitment(chat: dict[str, Any]) -> bool:
    _, url = _listing(chat)
    markers = [x.lower().strip() for x in _env("AVITO_RECRUITMENT_URL_MARKERS", "vakansii").split(",")]
    return any(marker and marker in url.lower() for marker in markers)


class Http:
    def request(
        self,
        url: str,
        *,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> tuple[int, Any]:
        payload = None
        req_headers = dict(headers or {})
        if data is not None:
            payload = json.dumps(data, ensure_ascii=False).encode()
            req_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(url, data=payload, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                return response.status, json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(text)
            except json.JSONDecodeError:
                return exc.code, text

    def form(
        self, url: str, data: dict[str, str], *, timeout: int = 30
    ) -> tuple[int, Any]:
        request = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(data).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                return response.status, json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(text)
            except json.JSONDecodeError:
                return exc.code, text


class AvitoClient:
    def __init__(self) -> None:
        self.client_id = _env("AVITO_CLIENT_ID")
        self.client_secret = _env("AVITO_CLIENT_SECRET")
        if not self.client_id or not self.client_secret:
            raise RuntimeError("AVITO_CLIENT_ID / AVITO_CLIENT_SECRET не заданы")
        self.http = Http()
        self._token = ""
        self._expires_at = 0.0
        self._user_id: int | None = None

    def _headers(self) -> dict[str, str]:
        if not self._token or time.monotonic() >= self._expires_at:
            status, payload = self.http.form(
                TOKEN_URL,
                {
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            if status >= 400 or not isinstance(payload, dict) or not payload.get("access_token"):
                raise RuntimeError(f"Avito token failed: HTTP {status}")
            self._token = str(payload["access_token"])
            self._expires_at = time.monotonic() + max(60, int(payload.get("expires_in", 3600)) - 120)
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{AVITO_API}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        status, payload = self.http.request(url, headers=self._headers(), timeout=60)
        if status >= 400:
            raise RuntimeError(f"Avito GET {path}: HTTP {status}")
        return payload

    def _post(self, path: str, body: dict[str, Any]) -> Any:
        status, payload = self.http.request(
            f"{AVITO_API}{path}",
            method="POST",
            data=body,
            headers=self._headers(),
            timeout=60,
        )
        if status >= 400:
            raise RuntimeError(f"Avito POST {path}: HTTP {status}")
        return payload

    def user_id(self) -> int:
        if self._user_id is None:
            configured = _env("AVITO_USER_ID")
            if configured:
                self._user_id = int(configured)
            else:
                payload = self._get("/core/v1/accounts/self")
                self._user_id = int(payload["id"])
        return self._user_id

    def product_chats(self) -> list[dict[str, Any]]:
        page_size = min(100, max(1, int(_env("AVITO_CHATS_PAGE_SIZE", "100"))))
        max_pages = max(1, min(20, int(_env("AVITO_CHATS_MAX_PAGES", "5"))))
        chats: list[dict[str, Any]] = []
        for page in range(max_pages):
            raw = self._get(
                f"/messenger/v2/accounts/{self.user_id()}/chats",
                {"limit": page_size, "offset": page * page_size},
            )
            batch = raw.get("chats", []) if isinstance(raw, dict) else raw
            if not isinstance(batch, list) or not batch:
                break
            chats.extend(chat for chat in batch if isinstance(chat, dict) and not _is_recruitment(chat))
            if len(batch) < page_size:
                break
        return chats

    def messages(self, chat_id: str, limit: int = 20) -> list[dict[str, Any]]:
        raw = self._get(
            f"/messenger/v3/accounts/{self.user_id()}/chats/{urllib.parse.quote(chat_id, safe='')}/messages/",
            {"limit": min(100, max(1, limit)), "offset": 0},
        )
        messages = raw.get("messages", []) if isinstance(raw, dict) else []
        return [item for item in messages if isinstance(item, dict)]

    def send(self, chat_id: str, text: str) -> None:
        self._post(
            f"/messenger/v1/accounts/{self.user_id()}/chats/{urllib.parse.quote(chat_id, safe='')}/messages",
            {"message": {"text": text}, "type": "text"},
        )


class Store:
    def __init__(self) -> None:
        path = Path(_env("AVITO_WORKER_DB", "/var/www/pepperoni/data/avito-worker.sqlite3"))
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS chats (
              chat_id TEXT PRIMARY KEY,
              last_inbound_id TEXT,
              intro_sent INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS leads (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_message_id TEXT UNIQUE NOT NULL,
              chat_id TEXT NOT NULL,
              phone TEXT NOT NULL,
              payload TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              attempts INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              delivered_at TEXT,
              last_error TEXT
            );
            """
        )
        self.db.commit()

    def chat(self, chat_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,)).fetchone()

    def save_chat(self, chat_id: str, *, last_inbound_id: str, intro_sent: bool) -> None:
        self.db.execute(
            """
            INSERT INTO chats(chat_id, last_inbound_id, intro_sent, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
              last_inbound_id=excluded.last_inbound_id,
              intro_sent=excluded.intro_sent,
              updated_at=excluded.updated_at
            """,
            (chat_id, last_inbound_id, int(intro_sent), _utc_now()),
        )
        self.db.commit()

    def create_lead(self, *, source_message_id: str, chat_id: str, phone: str, payload: str) -> None:
        self.db.execute(
            """
            INSERT OR IGNORE INTO leads(source_message_id, chat_id, phone, payload, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source_message_id, chat_id, phone, payload, _utc_now()),
        )
        self.db.commit()

    def pending_leads(self) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM leads WHERE status = 'pending' ORDER BY id LIMIT 30"
        ).fetchall()

    def delivered(self, lead_id: int) -> None:
        self.db.execute(
            "UPDATE leads SET status='delivered', attempts=attempts+1, delivered_at=?, last_error=NULL WHERE id=?",
            (_utc_now(), lead_id),
        )
        self.db.commit()

    def failed(self, lead_id: int, error: str) -> None:
        self.db.execute(
            "UPDATE leads SET attempts=attempts+1, last_error=? WHERE id=?",
            (error[:500], lead_id),
        )
        self.db.commit()


class Catalog:
    def __init__(self) -> None:
        self.url = _env("AVITO_CATALOG_URL", "https://api.pepperoni.tatar/api/products")
        self.cache_seconds = max(60, int(_env("AVITO_CATALOG_CACHE_SECONDS", "600")))
        self._expires = 0.0
        self._products: list[dict[str, Any]] = []

    def products(self) -> list[dict[str, Any]]:
        if self._products and time.monotonic() < self._expires:
            return self._products
        status, payload = Http().request(self.url, timeout=20)
        if status >= 400 or not isinstance(payload, dict):
            LOG.warning("catalog unavailable: HTTP %s; using cached copy", status)
            return self._products
        products = payload.get("products")
        if isinstance(products, list):
            self._products = [product for product in products if isinstance(product, dict)]
            self._expires = time.monotonic() + self.cache_seconds
        return self._products

    def relevant_context(self, *texts: str) -> str:
        terms = set(WORD_RE.findall(" ".join(texts).lower()))
        scored: list[tuple[float, dict[str, Any]]] = []
        for product in self.products():
            name = str(product.get("name") or "")
            words = set(WORD_RE.findall(name.lower()))
            overlap = len(terms & words)
            fuzzy = max((SequenceMatcher(None, term, word).ratio() for term in terms for word in words), default=0)
            score = overlap * 2 + fuzzy
            if score >= 1.2:
                scored.append((score, product))
        lines = []
        for _, product in sorted(scored, key=lambda row: row[0], reverse=True)[:4]:
            offers = product.get("offers") or {}
            lines.append(
                " | ".join(
                    part
                    for part in (
                        f"Товар: {product.get('name')}",
                        f"SKU: {product.get('sku')}",
                        f"Цена: {offers.get('price')} {offers.get('priceCurrency')}" if offers.get("price") else "",
                        f"Мин. заказ: {product.get('minOrder')}" if product.get("minOrder") else "",
                        f"Наличие: {offers.get('availability')}" if offers.get("availability") else "",
                    )
                    if part
                )
            )
        return "\n".join(lines) or "Подходящий товар в каталоге не найден."


class Llm:
    def __init__(self) -> None:
        openai_key = _env("OPENAI_API_KEY")
        explicit_key = _env("LLM_API_KEY")
        if explicit_key:
            self.key = explicit_key
            self.base = _env("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            self.model = _env("LLM_MODEL", "gpt-4.1-mini")
        elif openai_key:
            self.key = openai_key
            self.base = "https://api.openai.com/v1"
            self.model = "gpt-4.1-mini"
        else:
            self.key = _env("DEEPSEEK_API_KEY")
            self.base = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
            self.model = _env("DEEPSEEK_MODEL", "deepseek-v4-flash")

    def reply(self, history: list[dict[str, str]], catalog_context: str) -> str:
        if not self.key:
            raise RuntimeError("LLM_API_KEY / DEEPSEEK_API_KEY не задан")
        system = """Ты консультант «Казанских Деликатесов» в чате Авито.
Отвечай по-русски, кратко и доброжелательно. Факты о товарах бери только из
контекста каталога ниже; если факта нет, честно скажи, что менеджер уточнит.
Не обещай наличие, доставку, звонок или передачу заявки. Не говори, что передал
контакт менеджеру — это делает только система после успешной доставки лида.
Когда покупатель хочет заказать или получить предложение, попроси город,
телефон и имя. Не используй Markdown или HTML.

Каталог:
""" + catalog_context
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *history[-16:]],
            "temperature": 0.3,
            "max_tokens": 350,
        }
        if "deepseek" in self.base or "deepseek" in self.model:
            body["thinking"] = {"type": "disabled"}
        status, payload = Http().request(
            f"{self.base}/chat/completions",
            method="POST",
            data=body,
            headers={"Authorization": f"Bearer {self.key}"},
            timeout=60,
        )
        if status >= 400 or not isinstance(payload, dict):
            raise RuntimeError(f"LLM HTTP {status}")
        choices = payload.get("choices") or []
        message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
        result = message.get("content") if isinstance(message, dict) else ""
        if not isinstance(result, str) or not result.strip():
            raise RuntimeError("LLM returned empty response")
        return result.strip()[:4000]


class Telegram:
    def __init__(self) -> None:
        self.token = _env("LEADS_BOT_TOKEN")
        self.group_id = _env("LEADS_GROUP_ID")
        if not self.token or not self.group_id:
            raise RuntimeError("LEADS_BOT_TOKEN / LEADS_GROUP_ID не заданы")

    def send(self, text: str) -> None:
        status, payload = Http().request(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            method="POST",
            data={"chat_id": self.group_id, "text": text[:4000], "disable_web_page_preview": True},
            timeout=30,
        )
        if status >= 400 or not isinstance(payload, dict) or not payload.get("ok"):
            raise RuntimeError(f"Telegram sendMessage failed: HTTP {status}")


def _buyer_name(chat: dict[str, Any], seller_id: int) -> str:
    for user in chat.get("users") or []:
        if isinstance(user, dict) and user.get("id") != seller_id:
            name = str(user.get("name") or "").strip()
            if name:
                return name
    return "—"


def _history(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for message in sorted(messages, key=lambda item: int(item.get("created") or 0)):
        text = _message_text(message)
        if not text or message.get("type") == "system":
            continue
        out.append(
            {
                "role": "user" if str(message.get("direction")).lower() == "in" else "assistant",
                "content": text,
            }
        )
    return out


def _lead_body(
    *,
    chat: dict[str, Any],
    seller_id: int,
    phone: str,
    inbound: list[dict[str, Any]],
) -> str:
    title, url = _listing(chat)
    summary = "\n".join(_message_text(message) for message in inbound if _message_text(message))[-1200:]
    lines = [
        "🟣 Лид Авито",
        f"Телефон: {phone}",
        f"Имя в профиле Авито: {_buyer_name(chat, seller_id)}",
        f"Объявление: {title}",
        f"Чат Авито: {chat.get('id')}",
    ]
    if url:
        lines.append(f"Ссылка: {url}")
    if summary:
        lines.extend(["", f"Переписка клиента:\n{summary}"])
    return "\n".join(lines)


@dataclass
class Worker:
    avito: AvitoClient
    store: Store
    catalog: Catalog
    llm: Llm
    telegram: Telegram

    def _deliver_pending(self) -> None:
        for lead in self.store.pending_leads():
            try:
                self.telegram.send(str(lead["payload"]))
                self.store.delivered(int(lead["id"]))
                LOG.info("avito lead delivered chat=%s lead_id=%s", lead["chat_id"], lead["id"])
            except Exception as exc:
                self.store.failed(int(lead["id"]), str(exc))
                LOG.warning("avito lead delivery pending chat=%s: %s", lead["chat_id"], exc)

    def _process_chat(self, chat: dict[str, Any]) -> None:
        chat_id = str(chat["id"])
        last = chat.get("last_message") or {}
        if str(last.get("direction") or "").lower() != "in":
            return
        messages = self.avito.messages(chat_id)
        inbound = [
            message
            for message in messages
            if str(message.get("direction") or "").lower() == "in" and _message_text(message)
        ]
        if not inbound:
            return
        inbound.sort(key=lambda item: int(item.get("created") or 0))
        latest = inbound[-1]
        latest_id = str(latest.get("id") or "")
        state = self.store.chat(chat_id)
        if state and state["last_inbound_id"] == latest_id:
            return

        # Process only the customer messages that appeared after the last handled
        # inbound. This preserves a phone + city/name burst, while preventing an
        # old phone from becoming a duplicate lead on every later message.
        new_inbound = inbound
        if state and state["last_inbound_id"]:
            previous_id = str(state["last_inbound_id"])
            for index, message in enumerate(inbound):
                if str(message.get("id") or "") == previous_id:
                    new_inbound = inbound[index + 1 :]
                    break
            else:
                # History window rolled over. The newest inbound is safe; do not
                # reprocess older data whose delivery status is unknown here.
                new_inbound = [latest]
        if not new_inbound:
            return

        phones = _phones_from(new_inbound)
        if phones:
            phone, source = phones[-1]
            source_id = str(source.get("id") or latest_id)
            payload = _lead_body(
                chat=chat,
                seller_id=self.avito.user_id(),
                phone=phone,
                inbound=new_inbound,
            )
            self.store.create_lead(
                source_message_id=source_id,
                chat_id=chat_id,
                phone=phone,
                payload=payload,
            )
            self._deliver_pending()
            delivered = self.store.db.execute(
                "SELECT status FROM leads WHERE source_message_id=?", (source_id,)
            ).fetchone()
            if delivered and delivered["status"] == "delivered":
                self.avito.send(chat_id, LEAD_THANKS)
            self.store.save_chat(chat_id, last_inbound_id=latest_id, intro_sent=True)
            return

        intro_sent = bool(state and state["intro_sent"])
        if not intro_sent:
            self.avito.send(chat_id, INTRO)
            self.store.save_chat(chat_id, last_inbound_id=latest_id, intro_sent=True)
            LOG.info("avito intro sent chat=%s", chat_id)
            return

        conversation = _history(messages)
        title, _ = _listing(chat)
        reply = self.llm.reply(conversation, self.catalog.relevant_context(title, _message_text(latest)))
        self.avito.send(chat_id, reply)
        self.store.save_chat(chat_id, last_inbound_id=latest_id, intro_sent=True)
        LOG.info("avito LLM reply sent chat=%s", chat_id)

    def tick(self) -> None:
        self._deliver_pending()
        chats = self.avito.product_chats()
        for chat in chats:
            try:
                self._process_chat(chat)
            except Exception:
                LOG.exception("avito chat processing failed chat=%s", chat.get("id"))


def main() -> int:
    logging.basicConfig(
        level=_env("AVITO_WORKER_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    worker = Worker(AvitoClient(), Store(), Catalog(), Llm(), Telegram())
    interval = max(5.0, float(_env("AVITO_POLL_INTERVAL", "10")))
    LOG.info("avito worker started interval=%ss", interval)
    while True:
        started = time.monotonic()
        try:
            worker.tick()
        except Exception:
            LOG.exception("avito worker tick failed")
        time.sleep(max(0.0, interval - (time.monotonic() - started)))


if __name__ == "__main__":
    raise SystemExit(main())
