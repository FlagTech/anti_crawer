"""Attach a ClientHello-derived JA3 result to requests sent to the local app.

This addon is deliberately limited to the training reverse proxy. The app only
trusts its headers when the shared local secret is also present.
"""
from __future__ import annotations

import hashlib
import os

from mitmproxy import http, tls

PROXY_SECRET = os.getenv("TLS_PROXY_SECRET", "local-tls-demo-proxy-only")


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "big")


def _is_grease(value: int) -> bool:
    return (value & 0x0F0F) == 0x0A0A and (value >> 8) == (value & 0xFF)


def _non_grease(values: list[int]) -> list[int]:
    return [value for value in values if not _is_grease(value)]


def fingerprint(client_hello: tls.ClientHello) -> tuple[str, bool, bool]:
    """Calculate JA3 from the TLS ClientHello body supplied by mitmproxy."""
    raw = client_hello.raw_bytes(wrap_in_record=False)
    version = _u16(raw, 0)
    offset = 34  # legacy_version + random
    session_id_length = raw[offset]
    offset += 1 + session_id_length
    cipher_length = _u16(raw, offset)
    offset += 2
    cipher_suites = [_u16(raw, index) for index in range(offset, offset + cipher_length, 2)]
    offset += cipher_length
    compression_length = raw[offset]
    offset += 1 + compression_length
    extension_length = _u16(raw, offset)
    offset += 2
    extension_end = offset + extension_length
    extension_types: list[int] = []
    groups: list[int] = []
    point_formats: list[int] = []
    alpn: list[bytes] = []
    while offset < extension_end:
        extension_type = _u16(raw, offset)
        body_length = _u16(raw, offset + 2)
        body = raw[offset + 4 : offset + 4 + body_length]
        offset += 4 + body_length
        extension_types.append(extension_type)
        if extension_type == 10 and len(body) >= 2:
            length = _u16(body, 0)
            groups = [_u16(body, index) for index in range(2, min(2 + length, len(body)), 2)]
        elif extension_type == 11 and body:
            point_formats = list(body[1 : 1 + body[0]])
        elif extension_type == 16 and len(body) >= 2:
            length = _u16(body, 0)
            index = 2
            while index < min(2 + length, len(body)):
                item_length = body[index]
                alpn.append(body[index + 1 : index + 1 + item_length])
                index += 1 + item_length
    source = ",".join(
        [
            str(version),
            "-".join(map(str, _non_grease(cipher_suites))),
            "-".join(map(str, _non_grease(extension_types))),
            "-".join(map(str, _non_grease(groups))),
            "-".join(map(str, point_formats)),
        ]
    )
    has_grease = any(_is_grease(value) for value in cipher_suites + extension_types + groups)
    return hashlib.md5(source.encode()).hexdigest(), has_grease, b"h2" in alpn


class TlsFingerprintAddon:
    def __init__(self) -> None:
        self.by_connection: dict[str, tuple[str, bool, bool]] = {}

    def tls_clienthello(self, data: tls.ClientHelloData) -> None:
        self.by_connection[data.context.client.id] = fingerprint(data.client_hello)

    def request(self, flow: http.HTTPFlow) -> None:
        result = self.by_connection.get(flow.client_conn.id)
        if result is None:
            return
        flow.request.headers["X-Training-TLS-Proxy"] = PROXY_SECRET
        ja3, has_grease, has_h2 = result
        flow.request.headers["X-Training-TLS-JA3"] = ja3
        flow.request.headers["X-Training-TLS-Classification"] = "browser-like" if has_grease and has_h2 else "non-browser-like"


addons = [TlsFingerprintAddon()]
