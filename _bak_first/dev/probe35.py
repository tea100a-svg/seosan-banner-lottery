import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_multipage as V
from playwright.sync_api import sync_playwright
srv, base = V.start_server()
with sync_playwright() as p:
    b=V.launch(p); ctx=b.new_context(viewport={'width':1280,'height':1000}); pg=ctx.new_page(); pg.set_default_timeout(12000)
    w=V.Watcher(pg, base)
    V.goto(pg, base+'apply.html', 600)
    pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
    print('unit', pg.evaluate("""() => { const v=window.SEOSAN_VERIFY; return { a: v.checkText('병 신 같은 놈'), m: v.checkText('베트남 처녀 신부 알선'), ok: v.checkText('해미읍성 야간 문화행사') }; }"""))
    pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({ company:'햇살농원', owner:'김정수', phone:'010-1111-2222', advertiser:'햇살농원', text:'병신 같은 놈', qty:1, agree:true })""")
    pg.wait_for_timeout(300)
    print('note', pg.evaluate("() => window.SEOSAN_VERIFY.abuseNote('#abuseNote')"))
    print('valid', pg.evaluate("() => window.SEOSAN_VERIFY.validateStep(1)"))
    V.goto(pg, base+'admin-review.html', 600)
    print('review first has 임박', pg.evaluate("() => { const t=document.querySelector('#reviewList tbody tr'); return t ? t.textContent.indexOf('임박')>=0 : null; }"))
    V.goto(pg, base+'admin-desig.html', 500)
    print('desig', pg.evaluate("() => { const b=document.querySelector('#btnDesigBatchAllPrint'), t=document.querySelector('#desigBatchList'); if(!b||!t) return null; return [Math.round(b.getBoundingClientRect().top), Math.round(t.getBoundingClientRect().top)]; }"))
    print('problems', w.problems()[:3])
    ctx.close(); b.close()
srv.shutdown()
