#!/usr/bin/env python3
"""Dedicated HTTP server for the ClinSync Web Application (from harsha97 & Hrishi).

Serves `app.html` for root and client routes, and static assets from `assets/`.
Listens on port 3000 by default across all network interfaces (0.0.0.0).

Usage:
    .venv/bin/python tools/serve_webapp.py [--port 3000] [--host 0.0.0.0]
"""
from __future__ import annotations

import argparse
import functools
import http.server
import pathlib
import socketserver

ROOT = pathlib.Path(__file__).resolve().parent.parent
FALLBACK = 'app.html'


class WebAppHandler(http.server.SimpleHTTPRequestHandler):
    """Serves ClinSync Web App, mapping root and SPA routes to `app.html`."""

    def translate_path(self, path: str) -> str:
        # Strip query string and fragment
        clean_path = path.split('?', 1)[0].split('#', 1)[0]
        
        # If root or index or login route requested, serve app.html directly
        if clean_path in ('', '/', '/index.html', '/login', '/signup', '/patient', '/doctor'):
            return str(ROOT / FALLBACK)

        # Attempt standard file translation within repo root
        translated = super().translate_path(path)
        candidate = pathlib.Path(translated)
        
        if candidate.exists() and candidate.is_file():
            return str(candidate)

        if candidate.exists() and candidate.is_dir() and (candidate / FALLBACK).exists():
            return str(candidate / FALLBACK)

        # Non-existing route -> fallback to app.html for client-side routing
        return str(ROOT / FALLBACK)

    def end_headers(self) -> None:
        self.send_header('Cache-Control', 'no-store, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        # Suppress routine GET logging for cleaner terminal output
        return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=3000)
    parser.add_argument('--host', default='0.0.0.0')
    args = parser.parse_args()

    app_html = ROOT / FALLBACK
    if not app_html.exists():
        print(f'Error: {app_html} does not exist.')
        return 1

    handler = functools.partial(WebAppHandler, directory=str(ROOT))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        print(f'ClinSync Dedicated Web App running at http://{args.host}:{args.port} (Serving {app_html.name})')
        print(f'Local URL: http://127.0.0.1:{args.port}/#/login')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nWeb app server stopped')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
