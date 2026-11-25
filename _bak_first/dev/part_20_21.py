# -*- coding: utf-8 -*-
"""서산시지부 현수막 지정게시대 — 멀티페이지(.html 분리) 자동 검증.

    python3 seosan-banner-lottery/multipage/verify_multipage.py            # 전체 검증
    python3 seosan-banner-lottery/multipage/verify_multipage.py --no-file  # file:// 검사 생략

로컬 HTTP 서버로 multipage/ 를 띄우고 실제 Chromium(Playwright)으로 다음을 확인한다.
  1) 13개 .html 페이지 로드 시 콘솔 오류·JS 예외 0건, 실패한 요청(4xx/5xx) 0건
  2) 상단 네비 탭 · 서브페이지 탭 클릭 → location.pathname 이 해당 .html 로 실제 이동
  3) 페이지 간 localStorage 상태 공유 (로그인 · 선착순 · 관리자 · 고장 · 공지)
  4) 360px 모바일 뷰포트에서 13개 페이지 가로 넘침 0건 + 게시대 한 줄 보기 유지
  5) 게시대현황: 페이지 넘김 없이 77개소 한 줄 렌더 · 검색 필터
  6) 주별 현황 달력: 월 이동 · 주(월~일) 클릭 → 운영일정 5개·주간 요약·게시대별 현황
  7) 접수 페이지: 달력에서 미래 주(사전 접수) 선택 → 2·3·4단계·접수 데이터·마이페이지 연결
  8) 관리자 공문: 게첨 주 달력 · 특정 위치(동·단) 지정 · 2주 결재(지부장→감사 2인 중 1인)
  9) 의료원사거리: 본게시대(A~D) 먼저 · 비선호 담장(F·G) 나중 (추첨·공문 공통)
 10) 광고대행사 10곳(대형 3곳 5건 이상) · 회원가입 샘플 등록증 제출
 11) 게시 지정서: 서명란 없음 · 광고내용 아래 선 유지 · A4 한 장 채움
 12) 규격 도식: 기둥 없음 · 표시면 배경·예시 문구 · 파일 다운로드는 마지막 순서
 11) 행사 우선접수: 신청(1·2·3순위) → 시안 승인 → 5명 중 3명 찬성 확정 / 미승인 시 일반 추첨 전환
 12) 배정 우선순위: 시청 공문 → 행사 우선 승인 → 일반 추첨 (추첨 엔진)
 13) 시한임박 가산점: 기본 0% · 인정 범위 차차주(20일) · 직책자 부여 한도(지부장 5%·수석 3%·현장 3%·사무 2%, 초과 차단) · 회원사 가산
 14) 목요일 선착순 09:00~18:00 · 금요일 10:00 미입고 자동 취소 문구/로직
 15) 매주 월요일 추첨 → 차주 월요일 게첨 · 지난 회차 시연 데이터 · 서식 화면 빠른 이동
 16) file:// 직접 열기
 17) 현장 게첨사진 — 게시대 동 단위 등록 · 접수번호별 사진 다운로드·인쇄
 18) 공문 파일 자동 인식 · 시연용 공문 샘플 4종
 19) 직책별 가산점 부여 한도 설정 — 최고권한 변경 · 부여 패널 동적 반영
 20) PC / 모바일 2종 버전 — 자동 판별 · 전환 토글 · 버전별 레이아웃
"""
import functools
import glob
import http.server
import io
import os
import re
import socketserver
import sys
import threading
import time
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))

