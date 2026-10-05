"""Capture the Home hero headline mid-animation, to check the line reveal.

Reloads `#/home` (so `LineReveal` remounts and replays) and grabs the hero
region at a series of offsets, writing a contact sheet per frame.

Usage:
    .venv/bin/python tools/capture_hero_frames.py
    .venv/bin/python tools/capture_hero_frames.py --at 0 150 400 900 1400

Frames land in /tmp/ref/frames/.
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

import websocket

PORT = 9335
BASE = 'http://127.0.0.1:8090'
OUT = pathlib.Path('/tmp/ref/frames')

# The hero region: below the top bar, through the headline and subtitle.
HERO_CLIP = {'x': 0, 'y': 60, 'width': 430, 'height': 380, 'scale': 1}


def launch():
    return subprocess.Popen(
        [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '--headless=new', '--disable-gpu', '--hide-scrollbars',
            f'--remote-debugging-port={PORT}', '--remote-allow-origins=*',
            '--user-data-dir=/tmp/clinsync-hero',
            '--window-size=430,932', '--force-device-scale-factor=2',
            f'{BASE}/#/home',
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


class Cdp:
    def __init__(self, ws):
        self.ws = ws
        self._id = 0
        self.exceptions = []

    def cmd(self, method, **params):
        self._id += 1
        self.ws.send(
            json.dumps({'id': self._id, 'method': method, 'params': params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('method') == 'Runtime.exceptionThrown':
                det = msg['params']['exceptionDetails']
                self.exceptions.append(det.get('text', ''))
            if msg.get('id') == self._id:
                return msg.get('result', {})

    def shot(self, name, clip=None):
        params = {'format': 'png'}
        if clip:
            params['clip'] = clip
        data = self.cmd('Page.captureScreenshot', **params)['data']
        (OUT / f'{name}.png').write_bytes(base64.b64decode(data))
        print(f'  frame {name}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--at', type=int, nargs='*',
                    default=[0, 140, 300, 500, 750, 1050, 1400],
                    help='offsets in ms from the start of the sampling window')
    ap.add_argument('--boot', type=float, default=4.0,
                    help='seconds to wait after reload before sampling starts; '
                         'tune so the window lands inside the reveal')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    proc = launch()
    time.sleep(10)
    targets = json.loads(
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list').read())
    page = next(t for t in targets if t.get('type') == 'page')
    ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=90)
    cdp = Cdp(ws)
    cdp.cmd('Page.enable')
    cdp.cmd('Runtime.enable')

    # A reload remounts HomeScreen, which is what replays LineReveal. The reveal
    # runs on the first frame after the hero mounts, so `--boot` must be short
    # enough to land inside it — each screenshot also costs ~100 ms, so the
    # printed offsets are later than requested.
    cdp.cmd('Page.reload', ignoreCache=False)
    time.sleep(args.boot)

    elapsed = 0
    for ms in sorted(args.at):
        wait = (ms - elapsed) / 1000.0
        if wait > 0:
            time.sleep(wait)
        elapsed = ms
        cdp.shot(f'hero_{ms:04d}ms', HERO_CLIP)

    ws.close()
    proc.terminate()
    print(f'Exceptions: {len(cdp.exceptions)}')
    print(f'Frames -> {OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
