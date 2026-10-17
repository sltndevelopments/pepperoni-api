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
    check(re.search(r"cryptography==\d+\.\d+\.\d+", wf),
          "workflow pins cryptography to an exact version")
    check(not re.search(r"pip install cryptography\s*$", wf, re.M),
          "workflow does not install unpinned cryptography")
    for action in ("actions/checkout", "actions/setup-python",
                   "actions/upload-artifact"):
        check(re.search(rf"uses:\s*{re.escape(action)}@[0-9a-f]{{40}}", wf),
              f"{action} is pinned to a commit SHA")
        check(not re.search(rf"uses:\s*{re.escape(action)}@v\d", wf),
              f"{action} is not floating on a major tag")
    check("::warning::search-queries-export: partial export" in wf,
          "partial export is a warning, not a failure")
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
    check("search-queries-export: gsc unavailable" in exporter_src,
          "fixed gsc-unavailable message")
    check("search-queries-export: yandex unavailable" in exporter_src,
          "fixed yandex-unavailable message")
    check("search-queries-export: all sources failed" in exporter_src,
          "fixed both-sources-failed message")
    check("sys.tracebacklimit = 0" in exporter_src, "exporter disables traceback dumps")
    check("except Exception" in exporter_src, "exporter main() catches Exception")
    check("RETRY_ATTEMPTS = 3" in exporter_src, "each source retries 3 times")
    check("HTTP_TIMEOUT = 8" in exporter_src, "HTTP timeout is short")
    check("sys.stdout.buffer.write" in exporter_src, "export writes the tar to stdout")
    check("write_text" not in exporter_src and "write_bytes" not in exporter_src,
          "export does not write plaintext files")

    check("encrypt_to_age" in sealer, "sealer reuses encrypt_to_age")
    check("print_counts" in sealer, "sealer prints counts only")
    check("seal_search_queries: age failed" in sealer, "sealer uses a fixed age-failed message")
    check("seal_search_queries: empty stdin" in sealer, "sealer uses a fixed empty-stdin message")
    check("sys.tracebacklimit = 0" in sealer, "sealer disables traceback dumps")
    check("except Exception" in sealer, "sealer wraps print_counts in except Exception")
    check("sys.tracebacklimit = 0" in printer, "printer disables traceback dumps")
    check("except Exception" in printer, "print_counts catches Exception")
    check("yandex=unavailable" in exporter_src or 'UNAVAILABLE = "unavailable"' in exporter_src,
          "partial export records yandex=unavailable")

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

    # Unexpected exception: class name only, no traceback, no planted query.
    def boom(*_a, **_k):
        raise OSError(f"Network is unreachable: {PLANTED_QUERY} {PLANTED_URL}")

    old_collect = exporter.collect
    exporter.collect = boom  # type: ignore[assignment]
    buf_out, buf_err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = buf_out, buf_err
        rc = exporter.main()
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        exporter.collect = old_collect
    leaked = buf_out.getvalue() + buf_err.getvalue()
    check(rc != 0, "unexpected OSError exits nonzero")
    check("search-queries-export: OSError" in buf_err.getvalue(),
          "unexpected error prints the class name only")
    check("Traceback" not in leaked and 'File "' not in leaked,
          "unexpected error prints no traceback")
    check(PLANTED_QUERY not in leaked and PLANTED_URL not in leaked,
          "unexpected error prints no query text")
    check("Network is unreachable" not in leaked,
          "unexpected error prints no exception message")

    def gsc_ok(_sa: str) -> dict:
        return {
            "rows": [{"query": PLANTED_QUERY, "page": PLANTED_URL,
                      "country": "rus", "device": "MOBILE",
                      "clicks": 1, "impressions": 2, "ctr": 0.5, "position": 3}],
            "indexed": 4,
            "excluded": 1,
        }

    def ya_ok(_tok: str) -> dict:
        return {
            "rows": [{"query": PLANTED_QUERY, "shows": 1, "clicks": 0,
                      "avg_position": 2.0}],
            "urls": [],
            "indexed": 3,
            "excluded": 1,
        }

    def ya_down(_tok: str) -> dict:
        raise OSError(f"Errno 101 Network is unreachable {PLANTED_QUERY}")

    def gsc_down(_sa: str) -> dict:
        raise OSError(f"GSC unreachable {PLANTED_URL}")

    def run_collect(gsc_fn, ya_fn):
        old_gsc, old_ya = exporter.collect_gsc, exporter.collect_yandex
        saved = {
            "gsc": os.environ.get("GSC_SERVICE_ACCOUNT_KEY"),
            "b64": os.environ.get("GSC_SERVICE_ACCOUNT_KEY_B64"),
            "ya": os.environ.get("YANDEX_WM_TOKEN"),
        }
        os.environ["GSC_SERVICE_ACCOUNT_KEY"] = '{"type":"service_account"}'
        os.environ["YANDEX_WM_TOKEN"] = "token"
        os.environ.pop("GSC_SERVICE_ACCOUNT_KEY_B64", None)
        exporter.collect_gsc = gsc_fn  # type: ignore[assignment]
        exporter.collect_yandex = ya_fn  # type: ignore[assignment]
        buf_err = io.StringIO()
        old_err = sys.stderr
        sys.stderr = buf_err
        files = None
        code = 0
        try:
            files = exporter.collect()
        except SystemExit as exc:
            code = int(exc.code) if isinstance(exc.code, int) else 1
        finally:
            sys.stderr = old_err
            exporter.collect_gsc, exporter.collect_yandex = old_gsc, old_ya
            if saved["gsc"] is None:
                os.environ.pop("GSC_SERVICE_ACCOUNT_KEY", None)
            else:
                os.environ["GSC_SERVICE_ACCOUNT_KEY"] = saved["gsc"]
            if saved["b64"] is None:
                os.environ.pop("GSC_SERVICE_ACCOUNT_KEY_B64", None)
            else:
                os.environ["GSC_SERVICE_ACCOUNT_KEY_B64"] = saved["b64"]
            if saved["ya"] is None:
                os.environ.pop("YANDEX_WM_TOKEN", None)
            else:
                os.environ["YANDEX_WM_TOKEN"] = saved["ya"]
        return files, code, buf_err.getvalue()

    files, code, err = run_collect(gsc_ok, ya_down)
    check(code == 0 and files is not None, "Yandex down still collects GSC")
    check("search-queries-export: yandex unavailable" in err,
          "Yandex down prints yandex unavailable")
    check("Traceback" not in err and PLANTED_QUERY not in err and PLANTED_URL not in err,
          "Yandex down stderr has no traceback or query")
    ya_counts = counts_from_tar_bytes(exporter._tar_bytes(files or {}))
    check(ya_counts.get("yandex") == "unavailable",
          "counts record yandex=unavailable")
    check(ya_counts.get("gsc") == "ok", "counts record gsc=ok")
    check(int(ya_counts["gsc_rows"]) == 1, "GSC rows are kept when Yandex is down")
    check("yandex=unavailable" in format_counts(ya_counts),
          "counts line prints yandex=unavailable")

    files2, code2, err2 = run_collect(gsc_down, ya_ok)
    check(code2 == 0 and files2 is not None, "GSC down still collects Yandex")
    check("search-queries-export: gsc unavailable" in err2,
          "GSC down prints gsc unavailable")
    check("Traceback" not in err2 and PLANTED_QUERY not in err2 and PLANTED_URL not in err2,
          "GSC down stderr has no traceback or query")
    gsc_counts = counts_from_tar_bytes(exporter._tar_bytes(files2 or {}))
    check(gsc_counts.get("gsc") == "unavailable", "counts record gsc=unavailable")
    check(int(gsc_counts["yandex_rows"]) == 1, "Yandex rows are kept when GSC is down")

    files3, code3, err3 = run_collect(gsc_down, ya_down)
    check(code3 != 0 and files3 is None, "both sources down exits nonzero")
    check("search-queries-export: all sources failed" in err3,
          "both down uses a fixed message")
    check("Traceback" not in err3 and PLANTED_QUERY not in err3,
          "both down stderr has no traceback or query")

    garbage = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seal_search_queries.py"),
         "--out", str(ROOT / "does-not-matter.tar.age")],
        cwd=ROOT,
        input=b"not-a-tar " + PLANTED_QUERY.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    gerr = garbage.stderr.decode("utf-8", "replace")
    gout = garbage.stdout.decode("utf-8", "replace")
    check(garbage.returncode != 0, "sealer garbage tar exits nonzero")
    check(re.fullmatch(r"seal_search_queries: [A-Za-z][A-Za-z0-9_]+\n", gerr),
          "sealer garbage tar prints a fixed class-name message")
    check("Traceback" not in gerr + gout and 'File "' not in gerr + gout,
          "sealer garbage tar prints no traceback")
    check(PLANTED_QUERY not in gerr and PLANTED_QUERY not in gout,
          "sealer garbage tar prints no planted query")

    # Retry count.
    sleeps: list[float] = []
    n = {"c": 0}

    def always_fail():
        n["c"] += 1
        raise OSError("x")

    old_sleep = exporter.time.sleep
    exporter.time.sleep = lambda s: sleeps.append(s)  # type: ignore[assignment]
    try:
        exporter._retry(always_fail)
        retried = False
    except OSError:
        retried = True
    exporter.time.sleep = old_sleep
    check(retried and n["c"] == 3, "retry helper attempts 3 times")
    check(len(sleeps) == 2, "retry helper backs off between attempts")

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
