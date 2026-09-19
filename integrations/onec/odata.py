"""OData client for the 1C:Enterprise UNF database.

The 1C HTTP service lives on the office LAN (``http://192.168.11.40/unf``), so
every request deliberately bypasses the outbound HTTP proxy. The proxy has no
route into 192.168.11.0/24 and would turn a working call into a silent timeout,
which is exactly the failure this module is built to avoid.

Auth is preemptive HTTP Basic: 1C answers a challenge-less request with 401 and
``WWW-Authenticate: Basic realm="1C:Enterprise 8.5"``, so waiting for the
challenge only doubles every round trip.

Entity names are Cyrillic (``Catalog_Контрагенты``) and must be percent-encoded
in the path. Query values are encoded with ``%20`` rather than ``+`` because 1C
does not decode ``+`` as a space inside ``$filter``.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from datetime import datetime
from typing import Any

LOG = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://192.168.11.40/unf/odata/standard.odata/"
DEFAULT_PAGE_SIZE = 500
DEFAULT_TIMEOUT = 60

# Transient conditions worth a retry. 401/403 are not here on purpose: bad
# credentials must fail on the first call instead of hammering 1C.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
BACKOFF_BASE = 2.0

# Entity sets used by the sales reports. These names are the ones handed over
# with the task and have NOT been verified against a live ``$metadata`` yet —
# confirm them with ``python -m integrations.onec.odata --check`` from a host
# with the VPN up before relying on them, and correct here if 1C disagrees.
ENTITY_COUNTERPARTIES = "Catalog_Контрагенты"
ENTITY_SALES = "AccumulationRegister_Продажи_RecordType"
ENTITY_CUSTOMER_ORDERS = "Document_ЗаказПокупателя"
ENTITY_ORDER_FULFILMENT = "AccumulationRegister_ЗаказыПокупателей_RecordType"

RECORD_TYPE_RECEIPT = "Receipt"
RECORD_TYPE_EXPENSE = "Expense"


class ODataError(RuntimeError):
    """A 1C OData call failed. Carries the HTTP status and the raw body."""

    def __init__(self, message: str, *, status: int = 0, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def odata_datetime(value: datetime | str) -> str:
    """Render a datetime as an OData v3 literal: ``datetime'2026-07-01T00:00:00'``."""
    if isinstance(value, str):
        stamp = value
    else:
        stamp = value.replace(microsecond=0, tzinfo=None).isoformat()
    return f"datetime'{stamp}'"


def _encode_segment(entity: str) -> str:
    """Percent-encode one path segment, keeping OData key predicates readable."""
    return urllib.parse.quote(entity, safe="()',")


def _encode_query(params: dict[str, Any]) -> str:
    clean = {k: str(v) for k, v in params.items() if v is not None and v != ""}
    return urllib.parse.urlencode(clean, quote_via=urllib.parse.quote, safe="")


class HttpTransport:
    """Minimal urllib transport that never routes through the ambient proxy."""

    def __init__(self, *, trust_env_proxy: bool = False) -> None:
        handlers: list[urllib.request.BaseHandler] = []
        if not trust_env_proxy:
            handlers.append(urllib.request.ProxyHandler({}))
        self._opener = urllib.request.build_opener(*handlers)

    def request(
        self, url: str, *, headers: dict[str, str], timeout: int
    ) -> tuple[int, bytes]:
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with self._opener.open(req, timeout=timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()


class ODataClient:
    """Read-only client for the 1C UNF OData endpoint."""

    def __init__(
        self,
        base_url: str = "",
        user: str = "",
        password: str = "",
        *,
        transport: Any | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        page_size: int = DEFAULT_PAGE_SIZE,
        sleep: Any = time.sleep,
    ) -> None:
        self.base_url = (base_url or _env("ODATA_URL") or DEFAULT_BASE_URL).rstrip("/") + "/"
        self.user = user or _env("ODATA_USER")
        self.password = password or _env("ODATA_PASSWORD")
        if not self.user or not self.password:
            raise RuntimeError("ODATA_USER / ODATA_PASSWORD не заданы")
        self.timeout = timeout
        self.page_size = page_size
        self._transport = transport or HttpTransport()
        self._sleep = sleep

    def _headers(self) -> dict[str, str]:
        token = base64.b64encode(f"{self.user}:{self.password}".encode()).decode("ascii")
        return {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
        }

    def _url(self, entity: str, params: dict[str, Any] | None = None) -> str:
        url = self.base_url + _encode_segment(entity)
        query = _encode_query(params or {})
        return f"{url}?{query}" if query else url

    def _fetch(self, url: str) -> bytes:
        last_error = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                status, body = self._transport.request(
                    url, headers=self._headers(), timeout=self.timeout
                )
            except urllib.error.URLError as exc:
                # No route / refused / timed out — the classic symptom of the
                # VPN being down. Worth one more try, then give up loudly.
                last_error = f"сеть недоступна: {exc.reason}"
                if attempt == MAX_ATTEMPTS:
                    raise ODataError(f"1C OData {url}: {last_error}") from exc
                self._sleep(BACKOFF_BASE ** attempt)
                continue

            if status < 400:
                return body

            text = body.decode("utf-8", errors="replace")
            if status in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                LOG.warning("1C OData %s: HTTP %s, повтор %s", url, status, attempt)
                self._sleep(BACKOFF_BASE ** attempt)
                continue
            raise ODataError(f"1C OData {url}: HTTP {status}", status=status, body=text)

        raise ODataError(f"1C OData {url}: {last_error}")

    def metadata(self) -> str:
        """Fetch raw ``$metadata`` XML. The cheapest proof the link is alive."""
        return self._fetch(self.base_url + "$metadata").decode("utf-8", errors="replace")

    def get(
        self,
        entity: str,
        *,
        filter: str = "",
        select: str = "",
        orderby: str = "",
        expand: str = "",
        top: int | None = None,
        skip: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch one page of an entity set."""
        params: dict[str, Any] = {"$format": "json"}
        if filter:
            params["$filter"] = filter
        if select:
            params["$select"] = select
        if orderby:
            params["$orderby"] = orderby
        if expand:
            params["$expand"] = expand
        if top is not None:
            params["$top"] = top
        if skip:
            params["$skip"] = skip

        body = self._fetch(self._url(entity, params))
        if not body:
            return []
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ODataError(
                f"1C OData {entity}: ответ не JSON",
                body=body.decode("utf-8", errors="replace")[:500],
            ) from exc
        value = payload.get("value") if isinstance(payload, dict) else None
        if value is None:
            raise ODataError(f"1C OData {entity}: в ответе нет поля value")
        return list(value)

    def iter_all(
        self,
        entity: str,
        *,
        filter: str = "",
        select: str = "",
        orderby: str = "",
        limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Page through an entity set with ``$top``/``$skip``.

        Registers return thousands of rows, so callers stream instead of
        materialising everything. ``orderby`` is worth passing: without a stable
        sort, paging over a changing table can repeat or skip rows.
        """
        skip = 0
        seen = 0
        while True:
            page_size = self.page_size
            if limit is not None:
                page_size = min(page_size, limit - seen)
                if page_size <= 0:
                    return
            rows = self.get(
                entity,
                filter=filter,
                select=select,
                orderby=orderby,
                top=page_size,
                skip=skip,
            )
            if not rows:
                return
            for row in rows:
                yield row
                seen += 1
                if limit is not None and seen >= limit:
                    return
            if len(rows) < page_size:
                return
            skip += len(rows)

    # --- Domain helpers -------------------------------------------------

    def counterparties(self, *, limit: int | None = None) -> Iterator[dict[str, Any]]:
        """Active (non-folder) counterparties."""
        return self.iter_all(
            ENTITY_COUNTERPARTIES,
            filter="IsFolder eq false and DeletionMark eq false",
            orderby="Ref_Key",
            limit=limit,
        )

    def sales(
        self,
        date_from: datetime | str,
        date_to: datetime | str,
        *,
        limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Sales register records over a period, half-open on the upper bound."""
        clause = (
            f"Period ge {odata_datetime(date_from)} "
            f"and Period lt {odata_datetime(date_to)}"
        )
        return self.iter_all(
            ENTITY_SALES, filter=clause, orderby="Period", limit=limit
        )

    def customer_orders(
        self,
        date_from: datetime | str,
        date_to: datetime | str,
        *,
        posted_only: bool = True,
        limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Customer orders over a period."""
        clause = (
            f"Date ge {odata_datetime(date_from)} "
            f"and Date lt {odata_datetime(date_to)}"
        )
        if posted_only:
            clause += " and Posted eq true"
        return self.iter_all(
            ENTITY_CUSTOMER_ORDERS, filter=clause, orderby="Date", limit=limit
        )

    def order_fulfilment(
        self,
        date_from: datetime | str,
        date_to: datetime | str,
        *,
        record_type: str = "",
        limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Order register movements; ``record_type`` filters Receipt vs Expense."""
        clause = (
            f"Period ge {odata_datetime(date_from)} "
            f"and Period lt {odata_datetime(date_to)}"
        )
        if record_type:
            clause += f" and RecordType eq '{record_type}'"
        return self.iter_all(
            ENTITY_ORDER_FULFILMENT, filter=clause, orderby="Period", limit=limit
        )


def _check() -> int:
    """Prove the tunnel and the credentials work. Exit code 0 means live."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        client = ODataClient()
    except RuntimeError as exc:
        LOG.error("✗ %s", exc)
        return 2

    LOG.info("→ %s", client.base_url)
    try:
        xml = client.metadata()
    except ODataError as exc:
        LOG.error("✗ %s", exc)
        if "сеть недоступна" in str(exc):
            LOG.error("  Похоже, туннель не поднят: проверьте `wg show wg0` (received > 0).")
        elif exc.status in (401, 403):
            LOG.error("  Логин/пароль отклонены 1С (realm 1C:Enterprise 8.5).")
        return 1

    LOG.info("✓ $metadata получены: %s символов", len(xml))
    count = sum(1 for _ in client.counterparties(limit=1))
    LOG.info("✓ выборка контрагентов вернула строк: %s", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(_check())