def write_test_official():
    """공문 자동 인식 검증용 텍스트 공문 파일을 만든다."""
    body = ('서산시청 안전총괄과\n\n문서번호 : 서산시청 안전총괄과-1582\n시행일자 : 2026. 11. 20.\n\n'
            '제목 : 겨울철 제설·도로결빙 안전운전 캠페인 안내\n\n'
            '1. 겨울철 강설과 도로결빙으로 인한 교통사고 예방을 위하여 캠페인을 전개합니다.\n'
            '2. 현수막 8매를 게첨하여 주시기 바랍니다.\n3. 게첨 기간 : 1주\n')
    path = os.path.join(ROOT, '_verify_official.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(body)
    return path


def write_test_license():
    """등록번호 자동 추출 검증용 텍스트 등록증 파일을 만든다."""
    body = ('옥 외 광 고 업  등 록 증\n\n'
            '등록번호 : 충남서산-제2022-0157호\n'
            '상　　호 : 서산광고기획 (시연용)\n'
            '대 표 자 : 김서산\n'
            '영업소 소재지 : 충남 서산시 덕지천로 1\n')
    path = os.path.join(ROOT, '_verify_license.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(body)
    return path


def write_test_png(w=64, h=40, rgb=(210, 60, 60)):
    """업로드 검증용 작은 PNG 파일을 만들어 경로를 돌려준다."""
    import struct
    import zlib
    raw = b''
    for _ in range(h):
        raw += b'\x00' + bytes(rgb) * w

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
           chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
    path = os.path.join(ROOT, '_verify_upload.png')
    with open(path, 'wb') as f:
        f.write(png)
    return path


PAGES = ['index.html', 'apply.html', 'remain.html', 'first.html', 'guide-rules.html', 'guide-faq.html', 'guide.html',
         'mypage.html', 'mypage-detail.html', 'admin-review.html', 'admin-event.html', 'admin-draw.html',
         'admin-official.html', 'admin-pay.html', 'admin-deliver.html', 'admin-report.html',
         'admin-desig.html', 'admin-photos.html', 'admin-docs.html', 'admin-board.html', 'admin-course.html',
         'admin-roles.html', 'admin-members.html', 'admin-system.html']
ADMIN_PAGES = [p2 for p2 in PAGES if p2.startswith('admin-')]

NAV_EXPECT = [('게시대 현황', 'index.html'), ('주간 추첨 접수', 'apply.html'), ('미배정 상시접수', 'remain.html'),
              ('취소분 선착순', 'first.html'), ('규격·안내', 'guide-rules.html'), ('마이페이지', 'mypage.html'),
              ('협회 관리자', 'admin-draw.html')]
ADMIN_SUB_EXPECT = [('admin-review.html', 'review'), ('admin-event.html', 'event'), ('admin-draw.html', 'draw'),
                    ('admin-official.html', 'official'), ('admin-pay.html', 'pay'), ('admin-deliver.html', 'deliver'),
                    ('admin-report.html', 'report'), ('admin-desig.html', 'desig'), ('admin-photos.html', 'photos'),
                    ('admin-docs.html', 'docs'), ('admin-board.html', 'board'),
                    ('admin-course.html', 'course'), ('admin-roles.html', 'roles'),
                    ('admin-members.html', 'members'), ('admin-system.html', 'system')]
# 파일 다운로드는 가장 마지막 순서 (2026-11-22 김재봉 님 지시)
GUIDE_SUB_EXPECT = [('guide-rules.html', 'rules'), ('guide-faq.html', 'faq'), ('guide.html', 'file')]
GUIDE_PAGE_KEY = {'guide.html': 'file', 'guide-rules.html': 'rules', 'guide-faq.html': 'faq'}

STORE_KEY = 'seosan-banner-lottery-v6'
STORE_KEY_ADMIN = 'seosan-banner-admin'

results = []
fails = []


def ok(name, detail=''):
    results.append(('PASS', name, detail))
    print('  ✔ %s%s' % (name, (' — ' + detail) if detail else ''), flush=True)


def ng(name, detail=''):
    results.append(('FAIL', name, detail))
    fails.append((name, detail))
    print('  ✘ %s%s' % (name, (' — ' + detail) if detail else ''), flush=True)


class _StopRun(Exception):
    pass


_STOP_AT = os.environ.get('VERIFY_STOP_AT', '')


def head(txt):
    if _STOP_AT and txt.startswith(_STOP_AT):
        raise _StopRun()
    print('\n== %s ==' % txt, flush=True)


# ---------------------------------------------------------------------------
# 로컬 HTTP 서버
# ---------------------------------------------------------------------------
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def start_server():
    handler = functools.partial(QuietHandler, directory=ROOT)
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, 'http://127.0.0.1:%d/' % srv.server_address[1]


# ---------------------------------------------------------------------------
# Chromium 실행 (샌드박스에 시스템 라이브러리가 없을 때 대비)
# ---------------------------------------------------------------------------
def launch(p):
    prebuilt = os.environ.get('CHROMIUM_PATH', '')
    candidates = [c for c in (prebuilt, '/workspace/.preview-run/chrome-headless-shell') if c and os.path.exists(c)]
    for exe in candidates:
        e = dict(os.environ)
        base = os.path.dirname(exe)
        e['LD_LIBRARY_PATH'] = ':'.join(os.path.join(base, d) for d in ('syslibs', 'libs', 'shim'))
        try:
            return p.chromium.launch(executable_path=exe, env=e, args=['--no-sandbox', '--disable-dev-shm-usage'])
        except Exception as exc:      # noqa: BLE001 - 다음 후보로
            print('  (chromium %s 실행 실패: %s)' % (exe, str(exc).splitlines()[0][:120]), flush=True)
    return p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])


