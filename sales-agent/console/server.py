"""
Локальная веб-консоль (stdlib only). Не деплоится на Vercel.

  python -m console.cli serve
  → http://127.0.0.1:8765
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.gate import Gate
from core.store import Store

STATIC = Path(__file__).parent / "static"


class ConsoleHandler(BaseHTTPRequestHandler):
    store = Store()
    gate = Gate(store)

    def log_message(self, format: str, *args) -> None:
        pass  # тихий сервер

    def _json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, content: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        self.store.init()
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            idx = STATIC / "index.html"
            self._html(idx.read_bytes())
            return

        if path == "/api/stats":
            self._json(self.store.stats())
            return

        if path == "/api/leads":
            qs = parse_qs(urlparse(self.path).query)
            tier = qs.get("tier", [None])[0]
            self._json({"leads": self.store.list_leads(tier=tier, limit=50)})
            return

        if path == "/api/inbox":
            self._json({"messages": self.store.inbox(30)})
            return

        if path == "/api/approvals":
            self._json({"approvals": self.store.list_approvals("pending", 30)})
            return

        if path == "/api/drafts":
            self._json({"drafts": self.store.list_drafts(limit=30)})
            return

        if path == "/api/audit":
            self._json({"audit": self.store.audit_tail(40)})
            return

        self.send_error(404)

    def do_POST(self) -> None:
        self.store.init()
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {}

        if path == "/api/approve":
            aid = body.get("approval_id")
            r = self.gate.approve(aid, decided_by="web") if aid else None
            self._json({"ok": bool(r)})
            return

        if path == "/api/reject":
            aid = body.get("approval_id")
            r = self.gate.reject(aid, decided_by="web") if aid else None
            self._json({"ok": bool(r)})
            return

        if path == "/api/cycle":
            from orchestrator.run_cycle import run_cycle
            r = run_cycle(dry_run_send=True, max_drafts=body.get("max_drafts", 3))
            self._json(r)
            return

        self.send_error(404)


def main(port: int = 8765) -> None:
    Store().init()
    server = HTTPServer(("127.0.0.1", port), ConsoleHandler)
    print(f"Sales Agent console: http://127.0.0.1:{port}")
    print("Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
