# -*- coding: utf-8 -*-
"""remain.html / first.html 두 창구 분리 점검."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_multipage as V
from playwright.sync_api import sync_playwright

srv, base = V.start_server()
with sync_playwright() as p:
    b = V.launch(p)
    for name in ('remain.html', 'first.html'):
        ctx = b.new_context(viewport={'width': 1400, 'height': 1000})
        pg = ctx.new_page(); pg.set_default_timeout(12000)
        w = V.Watcher(pg, base)
        V.goto(pg, base + name, 700)
        print('==', name, 'problems', w.problems()[:2])
        print(' chips', (pg.text_content('#fcModeChips') or '').replace('\n', ' '))
        print(' state', pg.evaluate("() => window.SEOSAN_VERIFY.fcState()"))
        print(' max', pg.evaluate("() => window.SEOSAN_VERIFY.fcMax()"), 'rows',
              pg.eval_on_selector_all('#firstList .fc-item', 'e => e.length'),
              'btn', pg.eval_on_selector_all('[data-fcpick]:not([disabled])', 'e => e.length'))
        print(' banner', (pg.text_content('#fcBanner') or '')[:100].replace('\n', ' '))
        pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
        st = pg.evaluate("""() => window.SEOSAN_VERIFY.fcSet({ advertiser: '분리검증광고주', text: '두 창구 분리 검증 문구',
            file: true, agree: true, license: true, qty: 1, picks: 'auto' })""")
        print(' set', st)
        print(' next1', pg.evaluate("() => window.SEOSAN_VERIFY.fcNext()"), pg.evaluate("() => window.SEOSAN_VERIFY.fcStep()"))
        if name == 'first.html':
            print(' validate2(open?)', pg.evaluate("() => window.SEOSAN_VERIFY.fcValidate(2)"))
        else:
            print(' next2', pg.evaluate("() => window.SEOSAN_VERIFY.fcNext()"), pg.evaluate("() => window.SEOSAN_VERIFY.fcStep()"))
        ctx.close()
    b.close()
srv.shutdown()
