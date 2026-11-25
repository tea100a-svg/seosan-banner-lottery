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
okn = 0; bad = []
def ok(n, c, x=''):
    global okn
    if c: okn += 1; print('  OK  ', n)
    else: bad.append(n); print('  FAIL', n, str(x)[:200])

with sync_playwright() as p:
    e = dict(os.environ); e['LD_LIBRARY_PATH'] = ':'.join(os.path.join(os.path.dirname(exe), d) for d in ('syslibs','libs','shim'))
    b = p.chromium.launch(executable_path=exe, env=e, args=['--no-sandbox','--disable-dev-shm-usage'])
    ctx = b.new_context(viewport={'width':1400,'height':1000}); pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda x: errs.append(str(x)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    for page, key in [('admin-political.html','political'), ('admin-loc.html','loc'), ('admin-official-review.html','officialreview')]:
        pg.goto(base+page, wait_until='load'); pg.wait_for_timeout(700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); } catch (e) {} }")
        pg.wait_for_timeout(400)
        subs = pg.eval_on_selector_all('#adminSub a', 'els => els.map(e => [e.getAttribute("data-adminsub"), e.classList.contains("on")])')
        on_key = [k for k, o in subs if o]
        print(page, 'subtab order', [k for k, _ in subs][:6], 'on=', on_key)
        ok(page + ' 서브탭 3번째 = 2주 공문 심사', [k for k, _ in subs][:3] == ['review','official','officialreview'], subs[:4])
        ok(page + ' 서브탭 순서(정치행정 4번째)', [k for k, _ in subs][3] == 'political', subs[:5])
        ok(page + ' 자기 탭 활성', on_key == [key], on_key)
    # 정치행정 데이터
    pg.goto(base+'admin-political.html', wait_until='load'); pg.wait_for_timeout(700)
    pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
    pg.wait_for_timeout(400)
    pol = pg.eval_on_selector_all('#polList tbody tr', 'e => e.length')
    ok('정치행정 심사 목록 렌더', pol > 0, pol)
    # 게시위치
    pg.goto(base+'admin-loc.html', wait_until='load'); pg.wait_for_timeout(800)
    pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
    pg.wait_for_timeout(500)
    items = pg.eval_on_selector_all('#locList .loc-item', 'e => e.length')
    pg.click('#locList .loc-item')
    pg.wait_for_timeout(400)
    btn = pg.eval_on_selector('td [data-locdeliver]', 'e => e.textContent.trim()') if pg.query_selector("td [data-locdeliver]") else ''
    ok('게시위치 목록·입고확인 버튼', items > 0 and ('입고' in (btn or '')), (items, btn))
    # 2주 공문 심사
    pg.goto(base+'admin-official-review.html', wait_until='load'); pg.wait_for_timeout(700)
    pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
    pg.wait_for_timeout(400)
    rv = pg.evaluate("() => ({ info: (document.querySelector('#offReviewInfo')||{}).textContent, rows: document.querySelectorAll('#offReviewList tbody tr').length, btns: document.querySelectorAll('#offReviewList [data-offapprove]').length })")
    ok('2주 공문 심사 목록 렌더', '결재 대기' in (rv['info'] or ''), rv)
    # 권한 매트릭스
    pg.goto(base+'admin-roles.html', wait_until='load'); pg.wait_for_timeout(800)
    pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
    pg.wait_for_timeout(500)
    mx = pg.evaluate("() => window.SEOSAN_VERIFY.permMatrix()")
    ok('권한 매트릭스 9직책 × 17페이지', mx and mx['rows'] == 17 and mx['cols'] == 9 and mx['cells'] == 153, mx)
    # 사무실무원1에서 권한해제 → 탭 숨김
    pg.evaluate("() => window.SEOSAN_VERIFY.setPerm('staff1', 'photos', false)")
    pg.wait_for_timeout(300)
    pg.evaluate("() => window.SEOSAN_VERIFY.setRole('staff')")
    pg.wait_for_timeout(400)
    tabs = pg.evaluate("() => window.SEOSAN_VERIFY.visibleTabs()")
    ok('사무실무원1 — 게첨사진 탭 숨김', 'photos' not in tabs and 'review' in tabs, tabs)
    ok('사무실무원1 — 관리자 권한 탭 숨김', 'roles' not in tabs, tabs)
    pg.goto(base+'admin-photos.html', wait_until='load'); pg.wait_for_timeout(700)
    lock = pg.query_selector('#permLockBox')
    ok('권한 없는 페이지 직접 접근 차단', bool(lock), lock)
    # 복원 + 총괄에서 roles 노출
    pg.evaluate("() => { try { window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.setPerm('staff1','photos',true); } catch (e) {} }")
    pg.wait_for_timeout(200)
    pg.goto(base+'admin-photos.html', wait_until='load'); pg.wait_for_timeout(500)
    pg.evaluate("() => window.SEOSAN_VERIFY.setRole('super')")
    pg.wait_for_timeout(300)
    ok('총괄 — 복원 후 접근 가능', not pg.query_selector('#permLockBox'))
    pg.goto(base+'admin-roles.html', wait_until='load'); pg.wait_for_timeout(400)
    pg.evaluate("() => window.SEOSAN_VERIFY.setRole('staff')")
    pg.wait_for_timeout(400)
    ok('비총괄 — 관리자 권한 페이지 잠금', bool(pg.query_selector('#permLockBox')))
    ok('콘솔 오류 0', not errs, errs[:3])
    b.close()
s.shutdown()
print('\n통과', okn, '실패', len(bad), bad)
