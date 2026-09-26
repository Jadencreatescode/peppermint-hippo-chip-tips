#!/usr/bin/env python3
"""Local preview server for the tablet only Chip Tips app.

The application stores shift data in the tablet browser. This server serves
only static files and never receives or stores shift information.
"""

from __future__ import annotations

import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


class StaticAppHandler(BaseHTTPRequestHandler):
    server_version = "ChipTipsStatic/2.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        requested = (STATIC / relative).resolve()
        try:
            requested.relative_to(STATIC.resolve())
        except ValueError:
            return self.send_error(HTTPStatus.FORBIDDEN)
        if not requested.is_file():
            requested = STATIC / "index.html"
        content = requested.read_bytes()
        content_type = mimetypes.guess_type(str(requested))[0] or "application/octet-stream"
        if requested.suffix == ".webmanifest":
            content_type = "application/manifest+json"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        no_cache = requested.name in {"index.html", "sw.js"} or requested.suffix in {".js", ".css", ".webmanifest"}
        self.send_header("Cache-Control", "no-cache" if no_cache else "public, max-age=3600")
        self.end_headers()
        self.wfile.write(content)


def make_server(host: str = "127.0.0.1", port: int = 8787) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), StaticAppHandler)


if __name__ == "__main__":
    host = os.environ.get("CHIP_TIPS_HOST", "127.0.0.1")
    port = int(os.environ.get("CHIP_TIPS_PORT", "8787"))
    server = make_server(host, port)
    print(f"Chip Tips preview is running at http://{host}:{port}")
    print("Shift information is stored only in the tablet browser.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Chip Tips")
    finally:
        server.server_close()
