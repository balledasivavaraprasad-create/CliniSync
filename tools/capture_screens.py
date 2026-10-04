"""Capture screenshots of every ClinSync route from the built web app.

Drives headless Chrome over the DevTools protocol; each route is loaded as a
full page load so go_router resolves it the same way a cold start would.

`flutter build web` defaults to Flutter's **hash** URL strategy, so routes are
addressed as `/#/patients/<id>`. The mobile targets use real paths.
"""
import base64
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

import websocket

PORT = 9333
BASE = 'http://127.0.0.1:8090'
PATIENT = 'pat_demo_patient_001'
OUT = pathlib.Path('/tmp/ref/shots')
OUT.mkdir(parents=True, exist_ok=True)

ROUTES = [
    ('01_home', '/home'),
    ('02_patients', '/patients'),
    ('03_overview', f'/patients/{PATIENT}'),
    ('04_documents', f'/patients/{PATIENT}/documents'),
    ('05_timeline', f'/patients/{PATIENT}/timeline'),
    ('06_medications', f'/patients/{PATIENT}/medications'),
    ('07_investigations', f'/patients/{PATIENT}/investigations'),
    ('08_issues', f'/patients/{PATIENT}/issues'),
    ('09_facts', f'/patients/{PATIENT}/facts'),
    ('10_reconcile', f'/patients/{PATIENT}/medications/metformin/reconcile?name=Metformin'),
    ('11_trend', f'/patients/{PATIENT}/investigations/{PATIENT}:hba1c/trend?name=HbA1c'),
    ('12_specialty', '/specialty?patient=' + PATIENT),
    ('13_brief', f'/patients/{PATIENT}/brief'),
    ('14_consultation', f'/patients/{PATIENT}/consultation?specialty=diabetology'),
    ('15_memory', f'/patients/{PATIENT}/memory'),
    ('16_records', '/records'),
    ('17_memory_tab', '/memory'),
    ('18_tokens', '/galleries/tokens'),
    ('19_components', '/galleries/components'),
    ('20_camera', f'/camera/{PATIENT}'),
    ('21_voice', f'/voice/{PATIENT}'),
]


def launch():
    proc = subprocess.Popen(
        [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '--headless=new', '--disable-gpu', '--hide-scrollbars',
            f'--remote-debugging-port={PORT}', '--remote-allow-origins=*',
            '--user-data-dir=/tmp/clinsync-chrome',
            '--window-size=430,932', '--force-device-scale-factor=2',
            f'{BASE}/#/home',
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(10)
    return proc


def connect():
    targets = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list').read())
    page = next(t for t in targets if t.get('type') == 'page')
    return websocket.create_connection(page['webSocketDebuggerUrl'], timeout=90)


class Cdp:
    def __init__(self, ws):
        self.ws = ws
        self._id = 0
        self.errors = []

    def cmd(self, method, **params):
        self._id += 1
        self.ws.send(json.dumps({'id': self._id, 'method': method, 'params': params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('method') == 'Runtime.exceptionThrown':
                det = msg['params']['exceptionDetails']
                self.errors.append(det.get('text', '') + ' ' + str(det.get('exception', {}).get('description', ''))[:300])
            if msg.get('id') == self._id:
                return msg.get('result', {})

    def goto(self, url, wait=6.0):
        self.cmd('Page.navigate', url=url)
        time.sleep(wait)

    def shot(self, name):
        r = self.cmd('Page.captureScreenshot', format='png')
        (OUT / f'{name}.png').write_bytes(base64.b64decode(r['data']))
        print('  shot', name)


def main():
    only = set(sys.argv[1:])
    proc = launch()
    cdp = Cdp(connect())
    cdp.cmd('Page.enable')
    cdp.cmd('Runtime.enable')
    cdp.cmd('Log.enable')
    try:
        for name, route in ROUTES:
            if only and name not in only:
                continue
            cdp.goto(f'{BASE}/#{route}')
            cdp.shot(name)
    finally:
        print('\nDart/JS exceptions seen:', len(cdp.errors))
        for e in cdp.errors[:20]:
            print('  !', e)
        proc.terminate()
    print('shots ->', OUT)


if __name__ == '__main__':
    main()
