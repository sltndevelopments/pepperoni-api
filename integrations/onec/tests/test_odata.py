from __future__ import annotations

import base64
import json
import os
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from integrations.onec import odata
from integrations.onec.odata import (
    ENTITY_COUNTERPARTIES,
    HttpTransport,
    ODataClient,
    ODataError,
    odata_datetime,
)


class FakeTransport:
    """Records requests and replays canned responses in order."""

    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[str] = []
        self.headers: list[dict[str, str]] = []

    def request(self, url, *, headers, timeout):
        self.calls.append(url)
        self.headers.append(dict(headers))
        if not self.responses:
            raise AssertionError(f"unexpected extra request: {url}")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        status, payload = item
        if isinstance(payload, (dict, list)):
            return status, json.dumps(payload, ensure_ascii=False).encode()
        return status, payload.encode() if isinstance(payload, str) else payload


def page(rows: list[dict]) -> tuple[int, dict]:
    return 200, {"odata.metadata": "http://x/$metadata", "value": rows}


def make_client(responses: list[object], **kwargs) -> tuple[ODataClient, FakeTransport]:
    transport = FakeTransport(responses)
    client = ODataClient(
        "http://192.168.11.40/unf/odata/standard.odata/",
        "Odata.user",
        "secret",
        transport=transport,
        sleep=lambda _s: None,
        **kwargs,
    )
    return client, transport


class DatetimeLiteralTest(unittest.TestCase):
    def test_formats_odata_v3_literal(self) -> None:
        got = odata_datetime(datetime(2026, 7, 1, 0, 0, 0))
        self.assertEqual(got, "datetime'2026-07-01T00:00:00'")

    def test_drops_microseconds(self) -> None:
        got = odata_datetime(datetime(2026, 7, 1, 12, 30, 5, 123456))
        self.assertEqual(got, "datetime'2026-07-01T12:30:05'")

    def test_passes_through_string(self) -> None:
        self.assertEqual(
            odata_datetime("2026-07-01T00:00:00"), "datetime'2026-07-01T00:00:00'"
        )


class ConfigTest(unittest.TestCase):
    def test_base_url_gets_single_trailing_slash(self) -> None:
        for given in (
            "http://192.168.11.40/unf/odata/standard.odata",
            "http://192.168.11.40/unf/odata/standard.odata/",
            "http://192.168.11.40/unf/odata/standard.odata///",
        ):
            with self.subTest(given=given):
                client = ODataClient(given, "u", "p", transport=FakeTransport([]))
                self.assertEqual(
                    client.base_url, "http://192.168.11.40/unf/odata/standard.odata/"
                )

    def test_missing_credentials_fail_fast(self) -> None:
        with self.assertRaises(RuntimeError):
            ODataClient("http://x/", "", "", transport=FakeTransport([]))


class RequestShapeTest(unittest.TestCase):
    def test_preemptive_basic_auth_header(self) -> None:
        client, transport = make_client([page([])])
        list(client.get(ENTITY_COUNTERPARTIES))
        expected = base64.b64encode(b"Odata.user:secret").decode()
        self.assertEqual(transport.headers[0]["Authorization"], f"Basic {expected}")
        self.assertEqual(transport.headers[0]["Accept"], "application/json")

    def test_format_json_always_present(self) -> None:
        client, transport = make_client([page([])])
        client.get(ENTITY_COUNTERPARTIES)
        self.assertIn("%24format=json", transport.calls[0])

    def test_cyrillic_entity_is_percent_encoded(self) -> None:
        client, transport = make_client([page([])])
        client.get(ENTITY_COUNTERPARTIES)
        url = transport.calls[0]
        self.assertIn("Catalog_%D0%9A%D0%BE%D0%BD%D1%82%D1%80%D0%B0%D0%B3%D0%B5%D0%BD%D1%82%D1%8B", url)
        # A raw Cyrillic byte in the path would make 1C answer 400.
        self.assertTrue(url.isascii())

    def test_spaces_in_filter_encode_as_percent20_not_plus(self) -> None:
        client, transport = make_client([page([])])
        client.get(ENTITY_COUNTERPARTIES, filter="IsFolder eq false")
        url = transport.calls[0]
        self.assertIn("%20eq%20", url)
        self.assertNotIn("+eq+", url)

    def test_query_options_are_passed_through(self) -> None:
        client, transport = make_client([page([])])
        client.get(
            ENTITY_COUNTERPARTIES,
            select="Ref_Key,Description",
            orderby="Description",
            top=10,
            skip=20,
        )
        url = urllib.parse.unquote(transport.calls[0])
        self.assertIn("$select=Ref_Key,Description", url)
        self.assertIn("$orderby=Description", url)
        self.assertIn("$top=10", url)
        self.assertIn("$skip=20", url)

    def test_skip_zero_is_omitted(self) -> None:
        client, transport = make_client([page([])])
        client.get(ENTITY_COUNTERPARTIES, skip=0)
        self.assertNotIn("skip", transport.calls[0])

    def test_metadata_hits_metadata_path(self) -> None:
        client, transport = make_client([(200, "<edmx:Edmx/>")])
        xml = client.metadata()
        self.assertEqual(xml, "<edmx:Edmx/>")
        self.assertTrue(transport.calls[0].endswith("/$metadata"))