class Watcher:
    """페이지의 콘솔 오류·JS 예외·실패 요청을 모은다."""

    def __init__(self, page, base):
        self.console, self.errors, self.bad_requests = [], [], []
        self.base = base
        page.on('console', self._console)
        page.on('pageerror', lambda e: self.errors.append(str(e)))
        page.on('response', self._response)

    def _console(self, msg):
        if msg.type == 'error':
            self.console.append(msg.text)

    def _response(self, resp):
        try:
            if resp.url.startswith(self.base) and resp.status >= 400:
                self.bad_requests.append('%s %s' % (resp.status, resp.url))
        except Exception:      # noqa: BLE001
            pass

    def problems(self):
        return self.console + self.errors + self.bad_requests


def settle(pg, ms=250):
    """페이지 로드 후 자동으로 뜨는 안내/공지 모달을 닫고 렌더를 기다린다."""
    pg.wait_for_timeout(ms)
    try:
        if pg.evaluate("!!document.querySelector('#modal.open')"):
            pg.keyboard.press('Escape')
            pg.wait_for_timeout(120)
        if pg.evaluate("!!document.querySelector('#modal.open')"):
            btn = pg.query_selector('#modal .modal-x')
            if btn:
                btn.click()
                pg.wait_for_timeout(80)
    except Exception:      # noqa: BLE001
        pass


FAST = os.environ.get('VERIFY_FAST') == '1'
FAST2 = os.environ.get('VERIFY_FAST') == '2'      # settle 대기 최소화(전 구간 시간 단축)


def expand_places(pg, ms=250):
    """게시대 현황은 기본 점힘(2026-11-23 UI) — 행을 누르기 전에 펼친다."""
    try:
        hidden = pg.evaluate("() => { const b = document.getElementById('placementFold'); return !b || b.hidden; }")
        if hidden:
            pg.click('#btnPlaceToggle')
            pg.wait_for_timeout(ms)
        return not hidden
    except Exception:      # noqa: BLE001
        return False


def goto(pg, url, ms=300):
    pg.goto(url, wait_until='load')
    settle(pg, 0 if FAST2 else (min(ms, 220) if FAST else ms))
    # 비로그인 접수 화면은 진입 즉시 로그인 팝업(또는 부정접수 경고)이 뜬다 —
    # 자동화는 뜨는 팝업을 닫기만 하고(비회원 선택은 각 테스트에서) 진행한다.
    for _ in range(4):
        try:
            if pg.evaluate("() => { const m = document.querySelector('#modal'); return !!(m && m.classList.contains('open')); }"):
                pg.keyboard.press('Escape')
                pg.wait_for_timeout(120)
                if pg.evaluate("() => { const m = document.querySelector('#modal'); return !!(m && m.classList.contains('open')); }"):
                    btn = pg.query_selector('#modal .modal-x')
                    if btn:
                        btn.click()
                        pg.wait_for_timeout(80)
            else:
                pg.wait_for_timeout(260)
        except Exception:      # noqa: BLE001
            break


def app_count(page):
    return page.evaluate("""() => {
        try { const o = JSON.parse(localStorage.getItem('%s') || 'null'); return o && o.apps ? o.apps.length : -1; }
        catch (e) { return -2; }
    }""" % STORE_KEY)


def store(page, js='o'):
    """localStorage 저장소를 JS 식으로 읽는다 (o = 저장 객체)."""
    return page.evaluate("""() => {
        try { const o = JSON.parse(localStorage.getItem('%s') || 'null'); return %s; }
        catch (e) { return null; }
    }""" % (STORE_KEY, js))


def broken_count(page):
    return page.evaluate("""() => {
        try { const o = JSON.parse(localStorage.getItem('%s') || 'null');
              return o ? o.placements.filter(p => p.broken).length : -1; }
        catch (e) { return -2; }
    }""" % STORE_KEY)


def path_of(url):
    return urllib.parse.urlparse(url).path


