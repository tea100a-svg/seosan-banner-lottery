# -*- coding: utf-8 -*-
"""배포본(_deploy)에서 index.html 게시대 접수 버튼이 보이는지 확인."""
import functools, http.server, os, socketserver, threading
from playwright.sync_api import sync_playwright
import verify_multipage as V

ROOT = os.path.abspath('../_deploy')
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT))
srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = 'http://127.0.0.1:%d/' % srv.server_address[1]
with sync_playwright() as p:
    b = V.launch(p)
    ctx = b.new_context(viewport={'width': 1280, 'height': 900})
    pg = ctx.new_page()
    pg.set_default_timeout(8000)
    V.goto(pg, base + 'index.html', 500)
    print('problems', V.Watcher(pg, base).problems())
    pid = pg.evaluate("() => { const p = window.SEOSAN_VERIFY.state().placements.filter(x => !x.broken)[0]; return p ? p.id : ''; }")
    print('pid', pid)
    els = pg.eval_on_selector_all('[data-apply]', 'els => els.length')
    print('data-apply buttons', els)
    vis = pg.evaluate("""(id) => { const el = document.querySelector('#placementGrid [data-apply="'+id+'"]');
        if (!el) return null; const r = el.getBoundingClientRect();
        return { display: getComputedStyle(el).display, w: r.width, h: r.height,
          gridDisplay: getComputedStyle(el.closest('.pl-fold') || el.parentElement).display }; }""", pid)
    print('vis', vis)
    print('grid html len', len(pg.inner_html('#placementGrid') or ''))
    ctx.close(); b.close()
srv.shutdown()
