#!/usr/bin/env python3
"""Gates for the public-safe GSC/Yandex query export workflow."""
from __future__ import annotations

import io
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fail = 0
sys.path.insert(0, str(ROOT / "scripts"))
from print_search_queries_report import (  # noqa: E402
    COUNT_KEYS,
    counts_from_tar_bytes,
    format_counts,
    print_counts,
)
from seal_vps_git_recon import encrypt_to_age  # noqa: E402
import export_search_queries as exporter  # noqa: E402

PLANTED_QUERY = "leaked-secret-query-pepperoni"
PLANTED_URL = "https://pepperoni.tatar/leaked-page"


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def _tar_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w|") as tf:
        for name, text in files.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = stat.S_IRUSR | stat.S_IWUSR
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _fixture_tar() -> bytes:
    return _tar_bytes({
        "meta.txt": (
            "gsc_rows=2\n"
            "yandex_rows=1\n"
            "yandex_url_rows=0\n"
            "gsc_indexed=10\n"
            "gsc_excluded=3\n"
            "yandex_indexed=8\n"
            "yandex_excluded=2\n"
        ),
        "gsc-queries.json": (
            '[{"query":"%s","page":"%s","country":"rus",'
            '"device":"MOBILE","clicks":1,"impressions":9,'
            '"ctr":0.1,"position":4.2}]\n' % (PLANTED_QUERY, PLANTED_URL)
        ),
        "yandex-queries.json": (
            '[{"query":"%s","shows":5,"clicks":1,"avg_position":3.0}]\n'
            % PLANTED_QUERY
        ),
        "yandex-url-queries.json": "[]\n",
        "index-counts.json": '{"gsc_indexed":10,"gsc_excluded":3}\n',
    })


