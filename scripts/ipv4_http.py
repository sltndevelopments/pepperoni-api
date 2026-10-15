#!/usr/bin/env python3
"""Force IPv4 for HTTPS clients on hosts that publish AAAA but have no IPv6 route.

VPS Selectel resolved api.webmaster.yandex.net to 2a02:6b8::2:61 first;
connect() then failed with OSError errno 101 (Network is unreachable).
Google and IndexNow (IPv4) succeeded on the same run.
"""
from __future__ import annotations

import http.client
import socket
import ssl
import urllib.request
from contextlib import contextmanager
from urllib.request import HTTPSHandler, build_opener


class IPv4HTTPSConnection(http.client.HTTPSConnection):
    def connect(self) -> None:
        err: OSError | None = None
        infos = socket.getaddrinfo(
            self.host, self.port, socket.AF_INET, socket.SOCK_STREAM
        )
        if not infos:
            raise OSError("no IPv4 address for " + str(self.host))
        for af, socktype, proto, _canon, sa in infos:
            sock = None
            try:
                sock = socket.socket(af, socktype, proto)
                sock.settimeout(self.timeout)
                sock.connect(sa)
                ctx = self._context or ssl.create_default_context()
                self.sock = ctx.wrap_socket(sock, server_hostname=self.host)
                return
            except OSError as exc:
                err = exc
                if sock is not None:
                    sock.close()
        raise err or OSError("IPv4 connect failed for " + str(self.host))


class IPv4HTTPSHandler(HTTPSHandler):
    def https_open(self, req):
        return self.do_open(IPv4HTTPSConnection, req, context=self._context)


@contextmanager
def force_ipv4_https():
    """Temporarily make urllib.request.urlopen use IPv4-only HTTPS."""
    ctx = ssl.create_default_context()
    opener = build_opener(IPv4HTTPSHandler(context=ctx))
    previous = getattr(urllib.request, "_opener", None)
    urllib.request.install_opener(opener)
    try:
        yield
    finally:
        urllib.request._opener = previous
