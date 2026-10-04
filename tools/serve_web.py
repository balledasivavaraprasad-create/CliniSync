#!/usr/bin/env python3
"""SPA-aware static server for the built Flutter web app.

Flutter web + go_router uses path-based URLs, so a plain static file server
returns 404 for `/patients/<id>` and every deep link fails. Production hosting
needs the same rewrite (see README → "Hosting the web build").

Usage:
    .venv/bin/python tools/serve_web.py [--port 8090] [--dir build/web]
"""
from __future__ import annotations

import argparse
import functools
import http.server
import pathlib
import socketserver

FALLBACK = 'index.html'


class SPAHandler(http.server.SimpleHTTPRequestHandler):
    """Serves files, falling back to `index.html` for client-side routes."""

    def translate_path(self, path: str) -> str:
        translated = super().translate_path(path)
        candidate = pathlib.Path(translated)
        if candidate.exists() and candidate.is_dir() and (candidate / 'index.html').exists():
            return str(candidate / 'index.html')
        if candidate.exists():
            return translated
        # Unknown path → hand it to the Flutter router.
        return str(pathlib.Path(self.directory) / FALLBACK)  # type: ignore[attr-defined]

    def end_headers(self) -> None:
        # Never cache during QA, or a rebuild will not be picked up.
        self.send_header('Cache-Control', 'no-store, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        return  # keep the QA output readable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8090)
    parser.add_argument('--dir', default='build/web')
    args = parser.parse_args()

    root = pathlib.Path(args.dir).resolve()
    if not (root / FALLBACK).exists():
        print(f'{FALLBACK} not found in {root}. Run `flutter build web` first.')
        return 1

    handler = functools.partial(SPAHandler, directory=str(root))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('127.0.0.1', args.port), handler) as httpd:
        print(f'ClinSync web build served at http://127.0.0.1:{args.port}  (root: {root})')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nstopped')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
