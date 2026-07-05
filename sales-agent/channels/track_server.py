"""
Минимальный HTTP-сервер для open-tracking пикселя писем.

GET /o/<token>.gif → 1x1 прозрачный GIF, пишет открытие в email_opens.
stdlib only — не тянуть Flask/FastAPI ради одного эндпоинта.

Запуск: python3 -m channels.track_server [--port 8081]
На VPS — отдельный systemd unit, за nginx location /sales-track/.
"""
from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.store import Store

# 1x1 прозрачный GIF (43 байта) — минимальный валидный пиксель.
_PIXEL = bytes.fromhex(
    "47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024c01003b"
)


class TrackHandler(BaseHTTPRequestHandler):
    store = Store()

    def log_message(self, format: str, *args) -> None:
        pass

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/o/") and path.endswith(".gif"):
            token = path[len("/o/"):-len(".gif")]
            try:
                self.store.record_email_open(
                    token,
                    ip=self.headers.get("X-Real-IP") or self.client_address[0],
                    ua=self.headers.get("User-Agent", "")[:300],
                )
            except Exception:
                pass
            self.send_response(200)
            self.send_header("Content-Type", "image/gif")
            self.send_header("Content-Length", str(len(_PIXEL)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(_PIXEL)
            return
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_error(404)


def main(port: int = 8081) -> None:
    Store().init()
    server = ThreadingHTTPServer(("127.0.0.1", port), TrackHandler)
    print(f"Sales open-tracking server: http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    main(port)
