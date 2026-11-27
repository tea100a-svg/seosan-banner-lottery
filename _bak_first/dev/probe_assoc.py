# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_multipage as V
from playwright.sync_api import sync_playwright
srv, base = V.start_server()
with sync_playwright() as p:
    b = V.launch(p)
    ctx = b.new_context(viewport={'width': 1400, 'height': 1000})
    pg = ctx.new_page(); pg.set_default_timeout(15000)
    w = V.Watcher(pg, base)
    V.goto(pg, base + 'admin-members.html', 600)
    r = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY;
        v.setRole('chief'); v.assocSet('M-1002', true, '5');
        v.setRole('staff'); v.assocSet('M-1002', true, '2');
        v.setRole('staff'); v.assocSet('M-1002', true, '0');
        return { grants: v.assocGrants('M-1002'), total: v.assocGrantTotal('M-1002'), panel: v.assocPanel() }; }""")
    print('total', r['total'], 'grants', r['grants'])
    print('info', r['panel']['info'][:200])
    html = r['panel']['html']
    print('html snippet', html[:600].replace('\n', ' '))
    print('has 합계 +5%', '합계 +5%' in html, '| has 지부장 김서산 +5%', '지부장 김서산 +5%' in html)
    print('problems', w.problems()[:3])
    ctx.close(); b.close()
srv.shutdown()
