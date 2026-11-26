# -*- coding: utf-8 -*-
"""first.html 4단계 — 목요일 선착순 창구 점검."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_multipage as V
from playwright.sync_api import sync_playwright

srv, base = V.start_server()
with sync_playwright() as p:
    b = V.launch(p)
    ctx = b.new_context(viewport={'width': 1400, 'height': 1000})
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    w = V.Watcher(pg, base)
    V.goto(pg, base + 'first.html', 800)
    pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
    print('set', pg.evaluate("() => window.SEOSAN_VERIFY.fcSet({mode:'next', daySim:'thu', fcTime:'open', advertiser:'목요검증광고주', text:'목요 선착순 검증 문구', file:true, agree:true, license:true, qty:3, picks:'auto'})"))
    print('banner', (pg.text_content('#fcBanner') or '')[:120].replace('\n', ' '))
    print('nextA', pg.evaluate("() => window.SEOSAN_VERIFY.fcNext()"), pg.evaluate("() => window.SEOSAN_VERIFY.fcStep()"))
    print('nextB', pg.evaluate("() => window.SEOSAN_VERIFY.fcNext()"), pg.evaluate("() => window.SEOSAN_VERIFY.fcStep()"))
    print('nextC', pg.evaluate("() => window.SEOSAN_VERIFY.fcNext()"), pg.evaluate("() => window.SEOSAN_VERIFY.fcStep()"))
    print('summary', (pg.evaluate("() => window.SEOSAN_VERIFY.fcSummary()") or '')[:260].replace('\n', ' '))
    before = pg.evaluate("() => window.SEOSAN_VERIFY.apps().length")
    print('submit', pg.evaluate("() => window.SEOSAN_VERIFY.fcSubmit()"))
    print('apps', before, pg.evaluate("() => window.SEOSAN_VERIFY.apps().length"))
    print('due', pg.evaluate("() => { const a = window.SEOSAN_VERIFY.state().apps.slice(-1)[0]; return {id:a.id,status:a.status,due:a.deliveryDue,firstCome:a.firstCome,qty:a.qty,places:a.assignedPlaces}; }"))
    print('modal', (pg.text_content('#modalBody') or '')[:140].replace('\n', ' '))
    print('problems:', w.problems()[:5])
    # 다음 건 접수 → 상단 이동 · 1단계 초기화
    pg.click('#btnFcDone')
    pg.wait_for_timeout(400)
    print('after done step', pg.evaluate("() => window.SEOSAN_VERIFY.fcStep()"),
          'adv', pg.evaluate("() => (document.querySelector('#fcAdvertiser')||{}).value"),
          'scrollY', pg.evaluate("() => window.scrollY"))
    print('problems2:', w.problems()[:5])
    ctx.close(); b.close()
srv.shutdown()
