#!/usr/bin/env python3
"""gsc-inspect.py: mock HTTP, CSV columns, token never printed."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

spec = importlib.util.spec_from_file_location("gsc_inspect", SCRIPTS / "gsc-inspect.py")
insp = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(insp)

fail = 0
SAMPLE = {
    "inspectionResult": {
        "indexStatusResult": {
            "verdict": "PASS",
            "coverageState": "Submitted and indexed",
            "indexingState": "INDEXING_ALLOWED",
            "robotsTxtState": "ALLOWED",
            "pageFetchState": "SUCCESSFUL",
            "lastCrawlTime": "2026-10-17T00:00:00Z",
            "googleCanonical": "https://pepperoni.tatar/en/pepperoni",
            "userCanonical": "https://pepperoni.tatar/en/pepperoni",
            "sitemap": ["https://pepperoni.tatar/sitemap.xml"],
        },
        "richResultsResult": {
            "verdict": "PASS",
            "detectedItems": [
                {"richResultType": "FAQ", "items": [{"issues": []}]},
            ],
        },
        "mobileUsabilityResult": {"verdict": "PASS"},
    }
}


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def main() -> int:
    row = insp.flatten_inspect("https://pepperoni.tatar/en/pepperoni", SAMPLE)
    check(row["verdict"] == "PASS", "parses index verdict")
    check(row["coverageState"] == "Submitted and indexed", "parses coverageState")
    check(row["canonical_match"] == "yes", "canonical_match when equal")
    check(row["richResultsVerdict"] == "PASS", "parses rich results verdict")
    check(row["richResultsTypes"] == "FAQ", "parses detected rich result types")
    check(row["mobileUsability"] == "PASS", "parses mobile usability")
    for col in insp.COLUMNS:
        check(col in row, f"column {col} defined")

    listed = insp.read_url_list(ROOT / "data" / "inspect_urls.txt")
    check(len(listed) >= 80, f"inspect_urls.txt seeded ({len(listed)})")
    check(all(u.startswith("https://pepperoni.tatar") for u in listed),
          "seed URLs are on pepperoni.tatar")

    workflow = (ROOT / ".github" / "workflows" / "gsc-inspect.yml").read_text()
    check("workflow_dispatch" in workflow, "workflow is manual")
    check("workflow_run" not in workflow, "workflow is not chained to deploy")
    check("deploy-vps" not in workflow, "workflow does not mention deploy-vps")
    check("GSC_SERVICE_ACCOUNT_KEY" in workflow, "workflow uses the existing secret")
    check("gsc-inspect" in workflow and "retention-days: 14" in workflow,
          "uploads CSV artifact for 14 days")

    deploy = (ROOT / ".github" / "workflows" / "deploy-vps.yml").read_text()
    check("gsc-inspect" not in deploy, "inspect is not in the deploy chain")

    token = "tok_secret_abcdef"
    key = '{"private_key":"-----BEGIN PRIVATE KEY-----FAKE","client_email":"sa@x"}'
    captured = io.StringIO()

    class FakeResp:
        def __init__(self, payload):
            self._payload = json.dumps(payload).encode()

        def read(self):
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=20):
        auth = req.get_header("Authorization") or req.headers.get("Authorization") or ""
        check(auth.endswith(token) or token in str(auth), "request uses the bearer token")
        return FakeResp(SAMPLE)

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "gsc-inspect-2026-10-17.csv"
        with patch.object(insp, "_load_gsc_key", return_value=key), \
             patch.object(insp, "get_access_token", return_value=token), \
             patch.object(insp.urllib.request, "urlopen", fake_urlopen), \
             patch.object(sys, "stdout", captured):
            os.environ["GSC_INSPECT_URLS"] = "https://pepperoni.tatar/en/pepperoni"
            code = insp.main(["--urls", "https://pepperoni.tatar/en/pepperoni",
                              "--out", str(dest)])
        check(code == 0, "mocked inspect exits 0")
        text = captured.getvalue()
        check(token not in text, "stdout never prints the token")
        check("BEGIN PRIVATE KEY" not in text, "stdout never prints the key")
        check(dest.is_file(), "CSV written")
        header = dest.read_text(encoding="utf-8").splitlines()[0]
        for col in insp.COLUMNS:
            check(col in header.split(","), f"CSV has {col}")

    if fail:
        print(f"test_gsc_inspect: {fail} FAIL")
        return 1
    print("test_gsc_inspect: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
