import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_multipage as V
from playwright.sync_api import sync_playwright
srv, base = V.start_server()
pages = ['index.html','apply.html','remain.html','first.html','admin-deliver.html','admin-desig.html','admin-docs.html','admin-official.html','mypage.html']
with sync_playwright() as p:
    b=V.launch(p)
    for name in pages:
        ctx=b.new_context(viewport={'width':1280,'height':900}); pg=ctx.new_page(); pg.set_default_timeout(12000)
        w=V.Watcher(pg, base); V.goto(pg, base+name, 500)
        extra={}
        if name=='admin-deliver.html':
            pg.fill('#deliverSearch','햇살'); pg.wait_for_timeout(300)
            extra['rows']=pg.eval_on_selector_all('#deliverTable tbody tr','e=>e.length')
            extra['info']=(pg.text_content('#deliverInfo') or '')[:60]
        if name=='admin-desig.html':
            extra['topbtn']=pg.evaluate("() => { const b=document.querySelector('#btnDesigBatchAllPrint'); if(!b) return null; const r=b.getBoundingClientRect(); return {y: Math.round(r.top+window.scrollY), h: Math.round(r.height)}; }")
        if name=='admin-docs.html':
            extra['wo']=pg.evaluate("() => window.SEOSAN_VERIFY.woHead()['week']")
        if name=='index.html':
            extra['nav']=pg.evaluate("() => Array.from(document.querySelectorAll('nav.site-nav a')).map(a=>[a.getAttribute('href'), a.classList.contains('hidden')])")
            extra['today']=pg.eval_on_selector_all('#weekStrip .wk.today','e=>e.length')
            extra['now']=pg.evaluate("() => window.SEOSAN_VERIFY.now()")
        print(name, 'problems', w.problems()[:2], extra)
        ctx.close()
    b.close()
srv.shutdown()
