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
with sync_playwright() as p:
    e = dict(os.environ); e['LD_LIBRARY_PATH'] = ':'.join(os.path.join(os.path.dirname(exe), d) for d in ('syslibs','libs','shim'))
    b = p.chromium.launch(executable_path=exe, env=e, args=['--no-sandbox','--disable-dev-shm-usage'])
    ctx = b.new_context(viewport={'width':1280,'height':1000}); pg = ctx.new_page()
    pg.goto(base+'admin-review.html', wait_until='load'); pg.wait_for_timeout(800)
    pg.evaluate("() => { const m=document.querySelector('#modal'); if(m) m.classList.remove('open'); }")
    rows = pg.evaluate("""() => Array.from(document.querySelectorAll('#reviewList tbody tr')).map(r => ({
        t: r.textContent.replace(/\\s+/g,' ').slice(0,90),
        urg: !!r.querySelector('.urgent-badge:not(.off)'),
        off: !!r.querySelector('.urgent-badge.off') }))""")
    for r in rows: print(r)
    b.close()
s.shutdown()
