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
UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 '
      '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')
exe = '/workspace/.preview-run/chrome-headless-shell'
with sync_playwright() as p:
    e = dict(os.environ); e['LD_LIBRARY_PATH'] = ':'.join(os.path.join(os.path.dirname(exe), d) for d in ('syslibs','libs','shim'))
    b = p.chromium.launch(executable_path=exe, env=e, args=['--no-sandbox','--disable-dev-shm-usage'])
    ctx = b.new_context(viewport={'width':360,'height':800}, user_agent=UA, is_mobile=True, has_touch=True)
    pg = ctx.new_page(); pg.goto(base+'index.html', wait_until='load'); pg.wait_for_timeout(700)
    pg.evaluate("() => { const m=document.querySelector('#modal'); if(m) m.classList.remove('open'); }")
    info = pg.evaluate("""() => Array.prototype.slice.call(document.querySelectorAll('nav.site-nav a.tab, #mobileTabbar a'))
        .map(el => ({t: el.textContent.trim().slice(0,8), h: Math.round(el.getBoundingClientRect().height), w: Math.round(el.getBoundingClientRect().width), cls: el.className}))""")
    print(info)
    b.close()
s.shutdown()
