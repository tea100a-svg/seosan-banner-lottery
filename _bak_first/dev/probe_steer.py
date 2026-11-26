# -*- coding: utf-8 -*-
"""공문 자동배정/만석·인접추천 · 작업지시서 날짜 · 검색 자동펼침 점검."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_multipage as V
from playwright.sync_api import sync_playwright

srv, base = V.start_server()
with sync_playwright() as p:
    b = V.launch(p)
    ctx = b.new_context(viewport={'width': 1400, 'height': 1100})
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    w = V.Watcher(pg, base)
    V.goto(pg, base + 'admin-official.html', 800)
    if pg.query_selector('#adminRoleSel'):
        pg.select_option('#adminRoleSel', 'staff')
        pg.wait_for_timeout(300)
    print('problems1', w.problems()[:3])
    pg.click('[data-offsample="traffic"]')
    pg.wait_for_timeout(700)
    st = pg.evaluate("""() => ({ form: window.SEOSAN_VERIFY.offForm(), hits: window.SEOSAN_VERIFY.offHits(),
        rec: window.SEOSAN_VERIFY.offRec(), sel: window.SEOSAN_VERIFY.offSel(),
        box: (document.querySelector('#offRecBox')||{}).textContent || '',
        pick: (document.querySelector('#offQtyLine')||{}).textContent || '' })""")
    print('form', st['form'])
    print('hits', st['hits'][:220])
    print('rec', st['rec'])
    print('sel', st['sel'])
    print('box', st['box'][:300])
    print('pick', st['pick'])
    btns = pg.eval_on_selector_all('[data-offrec]', 'els => els.map(e => e.getAttribute("data-offrec"))')
    print('rec buttons', btns)
    if btns:
        pg.click('[data-offrec="%s"]' % btns[0])
        pg.wait_for_timeout(400)
        print('after click sel', pg.evaluate("() => window.SEOSAN_VERIFY.offSel()"),
              'line', pg.text_content('#offQtyLine'))
    print('problems2', w.problems()[:3])

    # 작업지시서 날짜
    V.goto(pg, base + 'admin-docs.html', 800)
    print('wo head', pg.evaluate("() => window.SEOSAN_VERIFY.woHead()"))
    print('wo week', pg.evaluate("() => window.SEOSAN_VERIFY.woWeek()"))
    pg.fill('#woDatePick', '2026-12-07')
    pg.wait_for_timeout(600)
    print('wo head2', pg.evaluate("() => window.SEOSAN_VERIFY.woHead()"))
    print('wo week2', pg.evaluate("() => window.SEOSAN_VERIFY.woWeek()"))
    print('problems3', w.problems()[:3])

    # 검색 자동 펼침
    V.goto(pg, base + 'index.html', 600)
    print('fold hidden before', pg.evaluate("() => { const b=document.getElementById('placementFold'); return b ? b.hidden : null; }"))
    pg.fill('#statusSearch', '의료원')
    pg.wait_for_timeout(500)
    print('fold hidden after', pg.evaluate("() => { const b=document.getElementById('placementFold'); return b ? b.hidden : null; }"))
    print('rows', pg.eval_on_selector_all('#placementGrid .plrow', 'els => els.length'))
    print('kpi', pg.text_content('#statusStats')[:120].replace('\n', ' '))
    print('overlap', pg.evaluate("""() => { const wrap=document.querySelector('.search-lg'); const svg=wrap.querySelector('svg');
        const inp=wrap.querySelector('input'); const a=svg.getBoundingClientRect(), b=inp.getBoundingClientRect();
        return { svgRight: Math.round(a.right), inputLeft: Math.round(b.left), overlap: a.right > b.left + 1,
          svgPos: getComputedStyle(svg).position }; }"""))
    print('problems4', w.problems()[:3])
    ctx.close(); b.close()
srv.shutdown()
