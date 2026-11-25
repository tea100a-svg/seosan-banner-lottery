# -*- coding: utf-8 -*-
import functools, http.server, os, socketserver, threading
from playwright.sync_api import sync_playwright
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
h = functools.partial(Q, directory=ROOT)
s = socketserver.ThreadingTCPServer(('127.0.0.1', 0), h); s.daemon_threads = True
threading.Thread(target=s.serve_forever, daemon=True).start()
base = 'http://127.0.0.1:%d/' % s.server_address[1]
exe = '/workspace/.preview-run/chrome-headless-shell'
errs = []
with sync_playwright() as p:
    e = dict(os.environ); e['LD_LIBRARY_PATH'] = ':'.join(os.path.join(os.path.dirname(exe), d) for d in ('syslibs','libs','shim'))
    b = p.chromium.launch(executable_path=exe, env=e, args=['--no-sandbox','--disable-dev-shm-usage'])
    ctx = b.new_context(viewport={'width':1280,'height':1000}); pg = ctx.new_page()
    pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    pg.on('pageerror', lambda e2: errs.append('ERR '+str(e2)))
    pg.goto(base+'index.html', wait_until='load'); pg.wait_for_timeout(900)
    print('rule strip:', repr(pg.text_content('#weekRuleStrip'))[:200])
    print('strip2:', repr(pg.text_content('#applyRuleStrip') if pg.query_selector('#applyRuleStrip') else None))
    print('errors:', errs[:5])
    b.close()
s.shutdown()