class ResponseParsingTest(unittest.TestCase):
    def test_returns_value_list(self) -> None:
        client, _ = make_client([page([{"Ref_Key": "a"}, {"Ref_Key": "b"}])])
        rows = client.get(ENTITY_COUNTERPARTIES)
        self.assertEqual([r["Ref_Key"] for r in rows], ["a", "b"])

    def test_empty_body_is_empty_list(self) -> None:
        client, _ = make_client([(200, "")])
        self.assertEqual(client.get(ENTITY_COUNTERPARTIES), [])

    def test_non_json_body_raises(self) -> None:
        client, _ = make_client([(200, "<html>login</html>")])
        with self.assertRaises(ODataError):
            client.get(ENTITY_COUNTERPARTIES)

    def test_missing_value_field_raises(self) -> None:
        client, _ = make_client([(200, {"odata.metadata": "x"})])
        with self.assertRaises(ODataError):
            client.get(ENTITY_COUNTERPARTIES)


class ErrorHandlingTest(unittest.TestCase):
    def setUp(self) -> None:
        # Retries log a warning by design; keep it out of the test report.
        patcher = patch.object(odata.LOG, "warning")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_401_raises_with_status_and_no_retry(self) -> None:
        client, transport = make_client([(401, "Unauthorized")])
        with self.assertRaises(ODataError) as ctx:
            client.get(ENTITY_COUNTERPARTIES)
        self.assertEqual(ctx.exception.status, 401)
        self.assertEqual(len(transport.calls), 1, "bad credentials must not be retried")

    def test_503_is_retried_then_succeeds(self) -> None:
        client, transport = make_client(
            [(503, "busy"), page([{"Ref_Key": "a"}])]
        )
        rows = client.get(ENTITY_COUNTERPARTIES)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(transport.calls), 2)

    def test_retries_exhaust_and_raise(self) -> None:
        client, transport = make_client([(503, "busy")] * 3)
        with self.assertRaises(ODataError) as ctx:
            client.get(ENTITY_COUNTERPARTIES)
        self.assertEqual(ctx.exception.status, 503)
        self.assertEqual(len(transport.calls), 3)

    def test_network_error_is_retried_then_reported(self) -> None:
        err = urllib.error.URLError("No route to host")
        client, transport = make_client([err, err, err])
        with self.assertRaises(ODataError) as ctx:
            client.get(ENTITY_COUNTERPARTIES)
        self.assertIn("сеть недоступна", str(ctx.exception))
        self.assertEqual(len(transport.calls), 3)

    def test_network_error_recovers(self) -> None:
        client, _ = make_client(
            [urllib.error.URLError("timed out"), page([{"Ref_Key": "a"}])]
        )
        self.assertEqual(len(client.get(ENTITY_COUNTERPARTIES)), 1)