def main(argv):
    skip_file = '--no-file' in argv
    head('준비')
    missing = [f for f in PAGES if not os.path.exists(os.path.join(ROOT, f))]
    if missing:
        ng('페이지 파일 존재', ', '.join(missing))
        return 1
    srv, base = start_server()
    print('  HTTP 서버: %s → %s' % (base, ROOT), flush=True)
    stop = {'hit': False}
    try:
      with sync_playwright() as p:
        browser = launch(p)
        print('  Chromium:', browser.version, flush=True)

        # ------------------------------------------------------------------
        # 1) 13개 페이지 로드 — 오류 0건 · 자기 섹션만 렌더
        # ------------------------------------------------------------------
        head('20. PC / 모바일 2종 버전 — 자동 판별 · 전환 토글 · 버전별 레이아웃')
        MOBILE_UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 '
                     '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')

        # 20-1) 모바일 접속(360 + 모바일 UA) → mobile 버전 자동
        ctx = browser.new_context(viewport={'width': 360, 'height': 800}, user_agent=MOBILE_UA,
                                  is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'index.html', 500)
        mob = pg.evaluate("() => window.SEOSAN_VERIFY.deviceViewState()")
        sw = pg.evaluate("() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth })")
        (ok if mob['view'] == 'mobile' and mob['tabbar'] and mob['tabbarBottom'] <= 2 and mob['bodyWidth'] <= 430
         and 'PC 버전' in mob['toggle'] and sw['sw'] <= sw['cw'] else ng)(
            '모바일 접속 — mobile 버전 자동 · 하단 탭바 · 1열 카드 · 넘침 0', '%s · %s' % (mob, sw))
        (ok if mob['smallTargets'] == 0 else ng)('모바일 터치 타겟 — 상단 탭·하단 탭 44px 이상', '%d개 부족' % mob['smallTargets'])
        tabs = pg.eval_on_selector_all('#mobileTabbar a', 'els => els.map(a => [a.getAttribute("href"), a.getAttribute("data-mtab"), a.textContent.trim()])')
        (ok if len(tabs) == 5 and [t[1] for t in tabs] == ['status', 'apply', 'remain', 'mypage', 'admin'] else ng)(
            '모바일 하단 탭바 5개 — 현황·접수·상시·마이·관리자', str([t[2] for t in tabs]))
        # 모바일 버전에서 관리자·접수 화면도 가로 넘침 0
        over = []
        for name in ('apply.html', 'admin-docs.html', 'mypage.html'):
            goto(pg, base + name, 350)
            m2 = pg.evaluate("() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth })")
            if m2['sw'] > m2['cw']:
                over.append((name, m2))
        (ok if not over else ng)('모바일 버전 — 접수·서식·마이페이지 가로 넘침 0', str(over))

        # 20-2) 모바일에서 'PC 버전'으로 전환 → 새로고침해도 유지 → 자동 감지로 복귀
        goto(pg, base + 'index.html', 400)
        pg.click('#btnViewToggle')
        pg.wait_for_timeout(400)
        to_pc = pg.evaluate("() => window.SEOSAN_VERIFY.deviceViewState()")
        pg.reload()
        settle(pg, 500)
        keep = pg.evaluate("() => window.SEOSAN_VERIFY.deviceViewState()")
        (ok if to_pc['view'] == 'pc' and not to_pc['tabbar'] and keep['view'] == 'pc' and keep['stored'] == 'pc' else ng)(
            '📱→🖥️ 수동 전환 · 새로고침 후에도 PC 버전 유지', '%s / %s' % (to_pc['view'], keep['view']))
        pg.click('#btnViewAuto')
        pg.wait_for_timeout(400)
        back = pg.evaluate("() => window.SEOSAN_VERIFY.deviceViewState()")
        (ok if back['view'] == 'mobile' and back['stored'] == '' else ng)(
            '자동 감지로 복귀 — 휴대폰에서는 다시 mobile', str(back))
        probs = w.problems()
        (ok if not probs else ng)('모바일 버전 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # 20-3) 데스크톱 접속(1280) → pc 버전 자동 · 넓은 컨테이너 · 다단 여지
        ctx = browser.new_context(viewport={'width': 1280, 'height': 800})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'index.html', 500)
        pcv = pg.evaluate("() => window.SEOSAN_VERIFY.deviceViewState()")
        (ok if pcv['view'] == 'pc' and not pcv['tabbar'] and pcv['wrapWidth'] >= 1240 and '모바일 버전' in pcv['toggle'] else ng)(
            '데스크톱 접속 — pc 버전 자동 · 넓은 컨테이너(1280px) · 하단 탭바 없음', str(pcv))
        pg.click('#btnViewToggle')
        pg.wait_for_timeout(450)
        prev = pg.evaluate("() => window.SEOSAN_VERIFY.deviceViewState()")
        (ok if prev['view'] == 'mobile' and prev['tabbar'] and 420 <= prev['bodyWidth'] <= 440 else ng)(
            '🖥️→📱 모바일 버전 미리보기 — 430px 중앙 프레임 · 하단 탭바', str(prev))
        pg.click('#btnViewToggle')
        pg.wait_for_timeout(350)
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.deviceView()") == 'pc' else ng)(
            '다시 PC 버전으로 복귀', 'toggle')

        # 20-4) URL 파라미터 ?view=pc — 휴대폰에서도 PC 버전 강제
        ctx2 = browser.new_context(viewport={'width': 360, 'height': 800}, user_agent=MOBILE_UA)
        pg2 = ctx2.new_page()
        pg2.set_default_timeout(20000)
        goto(pg2, base + 'index.html?view=pc', 500)
        forced = pg2.evaluate("() => window.SEOSAN_VERIFY.deviceViewState()")
        (ok if forced['view'] == 'pc' and not forced['tabbar'] else ng)(
            '?view=pc — 휴대폰에서도 PC 버전으로 열림', str(forced))
        goto(pg2, base + 'index.html?view=mobile', 400)
        (ok if pg2.evaluate("() => window.SEOSAN_VERIFY.deviceView()") == 'mobile' else ng)(
            '?view=mobile — 모바일 버전으로 열림', 'param')
        probs = w.problems()
        (ok if not probs else ng)('PC 버전 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx2.close()
        ctx.close()

        # ------------------------------------------------------------------
        # 21) 진행 중 주간(11.23~11.29) 잔여석 접수 · 신청자 유형별 설치 안내
        # ------------------------------------------------------------------
        head('21. 진행 중 주간(11.23~11.29) 잔여석 접수 · 4단계 흐름 통일 · 광고사 직접설치 / 일반인 광고사 의뢰 안내')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'remain.html', 600)
        lv = pg.evaluate("() => window.SEOSAN_VERIFY.liveWeek()")
        (ok if lv['start'] == '2026-11-23' and lv['end'] == '2026-11-29' and lv['open'] and lv['left'] > 0 else ng)(
            '진행 중 주간 잔여석 접수 개방 — 11.23~11.29 · 잔여 면 조회', str(lv))
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.fcMode()") == 'live' else ng)(
            '첫 화면 기본 창구 = 진행 중 주간 잔여석', pg.evaluate("() => window.SEOSAN_VERIFY.fcMode()"))

        # 21-1) 주간 추첨 접수와 **같은 4단계 흐름** — ①광고주·문구·시안 ②창구·수량 ③게시대 ④확인·접수
        steps = pg.eval_on_selector_all('#fcStepper .step', 'els => els.map(e => [e.getAttribute("data-step"), e.textContent.trim()])')
        (ok if len(steps) == 4 and [s[0] for s in steps] == ['1', '2', '3', '4'] and '광고주' in steps[0][1]
             and '창구' in steps[1][1] and '게시대' in steps[2][1] and '확인' in steps[3][1] else ng)(
            '미배정 선착순 — 4단계 스테퍼(광고주·창구·게시대·확인)', str(steps)[:150])
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.fcStep()") == 1 else ng)(
            '첫 화면 = 1단계(광고주·문구·시안)', 'step=%s' % pg.evaluate("() => window.SEOSAN_VERIFY.fcStep()"))
        order = pg.evaluate("""() => {
          const g = (id) => { const el = document.getElementById(id); return el ? Math.round(el.getBoundingClientRect().top + window.scrollY) : null; };
          const step1 = document.querySelector('#fcStep1');
          const step4 = document.querySelector('#fcStep4');
          return { adv: g('fcAdvertiser'), text: g('fcText'), design: g('fcFDesign'), lic: g('fcLicWrapEl'),
            notes: g('fcNotes'), list: g('firstList'), banner: g('fcBanner'),
            memberBanner: !!document.querySelector('#memberBanner'),
            step1Visible: step1 ? getComputedStyle(step1).display !== 'none' : null,
            step4Visible: step4 ? getComputedStyle(step4).display !== 'none' : null }; }""")
        (ok if order['adv'] is not None and order['adv'] < order['text'] < order['design'] and order['adv'] < 600 else ng)(
            '1단계 — 실제 광고주 → 문구 → 시안이 최상단', str({k: order[k] for k in ('adv', 'text', 'design')}))
        (ok if (not order['memberBanner']) and order['step1Visible'] and not order['step4Visible'] else ng)(
            '1단계 — 로그인 정보 박스 없음 · 한 번에 한 단계만 표시', str(order)[:130])
        dom_order = pg.evaluate("""() => { const l = document.querySelector('#firstList'), n = document.querySelector('#fcNotes');
            return !!(l && n && (l.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING)); }""")
        (ok if dom_order else ng)('4단계 — 장황한 안내문구는 게시대 목록보다 아래(하단)', 'dom order=%s' % dom_order)

        # 21-2) 1단계 검증 — 광고주·문구·시안·동의가 없으면 다음 단계로 가지 않는다
        pg.evaluate("() => { const v = window.SEOSAN_VERIFY; v.guestAccept(); v.fcSet({ mode: 'live', advertiser: '', text: '', file: false, agree: false, license: false }); }")
        blocked = pg.evaluate("() => window.SEOSAN_VERIFY.fcValidate(1)")
        step_blocked = pg.evaluate("() => window.SEOSAN_VERIFY.fcNext()")
        (ok if blocked is False and step_blocked is False and pg.evaluate("() => window.SEOSAN_VERIFY.fcStep()") == 1 else ng)(
            '1단계 — 필수 미입력 시 다음 단계 차단 · 1단계 유지', 'validate=%s next=%s' % (blocked, step_blocked))
        inv = pg.evaluate("""() => { const el = document.querySelector('#fcForm .field.invalid');
            return el ? { id: el.id, scroll: Math.round(el.getBoundingClientRect().top + window.scrollY) } : null; }""")
        (ok if inv and inv['id'] == 'fcFAdv' else ng)('필수 미입력 칸 강조(자동 스크롤·포커스 대상)', str(inv))

        # 21-3) 2단계 — 창구 chips · 설치 안내 배너 · 신청 수량(잔여 매수 범위)
        pg.evaluate("""() => window.SEOSAN_VERIFY.fcSet({ mode: 'live', advertiser: '검증진행주간광고주', text: '진행 중 주간 잔여석 접수 검증',
            file: true, agree: true, license: true, qty: 1, picks: [] })""")
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSetStep(2)")
        pg.wait_for_timeout(250)
        chips = pg.text_content('#fcModeChips') or ''
        (ok if '미배정 상시접수' in chips else ng)(
            '2단계 — 창구 칩(미배정 상시접수 · 제한 없음)', chips[:120].replace('\n', ' '))
        banner = pg.text_content('#fcBanner') or ''
        (ok if '진행 중 주간' in banner and '요일·일과시간 제한 없이' in banner else ng)(
            '진행 주간 안내 — 요일·일과시간 제한 없이 접수', banner[:90].replace('\n', ' '))
        (ok if '일반인은 직접 설치가 금지' in banner and '광고사에 설치를 의뢰' in banner
             and '의뢰하시거나 직접 설치' not in banner else ng)(
            '비회원(일반인) 배너 — 직접설치 금지 · 광고사 의뢰 안내', banner[:140].replace('\n', ' '))
        qinfo = pg.text_content('#fcQtyHint') or ''
        qmax = pg.evaluate("() => window.SEOSAN_VERIFY.fcMax()")
        (ok if '잔여 매수' in qinfo and qmax >= 1 else ng)('2단계 — 신청 수량(잔여 매수 범위 안내)', qinfo[:110])
        over = pg.evaluate("() => { const v = window.SEOSAN_VERIFY; v.fcSet({ qty: 50 }); return v.fcValidate(2); }")
        (ok if over is True else ng)('2단계 — 잔여 범위 안 수량은 통과', str(over))
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSet({ qty: 1, picks: [] })")

        # 21-4) 3단계 — 잔여 게시대 한 줄 보기 · 정치행정 제외 · 담기
        rows = pg.eval_on_selector_all('#firstList .fc-item', 'e => e.length')
        btns = pg.eval_on_selector_all('[data-fcpick]:not([disabled])', 'e => e.length')
        (ok if rows >= 77 and btns > 0 else ng)(
            '3단계 — 잔여 게시대 한 줄 보기 · 담기 버튼', '%d행 · 버튼 %d개' % (rows, btns))
        low_in = pg.evaluate("""() => { const lows = (window.SEOSAN_VERIFY.lowBoards() || []).map(x => x.name);
            const names = Array.from(document.querySelectorAll('#firstList .fc-item .fmain b')).map(e => e.textContent);
            return names.filter(n => lows.some(l => n.indexOf(l) >= 0) || n.indexOf('정치행정') >= 0); }""")
        (ok if not low_in else ng)('3단계 — 정치행정(공문 전용) 게시대 제외', str(low_in)[:100])
        pick_pid = pg.eval_on_selector('[data-fcpick]:not([disabled])', 'e => e.getAttribute("data-fcpick")')
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSetStep(3)")
        pg.wait_for_timeout(200)
        pg.click('[data-fcpick="%s"]' % pick_pid)
        pg.wait_for_timeout(250)
        picked = pg.evaluate("() => window.SEOSAN_VERIFY.fcPicks()")
        (ok if picked == [pick_pid] else ng)('3단계 — [담기] → 선택한 게시대에 담김', str(picked))
        slots_txt = pg.text_content('#fcPickSlots') or ''
        (ok if '1.' in slots_txt and pg.query_selector('[data-fcunpick]') else ng)(
            '3단계 — 담은 게시대 목록 · 해제 버튼', slots_txt[:90].replace('\n', ' '))
        pg.click('[data-fcunpick="%s"]' % pick_pid)
        pg.wait_for_timeout(200)
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.fcPicks()") == [] else ng)('3단계 — [✕] 선택 해제')
        pg.click('[data-fcpick="%s"]' % pick_pid)
        pg.wait_for_timeout(200)

        # 21-5) 4단계 — 수수료·설치 방식 확인 → 접수 제출
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSetStep(4)")
        pg.wait_for_timeout(250)
        ssum = pg.evaluate("() => window.SEOSAN_VERIFY.fcSummary()")
        fee = pg.text_content('#fcFeeTotal') or ''
        install = pg.text_content('#fcInstallInfo') or ''
        (ok if '진행 중 주간' in ssum and '1개소 1매' in ssum and fee.strip() == '10,700원' else ng)(
            '4단계 — 접수 내용 요약 · 수수료 10,700원', (ssum[:90] + ' / ' + fee).replace('\n', ' '))
        (ok if '일반인은 직접 설치가 금지' in install and '광고사에 설치를 의뢰' in install else ng)(
            '4단계 — 설치 방식(일반인 직접설치 금지 · 광고사 의뢰) 확인', install[:110].replace('\n', ' '))
        foot = pg.evaluate("() => window.SEOSAN_VERIFY.fcFoot()")
        (ok if '접수 제출' in foot['next'] else ng)('4단계 — 하단 플로팅 [접수 제출]', str(foot)[:110])
        before_apps = app_count(pg)
        lv_before = pg.evaluate("() => window.SEOSAN_VERIFY.liveWeek()")['left']
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSubmit()")
        pg.wait_for_timeout(600)
        done_t = pg.text_content('#modalBody') or ''
        (ok if '접수가 완료' in done_t and '광고사에 설치를 의뢰' in done_t else ng)(
            '접수 완료 안내 — 일반인 광고사 의뢰 안내', done_t[:130].replace('\n', ' '))
        pg.evaluate("() => window.SEOSAN_VERIFY.closeModal()")
        after_apps = app_count(pg)
        (ok if after_apps == before_apps + 1 else ng)('진행 주간 접수 저장', '%d건 → %d건' % (before_apps, after_apps))
        live_app = store(pg, "o.apps.filter(a => a.liveWeek).slice(-1)[0]")
        (ok if live_app and live_app['round'] == '2026-W46' and live_app['start'] == '2026-11-23'
             and live_app['directInstall'] and live_app['installType'] == 'general'
             and '일반인은 직접 설치가 금지' in (live_app['directInstallMsg'] or '') else ng)(
            '접수 데이터 — directInstall·직접설치 안내 저장', str({k: live_app.get(k) for k in ('id', 'round', 'start', 'status', 'installType')}) if live_app else '없음')
        lv2 = pg.evaluate("() => window.SEOSAN_VERIFY.liveWeek()")
        (ok if lv2['left'] == lv_before - 1 else ng)(
            '진행 주간 잔여 면 감소 — 접수 1면 차감', '%d면 → %d면' % (lv_before, lv2['left']))
        goto(pg, base + 'mypage-detail.html?id=' + live_app['id'], 600)
        det = pg.text_content('#mpBody') or ''
        (ok if '설치 방식' in det and '일반인은 직접 설치가 금지' in det and '광고사 의뢰' in det else ng)(
            '마이페이지 접수 상세 — 진행 주간 설치 안내 표시', det[:120].replace('\n', ' '))

        # 21-6) 광고대행사 로그인 — 배너·4단계 요약이 광고사 직접 설치로 바뀐다 (등록증 칸도 사라짐)
        goto(pg, base + 'first.html', 500)
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1002')")
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSet({})")
        pg.wait_for_timeout(300)
        ban_a = pg.text_content('#fcBanner') or ''
        (ok if '광고사에서 직접 현장에 설치(게첨)' in ban_a and '일반인은 직접 설치가 금지' not in ban_a else ng)(
            '광고대행사 로그인 — 배너가 광고사 직접 설치 안내로 분기', ban_a[:130].replace('\n', ' '))
        (ok if not pg.query_selector('#fcLic') else ng)('광고대행사 — 1단계 등록증 칸 없음', 'fcLic=%s' % bool(pg.query_selector('#fcLic')))
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1001')")
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSet({})")
        pg.wait_for_timeout(250)
        ban_g = pg.text_content('#fcBanner') or ''
        (ok if '일반인은 직접 설치가 금지' in ban_g else ng)(
            '일반회원 로그인 — 배너가 광고사 의뢰 안내로 분기', ban_g[:130].replace('\n', ' '))
        (ok if pg.query_selector('#fcLic') and '등록증' in (pg.text_content('#fcLicWrapEl') or '') else ng)(
            '일반회원 — 1단계 등록증 사본 요청', (pg.text_content('#fcLicWrapEl') or '')[:90].replace('\n', ' '))

        # 21-7) 게시대 현황에서 이번 주 게첨 주 → [잔여석 접수] → 3단계에 미리 담김
        goto(pg, base + 'index.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        pg.evaluate("() => window.SEOSAN_VERIFY.setStatusWeek('2026-11-23')")
        pg.wait_for_timeout(500)
        notice = pg.text_content('#statusLiveNotice') or ''
        (ok if '11.23' in notice and '잔여' in notice and '광고사' in notice else ng)(
            '게시대 현황(이번 주) — 진행 주간 잔여석 접수 안내', notice[:140].replace('\n', ' '))
        expand_places(pg)
        live_row = pg.eval_on_selector_all('#placementGrid [data-fclive]:not([disabled])', 'e => e.length')
        (ok if live_row > 0 else ng)('게시대 현황(이번 주) — [잔여석 접수] 버튼', '%d개' % live_row)
        go_pid = pg.eval_on_selector('#placementGrid [data-fclive]:not([disabled])', 'e => e.getAttribute("data-fclive")')
        pg.click('#placementGrid [data-fclive="%s"]' % go_pid)
        pg.wait_for_load_state('load')
        pg.wait_for_timeout(900)
        (ok if 'remain.html' in pg.url and ('place=' + go_pid) in pg.url else ng)(
            '현황 [미배정 상시접수] → remain.html?place= 연결', pg.url.split('/')[-1])
        pg.wait_for_timeout(300)
        pre = pg.evaluate("() => ({ mode: window.SEOSAN_VERIFY.fcMode(), step: window.SEOSAN_VERIFY.fcStep(), picks: window.SEOSAN_VERIFY.fcPicks() })")
        (ok if pre['mode'] == 'live' and pre['step'] == 1 and pre['picks'] == [go_pid] else ng)(
            '연결된 게시대가 3단계에 미리 담김 (1단계부터 접수)', str(pre))
        pg.evaluate("""() => window.SEOSAN_VERIFY.fcSet({ advertiser: '현황연결검증광고주', text: '현황 잔여석 연결 검증', file: true,
            agree: true, license: true, qty: 1 })""")
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSetStep(3)")
        pg.wait_for_timeout(200)
        slots3 = pg.text_content('#fcPickSlots') or ''
        ssum3 = pg.evaluate("() => { window.SEOSAN_VERIFY.fcSetStep(4); return window.SEOSAN_VERIFY.fcSummary(); }")
        (ok if '1.' in slots3 and '진행 중 주간' in ssum3 and '선택 게시대' in ssum3 else ng)(
            '연결된 게시대 → 3단계 담김 확인 · 4단계 요약까지 이어짐', (slots3[:60] + ' | ' + ssum3[:60]).replace('\n', ' '))
        probs = w.problems()
        (ok if not probs else ng)('진행 주간 잔여석 화면 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

    except _StopRun:
        stop['hit'] = True
        print('  (검증 분할 — 요청한 지점에서 중단)', flush=True)
    srv.shutdown()

    # -----------------------------------------------------------------------
    head('결과')
    passed = len([r for r in results if r[0] == 'PASS'])
    print('  총 %d개 검사 · 통과 %d · 실패 %d' % (len(results), passed, len(fails)), flush=True)
    if fails:
        print('\n  실패 항목:', flush=True)
        for n, d in fails:
            print('   - %s — %s' % (n, d), flush=True)
        return 1
    print('  모든 검증 통과', flush=True)
    return 0


if __name__ == '__main__':
    t0 = time.time()
    code = main(sys.argv[1:])
    print('  (%.1fs)' % (time.time() - t0))
    sys.exit(code)
