"""Prove the built web app actually talks to the running backend.

`flutter analyze` passing says nothing about whether the two halves are wired
together: a wrong base URL still builds cleanly and every screen just renders
its own error state. This loads the app in headless Chrome — the same build that
`tools/serve_web.py` serves — and records the network requests it makes.

Usage:
    PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --port 8000 &
    .venv/bin/python tools/serve_web.py --port 8090 &
    .venv/bin/python tools/check_link.py

Exit code 0 when the app made real API calls and none failed; 1 otherwise.
"""
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

import websocket

PORT = 9334
BASE = 'http://127.0.0.1:8090'
PATIENT = 'pat_demo_patient_001'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

# Routes whose screens must fetch from the API to render anything real.
ROUTES = [
    '/home',
    '/patients',
    f'/patients/{PATIENT}',
    f'/patients/{PATIENT}/documents',
    f'/patients/{PATIENT}/medications',
    f'/patients/{PATIENT}/issues',
    f'/patients/{PATIENT}/brief',
    f'/patients/{PATIENT}/memory',
]


def launch():
    proc = subprocess.Popen(
        [
            CHROME,
            '--headless=new', '--disable-gpu', '--hide-scrollbars',
            f'--remote-debugging-port={PORT}', '--remote-allow-origins=*',
            '--user-data-dir=/tmp/clinsync-chrome-link',
            '--window-size=430,932',
            f'{BASE}/#/home',
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(10)
    return proc


def connect():
    targets = json.loads(
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list').read()
    )
    page = next(t for t in targets if t.get('type') == 'page')
    return websocket.create_connection(page['webSocketDebuggerUrl'], timeout=90)


class Cdp:
    """Just enough CDP to open a page and read its network log."""

    def __init__(self, ws):
        self.ws = ws
        self._id = 0
        self.calls: list[dict] = []
        self._route = ''

    def cmd(self, method, **params):
        self._id += 1
        self.ws.send(
            json.dumps({'id': self._id, 'method': method, 'params': params})
        )
        while True:
            msg = self._recv()
            if msg.get('id') == self._id:
                return msg.get('result', {})

    def _recv(self):
        msg = json.loads(self.ws.recv())
        if msg.get('method') == 'Network.responseReceived':
            r = msg['params']['response']
            url = r.get('url', '')
            if '/api/' in url:
                self.calls.append(
                    {'route': self._route, 'url': url, 'status': r['status']}
                )
        return msg

    def drain(self, seconds=0.4):
        """Absorb late responses so they are not labelled with the next route.

        `Page.navigate` returns long before the new page finishes fetching, so
        without this the last responses of one route get attributed to the next.
        """
        self.ws.settimeout(seconds)
        try:
            while True:
                self._recv()
        except Exception:
            pass
        finally:
            self.ws.settimeout(90)

    def visit(self, route):
        self.drain()
        self._route = route
        self.cmd('Page.navigate', url=f'{BASE}/#{route}')
        # Give the Flutter engine time to boot and finish its first fetches.
        time.sleep(6.0)


def main() -> int:
    if not pathlib.Path(CHROME).exists():
        raise SystemExit(f'Chrome not found at {CHROME}')

    proc = launch()
    try:
        cdp = Cdp(connect())
        cdp.cmd('Page.enable')
        cdp.cmd('Network.enable')
        for route in ROUTES:
            cdp.visit(route)

        # Collapse duplicates; a screen legitimately re-fetches on reload.
        seen: dict[tuple, dict] = {}
        for c in cdp.calls:
            seen[(c['route'], c['url'], c['status'])] = c
        calls = sorted(seen.values(), key=lambda x: (x['route'], x['url']))

        print(f'{"route":<42} {"status":<7} api call')
        print('-' * 104)
        for c in calls:
            print(f'{c["route"]:<42} {c["status"]:<7} '
                  f'{c["url"].replace("http://localhost:8000", "")}')

        ok = [c for c in calls if 200 <= c['status'] < 300]
        bad = [c for c in calls if c['status'] >= 400]

        print('-' * 104)
        print(f'{len(ok)} successful, {len(bad)} failed, {len(calls)} distinct')

        if not ok:
            print('\nFAIL: the app made no successful API call — it is NOT linked.')
            return 1
        if bad:
            print(f'\nFAIL: {len(bad)} API call(s) returned an error status.')
            for c in bad:
                print(f'  {c["status"]}  {c["route"]}  {c["url"]}')
            return 1

        print('\nPASS: the built app is reading live data from the backend.')
        return 0
    finally:
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == '__main__':
    sys.exit(main())