class PaginationTest(unittest.TestCase):
    def test_pages_until_short_page(self) -> None:
        client, transport = make_client(
            [
                page([{"i": 1}, {"i": 2}]),
                page([{"i": 3}]),
            ],
            page_size=2,
        )
        rows = list(client.iter_all(ENTITY_COUNTERPARTIES))
        self.assertEqual([r["i"] for r in rows], [1, 2, 3])
        self.assertEqual(len(transport.calls), 2)
        self.assertIn("%24skip=2", transport.calls[1])

    def test_stops_on_empty_page(self) -> None:
        client, transport = make_client(
            [page([{"i": 1}, {"i": 2}]), page([])], page_size=2
        )
        rows = list(client.iter_all(ENTITY_COUNTERPARTIES))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(transport.calls), 2)

    def test_full_page_then_empty_makes_extra_call(self) -> None:
        # A register whose row count is an exact multiple of the page size must
        # not silently truncate.
        client, _ = make_client(
            [page([{"i": 1}, {"i": 2}]), page([{"i": 3}, {"i": 4}]), page([])],
            page_size=2,
        )
        self.assertEqual(len(list(client.iter_all(ENTITY_COUNTERPARTIES))), 4)

    def test_limit_stops_mid_page(self) -> None:
        client, transport = make_client([page([{"i": 1}, {"i": 2}])], page_size=10)
        rows = list(client.iter_all(ENTITY_COUNTERPARTIES, limit=2))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(transport.calls), 1)

    def test_limit_shrinks_requested_top(self) -> None:
        client, transport = make_client([page([{"i": 1}])], page_size=500)
        list(client.iter_all(ENTITY_COUNTERPARTIES, limit=1))
        self.assertIn("%24top=1", transport.calls[0])

    def test_zero_limit_makes_no_request(self) -> None:
        client, transport = make_client([])
        self.assertEqual(list(client.iter_all(ENTITY_COUNTERPARTIES, limit=0)), [])
        self.assertEqual(transport.calls, [])

    def test_is_lazy(self) -> None:
        client, transport = make_client([page([{"i": 1}])], page_size=1)
        client.iter_all(ENTITY_COUNTERPARTIES)
        self.assertEqual(transport.calls, [], "iter_all must not fetch until consumed")


class DomainHelperTest(unittest.TestCase):
    def test_sales_filters_period_half_open(self) -> None:
        client, transport = make_client([page([])])
        list(client.sales(datetime(2026, 7, 1), datetime(2026, 8, 1)))
        url = urllib.parse.unquote(transport.calls[0])
        self.assertIn("Period ge datetime'2026-07-01T00:00:00'", url)
        self.assertIn("Period lt datetime'2026-08-01T00:00:00'", url)

    def test_counterparties_excludes_folders_and_deleted(self) -> None:
        client, transport = make_client([page([])])
        list(client.counterparties())
        url = urllib.parse.unquote(transport.calls[0])
        self.assertIn("IsFolder eq false", url)
        self.assertIn("DeletionMark eq false", url)

    def test_customer_orders_posted_only_by_default(self) -> None:
        client, transport = make_client([page([])])
        list(client.customer_orders(datetime(2026, 7, 1), datetime(2026, 8, 1)))
        self.assertIn("Posted eq true", urllib.parse.unquote(transport.calls[0]))

    def test_customer_orders_can_include_unposted(self) -> None:
        client, transport = make_client([page([])])
        list(
            client.customer_orders(
                datetime(2026, 7, 1), datetime(2026, 8, 1), posted_only=False
            )
        )
        self.assertNotIn("Posted", urllib.parse.unquote(transport.calls[0]))

    def test_order_fulfilment_filters_record_type(self) -> None:
        client, transport = make_client([page([])])
        list(
            client.order_fulfilment(
                datetime(2026, 7, 1), datetime(2026, 8, 1), record_type="Receipt"
            )
        )
        self.assertIn("RecordType eq 'Receipt'", urllib.parse.unquote(transport.calls[0]))


class ProxyBypassTest(unittest.TestCase):
    """The LAN host is unreachable through the ambient HTTPS_PROXY.

    ``build_opener(ProxyHandler({}))`` suppresses the default env-reading
    ProxyHandler, and an empty one registers no ``*_open`` methods, so it never
    lands in ``opener.handlers``. An empty handler list is therefore the proof
    that no proxy is in play — not evidence that the bypass is missing.
    """

    ENV_PROXY = {
        "http_proxy": "http://127.0.0.1:34695",
        "https_proxy": "http://127.0.0.1:34695",
    }

    def _proxies(self, transport: HttpTransport) -> list[dict]:
        return [
            h.proxies
            for h in transport._opener.handlers
            if isinstance(h, urllib.request.ProxyHandler)
        ]

    def test_default_transport_ignores_environment_proxy(self) -> None:
        with patch.dict(os.environ, self.ENV_PROXY):
            self.assertEqual(self._proxies(HttpTransport()), [])

    def test_opt_in_picks_up_environment_proxy(self) -> None:
        with patch.dict(os.environ, self.ENV_PROXY):
            proxies = self._proxies(HttpTransport(trust_env_proxy=True))
        self.assertTrue(proxies, "trust_env_proxy must install a real ProxyHandler")
        self.assertEqual(proxies[0].get("http"), self.ENV_PROXY["http_proxy"])


if __name__ == "__main__":
    unittest.main()
