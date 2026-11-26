import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_multipage as V
from playwright.sync_api import sync_playwright
srv, base = V.start_server()
with sync_playwright() as p:
    b=V.launch(p); ctx=b.new_context(viewport={'width':1400,'height':1000}); pg=ctx.new_page(); pg.set_default_timeout(12000)
    w=V.Watcher(pg, base)
    V.goto(pg, base+'remain.html', 600)
    pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
    print('youth boards', len(pg.evaluate("() => window.SEOSAN_VERIFY.youthList()")))
    pg.evaluate("""() => window.SEOSAN_VERIFY.fcSet({ advertiser:'나이트 유흥주점', text:'유흥주점 19금 이벤트', file:true, agree:true, license:true, qty:1, picks:[] })""")
    pg.wait_for_timeout(300)
    print('note', pg.evaluate("() => window.SEOSAN_VERIFY.abuseNote('#fcYouthNote')"))
    print('hit', pg.evaluate("() => window.SEOSAN_VERIFY.youthHit('나이트 유흥주점')"))
    yid = pg.evaluate("() => window.SEOSAN_VERIFY.youthList()[0]")
    print('toggle off', pg.evaluate("(p) => window.SEOSAN_VERIFY.youthToggle(p, false)", yid), 'toggle on', pg.evaluate("(p) => window.SEOSAN_VERIFY.youthToggle(p, true)", yid))
    print('problems', w.problems()[:3])
    ctx.close(); b.close()
srv.shutdown()