def main() -> int:
    wf = (ROOT / ".github" / "workflows" / "search-queries-export.yml").read_text(
        encoding="utf-8"
    )
    exporter_src = (ROOT / "scripts" / "export_search_queries.py").read_text(
        encoding="utf-8"
    )
    sealer = (ROOT / "scripts" / "seal_search_queries.py").read_text(encoding="utf-8")
    printer = (ROOT / "scripts" / "print_search_queries_report.py").read_text(
        encoding="utf-8"
    )
    pub = (ROOT / "ops" / "recon-age.pub").read_text(encoding="utf-8").strip()

    on_block = wf.split("jobs:")[0]
    check("workflow_dispatch" in on_block, "workflow has workflow_dispatch")
    check("push:" in on_block, "on: block has path-filtered push")
    check("pull_request:" not in on_block, "on: block has no pull_request")
    check("schedule:" not in on_block, "on: block has no schedule")
    check("ops/queries-trigger.txt" in on_block,
          "push paths include ops/queries-trigger.txt")
    check(re.search(r"branches:\s*\n\s*-\s*main\b", on_block),
          "push is limited to branch main")
    trigger = ROOT / "ops" / "queries-trigger.txt"
    check(trigger.is_file(), "ops/queries-trigger.txt exists")
    check(bool(re.search(r"20\d{2}-\d{2}-\d{2}", trigger.read_text(encoding="utf-8"))),
          "queries-trigger.txt has a dated line")

    check("secrets.GSC_SERVICE_ACCOUNT_KEY" in wf, "workflow uses GSC secret")
    check("secrets.YANDEX_WM_TOKEN" in wf, "workflow uses Yandex secret")
    check("apt-get install -y age" in wf, "workflow installs age")
    check("cryptography" in wf, "workflow installs cryptography for GSC JWT")
    check("seal_search_queries.py" in wf, "workflow seals via seal_search_queries.py")
    check("export_search_queries.py" in wf, "workflow exports via export_search_queries.py")
    check("ops/recon-age.pub" in wf, "workflow uses the committed recipient")
    check(pub == "age1uq55jgysck9tu0g4znardz3a8splzuxvqmpgvnxdcg2wktv4rcssnzks2d",
          "committed recipient is the recon age public key")
    check("search-queries.tar.age" in wf, "workflow writes the .age ciphertext")
    check(re.search(r"path:\s*search-queries\.tar\.age\s*$", wf, re.M),
          "upload-artifact path is only the .age file")
    check(not re.search(r"path:\s*search-queries/?\s*$", wf, re.M),
          "workflow does not upload a plaintext directory")
    check("tar -x" not in wf and "tar -xf" not in wf,
          "workflow does not unpack the tar on the runner")
    check("search-queries-export: export failed" in wf,
          "export failure prints only a fixed message")
    check("search-queries-export: seal failed" in wf,
          "seal failure prints only a fixed message")
    check('rcs=("${PIPESTATUS[@]}")' in wf,
          "workflow snapshots PIPESTATUS in one assignment")
    check("test ! -e search-queries.tar" in wf, "workflow asserts no plaintext tar")
    check("name: search-queries" in wf, "artifact name is search-queries")

    check("from fetch_gsc_queries import" in exporter_src,
          "export reuses fetch_gsc_queries helpers")
    check("from fetch_yandex_queries import" in exporter_src,
          "export reuses fetch_yandex_queries helpers")
    check("DAYS = 90" in exporter_src or "DAYS=90" in exporter_src.replace(" ", ""),
          "export window is 90 days")
    check("25000" in exporter_src, "GSC row cap is 25000")
    check('"query"' in exporter_src and '"page"' in exporter_src
          and '"country"' in exporter_src and '"device"' in exporter_src,
          "GSC dimensions include query, page, country, device")
    check("shows" in exporter_src and "avg_position" in exporter_src,
          "Yandex rows keep shows, clicks, avg position")
    check("popular-by-url" in exporter_src or "url" in exporter_src,
          "export attempts per-URL Yandex queries")
    check("searchable_pages_count" in exporter_src
          and "excluded_pages_count" in exporter_src,
          "Yandex index counts come from host summary")
    check("e.read()" not in exporter_src, "export does not print HTTP bodies")
    check("_quiet_stderr" in exporter_src, "helper stderr is swallowed")
    check("search-queries-export: missing gsc key" in exporter_src, "fixed missing-key message")
    check("search-queries-export: gsc failed" in exporter_src, "fixed gsc-failed message")
    check("search-queries-export: yandex failed" in exporter_src, "fixed yandex-failed message")
    check("sys.stdout.buffer.write" in exporter_src, "export writes the tar to stdout")
    check("write_text" not in exporter_src and "write_bytes" not in exporter_src,
          "export does not write plaintext files")

    check("encrypt_to_age" in sealer, "sealer reuses encrypt_to_age")
    check("print_counts" in sealer, "sealer prints counts only")
    check("seal_search_queries: age failed" in sealer, "sealer uses a fixed age-failed message")
    check("seal_search_queries: empty stdin" in sealer, "sealer uses a fixed empty-stdin message")

    data = _fixture_tar()
    counts = counts_from_tar_bytes(data)
    check(counts["gsc_rows"] == 2, "printer reads gsc_rows from meta")
    check(counts["yandex_excluded"] == 2, "printer reads yandex_excluded")
    buf = io.StringIO()
    rc = print_counts(data, buf)
    out = buf.getvalue()
    check(rc == 0, "printer exits 0")
    check(PLANTED_QUERY not in out, "printer stdout has no query text")
    check(PLANTED_URL not in out, "printer stdout has no page URL")
    check("leaked" not in out, "printer stdout has no planted leak token")
    for key in COUNT_KEYS:
        check(f"{key}=" in format_counts(counts), f"counts line includes {key}")

    # Missing secrets: exporter exits with a fixed message, no traceback leak.
    env = dict(os.environ)
    env.pop("GSC_SERVICE_ACCOUNT_KEY", None)
    env.pop("GSC_SERVICE_ACCOUNT_KEY_B64", None)
    env.pop("YANDEX_WM_TOKEN", None)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_search_queries.py")],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    check(proc.returncode != 0, "export without secrets exits nonzero")
    err = proc.stderr.decode("utf-8", "replace")
    check("search-queries-export: missing" in err, "missing secrets use a fixed message")
    check(PLANTED_QUERY not in err and PLANTED_URL not in err,
          "missing-secret stderr has no planted data")
    check(proc.stdout == b"", "export without secrets writes no stdout tar")

    # Empty stdin to sealer.
    seal = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seal_search_queries.py"),
         "--out", str(ROOT / "does-not-matter.tar.age")],
        cwd=ROOT,
        input=b"",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    check(seal.returncode == 2, "sealer empty stdin exits 2")
    check(b"seal_search_queries: empty stdin" in seal.stderr,
          "sealer empty stdin is a fixed message")

    with tempfile.TemporaryDirectory() as tmp:
        out_age = Path(tmp) / "search-queries.tar.age"
        try:
            encrypt_to_age(data, ROOT / "ops" / "recon-age.pub", out_age)
            blob = out_age.read_bytes()
            check(blob.startswith(b"age-encryption.org/v1"),
                  "ciphertext starts with the age header")
            check(PLANTED_QUERY.encode() not in blob,
                  "ciphertext does not contain planted query in the clear")
            check(PLANTED_URL.encode() not in blob,
                  "ciphertext does not contain planted URL in the clear")
        except SystemExit as exc:
            check("age is not installed" in str(exc),
                  "encrypt_to_age skipped only when age is missing")
            if "age is not installed" not in str(exc):
                print("  note", exc)

    if fail:
        print(f"test_search_queries_export: {fail} FAIL")
        return 1
    print("test_search_queries_export: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
