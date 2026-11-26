# -*- coding: utf-8 -*-
"""목요일 공휴일 · 목요일 링크 · 요일 필터 · 시연 달력 스모크 테스트"""
import functools, http.server, os, socketserver, threading, sys, json
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def srv():
    h = functools.partial(Q, directory=ROOT)
    s = socketserver.ThreadingTCPServer(('127.0.0.1', 0), h)
    s.daemon_threads = True
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, 'http://127.0.0.1:%d/' % s.server_address[1]


def launch(p):
    exe = '/workspace/.preview-run/chrome-headless-shell'
    if os.path.exists(exe):
        e = dict(os.environ)
        base = os.path.dirname(exe)
        e['LD_LIBRARY_PATH'] = ':'.join(os.path.join(base, d) for d in ('syslibs', 'libs', 'shim'))
        return p.chromium.launch(executable_path=exe, env=e, args=['--no-sandbox', '--disable-dev-shm-usage'])
    return p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])


okn = 0
bad = []


def ok(name, cond, extra=''):
    global okn
    if cond:
        okn += 1
        print('  OK  ', name)
    else:
        bad.append(name + (' — ' + str(extra) if extra else ''))
        print('  FAIL', name, extra)


s, base = srv()
with sync_playwright() as p:
    b = launch(p)
    ctx = b.new_context(viewport={'width': 1280, 'height': 1000})
    pg = ctx.new_page()
    errs = []
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)))
    pg.goto(base + 'index.html', wait_until='load')
    pg.wait_for_timeout(600)
    # 공지 모달 닫기
    pg.evaluate("() => { const m = document.querySelector('#modal'); if (m) m.classList.remove('open'); }")
    pg.click('#btnPlaceToggle')
    pg.wait_for_timeout(300)
    chips = pg.eval_on_selector_all('#statusDayChips button', 'els => els.map(e => e.textContent.trim())')
    ok('요일 필터 칩 = 전체·월·화·수', chips == ['전체', '월요일', '화요일', '수요일'], chips)
    pg.click('#statusDayChips button[data-day="화"]')
    pg.wait_for_timeout(300)
    cnt = pg.text_content('#statusListInfo')
    ok('화요일 필터 → 목록 22개소 내외', '화' not in cnt and ('표시 2' in cnt), cnt)
    rows = pg.eval_on_selector_all('#placementGrid .plrow, #placementGrid [data-detail]', 'e => e.length')
    ok('화요일 필터 행 렌더', rows > 0, rows)
    pg.click('#statusDayChips button[data-day=""]')
    pg.wait_for_timeout(200)

    # 목요일 → 타임라인 링크 first.html
    pg.evaluate("() => window.SEOSAN_VERIFY.setNow && window.SEOSAN_VERIFY.setNow('2026-11-26')")
    pg.wait_for_timeout(500)
    href = pg.eval_on_selector('#weekStrip a.wk.first', 'e => e.getAttribute("href")') if pg.query_selector('#weekStrip a.wk.first') else None
    ok('목요일 — 타임라인 취소분 카드가 first.html 링크', href == 'first.html', href)
    ok('목요일 — 취소분 메뉴 노출', pg.evaluate("() => !!document.querySelector('nav.site-nav a[href=\"first.html\"]:not(.hidden)')"))
    ok('목요일 — 취소분 접수 안내 배너', pg.evaluate("() => !!document.querySelector('#fcOpenNotice')"))

    # 공휴일 OFF 상태에서 금요일 → remain 링크
    pg.evaluate("() => window.SEOSAN_VERIFY.setNow('2026-11-27')")
    pg.wait_for_timeout(400)
    href2 = pg.eval_on_selector('#weekStrip a.wk.first', 'e => e.getAttribute("href")')
    ok('금요일(평시) — 타임라인 카드 → remain.html', href2 == 'remain.html', href2)
    ok('금요일(평시) — 취소분 메뉴 숨김', pg.evaluate("() => document.querySelector('nav.site-nav a[href=\"first.html\"]').classList.contains('hidden')"))

    # 공휴일 ON
    pg.click('[data-thuholy]')
    pg.wait_for_timeout(500)
    modal = pg.evaluate("() => { const m = document.querySelector('#modal'); return m && m.classList.contains('open') ? document.querySelector('#modalBody').textContent : ''; }")
    ok('공휴일 ON — 공지 팝업 자동 표시', ('공휴일 일정 안내' in (modal or '')) and ('금요일 14:00' in (modal or '')), (modal or '')[:120])
    ok('공휴일 ON — 오늘 하루 보지 않기 있음', pg.evaluate("() => !!document.querySelector('#holidayNoticeHide')"))
    pg.click('#btnHolidayOk')
    pg.wait_for_timeout(300)
    strip = pg.text_content('#weekStrip')
    ok('공휴일 ON — 타임라인 금요일 09:00~18:00 · 입고 14:00', ('금요일 09:00~18:00' in strip) and ('14:00' in strip), strip[:160].replace('\n', ' '))
    ok('공휴일 ON — 인덱스 공휴일/취소분 배너', pg.evaluate("() => !!document.querySelector('#fcOpenNotice') || !!document.querySelector('#holidayFcNotice')"))
    href3 = pg.eval_on_selector('#weekStrip a.wk.first', 'e => e.getAttribute("href")')
    ok('공휴일 ON + 금요일 — 취소분 링크 first.html', href3 == 'first.html', href3)

    # 목요일 + 공휴일 → 안내 + 메뉴 숨김
    pg.evaluate("() => window.SEOSAN_VERIFY.setNow('2026-11-26')")
    pg.wait_for_timeout(400)
    ok('공휴일 + 목요일 — 취소분 메뉴 숨김', pg.evaluate("() => document.querySelector('nav.site-nav a[href=\"first.html\"]').classList.contains('hidden')"))
    ok('공휴일 + 목요일 — 금요일 진행 안내', '금요일' in (pg.text_content('#statusLiveNotice') or ''))

    # first.html 금요일 + 공휴일 → 접수 열림, 입고 14:00
    pg.evaluate("() => window.SEOSAN_VERIFY.setNow('2026-11-27')")
    pg.wait_for_timeout(200)
    pg.goto(base + 'first.html', wait_until='load')
    pg.wait_for_timeout(600)
    pg.evaluate("() => { const m = document.querySelector('#modal'); if (m) m.classList.remove('open'); }")
    pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
    pg.wait_for_timeout(300)
    txt = pg.text_content('#fcBanner') if pg.query_selector('#fcBanner') else pg.text_content('main')
    ok('first 공휴일 금요일 — 접수 열림 · 14:00', ('금요일' in txt and '14:00' in txt), txt[:200].replace('\n', ' '))

    # 가이드 규칙
    pg.goto(base + 'guide-rules.html', wait_until='load')
    pg.wait_for_timeout(500)
    gt = pg.text_content('#guideHolidayNote') or ''
    ok('guide-rules — 공휴일 유의사항', '금요일 14:00' in gt, gt[:120])

    # 시연 달력 팝업
    pg.goto(base + 'index.html', wait_until='load')
    pg.wait_for_timeout(500)
    pg.evaluate("() => { const m = document.querySelector('#modal'); if (m) m.classList.remove('open'); }")
    pg.click('[data-democal]')
    pg.wait_for_timeout(400)
    cal = pg.evaluate("() => { const c = document.querySelector('#demoCal'); return c ? c.textContent : ''; }")
    ok('시연 달력 팝업 열림', '일' in cal and '년' in cal, cal[:80])
    pg.click('[data-democalnav="1"]')
    pg.wait_for_timeout(300)
    cal2 = pg.evaluate("() => document.querySelector('#demoCal') ? document.querySelector('#demoCal').textContent : ''")
    ok('달력 다음 달 이동', cal2 != cal, cal2[:60])
    pg.evaluate("() => { const b = document.querySelector('[data-democalday=\"2026-12-03\"]'); if (b) b.click(); }")
    pg.wait_for_timeout(400)
    nowiso = pg.evaluate("() => window.SEOSAN_VERIFY.now()")
    ok('달력 날짜 클릭 → 시연 기준일 변경', nowiso == '2026-12-03', nowiso)

    ok('콘솔 오류 0', not errs, errs[:3])
    ctx.close()
    b.close()
s.shutdown()
print('\n통과 %d · 실패 %d' % (okn, len(bad)))
for x in bad:
    print(' -', x)
sys.exit(1 if bad else 0)
