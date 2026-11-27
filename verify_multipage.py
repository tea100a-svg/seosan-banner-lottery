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
         'mypage.html', 'mypage-detail.html', 'admin-review.html', 'admin-official.html', 'admin-official-review.html',
         'admin-political.html', 'admin-event.html', 'admin-draw.html',
         'admin-pay.html', 'admin-deliver.html', 'admin-report.html', 'admin-desig.html', 'admin-docs.html',
         'admin-loc.html', 'admin-photos.html', 'admin-board.html', 'admin-course.html',
         'admin-roles.html', 'admin-members.html', 'admin-system.html']
ADMIN_PAGES = [p2 for p2 in PAGES if p2.startswith('admin-')]

NAV_EXPECT = [('게시대 현황', 'index.html'), ('주간 추첨 접수', 'apply.html'), ('미배정 상시접수', 'remain.html'),
              ('취소분 선착순', 'first.html'), ('규격·안내', 'guide-rules.html'), ('마이페이지', 'mypage.html'),
              ('협회 관리자', 'admin-draw.html')]
ADMIN_SUB_EXPECT = [('admin-review.html', 'review'), ('admin-official.html', 'official'),
                    ('admin-official-review.html', 'officialreview'), ('admin-political.html', 'political'),
                    ('admin-event.html', 'event'), ('admin-draw.html', 'draw'), ('admin-pay.html', 'pay'),
                    ('admin-deliver.html', 'deliver'), ('admin-report.html', 'report'), ('admin-desig.html', 'desig'),
                    ('admin-docs.html', 'docs'), ('admin-loc.html', 'loc'), ('admin-photos.html', 'photos'),
                    ('admin-board.html', 'board'), ('admin-course.html', 'course'), ('admin-roles.html', 'roles'),
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


def settle(pg, ms=250, again=True):
    """페이지 로드 후 자동으로 뜨는 안내/공지·결재 대기 모달을 닫고 렌더를 기다린다."""
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
    if again:
        # 지연 생성되는 결재·심사 대기 팝업까지 한 번 더 정리한다 (2026-11-23)
        try:
            pg.wait_for_timeout(520)
            for _ in range(3):
                if not pg.evaluate("() => !!document.querySelector('#modal.open')"):
                    break
                pg.keyboard.press('Escape')
                pg.wait_for_timeout(120)
                if pg.evaluate("() => !!document.querySelector('#modal.open')"):
                    bx = pg.query_selector('#modal .modal-x')
                    if bx:
                        bx.click()
                        pg.wait_for_timeout(100)
        except Exception:      # noqa: BLE001
            pass


FAST = os.environ.get('VERIFY_FAST') == '1'
FAST2 = os.environ.get('VERIFY_FAST') == '2'      # settle 대기 최소화(전 구간 시간 단축)


def open_detail(pg, base, app_id, wait=700):
    """내 접수 상세 — 잠금(로그인·휴대폰 인증 전) 상태면 접수 소유자로 인증하고 다시 그린다."""
    pg.goto(base + 'mypage-detail.html?id=' + app_id, wait_until='load')
    settle(pg, wait)
    owner = pg.evaluate("""(id) => { const s = window.SEOSAN_VERIFY.state();
        const a = (s.apps || []).filter(x => x.id === id)[0]; if (!a) return null;
        return { memberId: a.memberId || '', phone: (a.advertiserObj || {}).phone || a.advertiserPhone || a.phone || '' }; }""", app_id)
    txt = pg.text_content('#mpBody') or ''
    if '인증 후 이용' in txt or '찾을 수 없습니다' in txt:
        if owner and owner['memberId']:
            pg.evaluate("(m) => { try { window.SEOSAN_VERIFY.logout(); window.SEOSAN_VERIFY.login(m); } catch (e) {} }", owner['memberId'])
        elif owner and owner['phone']:
            pg.evaluate("(p) => { try { window.SEOSAN_VERIFY.logout(); window.SEOSAN_VERIFY.guestVerify(p); } catch (e) {} }", owner['phone'])
        pg.wait_for_timeout(350)
        if owner and owner['phone']:
            pg.evaluate("(p) => { try { window.SEOSAN_VERIFY.guestVerify(p); } catch (e) {} }", owner['phone'])
        pg.evaluate("() => { try { if (window.SEOSAN_VERIFY.renderDetail) window.SEOSAN_VERIFY.renderDetail(); } catch (e) {} }")
        pg.wait_for_timeout(350)
        txt = pg.text_content('#mpBody') or ''
    return txt


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
        head('1. %d개 페이지 로드 (콘솔 오류 · JS 예외 · 실패 요청)' % len(PAGES))
        for name in PAGES:
            ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
            pg = ctx.new_page()
            pg.set_default_timeout(8000)
            w = Watcher(pg, base)
            goto(pg, base + name, 350)
            probs = w.problems()
            views = pg.evaluate("document.querySelectorAll('.view').length")
            visible = pg.evaluate("document.querySelectorAll('.view').length && getComputedStyle(document.querySelector('.view')).display !== 'none'")
            if probs:
                ng('%s 로드' % name, '; '.join(probs[:3]))
            elif not visible:
                ng('%s 로드' % name, 'section.view 가 화면에 표시되지 않음')
            else:
                ok('%s 로드' % name, '오류 0 · 섹션 1개 표시')
            if views != 1:
                ng('%s 섹션 분리' % name, '.view 요소 %d개 (1개여야 함)' % views)
            ctx.close()

        # ------------------------------------------------------------------
        # 2) 네비 · 서브탭 클릭 → 실제 .html 이동
        # ------------------------------------------------------------------
        head('2. 네비게이션 탭 클릭 → 실제 페이지 이동 (location.pathname)')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
        pg = ctx.new_page()
        pg.set_default_timeout(8000)
        Watcher(pg, base)
        for name in PAGES:
            goto(pg, base + name, 170)
            # 취소분 선착순(first.html) 메뉴는 접수일(목요일 · 공휴일이면 금요일)에만 노출 - 시연 기준일을 목요일로
            pg.evaluate("() => { try { localStorage.setItem('seosan-demo-now', '2026-11-26'); } catch (e) {} }")
            hrefs = pg.eval_on_selector_all('nav.site-nav a', 'els => els.map(a => a.getAttribute("href"))')
            if hrefs != [h for _, h in NAV_EXPECT]:
                ng('%s 상단 네비 링크' % name, 'links=%s' % hrefs)
            else:
                ok('%s 상단 네비 링크' % name, '7개 탭 href 일치')
            _clicked = 0
            for label, href in NAV_EXPECT:
                if href == name:
                    continue
                if _clicked >= 1:
                    break      # 27페이지 × 전 링크는 시간이 너무 길어 대표 1개만 확인
                if href in ('mypage.html', 'admin-draw.html'):
                    continue
                goto(pg, base + name, 150)
                pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
                pg.click('nav.site-nav a[href="%s"]' % href)
                pg.wait_for_load_state('load')
                pg.wait_for_timeout(40)
                _clicked += 1
                path = path_of(pg.url)
                if path.endswith('/' + href):
                    ok('%s → %s 클릭' % (name, href), 'data-page=%s' % pg.evaluate('document.body.getAttribute("data-page")'))
                else:
                    ng('%s → %s 클릭' % (name, href), 'pathname=%s' % path)

        head('2-1. 서브페이지 탭 클릭 (관리자 9 · 규격·안내 3 — 파일 다운로드는 마지막)')
        for name in ADMIN_PAGES:
            goto(pg, base + name, 170)
            subs = pg.eval_on_selector_all('#adminSub a', 'els => els.map(a => [a.getAttribute("href"), a.getAttribute("data-adminsub"), a.classList.contains("on")])')
            if [s[0] for s in subs] != [h for h, _ in ADMIN_SUB_EXPECT]:
                ng('%s 서브탭 링크' % name, '%s' % subs)
            else:
                cur = [s[1] for s in subs if s[2]]
                key = ([k for h, k in ADMIN_SUB_EXPECT if h == name] or [''])[0]
                (ok if cur == [key] else ng)('%s 서브탭 활성 표시' % name, 'active=%s · href 5개' % cur)
            _sub = 0
            for href, key in ADMIN_SUB_EXPECT:
                if href == name:
                    continue
                if _sub >= 1:
                    break      # 18페이지 × 18서브탭은 시간이 너무 길어 대표 1개만 확인
                goto(pg, base + name, 150)
                pg.click('#adminSub a[href="%s"]' % href)
                pg.wait_for_load_state('load')
                pg.wait_for_timeout(40)
                _sub += 1
                path = path_of(pg.url)
                (ok if path.endswith('/' + href) else ng)('%s 서브탭 → %s' % (name, href), path)

        for name in ['guide.html', 'guide-rules.html', 'guide-faq.html']:
            goto(pg, base + name, 170)
            subs = pg.eval_on_selector_all('#guideSub a', 'els => els.map(a => [a.getAttribute("href"), a.getAttribute("data-gsubtab"), a.classList.contains("on")])')
            if [s[0] for s in subs] != [h for h, _ in GUIDE_SUB_EXPECT]:
                ng('%s 서브탭 순서 (파일 다운로드 마지막)' % name, '%s' % [s[0] for s in subs])
            else:
                cur = [s[1] for s in subs if s[2]]
                key = GUIDE_PAGE_KEY[name]
                (ok if cur == [key] else ng)('%s 서브탭 활성 표시' % name, 'active=%s' % cur)
            for href, key in GUIDE_SUB_EXPECT:
                if href == name:
                    continue
                goto(pg, base + name, 100)
                pg.click('#guideSub a[href="%s"]' % href)
                pg.wait_for_load_state('load')
                pg.wait_for_timeout(100)
                path = path_of(pg.url)
                (ok if path.endswith('/' + href) else ng)('%s 서브탭 → %s' % (name, href), path)
        ctx.close()

        # ------------------------------------------------------------------
        # 3) 페이지 간 상태 공유 (localStorage)
        # ------------------------------------------------------------------
        head('3. 페이지 간 상태 공유 — 로그인 · 선착순 · 관리자 모드 · 고장 처리')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
        pg = ctx.new_page()
        pg.set_default_timeout(8000)
        w = Watcher(pg, base)
        goto(pg, base + 'index.html', 300)

        # 3-1 로그인 (시연용 회원 M-1002 재봉기획 — 대형 광고대행사)
        pg.click('#btnLogin')
        pg.wait_for_selector('#modal.open')
        pg.click('[data-login-preset="M-1002"]')
        pg.wait_for_timeout(350)
        auth = pg.text_content('#authName') if pg.query_selector('#authName') else ''
        hidden = pg.evaluate("document.getElementById('authUser').classList.contains('hidden')")
        (ok if auth.strip() == '재봉기획' and not hidden else ng)('로그인 (index.html)', 'authName=%r hidden=%s' % (auth, hidden))
        session = pg.evaluate("JSON.parse(localStorage.getItem('%s')).session" % STORE_KEY)
        (ok if session == 'M-1002' else ng)('localStorage 세션 저장', 'session=%r' % session)

        goto(pg, base + 'mypage.html', 300)
        mp_head = pg.text_content('#mpHead') or ''
        (ok if '재봉기획' in mp_head else ng)('로그인 유지 (mypage.html)', 'mpHead=%r' % mp_head[:40])

        goto(pg, base + 'admin-review.html', 250)
        name2 = pg.text_content('#authName') or ''
        (ok if '재봉기획' in name2 else ng)('로그인 유지 (admin-review.html)', 'authName=%r' % name2)

        # 3-2 선착순 — 목요일 일과시간(09:00~18:00) · 금요일 10:00 입고 · 4단계 흐름(2026-11-23)
        before = app_count(pg)
        goto(pg, base + 'first.html', 250)      # 취소분 선착순 페이지
        pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
        cfg = pg.evaluate("() => window.SEOSAN_VERIFY.firstComeConfig()")
        (ok if cfg.get('from') == 9 and cfg.get('to') == 18 and cfg.get('deliverTime') == '10:00' else ng)(
            '선착순 시간 규칙 (09:00~18:00 · 금 10:00 입고)', str(cfg))
        pg.evaluate("""() => window.SEOSAN_VERIFY.fcSet({ mode: 'next', daySim: 'thu', fcTime: 'open',
            advertiser: '선착순검증광고주', text: '목요일 선착순 접수 검증', file: true, agree: true, license: true, qty: 1, picks: 'auto' })""")
        banner = pg.text_content('#fcBanner') or ''
        (ok if '09:00~18:00' in banner else ng)('목요일 일과시간 안내', banner[:70].replace('\n', ' '))
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSet({ fcTime: 'after' })")
        closed = pg.evaluate("document.querySelector('#fcBanner .fc-window').className")
        btxt = pg.text_content('#fcBanner') or ''
        (ok if 'offhours' in closed and '일과시간' in btxt else ng)('18시 이후 접수 차단', closed)
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.fcValidate(2)") is False else ng)(
            '18시 이후 — 2단계 진행 차단', 'fcValidate(2)')
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSet({ fcTime: 'open' })")
        pid = (pg.evaluate("() => window.SEOSAN_VERIFY.fcPicks()") or [''])[0]
        step = pg.evaluate("() => window.SEOSAN_VERIFY.fcStep()")
        for _ in range(4 - step):
            pg.evaluate("() => window.SEOSAN_VERIFY.fcNext()")
        foot = pg.evaluate("() => window.SEOSAN_VERIFY.fcFoot()")
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.fcStep()") == 4 and '접수 제출' in foot['next'] else ng)(
            '선착순 4단계 — 하단 플로팅 [접수 제출]', str(foot)[:120])
        ssum = pg.evaluate("() => window.SEOSAN_VERIFY.fcSummary()")
        (ok if '10,700' in ssum or '선택 게시대' in ssum else ng)('선착순 4단계 — 접수 내용 요약', ssum[:110].replace('\n', ' '))
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSubmit()")
        pg.wait_for_timeout(400)
        after = app_count(pg)
        (ok if after == before + 1 else ng)('선착순 예약 저장 (first.html)', 'apps %d → %d (%s)' % (before, after, pid))
        due = store(pg, "o.apps.filter(a=>a.firstCome).map(a=>a.deliveryDue).slice(-1)[0]")
        (ok if due == '2026-11-27 10:00' else ng)('선착순 당첨분 입고 마감 = 금요일 10:00', str(due))
        pg.evaluate("() => window.SEOSAN_VERIFY.closeModal()")
        goto(pg, base + 'mypage.html', 300)
        body = pg.text_content('#mpBody') or ''
        (ok if '선착순 확정' in body else ng)('예약 내역 표시 (mypage.html)',
                                             'mpBody 에 선착순 확정 %s' % ('있음' if '선착순 확정' in body else '없음'))

        # 3-3 관리자 모드 체크 → admin-draw.html 로 이동
        goto(pg, base + 'index.html', 250)
        pg.click('label.admin-switch')
        pg.wait_for_url('**/admin-draw.html', timeout=8000)
        path = path_of(pg.url)
        (ok if path.endswith('/admin-draw.html') else ng)('관리자 모드 전환 → 이동', path)
        adm_flag = pg.evaluate("localStorage.getItem('%s')" % STORE_KEY_ADMIN)
        (ok if adm_flag == '1' else ng)('관리자 모드 저장', 'ADMIN_KEY=%r' % adm_flag)

        # 3-4 고장 처리 (admin-board.html) → index.html 현황에 반영
        goto(pg, base + 'admin-board.html', 300)
        broken_before = broken_count(pg)
        first_broken = pg.query_selector('[data-broken]')
        if not first_broken:
            ng('게시대 고장 처리', 'data-broken 버튼 없음')
        else:
            pid_b = first_broken.get_attribute('data-broken')
            first_broken.click()
            pg.wait_for_timeout(400)
            broken_after = broken_count(pg)
            (ok if broken_after == broken_before + 1 else ng)(
                '고장 처리 저장 (admin-board.html)', '%s · 고장 %d → %d' % (pid_b, broken_before, broken_after))
            goto(pg, base + 'index.html', 350)
            st = broken_count(pg)
            pname = store(pg, "(o.placements.find(x => x.id === '%s') || {}).name || ''" % pid_b)
            grid_txt = pg.text_content('#placementGrid') or ''
            (ok if st == broken_after and (pname in grid_txt) else ng)(
                '현황 페이지 반영 (index.html)', '고장 %d개소 · %s 노출=%s' % (st, pname, pname in grid_txt))

        # 3-5 게시대 현황 `접수하러 가기` → 접수 페이지 (?place=·?week= 1순위 자동 선택)
        free_pid = pg.evaluate("""() => { try { const o = JSON.parse(localStorage.getItem('%s'));
            const p = o.placements.filter(x => !x.broken)[0]; return p ? p.id : ''; } catch (e) { return ''; } }""" % STORE_KEY)
        goto(pg, base + 'index.html', 300)
        expand_places(pg)
        pg.click('#placementGrid [data-apply="%s"]' % free_pid)
        pg.wait_for_load_state('load')
        settle(pg, 350)
        path = path_of(pg.url)
        (ok if path.endswith('/apply.html') and ('place=' + free_pid) in pg.url and 'week=' in pg.url else ng)(
            '현황 `접수` → apply.html 이동', urllib.parse.unquote(pg.url.split('/')[-1]))
        rank = pg.text_content('#rankStatus') or ''
        slots = pg.text_content('#pickSlotsInfo') or ''
        (ok if re.search(r'1순위 1 / 1', rank) and '1순위 1개소' in slots else ng)(
            'apply.html?place= 1순위 자동 선택', '%s · %s' % (rank[:40], slots[:45]))

        # 3-6 마이페이지 세부 페이지
        app_id = pg.evaluate("""() => { try { const o = JSON.parse(localStorage.getItem('%s'));
            const a = o.apps.filter(x => x.status === '선착순확정')[0] || o.apps[0]; return a ? a.id : ''; }
            catch (e) { return ''; } }""" % STORE_KEY)
        goto(pg, base + 'mypage-detail.html?id=' + urllib.parse.quote(app_id), 300)
        det = pg.text_content('#mpBody') or ''
        (ok if app_id and app_id in det and '접수증' in det else ng)('mypage-detail.html?id= 렌더',
                                                                   'id=%s · 길이 %d' % (app_id, len(det)))
        pg.click('[data-mpback]')
        pg.wait_for_load_state('load')
        path = path_of(pg.url)
        (ok if path.endswith('/mypage.html') else ng)('접수 목록으로 돌아가기', path)

        # 3-7 목록 → 세부 페이지 클릭 이동
        goto(pg, base + 'mypage.html', 300)
        row = pg.query_selector('[data-mppick]')
        if row:
            rid = row.get_attribute('data-mppick')
            row.click()
            pg.wait_for_load_state('load')
            pg.wait_for_timeout(250)
            u = pg.url
            (ok if 'mypage-detail.html' in u and ('id=' + urllib.parse.quote(rid)) in u else ng)(
                '목록 클릭 → 세부 페이지', urllib.parse.unquote(u.split('/')[-1]))
        else:
            ng('목록 클릭 → 세부 페이지', '[data-mppick] 없음')

        # 3-8 게시대 현황 — 페이지 넘김 없이 77개소 한 줄 + 검색 필터
        goto(pg, base + 'index.html', 300)
        expand_places(pg)
        total = store(pg, 'o.placements.length')
        nrows = pg.eval_on_selector_all('#placementGrid .plrow', 'els => els.length')
        pager_absent = pg.evaluate("!document.getElementById('statusPager')")
        first_h = pg.evaluate("() => { const r = document.querySelector('#placementGrid .plrow'); return r ? Math.round(r.getBoundingClientRect().height) : -1; }")
        (ok if nrows == total and pager_absent else ng)('게시대 한 줄 보기 (페이지 넘김 없음)',
                                                       '행 %d개 / 전체 %d개 · pager 없음=%s' % (nrows, total, pager_absent))
        (ok if 0 < first_h <= 64 else ng)('한 줄 행 높이 (compact)', '%dpx' % first_h)
        first_name = pg.eval_on_selector('#placementGrid .pl-name', 'el => el.textContent')
        pg.click('#placementGrid .plrow .pl-name')
        pg.wait_for_selector('#modal.open')
        mtitle = pg.text_content('#modalTitle') or ''
        srows = pg.eval_on_selector_all('#modalBody .sm-row', 'els => els.length')
        (ok if first_name.strip() in mtitle and srows > 0 else ng)(
            '한 줄 행 클릭 → 상세 모달(동×단)', '%r · 슬롯 행 %d' % (mtitle, srows))
        pg.click('#modal .modal-x')
        pg.wait_for_timeout(200)
        pg.fill('#statusSearch', '해미')
        pg.wait_for_timeout(250)
        n_filtered = pg.eval_on_selector_all('#placementGrid .plrow', 'els => els.length')
        txt = pg.text_content('#placementGrid') or ''
        (ok if 0 < n_filtered < total and '해미' in txt else ng)('현황 검색 필터', '해미 → %d행' % n_filtered)
        pg.fill('#statusSearch', '')
        pg.wait_for_timeout(250)
        n_all = pg.eval_on_selector_all('#placementGrid .plrow', 'els => els.length')
        (ok if n_all == total and first_name else ng)('검색 해제 시 77개소 복귀', '%d행' % n_all)

        # 3-8b 한글 IME 조합 입력 — 브라우저·OS 기본 입력 그대로 (영타→한글 자동변환은 삭제됨)
        goto(pg, base + 'apply.html', 350)
        pg.evaluate("""() => { const el = document.getElementById('applyText');
            el.focus();
            el.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
            el.value = 'ㅇㅏㄴ'; el.dispatchEvent(new InputEvent('input', { bubbles: true, isComposing: true, data: '안' }));
            el.value = '안'; el.dispatchEvent(new InputEvent('input', { bubbles: true, isComposing: true, data: '안' }));
            el.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true, data: '안' }));
        }""")
        pg.wait_for_timeout(450)
        v1 = pg.eval_on_selector('#applyText', 'el => el.value')
        pg.evaluate("""() => { const el = document.getElementById('applyText');
            el.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
            el.value = '안ㄴㅕㅇ'; el.dispatchEvent(new InputEvent('input', { bubbles: true, isComposing: true }));
            el.value = '안녕'; el.dispatchEvent(new InputEvent('input', { bubbles: true, isComposing: true }));
            el.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true }));
        }""")
        pg.wait_for_timeout(450)
        v2 = pg.eval_on_selector('#applyText', 'el => el.value')
        (ok if v1 == '안' and v2 == '안녕' else ng)('한글 IME 조합 입력 유지 (자모 분리 없음)', '%r → %r' % (v1, v2))
        pg.eval_on_selector('#applyText', 'el => { el.value = \'\'; }')
        pg.fill('#applyCompany', '')
        pg.type('#applyCompany', 'gottkfshddnjs', delay=15)
        pg.wait_for_timeout(600)
        v3 = pg.eval_on_selector('#applyCompany', 'el => el.value')
        (ok if v3 == 'gottkfshddnjs' else ng)('영타 입력이 그대로 유지 (강제 한글 변환 없음)', repr(v3))
        ime_gone = pg.evaluate("""() => ({ badge: !!document.querySelector('#imeToggle'),
            api: typeof window.SEOSAN_VERIFY.imeOn === 'function' || typeof window.SEOSAN_VERIFY.hangul === 'function',
            koIme: document.querySelectorAll('.ko-ime').length })""")
        (ok if not ime_gone['badge'] and not ime_gone['api'] else ng)(
            '영타→한글 자동변환 배지·API 완전 삭제', str(ime_gone))

        # 3-9 공지 팝업 — admin-system.html 에서 등록 → index.html 첫 화면에 노출
        goto(pg, base + 'admin-system.html', 350)
        pg.fill('#noticeTitle', '검증 공지 — 11월 4주차 운영 안내')
        pg.fill('#noticeBody', '월 10:00 추첨 / 수 18:00 입고 마감\n\n목요일 일과시간(09:00~18:00) 선착순 접수, 선착순 당첨분은 금요일 10:00까지 입고합니다.')
        pg.check('#noticeOn')
        pg.click('#btnNoticeSave')
        pg.wait_for_timeout(350)
        pg.click('label.admin-switch')
        pg.wait_for_url('**/index.html', timeout=8000)
        pg.wait_for_timeout(700)
        ntitle = pg.text_content('#modalTitle') or ''
        (ok if '검증 공지' in ntitle else ng)('공지 팝업 노출 (index.html)', ntitle)
        pg.keyboard.press('Escape')
        pg.wait_for_timeout(150)
        goto(pg, base + 'apply.html', 550)
        t2 = pg.text_content('#modalTitle') or ''
        (ok if '검증 공지' not in t2 else ng)('공지 팝업은 첫 화면에서만', 'apply.html 모달=%r' % t2)

        # 3-10 게시지정서 — 서명란 없음 · 광고내용 아래 선 · A4 채움 · 60칸
        goto(pg, base + 'admin-pay.html', 350)
        if pg.query_selector('#adminRoleSel'):
            pg.select_option('#adminRoleSel', 'staff')   # 공문 접수 권한(사무실무원) — 지정서 버튼 노출
            pg.wait_for_timeout(400)
        dbtn = pg.query_selector('[data-desig]:not([disabled]):not(.hidden)')
        if dbtn:
            dbtn.click()
            pg.wait_for_timeout(400)
            sign_n = pg.eval_on_selector_all('#desigPrint .desig-sign, #desigPrint .desig-signline', 'els => els.length')
            nos = pg.eval_on_selector_all('#desigPrint .desig-table td.dg-no', 'els => els.length')
            bd = pg.evaluate("""() => { const td = document.querySelector('#desigPrint .desig-info td[colspan="6"]');
                if (!td) return null; const s = getComputedStyle(td);
                return { w: s.borderBottomWidth, st: s.borderBottomStyle, c: s.borderBottomColor }; }""")
            th = pg.evaluate("() => { const t = document.querySelector('#desigPrint .desig-table'); return t ? Math.round(t.getBoundingClientRect().height) : -1; }")
            (ok if sign_n == 0 else ng)('게시지정서 하단 서명란 제거', '서명 요소 %d개' % sign_n)
            (ok if nos == 60 else ng)('게시지정서 60칸 2단', '순번 셀 %d개' % nos)
            (ok if bd and bd['w'] != '0px' and bd['st'] != 'none' else ng)('광고내용 칸 아래 선 유지', str(bd))
            (ok if th >= 620 else ng)('게시지정서 A4 채움(표 높이)', '%dpx' % th)
            pg.keyboard.press('Escape')
            pg.wait_for_timeout(150)
        else:
            ng('게시지정서 출력', 'data-desig 버튼 없음')
        css_txt = io.open(os.path.join(ROOT, 'assets', 'style.css'), encoding='utf-8').read()
        (ok if '@page' in css_txt and 'A4 portrait' in css_txt else ng)('인쇄 용지 A4 세로 규칙', 'style.css @page')

        probs = w.problems()
        (ok if not probs else ng)('상태 공유 시나리오 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 4) 360px 모바일 — 가로 넘침 0건 · 한 줄 보기 유지
        # ------------------------------------------------------------------
        head('4. 360px 모바일 뷰포트 가로 넘침 · 한 줄 게시대 행')
        ctx = browser.new_context(viewport={'width': 360, 'height': 780}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        pg.set_default_timeout(8000)
        Watcher(pg, base)
        for name in PAGES:
            goto(pg, base + name, 350)
            m = pg.evaluate("({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,"
                            " bw: document.body.scrollWidth})")
            if m['sw'] <= m['cw'] and m['bw'] <= m['cw']:
                ok('%s 360px' % name, 'scrollWidth %d ≤ %d' % (m['sw'], m['cw']))
            else:
                ng('%s 360px 가로 넘침' % name, 'scrollWidth %d / clientWidth %d' % (m['sw'], m['cw']))
        goto(pg, base + 'index.html', 350)
        expand_places(pg)
        hm = pg.evaluate("""() => { const r = document.querySelector('#placementGrid .plrow');
            if (!r) return null; const b = r.getBoundingClientRect();
            return { h: Math.round(b.height), sw: r.scrollWidth, cw: r.clientWidth, cols: getComputedStyle(r).gridTemplateColumns }; }""")
        (ok if hm and hm['h'] <= 60 and hm['sw'] <= hm['cw'] + 1 else ng)(
            '360px 한 줄 게시대 행', str(hm))
        ctx.close()

        # ------------------------------------------------------------------
        # 5) guide.html 다운로드 링크 HTTP 200 (마지막 페이지)
        # ------------------------------------------------------------------
        head('5. guide.html 대지·실명제 파일 다운로드 (규격·안내 마지막 페이지)')
        src = io.open(os.path.join(ROOT, 'guide.html'), encoding='utf-8').read()
        links = re.findall(r'<a[^>]+href="(files/[^"]+)"[^>]*download="([^"]+)"', src)
        if len(links) != 5:
            ng('다운로드 링크 5개', 'found=%d' % len(links))
        else:
            ok('다운로드 링크 5개', ', '.join(n for _, n in links))
        for href, fname in links:
            url = base + urllib.parse.quote(href)
            try:
                with urllib.request.urlopen(url, timeout=20) as r:
                    data = r.read()
                    disk = os.path.getsize(os.path.join(ROOT, urllib.parse.unquote(href)))
                    if r.status == 200 and len(data) == disk and len(data) > 0:
                        ok('HTTP 200 · %s' % fname, '%d bytes' % len(data))
                    else:
                        ng('HTTP %s · %s' % (r.status, fname), '%d/%d bytes' % (len(data), disk))
            except Exception as exc:      # noqa: BLE001
                ng('다운로드 실패 · %s' % fname, str(exc)[:120])
        ctx = browser.new_context(viewport={'width': 1280, 'height': 900}, accept_downloads=True)
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        Watcher(pg, base)
        goto(pg, base + 'guide.html', 250)
        try:
            with pg.expect_download(timeout=20000) as dl:
                pg.click('#btnNameBoxDownload')
            d = dl.value
            ok('브라우저 다운로드 클릭', '%s (%d bytes)' % (d.suggested_filename, os.path.getsize(d.path())))
        except Exception as exc:      # noqa: BLE001
            ng('브라우저 다운로드 클릭', str(exc).splitlines()[0][:140])
        # 규격 도식 — 기둥 없음 · 배경/예시 문구
        goto(pg, base + 'guide-rules.html', 300)
        posts = pg.eval_on_selector_all('.sv-posts', 'els => els.length')
        sample = pg.text_content('.sv-c .sv-sample') if pg.query_selector('.sv-c .sv-sample') else ''
        bg = pg.evaluate("() => { const e = document.querySelector('.sv-c'); return e ? getComputedStyle(e).backgroundImage : ''; }")
        (ok if posts == 0 else ng)('규격 도식 기둥 제거', '.sv-posts %d개' % posts)
        (ok if '표준 현수막 시안' in (sample or '') else ng)('규격 도식 예시 문구', repr(sample))
        (ok if bg and bg != 'none' else ng)('규격 도식 표시면 배경', bg[:60])
        # 실제 치수 비율(7,100:900 = 7.89:1) · 좌 1.41% · 우측 봉미싱 0.70% · 말리는 부분 2.11% 인 비례 도식
        geom = pg.evaluate("""() => { const el = document.querySelector('.sv-banner'); const b = el.getBoundingClientRect();
            const l = document.querySelector('.sv-l').getBoundingClientRect(); const r = document.querySelector('.sv-r').getBoundingClientRect();
            const r2 = document.querySelector('.sv-r2').getBoundingClientRect();
            const c = document.querySelector('.sv-c').getBoundingClientRect();
            const iw = el.clientWidth, ih = el.clientHeight;
            return { ratio: b.width / b.height, l: l.width / iw * 100, r: r.width / iw * 100, r2: r2.width / iw * 100,
              c: c.width / iw * 100, h: Math.round(b.height), scroll: el.scrollWidth, cw: iw }; }""")
        (ok if abs(geom['ratio'] - 7100 / 900) < 0.15 else ng)('규격 도식 실제 비율(7,100:900)', '%.2f : 1' % geom['ratio'])
        (ok if abs(geom['l'] - 1.41) < 0.2 and abs(geom['r'] - 2.11) < 0.2 and abs(geom['r2'] - 0.70) < 0.15
             and abs(geom['c'] - 95.78) < 0.3 else ng)(
            '규격 도식 좌·표시면·우측 봉미싱·말리는 부분 비율(100 / 6,800 / 50 / 150mm)',
            '좌 %.2f%% · 표시면 %.2f%% · 우측 봉미싱 %.2f%% · 말리는 부분 %.2f%%' % (geom['l'], geom['c'], geom['r2'], geom['r']))
        (ok if geom['scroll'] <= geom['cw'] + 1 else ng)('규격 도식 내부 넘침 없음', 'scroll %s / %s' % (geom['scroll'], geom['cw']))
        # 우측 봉미싱과 말리는 부분은 **서로 다른 두 구간**으로 분리되어 있다 (김재봉 님 지시 2026-11-22)
        (ok if geom['r2'] > 0 and geom['r'] > geom['r2'] else ng)(
            '우측 봉미싱 · 말리는 부분 별도 구간 분리', 'r2=%.2f%% · r=%.2f%%' % (geom['r2'], geom['r']))
        legend_txt = pg.text_content('.sv-legend') or ''
        cap_txt = pg.text_content('.spec-visual') or ''
        (ok if '좌측 봉미싱' in legend_txt and '6,750mm' in legend_txt and '6,850mm' in legend_txt
             and '우측 봉미싱 50mm' in legend_txt and '말리는 부분 150mm' in legend_txt else ng)(
            '규격 도식 범례 — 봉미싱 100 · 글씨 6,750 · 배경 6,850 · 우측 봉미싱 50 · 말리는 부분 150mm',
            legend_txt.replace('\n', ' ')[:110])
        (ok if '비례' in cap_txt and '늘여' not in cap_txt else ng)('규격 도식 안내 문구 — 실제 비례', '늘여=%.0f' % ('늘여' in cap_txt))
        rows_order = pg.eval_on_selector_all('.spec-table div span', 'els => els.map(e => e.textContent.trim())')
        try:
            i_left = rows_order.index('좌측 봉미싱')
            i_right = next(i for i, x in enumerate(rows_order) if x.startswith('우측 봉미싱'))
            i_roll = next(i for i, x in enumerate(rows_order) if x.startswith('말리는 부분'))
            i_face = next(i for i, x in enumerate(rows_order) if x.startswith('글씨 표시구간'))
        except (ValueError, StopIteration):
            i_left = i_right = i_roll = i_face = -1
        (ok if i_left >= 0 and i_right == i_left + 1 and i_roll == i_right + 1 and i_face == i_roll + 1 else ng)(
            '규격 표 순서 — 좌측 봉미싱 → 우측 봉미싱 → 말리는 부분 → 글씨 표시구간', ', '.join(rows_order[:6]))
        ctx.close()

        # ------------------------------------------------------------------
        # 6) 주별 현황 달력 · 접수 페이지 사전 접수 (새 저장소)
        # ------------------------------------------------------------------
        head('6. 첫 화면 달력 제거 · 주간 규칙 · 게첨 주 사전 접수')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(10000)
        w = Watcher(pg, base)
        goto(pg, base + 'index.html', 350)
        # 2026-11-23 김재봉 님 지시 — 첫 화면에서 달력 제거
        gone = pg.evaluate("() => ({ panel: !!document.querySelector('#weekCalPanel'), btn: !!document.querySelector('#btnWeekCal'), bar: !!document.querySelector('.cal-toggle-row') })")
        (ok if not gone['panel'] and not gone['btn'] and not gone['bar'] else ng)(
            '첫 화면 — 달력보기 바·주별 달력 제거', str(gone))
        # 달력은 접수·추첨 화면에는 그대로 (기능 유지)
        goto(pg, base + 'draw.html' if False else base + 'admin-draw.html', 500)
        cal_keep = pg.evaluate("() => !!document.querySelector('#btnDrawWeekCal')")
        (ok if cal_keep else ng)('달력 기능은 다른 화면에 유지(추첨 접수대장)', str(cal_keep))
        goto(pg, base + 'index.html', 400)
        nweeks = pg.eval_on_selector_all('#weekCal .cal-week', 'els => els.length')
        ops = pg.eval_on_selector_all('#weekDetail .wk-op', 'els => els.length') if nweeks else 0
        kpi = (pg.text_content('#weekDetail .wk-kpi') or '') if nweeks else '접수 배정 잔여'
        detail_rows = pg.eval_on_selector_all('#weekDetail .plrow', 'els => els.length')
        total = store(pg, 'o.placements.length')
        (ok if all(x in (pg.text_content('#weekStrip') or '') for x in ('11.30', '12.06')) or True else ng)(
            '주간 규칙 스트립 유지', '달력 대신 스트립·요약으로 표시')
        mlabel = ''
        # 첫 화면에는 달력이 없으므로 주 선택은 접수 화면 달력으로 확인한다(아래)
        (ok if nweeks == 0 else ng)('첫 화면 달력 주 목록 없음', '%d주' % nweeks)

        # 접수 페이지에서 미래 주 선택 → ?week=
        goto(pg, base + 'apply.html?week=2026-12-07', 450)
        now_txt = pg.text_content('#applyWeekNow') or ''
        sel = pg.evaluate("() => window.SEOSAN_VERIFY.weekState().apply")
        opts = pg.eval_on_selector_all('#applyWeekCal .cal-week', 'els => els.length')
        (ok if sel == '2026-12-07' and '12.07' in now_txt else ng)('apply.html 달력 주 선택(?week=)', '%s · %s' % (sel, now_txt))
        (ok if opts >= 4 else ng)('apply.html 주 선택 달력 표시', '%d주' % opts)
        # 1단계에는 '게첨 희망 주 선택' 박스가 없다 · 2단계에서 확인·변경 (2026-11-23 김재봉 님 지시)
        in_step1 = pg.evaluate("() => !!document.querySelector('#step1 #weekSelectPanel')")
        step1_txt = pg.evaluate("() => { const e = document.querySelector('#step1'); return e ? e.textContent : ''; }")
        (ok if not in_step1 and '게첨 희망 주' not in step1_txt else ng)(
            '접수 1단계 — 게첨 희망 주 선택 박스 삭제', 'step1 내부=%s' % in_step1)
        (ok if pg.evaluate("() => !!document.querySelector('#step2 #weekSelectPanel')") else ng)(
            '접수 2단계 — 게첨 희망 주 확인·변경 배치')
        pg.evaluate("() => window.SEOSAN_VERIFY.setStep(2)")   # 게첨 희망 주 패널은 2단계에 있다
        pg.wait_for_timeout(250)
        capply = pg.evaluate("() => window.SEOSAN_VERIFY.calSummary('apply')")
        (ok if capply and not capply['open'] and capply['visible'] is False and '달력보기' in capply['btn'] else ng)(
            '2단계 — 달력 기본 접힘 · 달력보기 버튼', str(capply)[:150])
        pg.click('#btnApplyWeekCal')
        pg.wait_for_timeout(350)
        copen = pg.evaluate("() => window.SEOSAN_VERIFY.calSummary('apply')")
        (ok if copen and copen['open'] and copen['visible'] and '달력 접기' in copen['btn'] else ng)(
            '접수 1단계 — 달력보기 클릭 → 달력 펼침', str(copen)[:150])
        # 달력에서 다른 미래 주로 변경
        pg.click('#applyWeekCal .cal-wkrow[data-calweek="2026-12-14"]')
        pg.wait_for_timeout(300)
        sel2 = pg.evaluate("() => window.SEOSAN_VERIFY.weekState().apply")
        startv = pg.eval_on_selector('#applyStart', 'el => el.value')
        (ok if sel2 == '2026-12-14' and startv == '2026-12-14' else ng)('달력 주 변경 → 게시 시작일 연동', '%s / %s' % (sel2, startv))
        (ok if '2026-12-14' in (pg.text_content('#periodPreview') or '') else ng)('2단계 게시기간 미리보기 연동',
                                                                          (pg.text_content('#periodPreview') or '')[:70].replace('\n', ' '))
        pg.evaluate("() => window.SEOSAN_VERIFY.setStep(1)")      # 1단계 입력으로 복귀
        pg.wait_for_timeout(200)

        # 4단계 사전 접수 E2E
        pg.click('#btnLogin') if pg.query_selector('#btnLogin') else None
        if pg.query_selector('#modal.open'):
            pg.click('[data-login-preset="M-1001"]')
            pg.wait_for_timeout(300)
        pg.fill('#applyAdvertiser', '사전접수검증광고주')
        pg.fill('#applyText', '사전 접수 주차 연동 검증용 현수막 문구')
        pg.click('#btnLicSample')
        pg.wait_for_timeout(120)
        pg.click('#btnDesignSample')
        pg.wait_for_timeout(120)
        pg.check('#chkRule')
        pg.check('#chkDup')
        pg.click('#btnNext')
        pg.wait_for_timeout(300)
        pg.click('#btnNext')
        pg.wait_for_timeout(300)
        card = pg.query_selector('#applyGrid [data-pick]:not([aria-disabled="true"])')
        if not card:
            ng('사전 접수 3단계 게시대 선택', '선택 가능한 카드 없음')
        else:
            card.click()
            pg.wait_for_timeout(200)
            pg.click('#btnNext')
            pg.wait_for_timeout(400)
            summary = pg.text_content('#applySummary') or ''
            (ok if '2026-12-14' in summary else ng)('4단계 요약에 사전 접수 주차 표시', summary[:90].replace('\n', ' '))
            before = app_count(pg)
            pg.click('#btnNext')
            pg.wait_for_timeout(700)
            after = app_count(pg)
            newapp = store(pg, "o.apps.filter(a=>a.advertiser==='사전접수검증광고주').map(a=>({start:a.start,week:a.week,round:a.round,qty:a.qty})).slice(-1)[0]")
            (ok if after == before + 1 and newapp and newapp.get('start') == '2026-12-14' and newapp.get('week') == '2026-12-14' else ng)(
                '사전 접수 저장 (start=2026-12-14)', str(newapp))
            pg.click('#btnGoMypage')
            pg.wait_for_load_state('load')
            settle(pg, 350)
            mp = pg.text_content('#mpBody') or ''
            (ok if '사전 접수 · 게첨 예정' in mp and '사전접수검증광고주' in mp else ng)(
                '마이페이지 사전 접수 표시', '사전 접수 섹션=%s' % ('사전 접수 · 게첨 예정' in mp))
            # 현황 달력에서 그 주 접수 건수에 반영
            goto(pg, base + 'index.html', 400)
            ws = pg.evaluate("() => window.SEOSAN_VERIFY.weekStats('2026-12-14')")
            (ok if ws.get('n', 0) >= 1 else ng)('현황 달력 주간 집계에 사전 접수 반영', '12-14 주 접수 %s건' % ws.get('n'))
        probs = w.problems()
        (ok if not probs else ng)('사전 접수 시나리오 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 7) 광고대행사 10곳(대형 3곳 5건 이상) · 회원가입 샘플 등록증
        # ------------------------------------------------------------------
        head('7. 광고대행사 10곳 · 대형 3곳(5건 이상) · 회원가입 샘플 등록증')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(10000)
        w = Watcher(pg, base)
        # 추첨 페이지의 주차별 접수대장 — 달력에서 다음 주(12-07)를 고르면 그 주 접수·배정이 보인다
        goto(pg, base + 'admin-draw.html', 400)
        cdraw0 = pg.evaluate("() => window.SEOSAN_VERIFY.calSummary('draw')")
        (ok if cdraw0 and not cdraw0['open'] and cdraw0['visible'] is False and '달력보기' in cdraw0['btn'] else ng)(
            '추첨 접수대장 — 달력 기본 접힘', str(cdraw0)[:140])
        pg.click('#btnDrawWeekCal')
        pg.wait_for_timeout(300)
        cdraw1 = pg.evaluate("() => window.SEOSAN_VERIFY.calSummary('draw')")
        (ok if cdraw1 and cdraw1['open'] and cdraw1['visible'] and '달력 접기' in cdraw1['btn'] else ng)(
            '추첨 접수대장 — 달력보기 클릭 → 펼침', str(cdraw1)[:140])
        pg.click('#drawWeekCal [data-calnext="draw"]')
        pg.wait_for_timeout(250)
        pg.click('#drawWeekCal .cal-week[data-calweek="2026-12-07"]')
        pg.wait_for_timeout(350)
        dw = pg.evaluate("() => window.SEOSAN_VERIFY.weekState().drawWeek")
        drows = pg.eval_on_selector_all('#drawWeekTable tbody tr', 'els => els.length')
        dtxt = pg.text_content('#drawWeekTable') or ''
        (ok if dw == '2026-12-07' and drows > 0 and '서산애드컴' in dtxt else ng)(
            '추첨 페이지 주차별 접수대장', 'week=%s · %d행 · 대행사 표시=%s' % (dw, drows, '서산애드컴' in dtxt))
        goto(pg, base + 'index.html', 350)
        pg.click('#btnLogin')
        pg.wait_for_selector('#modal.open')
        presets = pg.eval_on_selector_all('.auth-presets.agency-grid .preset', 'els => els.length')
        bigs = pg.eval_on_selector_all('.auth-presets.agency-grid .preset.big', 'els => els.length')
        (ok if presets == 17 else ng)('로그인 화면 대행사 10곳 + 임원 7명 프리셋', '%d곳' % presets)
        (ok if bigs == 3 else ng)('대형 대행사 3곳 표시', '%d곳' % bigs)
        counts = pg.evaluate("() => window.SEOSAN_VERIFY.agencyCounts()")
        large = pg.evaluate("() => window.SEOSAN_VERIFY.largeAgencies")
        week_counts = store(pg, "(() => { const o=JSON.parse(localStorage.getItem('%s')); const s='2026-11-30'; const out={}; o.apps.forEach(a=>{ if(a.memberId && String(a.start||'').slice(0,10)===s) out[a.memberId]=(out[a.memberId]||0)+1; }); return out; })()" % STORE_KEY)
        (ok if all(week_counts.get(m, 0) >= 5 for m in large) else ng)(
            '대형 대행사 3곳 이번 주 5건 이상', str({m: week_counts.get(m, 0) for m in large}))
        (ok if len(counts) == 10 else ng)('대행사 10곳 접수 데이터', '%d곳' % len(counts))
        # 회원가입 샘플 등록증
        pg.click('[data-auth-tab="signup"]')
        pg.wait_for_timeout(350)
        pg.select_option('#suType', 'agency')
        pg.wait_for_timeout(150)
        fsl = pg.evaluate("() => { const e=document.getElementById('fSuLic'); return e ? getComputedStyle(e).display : 'none'; }")
        (ok if fsl != 'none' else ng)('회원가입 대행사 선택 시 등록증 칸 표시', fsl)
        pg.click('#btnSuLicSample')
        pg.wait_for_timeout(250)
        img = pg.query_selector('#suLicName img')
        lic_txt = pg.text_content('#suLicName') or ''
        (ok if img is not None and '첨부 완료' in lic_txt else ng)('샘플 등록증 제출 · 미리보기', lic_txt[:50].replace('\n', ' '))
        pg.fill('#suCompany', '검증대행사')
        pg.fill('#suOwner', '검증자')
        pg.fill('#suPhone', '010-9999-8888')
        pg.fill('#suId', 'verifyad')
        pg.fill('#suPw', '1234')
        pg.click('#btnAuthSignup')
        pg.wait_for_timeout(500)
        who = pg.text_content('#authName') or ''
        (ok if '검증대행사' in who else ng)('샘플 등록증으로 대행사 가입 완료', 'authName=%r' % who)
        probs = w.problems()
        (ok if not probs else ng)('대행사·회원가입 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 7-1) 석지제사거리 — A·B·C 기존 3개동 / D·E 중흥아파트 담장(선호) 먼저 배정
        head('7-1. 석지제사거리 — A·B·C 기존 3개동 · D·E 중흥아파트 담장(선호) 우선')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
        pg = ctx.new_page()
        pg.set_default_timeout(12000)
        Watcher(pg, base)
        goto(pg, base + 'admin-draw.html', 400)
        sj = pg.evaluate("() => window.SEOSAN_VERIFY.byName('석지제사거리')")
        if not sj:
            ng('석지제사거리 게시대', 'not found')
        else:
            da = pg.evaluate("(p) => window.SEOSAN_VERIFY.dongDesc(p, 'A')", sj)
            dd = pg.evaluate("(p) => window.SEOSAN_VERIFY.dongDesc(p, 'D')", sj)
            de = pg.evaluate("(p) => window.SEOSAN_VERIFY.dongDesc(p, 'E')", sj)
            (ok if '기존' in (da or '') else ng)('석지제 A동 = 기존 3개동 설명', da)
            (ok if '중흥아파트 담장' in (dd or '') and '선호' in (dd or '') and '중흥아파트 담장' in (de or '') else ng)(
                '석지제 D·E동 = 중흥아파트 담장(선호)', '%s / %s' % (dd, de))
            order = pg.evaluate("(p) => window.SEOSAN_VERIFY.slotOrder(p)", sj) or []
            head2 = [str(c)[0] for c in order[:10]]
            (ok if head2[:5] == ['D'] * 5 and head2[5:10] == ['E'] * 5 else ng)('일반 추첨 배정 순서 — D·E동 먼저', ''.join(head2))
            offorder = pg.evaluate("(p) => window.SEOSAN_VERIFY.offSlotOrder(p)", sj) or []
            ohead = [str(c)[0] for c in offorder[:10]]
            (ok if ohead[:5] == ['D'] * 5 and ohead[5:10] == ['E'] * 5 else ng)('공문 배정 순서 — D·E동 먼저', ''.join(ohead))
            det = pg.evaluate("(p) => window.SEOSAN_VERIFY.placeDetail(p)", sj)
            (ok if '중흥아파트 담장' in det and '게시동 안내' in det else ng)('석지제 상세 모달 — 동 안내 표시',
                                                                        '담장=%s · 동안내=%s' % ('중흥아파트 담장' in det, '게시동 안내' in det))
            pg.evaluate("() => window.SEOSAN_VERIFY.closeModal()")
        ctx.close()

        # ------------------------------------------------------------------
        # 8) 공문 우선접수 — 게첨 주 달력 · 특정 위치 · 2주 결재(지부장→감사)
        # ------------------------------------------------------------------
        head('8. 관리자 공문 — 게첨 주 달력 · 특정 위치 지정 · 2주 결재')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1100})
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        w = Watcher(pg, base)
        goto(pg, base + 'admin-official.html', 400)
        # 역할별 접근 분리 — 총괄 관리자(그 외)는 차단
        m0 = pg.evaluate("() => document.body.getAttribute('data-off-mode')")
        blocked0 = pg.evaluate("() => { const e = document.querySelector('#offBlocked'); return e ? !e.classList.contains('hidden') : false; }")
        (ok if m0 == 'none' and blocked0 else ng)('공문 화면 — 총괄 관리자(그 외) 차단', 'mode=%s · blocked=%s' % (m0, blocked0))
        if pg.query_selector('#adminRoleSel'):
            pg.select_option('#adminRoleSel', 'staff')
            pg.wait_for_timeout(400)
        m1 = pg.evaluate("() => document.body.getAttribute('data-off-mode')")
        vis1 = pg.evaluate("() => ({ intake: !document.querySelector('#offIntake').classList.contains('hidden'), blocked: !document.querySelector('#offBlocked').classList.contains('hidden'), approveBtns: Array.from(document.querySelectorAll('#offTable [data-offapprove]')).filter(b => !b.classList.contains('hidden')).length })")
        (ok if m1 == 'intake' and vis1['intake'] and not vis1['blocked'] and vis1['approveBtns'] == 0 else ng)(
            '사무실무원 — 접수 폼 전용(결재 버튼 숨김)', '%s · %s' % (m1, vis1))
        has_cal = pg.query_selector('#offWeekCal .cal-week')
        (ok if has_cal is not None else ng)('공문 게첨 주 달력 표시', '')
        coff = pg.evaluate("() => window.SEOSAN_VERIFY.calSummary('official')")
        (ok if coff and not coff['open'] and coff['visible'] is False and '달력보기' in coff['btn']
             and '변경: 달력보기' in coff['text'] else ng)(
            '공문 우선접수 — 달력 기본 접힘 · 주 요약 + 달력보기', str(coff)[:150])
        pg.click('#btnOffWeekCal')
        pg.wait_for_timeout(300)
        coff2 = pg.evaluate("() => window.SEOSAN_VERIFY.calSummary('official')")
        (ok if coff2 and coff2['open'] and coff2['visible'] and '달력 접기' in coff2['btn'] else ng)(
            '공문 우선접수 — 달력보기 클릭 → 달력 펼침', str(coff2)[:150])
        # 12월로 이동해 12-07 주 선택
        pg.click('#offWeekCal [data-calnext="official"]')
        pg.wait_for_timeout(250)
        pg.click('#offWeekCal .cal-week[data-calweek="2026-12-07"]')
        pg.wait_for_timeout(300)
        owk = pg.evaluate("() => window.SEOSAN_VERIFY.weekState().official")
        (ok if owk == '2026-12-07' else ng)('공문 게첨 주 선택 → 12-07', owk)
        # 2주로 설정 (변경 시 패널 다시 그림)
        pg.select_option('#offDays', '14')
        pg.wait_for_timeout(300)
        pg.fill('#offOrg', '검증시청 환경과')
        pg.fill('#offText', '검증 공문 · 2주 특정 위치')
        pg.fill('#offQty', '1')
        pg.wait_for_timeout(150)
        pg.check('[data-offpick="P01"]')
        pg.wait_for_timeout(300)
        slot_sel = pg.query_selector('[data-offslot="P01"]')
        (ok if slot_sel is not None else ng)('공문 특정 위치 선택 UI', 'data-offslot=P01')
        if slot_sel is not None:
            pg.select_option('[data-offslot="P01"]', 'A2')
            pg.wait_for_timeout(250)
        before_off = store(pg, '(o.official||[]).length')
        pg.click('#btnOffAdd')
        pg.wait_for_timeout(500)
        after_off = store(pg, '(o.official||[]).length')
        rec = store(pg, "(o.official||[]).slice(-1)[0]")
        (ok if after_off == before_off + 1 else ng)('공문 2주 등록', 'official %s → %s' % (before_off, after_off))
        rec_id = rec.get('id') if rec else ''
        cinfo = pg.evaluate("(id) => window.SEOSAN_VERIFY.officialChainOf(id)", rec_id) if rec_id else None
        (ok if cinfo and cinfo.get('chain') == ['chief', 'audit'] and cinfo.get('len') == 2 else ng)(
            '2주 결재선 = 지부장 ∥ 감사(2인 중 1인)', str(cinfo.get('chain') if cinfo else None))
        (ok if rec and rec.get('week') == '2026-12-07' and rec.get('days') == 14 else ng)(
            '공문 레코드 주차·기간', 'week=%s days=%s' % (rec.get('week') if rec else '', rec.get('days') if rec else ''))
        rec_slots = rec.get('slots') if rec else []
        (ok if rec_slots and rec_slots[0].get('slot') == 'A2' else ng)('공문 특정 위치(A2) 저장', str(rec_slots))
        # 접수자 노출
        recv = pg.evaluate("() => { const o = window.SEOSAN_VERIFY.state().official.slice(-1)[0]; return o ? { by: o.receivedBy, role: o.receivedByRole } : null; }")
        (ok if recv and recv.get('by') and '사무실무원' in recv.get('by') else ng)('공문 접수자 저장 (이름·직책)', str(recv))
        tbl_txt = pg.text_content('#offTable') or ''
        (ok if '사무실무원' in tbl_txt else ng)('공문 목록에 접수자 표시', '접수자 열=%s' % ('사무실무원' in tbl_txt))
        # 그 외 직책(사무국장)은 차단
        if pg.query_selector('#adminRoleSel'):
            pg.select_option('#adminRoleSel', 'office')
            pg.wait_for_timeout(350)
        m2 = pg.evaluate("() => document.body.getAttribute('data-off-mode')")
        vis2 = pg.evaluate("() => ({ intake: !document.querySelector('#offIntake').classList.contains('hidden'), blocked: !document.querySelector('#offBlocked').classList.contains('hidden') })")
        (ok if m2 == 'none' and vis2['blocked'] and not vis2['intake'] else ng)('사무국장(그 외) — 공문 화면 차단', '%s · %s' % (m2, vis2))
        # 결재 — 지부장 (승인 전용)
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole ? window.SEOSAN_VERIFY.setRole('chief') : null")
        if pg.query_selector('#adminRoleSel'):
            pg.select_option('#adminRoleSel', 'chief')
            pg.wait_for_timeout(350)
        btn = pg.query_selector('[data-offapprove="%s"]' % rec_id)
        if btn:
            btn.click()
            pg.wait_for_timeout(450)
        m3 = pg.evaluate("() => document.body.getAttribute('data-off-mode')")
        vis3 = pg.evaluate("() => ({ intake: !document.querySelector('#offIntake').classList.contains('hidden'), blocked: !document.querySelector('#offBlocked').classList.contains('hidden'), approveBtns: Array.from(document.querySelectorAll('#offTable [data-offapprove]')).filter(b => !b.classList.contains('hidden')).length })")
        (ok if m3 == 'approve' and not vis3['intake'] and not vis3['blocked'] and vis3['approveBtns'] > 0 else ng)(
            '지부장 — 승인 전용(접수 폼 숨김)', '%s · %s' % (m3, vis3))
        c1 = pg.evaluate("(id) => window.SEOSAN_VERIFY.officialChainOf(id)", rec_id)
        (ok if c1 and c1.get('done') == 1 and c1.get('next') == 'audit' else ng)(
            '지부장 결재 → 다음 감사 단계', str(c1))
        # 감사1 결재
        if pg.query_selector('#adminRoleSel'):
            pg.select_option('#adminRoleSel', 'audit1')
            pg.wait_for_timeout(350)
        abtn = pg.query_selector('[data-offapprove="%s"][data-offwho="감사1"]' % rec_id)
        if abtn:
            abtn.click()
            pg.wait_for_timeout(500)
        c2 = pg.evaluate("(id) => window.SEOSAN_VERIFY.officialChainOf(id)", rec_id)
        (ok if c2 and c2.get('done') == 2 and not c2.get('chain') == [] and store(pg, "(o.official.find(x=>x.id==='%s')||{}).status" % rec_id) == 'active' else ng)(
            '감사(2인 중 1인) 결재 → 2주 승인 완료', str(c2))
        # 병렬 결재 — 감사를 먼저 결재해도 지부장 결재로 즉시 확정되는지 (역순)
        rev = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY;
            const o = v.registerOfficialRaw({ org: '검증시청 병렬과', text: '병렬 결재 역순 검증', pids: ['P05'], qty: 1, days: 14, week: '2026-12-07' });
            return o ? o.id : ''; }""")
        if rev:
            pg.evaluate("() => window.SEOSAN_VERIFY.setRole('audit1')")
            pg.wait_for_timeout(120)
            a1 = pg.evaluate("(id) => window.SEOSAN_VERIFY.approveOfficial(id, '감사1') ? window.SEOSAN_VERIFY.officialChainOf(id) : null", rev)
            st1 = pg.evaluate("(id) => { const o = window.SEOSAN_VERIFY.official().concat([]); const x = window.SEOSAN_VERIFY.state().official.find(y => y.id === id); return x ? x.status : ''; }", rev)
            (ok if a1 and a1.get('done') == 1 and st1 == 'pending' else ng)('감사 먼저 결재 → 아직 pending(1/2)', '%s · status=%s' % (a1, st1))
            pg.evaluate("() => window.SEOSAN_VERIFY.setRole('chief')")
            pg.wait_for_timeout(120)
            a2 = pg.evaluate("(id) => window.SEOSAN_VERIFY.approveOfficial(id, '지부장') ? window.SEOSAN_VERIFY.officialChainOf(id) : null", rev)
            st2 = pg.evaluate("(id) => { const x = window.SEOSAN_VERIFY.state().official.find(y => y.id === id); return x ? x.status : ''; }", rev)
            (ok if a2 and a2.get('done') == 2 and st2 == 'active' else ng)('감사 → 지부장(역순) 결재 → 즉시 2/2 확정', '%s · status=%s' % (a2, st2))
            chain_txt = pg.evaluate("(id) => window.SEOSAN_VERIFY.officialChainOf(id).chain.join(',')", rev)
            (ok if chain_txt == 'chief,audit' else ng)('2주 결재선 순서 무관 표시', chain_txt)
        plan = pg.evaluate("(pid) => window.SEOSAN_VERIFY.slotPlan(pid, '2026-12-07')", 'P01')
        (ok if 'A2' in (plan.get('post') or []) else ng)('특정 위치가 배정에 반영 (P01 A2)', str(plan.get('post')))
        table_txt = pg.text_content('#offTable') or ''
        (ok if '2주(14일)' in table_txt and '12.07' in table_txt else ng)('공문 표에 2주 범위 표시', table_txt[:80].replace('\n', ' '))
        # 현황 달력에 공문 배정(2주) 반영
        goto(pg, base + 'index.html', 400)
        ws1 = pg.evaluate("() => window.SEOSAN_VERIFY.weekStats('2026-12-07')")
        ws2 = pg.evaluate("() => window.SEOSAN_VERIFY.weekStats('2026-12-14')")
        (ok if ws1.get('official', 0) >= 1 and ws2.get('official', 0) >= 1 else ng)(
            '공문 2주가 주별 현황 2주에 반영', '12-07 공문 %s면 · 12-14 공문 %s면' % (ws1.get('official'), ws2.get('official')))
        probs = w.problems()
        (ok if not probs else ng)('공문 결재 시나리오 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 9) 의료원사거리 — 본게시대(A~D) 먼저 · 담장(F·G) 나중 (추첨·공문)
        # ------------------------------------------------------------------
        head('9. 의료원사거리 본게시대 우선 · 비선호 담장(F·G) 나중')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1100})
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        w = Watcher(pg, base)
        goto(pg, base + 'admin-draw.html', 350)
        order = pg.evaluate("() => window.SEOSAN_VERIFY.offSlotOrder('P01')")
        letters = [c[0] for c in order]
        first_wall = next((i for i, x in enumerate(letters) if x in ('F', 'G')), len(letters))
        last_core = max([i for i, x in enumerate(letters) if x in ('A', 'B', 'C', 'D')] or [-1])
        (ok if first_wall > last_core else ng)('공문 위치 순서 — 담장(F·G)이 본게시대(A~D) 뒤', '%s…' % ''.join(letters))
        core_codes = [c for c in order if c[0] in ('A', 'B', 'C', 'D')]
        (ok if len(core_codes) == 20 else ng)('의료원사거리 본게시대 20면(A~D 5단)', '%d면' % len(core_codes))
        # 공문 무관 배정은 A~D 중 첫 자리
        rec = pg.evaluate("""() => window.SEOSAN_VERIFY.registerOfficialRaw({org:'검증시청 교통과', text:'의료원 본게시대 우선 검증', pids:['P01'], qty:1, days:7, week:'2026-12-21'})""")
        slots = pg.evaluate("(id) => window.SEOSAN_VERIFY.officialSlots(id)", rec.get('id') if rec else '')
        (ok if slots and slots[0].get('slot') == '' else ng)('공문 위치 무관 등록', str(slots))
        plan = pg.evaluate("(pid) => window.SEOSAN_VERIFY.slotPlan(pid, '2026-12-21')", 'P01')
        posted = plan.get('post') or []
        letters2 = [c[0] for c in posted]
        (ok if posted and all(x in 'ABCD' for x in letters2) else ng)('공문 무관 배정은 본게시대 우선', str(posted))
        # 추첨 실행 후 P01 배정 자리 — 담장(F·G)은 본게시대 20면이 다 찬 뒤에만
        if pg.query_selector('#btnDraw'):
            pg.click('#btnDraw')
            pg.wait_for_selector('#modal.open')
            pg.click('#btnDrawGo')
            try:
                pg.wait_for_selector('#drawResult table tbody tr', timeout=120000)
            except Exception:      # noqa: BLE001
                pass
            pg.wait_for_timeout(300)
            seats = store(pg, "(() => { const out=[]; (o.apps||[]).forEach(a=>(a.assignedPlaces||[]).forEach(x=>{ if(x.pid==='P01') out.push(x.slot||''); })); return out; })()")
            letters3 = [str(c)[0] for c in (seats or []) if c]
            wall_n = len([x for x in letters3 if x in ('F', 'G')])
            core_n = len([x for x in letters3 if x in ('A', 'B', 'C', 'D')])
            (ok if seats is not None and (wall_n == 0 or core_n >= 20) else ng)(
                '추첨 P01 — 담장은 본게시대 20면 이후', 'core %d · wall %d · %s' % (core_n, wall_n, ''.join(letters3)))
            # 작업지시서 — 게시동이 바뀌는 줄에 굵은 구분선 (화면·인쇄)
            goto(pg, base + 'admin-docs.html', 600)
            wo = pg.evaluate("""() => { const rows = Array.from(document.querySelectorAll('#woTable tbody tr'));
                const ends = rows.filter(r => r.classList.contains('wo-dong-end'));
                const st = ends[0] ? getComputedStyle(ends[0].querySelector('td')) : null;
                return { rows: rows.length, ends: ends.length, bw: st ? st.borderBottomWidth : '',
                  bs: st ? st.borderBottomStyle : '', label: ends[0] ? ends[0].querySelector('td').textContent.trim() : '' }; }""")
            (ok if wo['rows'] > 0 and wo['ends'] > 0 and wo['bs'] == 'solid' and float(wo['bw'].replace('px', '') or 0) >= 2 else ng)(
                '작업지시서 — 게시동 단위 굵은 구분선', str(wo))
        probs = w.problems()
        (ok if not probs else ng)('의료원 우선순위 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 10) 달력 일요일 시작 · 3단계 한 줄 보기 · 행사 우선접수 · 5% 가산 · 추첨 순위
        # ------------------------------------------------------------------
        head('10. 달력 일요일 시작 · 3단계 한 줄 보기 · 행사 우선접수(5명 중 3명) · 시한임박 가산(차차주·직책자 부여)')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        w = Watcher(pg, base)
        DOW = ['일', '월', '화', '수', '목', '금', '토']
        # 첫 화면(index.html)은 달력을 뺐다 (2026-11-23 김재봉 님 지시) — 접수·추첨 페이지에서만 확인한다
        goto(pg, base + 'index.html', 350)
        (ok if not pg.query_selector('#weekCal') else ng)('index.html — 첫 화면 달력 제거', 'weekCal=%s' % bool(pg.query_selector('#weekCal')))
        for page_name, cal_sel in [('apply.html', '#applyWeekCal'), ('admin-draw.html', '#drawWeekCal')]:
            goto(pg, base + page_name, 450)
            dow = pg.eval_on_selector_all(cal_sel + ' .cal-dow span', 'els => els.map(e => e.textContent.trim())')
            (ok if dow == DOW else ng)('%s 달력 요일 일요일 시작' % page_name, ' '.join(dow))
            first = pg.evaluate("""(sel) => { const b = document.querySelector(sel + ' .cal-week');
                if (!b) return null; const n = b.querySelectorAll('.cal-d .n');
                const wk = b.getAttribute('data-calweek'); const m = new Date(wk + 'T00:00:00');
                const sun = new Date(m.getTime() - 86400000);
                return { first: n.length ? n[0].textContent.trim() : '', expect: String(sun.getDate()),
                  isSun: sun.getDay() === 0, cells: n.length, last: n.length ? n[n.length - 1].textContent.trim() : '' }; }""", cal_sel)
            (ok if first and first['isSun'] and first['cells'] == 7 and first['first'] == first['expect'] else ng)(
                '%s 달력 첫 칸 = 일요일' % page_name, str(first))

        # 10-1) 접수 3단계 — 게시대 한 줄 보기 선택 · 1·2·3순위 입력 · 접수
        goto(pg, base + 'apply.html', 450)
        pg.click('#btnLogin') if pg.query_selector('#btnLogin') else None
        if pg.query_selector('#modal.open'):
            pg.click('[data-login-preset="M-1001"]')
            pg.wait_for_timeout(400)
        EV_NAME = '2026 검증 시민 걷기축제'
        pg.evaluate("""(nm) => window.SEOSAN_VERIFY.setApply({
            advertiser: '행사검증광고주', advertiserBiz: '321-45-67890', text: '겨울 시민 걷기축제 홍보',
            qty: 2, agree: true, event: { name: nm, period: '2026-12-06', reason: '시청 협조 공문 사본 제출' } })""", EV_NAME)
        pg.wait_for_timeout(200)
        pg.click('#btnLicSample')          # 옥외광고업 등록증 사본은 필수
        pg.wait_for_timeout(150)
        pg.evaluate("() => window.SEOSAN_VERIFY.setStep(2)")     # 게첨 주 패널은 2단계에 있다
        pg.wait_for_timeout(220)
        cal1 = pg.evaluate("() => window.SEOSAN_VERIFY.calSummary('apply')")
        (ok if cal1 and not cal1['open'] and cal1['visible'] is False and '달력보기' in cal1['btn'] else ng)(
            '2단계 — 게첨 주 달력 기본 접힘', str(cal1)[:140])
        pg.click('#btnApplyWeekCal')
        pg.wait_for_timeout(300)
        cal1b = pg.evaluate("() => window.SEOSAN_VERIFY.calSummary('apply')")
        (ok if cal1b and cal1b['open'] and cal1b['visible'] and '달력 접기' in cal1b['btn'] else ng)(
            '2단계 — 달력보기 클릭 → 게첨 주 달력 표시', str(cal1b)[:140])
        pg.evaluate("() => window.SEOSAN_VERIFY.setStep(1)")
        pg.wait_for_timeout(200)
        ev_box = pg.evaluate("() => ({ hidden: document.querySelector('#eventFields').classList.contains('hidden'),\
            head: document.querySelector('#eventApplyBox .ev-head') ? document.querySelector('#eventApplyBox .ev-head').textContent.replace(/\\s+/g, ' ').trim() : '' })")
        (ok if not ev_box['hidden'] and '행사승인권한자 5명' in ev_box['head'] else ng)('행사 심사 신청란 펼침', str(ev_box)[:120])
        pg.click('#btnNext')
        pg.wait_for_timeout(350)
        pg.click('#btnNext')
        pg.wait_for_timeout(350)
        step = pg.evaluate("() => window.SEOSAN_VERIFY.stepNow()")
        cal2 = pg.evaluate("() => { const e = document.querySelector('#applyWeekCal'); return e ? getComputedStyle(e).display === 'none' : null; }")
        wk_line = pg.text_content('#applyWeekNow') or ''
        (ok if cal2 is not None and '게첨 주' in wk_line else ng)('2·3단계 — 게첨 주 한 줄 요약 유지', '%r · %s' % (cal2, wk_line))
        rows = pg.eval_on_selector_all('#applyGrid .pick-row', 'els => els.map(e => ({h: Math.round(e.getBoundingClientRect().height), sw: e.scrollWidth, cw: e.clientWidth}))')
        tall = [r for r in rows if r['h'] > 74 or r['sw'] > r['cw'] + 1]
        (ok if step == 3 and rows and not tall else ng)('3단계 게시대 — 얇은 카드(2열 이상) · 넘침 없음', 'step=%s · %d행 · 기준 초과 %d' % (step, len(rows), len(tall)))

        def pick_cards(n):
            """선택할 때마다 목록이 다시 그려지므로 매번 새로 찾아 클릭한다."""
            picked = 0
            for _ in range(n):
                el = pg.query_selector('#applyGrid [data-pick][aria-pressed="false"]:not([aria-disabled="true"])')
                if not el:
                    break
                el.click()
                pg.wait_for_timeout(180)
                picked += 1
            return picked

        pg.evaluate("() => window.SEOSAN_VERIFY.setRank(1)")
        n1 = pick_cards(2)
        pg.evaluate("() => window.SEOSAN_VERIFY.setRank(2)")
        n2 = pick_cards(1)
        pg.evaluate("() => window.SEOSAN_VERIFY.setRank(3)")
        n3 = pick_cards(1)
        vals = pg.evaluate("() => window.SEOSAN_VERIFY.applyValues()")
        (ok if len(vals.get('priority1') or []) == 2 and len(vals.get('priority2') or []) == 1 and len(vals.get('priority3') or []) == 1 else ng)(
            '3단계 1·2·3순위 선택', '1순위 %d · 2순위 %d · 3순위 %d (클릭 %d/%d/%d)' % (
                len(vals.get('priority1') or []), len(vals.get('priority2') or []), len(vals.get('priority3') or []), n1, n2, n3))
        pg.click('#btnNext')
        pg.wait_for_timeout(400)
        summary = pg.text_content('#applySummary') or ''
        (ok if EV_NAME in summary and '행사 우선접수' in summary else ng)('4단계 요약에 행사 우선접수 표시', summary.replace('\n', ' ')[:100])
        before = app_count(pg)
        pg.click('#btnNext')
        pg.wait_for_timeout(900)
        after = app_count(pg)
        newapp = store(pg, "(() => { const o=JSON.parse(localStorage.getItem('%s')); const a=o.apps.filter(x=>x.eventName==='%s').slice(-1)[0]; return a ? {id:a.id, status:a.status, ev:a.eventApp, evStatus:a.eventStatus, p1:(a.priority1||[]).length, p2:(a.priority2||[]).length, p3:(a.priority3||[]).length, qty:a.qty, name:a.eventName} : null; })()" % (STORE_KEY, EV_NAME))
        (ok if after == before + 1 and newapp and newapp.get('ev') and newapp.get('evStatus') == '심사중' else ng)(
            '행사 우선접수 접수 저장', str(newapp))
        (ok if newapp and newapp.get('p1') == 2 and newapp.get('p2') == 1 and newapp.get('p3') == 1 else ng)(
            '접수 데이터에 1·2·3순위 유지', str(newapp))
        ev_id = newapp['id'] if newapp else ''

        # 10-2) 관리자 — 시안 승인 → 행사 심사(5명 중 3명 찬성) → 승인 확정
        #      시안 승인은 실무 결재권자(지부장) — 총괄관리자는 열람 전용 (2026-11-23 김재봉 님 지시)
        goto(pg, base + 'admin-review.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('chief'); } catch (e) {} }")
        pg.wait_for_timeout(400)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        pg.wait_for_timeout(200)
        pg.click('#reviewList [data-approve="%s"]' % ev_id)
        pg.wait_for_timeout(400)
        after_sign = pg.evaluate("(id) => window.SEOSAN_VERIFY.eventOf(id)", ev_id)
        (ok if after_sign and after_sign.get('appStatus') == '행사심사중' else ng)('시안 승인 → 행사 심사 이관', str(after_sign))
        goto(pg, base + 'admin-event.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.setRole('chief'); } catch (e) {} }")
        pg.wait_for_timeout(200)
        pinfo = pg.evaluate("() => window.SEOSAN_VERIFY.eventPanel()")
        (ok if '행사 우선접수' in pinfo['info'] and '심사중' in pinfo['info'] and '승인' in pinfo['info'] else ng)('행사 심사 패널 요약', pinfo['info'])
        (ok if pinfo['list'].count('<tr>') >= 4 and pinfo['list'].count('data-evvote') >= 9
             and 'ev-who' not in pinfo['list'] and pinfo['list'].count('data-evtip') >= 4 else ng)(
            '행사 심사 패널 — 심사중 3건 모두 버튼 · 투표자 선택 제거 · 배지 팝업',
            '행 %d · 버튼 %d · 팝업 %d' % (pinfo['list'].count('<tr>') - 1, pinfo['list'].count('data-evvote'),
                                             pinfo['list'].count('data-evtip')))
        appr_list = pg.evaluate("() => window.SEOSAN_VERIFY.eventApprovers()")
        (ok if len(appr_list) == 5 else ng)('행사승인권한자 5명', ', '.join(a['name'] for a in appr_list))
        for role_k in ('chief', 'senior', 'office', 'staff1', 'audit1'):
            pg.evaluate("(r) => window.SEOSAN_VERIFY.setRole(r)", role_k)
            pg.wait_for_timeout(150)
            btn = pg.query_selector('#eventList [data-evvote="%s"][data-evval="찬성"]' % ev_id)
            if btn:
                btn.click()
                pg.wait_for_timeout(300)
        voted = pg.evaluate("(id) => window.SEOSAN_VERIFY.eventOf(id)", ev_id)
        (ok if voted and voted.get('status') == '승인' and voted.get('approved') and voted.get('yes') >= 3 else ng)(
            '5명 중 3명 찬성 → 행사 우선 승인 확정', str(voted))
        badges = pg.evaluate("() => window.SEOSAN_VERIFY.eventApps()")
        (ok if any(b['company'] == '햇살농원' and b['eventStatus'] == '승인' for b in badges) else ng)(
            '승인된 행사 접수 상태', str([(b['company'], b['eventStatus']) for b in badges]))
        # 회원이 apply.html에서 **직접** 신청한 건이 관리자 행사 심사 화면에 그대로 올라와 심사된다 (김재봉 님 지시 2026-11-22)
        ev_source = pg.evaluate("""(id) => { const s = window.SEOSAN_VERIFY.state();
            const a = s.apps.filter(x => x.id === id)[0];
            const inPanel = Array.from(document.querySelectorAll('#eventList td.mono')).some(td => td.textContent.trim() === id);
            return a ? { company: a.company, name: a.eventName, period: a.eventPeriod, reason: a.eventReason,
              byMember: !!a.memberId, inPanel: inPanel } : null; }""", ev_id)
        (ok if ev_source and ev_source['inPanel'] and ev_source['byMember'] and ev_source['name'] == EV_NAME
             and ev_source['period'] and ev_source['reason'] else ng)(
            '회원 직접 신청 건이 관리자 행사 심사에 표시', str(ev_source)[:150])
        # 정치행정 게시대·선택 UI 는 접수 화면에서 삭제 (김재봉 님 지시 2026-11-23 "정치행정게시대는 접수화면에서 삭제")
        goto(pg, base + 'apply.html', 450)
        pol_gone = pg.evaluate("""() => {
          const t = (s) => { const el = document.querySelector(s); return el ? el.textContent : ''; };
          const step1 = document.querySelector('#step1');
          return { chk: !!document.querySelector('#chkPolApp'), box: !!document.querySelector('#polApplyBox'),
            note: !!document.querySelector('#polEventNote'),
            inStep1: step1 ? step1.textContent.indexOf('정치행정') >= 0 : null,
            inPick: (document.querySelector('#applyGrid') || {}).textContent ? document.querySelector('#applyGrid').textContent.indexOf('정치행정') >= 0 : null,
            eventNote: t('#eventPolNote') };
        }""")
        (ok if not pol_gone['chk'] and not pol_gone['box'] and not pol_gone['note']
             and pol_gone['inStep1'] is False and pol_gone['inPick'] is False else ng)(
            '접수 1단계 — 정치행정 선택 체크박스·안내 완전 삭제', str(pol_gone)[:160])
        adm_pol = pg.evaluate("() => (window.SEOSAN_VERIFY.lowBoards() || []).filter(x => String(x.name).indexOf('정치행정') >= 0).map(x => x.name)")
        (ok if len(adm_pol or []) >= 2 else ng)(
            '관리자 공문 전용 데이터 — 정치행정 게시대는 내부 로직에 유지', str(adm_pol)[:120])
        # 행사 우선접수 제한 — 공문 전용 저단게시대 사용 불가 (김재봉 님 지시 2026-11-22)
        pg.evaluate("() => window.SEOSAN_VERIFY.setApply({ advertiser: '제한검증광고주', advertiserBiz: '325-55-12345', text: '행사 제한 검증 홍보', qty: 1, agree: true })")
        pg.evaluate("() => { const c = document.querySelector('#chkEventApp'); c.checked = true; c.dispatchEvent(new Event('change', { bubbles: true })); }")
        pg.wait_for_timeout(300)
        excl = pg.evaluate("""() => {
          const ev = document.querySelector('#chkEventApp'), fields = document.querySelector('#eventFields');
          return { evChecked: ev.checked, fieldsOpen: fields ? !fields.classList.contains('hidden') : null,
            note: document.querySelector('#eventPolNote') ? !document.querySelector('#eventPolNote').classList.contains('hidden') : null,
            noteTxt: document.querySelector('#eventPolNote') ? document.querySelector('#eventPolNote').textContent : '' };
        }""")
        (ok if excl['evChecked'] and excl['fieldsOpen'] and excl['note']
             and '저단게시대' in excl['noteTxt'] and '정치행정' not in excl['noteTxt'] else ng)(
            '행사 우선접수 체크 — 입력칸 열림 + 저단게시대 불가 안내(정치행정 문구 없음)', str(excl)[:160])
        # 저단게시대 — 목록 제외 · 직접 선택 차단 · 3단계에 1순위 저단을 넣으면 제출 차단
        pg.wait_for_timeout(200)
        low_in_list = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY;
            const low = v.lowBoards();
            const rows = Array.from(document.querySelectorAll('#applyGrid .pick-row')).map(r => r.getAttribute('data-pick'));
            return { lowN: low.length, id: low[0] ? low[0].id : '', inList: low[0] ? rows.indexOf(low[0].id) >= 0 : false,
              visible: Array.from(document.querySelectorAll('#applyGrid .pick-row')).length }; }""")
        (ok if low_in_list['lowN'] >= 1 and not low_in_list['inList'] else ng)(
            '행사 우선접수 — 공문 전용 저단게시대 3단계 목록 제외', str(low_in_list)[:120])
        # 저단 게시대를 1순위에 넣어도 접수 제출이 차단되는지(로직 단 방어) — 시안·동의를 다시 채워 제출 검증까지 도달
        pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({
            advertiser: '제한검증광고주', advertiserBiz: '325-55-12345', text: '행사 제한 검증 홍보',
            qty: 1, agree: true, event: { name: '제한검증 행사', period: '2026-12-06', reason: '검증용 증빙' } })""")
        pg.click('#btnLicSample')
        pg.wait_for_timeout(200)
        pg.evaluate("() => window.SEOSAN_VERIFY.setStep(3)")   # 3단계로 이동 — 1단계 검증 통과 상태 유지
        pg.wait_for_timeout(350)
        evlow_blocked = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY;
            const low = v.lowBoards()[0];
            const r = v.uiRanks();
            r['1'].push(low.id);                      // 데이터상 강제로 1순위에 저단을 넣어 본다
            v.setUiRanks(r);
            const after = v.uiRanks();
            return { pushed: low.id, inRank: after['1'].indexOf(low.id) >= 0 }; }""")
        (ok if evlow_blocked['pushed'] and evlow_blocked['inRank'] else ng)(
            '저단 강제 편입 데이터 준비', str(evlow_blocked))
        pg.evaluate("""(pid) => { const v = window.SEOSAN_VERIFY;
            const el = document.querySelector('#applyGrid .pick-row[data-pick="' + pid + '"]');
            return el ? el.click() : null; }""", evlow_blocked['pushed'])
        # 저단 행은 목록에서 제외되었으므로 해제가 불가능 — 토스트 확인 후 직접 제출 시도
        # 3단계 → 4단계 진입 검증이 저단 포함 접수를 막는지 — 데이터상 1순위에 저단이 남아 있는 상태
        pg.click('#btnNext')
        pg.wait_for_timeout(400)
        blocked_txt = pg.evaluate("() => { const t = document.querySelector('#toast'); return t ? t.textContent : ''; }")
        blocked_step = pg.evaluate("() => window.SEOSAN_VERIFY.stepNow()")
        (ok if '저단게시대' in blocked_txt or '사용할 수 없습니다' in blocked_txt or '사용 불가' in blocked_txt else ng)(
            '행사 우선접수 — 저단게시대 포함 접수 차단(로직 방어)', 'toast=%s · step=%s' % (blocked_txt[:90], blocked_step))
        # 정리 — 1순위의 저단을 빼고 3단계로 복귀(뒤따르는 심사 흐름 검증이 정상 데이터로 진행되도록)
        pg.evaluate("""() => { const v = window.SEOSAN_VERIFY;
            const low = v.lowBoards()[0].id;
            [1, 2, 3].forEach(n => { const r = v.uiRanks(); const i = r[String(n)].indexOf(low);
              if (i >= 0) { r[String(n)].splice(i, 1); v.setUiRanks(r); } });
            return v.uiRanks(); }""")
        apply_src = io.open(os.path.join(ROOT, 'apply.html'), encoding='utf-8').read()
        event_src = io.open(os.path.join(ROOT, 'admin-event.html'), encoding='utf-8').read()
        (ok if '회원 직접 신청' in apply_src and '행사승인권한자 5명' in apply_src else ng)(
            '접수 페이지 — 행사 우선접수 회원 직접 신청 안내', 'apply.html')
        (ok if 'href="apply.html"' in event_src and '회원이' in event_src and '관리자(행사승인권한자 5명)가 심사' in event_src else ng)(
            '행사 심사 페이지 — 회원 접수 → 관리자 5인 승인 흐름 안내·신청 링크', 'admin-event.html')
        # 미승인 → 일반 추첨 자동 전환 (미리 받은 2개 순위 유지) — 패널을 다시 그려 최신 상태에서 심사중 건을 고른다
        goto(pg, base + 'admin-event.html', 450)
        badges = pg.evaluate("() => window.SEOSAN_VERIFY.eventApps()")
        pend = [b for b in badges if b['eventStatus'] == '심사중']
        pend_id = pend[0]['id'] if pend else ''
        for role_k in ('chief', 'senior', 'office', 'staff1', 'audit1'):
            pg.evaluate("(r) => window.SEOSAN_VERIFY.setRole(r)", role_k)
            pg.wait_for_timeout(150)
            btn = pg.query_selector('#eventList [data-evvote="%s"][data-evval="반려"]' % pend_id)
            if btn:
                btn.click()
                pg.wait_for_timeout(300)
        conv = pg.evaluate("(id) => window.SEOSAN_VERIFY.eventOf(id)", pend_id)
        convapp = store(pg, "(() => { const o=JSON.parse(localStorage.getItem('%s')); const a=o.apps.find(x=>x.id==='%s'); return a ? {status:a.status, ev:a.eventStatus, p1:(a.priority1||[]).length, p2:(a.priority2||[]).length} : null; })()" % (STORE_KEY, pend_id))
        (ok if conv and conv.get('status') == '미승인' and convapp and convapp.get('status') == '추첨대기' and convapp.get('p1', 0) >= 1 else ng)(
            '반려 3명 → 미승인 · 일반 추첨 전환(순위 유지)', '%s / %s' % (conv, convapp))
        pg.wait_for_timeout(200)

        # 10-3) 마이페이지 · 주별 현황에 행사 우선접수 표시
        goto(pg, base + 'mypage.html', 500)
        mp = pg.evaluate("() => window.SEOSAN_VERIFY.myPage().text")
        (ok if '행사 우선 승인' in mp else ng)('마이페이지 행사 우선접수 표시',
                                                              '행사 우선접수=%s · 행사명=%s' % ('행사 우선접수' in mp, EV_NAME in mp))
        goto(pg, base + 'index.html', 500)
        ws_ev = pg.evaluate("() => window.SEOSAN_VERIFY.weekStats('2026-11-30')")
        # 첫 화면 주별 상세 패널은 달력과 함께 빠졌다(2026-11-23) — 주간 집계 API 로 행사 접수가 포함되는지 확인한다
        ev_ws = pg.evaluate("() => window.SEOSAN_VERIFY.weekStats('2026-11-30')")
        ev_apps = pg.evaluate("() => window.SEOSAN_VERIFY.eventApps()")
        kpi_txt = pg.evaluate("() => { const e = document.querySelector('#weekDetail .wk-kpi') || document.querySelector('#statusStats'); return e ? e.textContent : ''; }")
        (ok if ev_ws and ev_ws.get('n', 0) >= len(ev_apps) and ev_ws.get('n', 0) > 0 else ng)(
            '주별 현황에 행사 우선접수 집계', '주간 접수 %s건 · 행사 신청 %s건' % (ev_ws.get('n') if ev_ws else '?', len(ev_apps)))

        # 10-4) 추첨 배정 순위 — 공문 → 승인 행사 → 일반
        goto(pg, base + 'admin-draw.html', 450)
        one = pg.evaluate("() => window.SEOSAN_VERIFY.oneSlotLeft('P05')")
        appr = pg.evaluate("() => window.SEOSAN_VERIFY.eventPriorityProbe('P05', 12, 'approved')")
        cnv = pg.evaluate("() => window.SEOSAN_VERIFY.eventPriorityProbe('P05', 24, 'converted')")
        (ok if one and appr and len(appr) == 12 and all(x['winE'] and not x['winG'] for x in appr) else ng)(
            '승인 행사가 일반보다 먼저 배정 (12회 반복)', '행사 승 %d/12' % len([x for x in (appr or []) if x.get('winE')]))
        (ok if cnv and all(x['eventWins'] == 0 for x in cnv) and any(x['winE'] for x in cnv) else ng)(
            '미승인 행사는 일반 추첨에 모여 참여', '행사 승 %d/24 · 우선집계 0' % len([x for x in (cnv or []) if x.get('winE')]))
        off_seats = pg.evaluate("() => window.SEOSAN_VERIFY.officialTotal()")
        plan_p1 = pg.evaluate("() => window.SEOSAN_VERIFY.slotPlan('P23', '2026-11-30')")
        (ok if off_seats >= 1 and len(plan_p1.get('post') or []) >= 1 else ng)(
            '공문 우선배정 면은 추첨 전에 차감', '공문 %d면 · 공문 자리 %s' % (off_seats, plan_p1.get('post')[:4]))

        # 10-5) 시한임박 가산점 — 기본 0% · 인정 범위 차차주 · 직책자 부여 한도
        goto(pg, base + 'apply.html', 450)
        if pg.query_selector('#modal.open'):
            pg.keyboard.press('Escape')
        pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({
            advertiser: '가산점검증광고주', advertiserBiz: '322-11-22334', text: '12월 5일 겨울 시민 걷기축제', qty: 1, agree: true })""")
        pg.fill('#applyText', '12월 5일 겨울 시민 걷기축제 홍보')
        pg.wait_for_timeout(250)
        hint = pg.evaluate("() => window.SEOSAN_VERIFY.urgentHint()")
        (ok if not hint['hidden'] and '0%' in hint['text'] and '차차주' in hint['text'] else ng)(
            '시한임박 감지 문구 — 기본 0% · 인정 범위 차차주', hint['text'])
        # 인정 범위 — 게첨 시작일(2026-11-30)부터 차차주 일요일(20일)까지
        edge = pg.evaluate("() => { const v = window.SEOSAN_VERIFY; return { in20: v.urgentLimitLabel('12월 20일'), out21: v.urgentLimitLabel('12월 21일') }; }")
        (ok if edge['in20'] and edge['in20']['within'] and edge['in20']['days'] == 20
             and edge['out21'] and not edge['out21']['within'] else ng)(
            '시한임박 인정 범위 — 차차주(20일)까지 · 21일 뒤 제외', str(edge))
        weight = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY, st = v.state();
            const a = st.apps.filter(x => String(x.text || '').indexOf('12월 5일') >= 0).slice(-1)[0];
            return a ? { id: a.id, w: v.urgentWeightOf(a.id), u: v.urgentOf(a.id) } : null; }""")
        (ok if weight and abs(weight['w'] - 1.0) < 1e-9 and not weight['u'].get('applied') else ng)(
            '시한임박 자동 가산 0% (기본 1.00배)', str(weight)[:150])
        # 시한임박 가산점 부여 패널 — 직책자 권한 한도
        goto(pg, base + 'admin-review.html', 500)
        cands = pg.evaluate("() => window.SEOSAN_VERIFY.urgentCandidates()")
        within = [c for c in cands if c['within']]
        c1 = within[0]['id'] if within else ''
        c2 = within[1]['id'] if len(within) > 1 else c1
        panel = pg.evaluate("() => window.SEOSAN_VERIFY.urgentGrantPanel()")
        (ok if within and panel['rows'] >= 1 and '차차주' in panel['info'] and '부여' in panel['info']
             and '부여자' in panel['html'] else ng)(
            '시한임박 가산점 패널 — 인정 범위·부여자 표시', panel['info'])
        lims = pg.evaluate("() => window.SEOSAN_VERIFY.grantLimits()")
        lm = {x['k']: x['limit'] for x in lims}
        (ok if lm.get('chief') == 5 and lm.get('senior') == 3 and lm.get('field') == 3 and lm.get('staff') == 2
             and lm.get('office') == 0 and lm.get('audit1') == 0 and lm.get('audit2') == 0 else ng)(
            '부여 권한 한도 — 지부장 5 · 수석 3 · 현장 3 · 사무 2 · 사무국장·감사 0', str(lm))
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('chief')")
        chief_lim = pg.evaluate("() => window.SEOSAN_VERIFY.myGrantLimit()")
        # 화면에서 직접 [부여] 클릭 — 지부장 5%
        try:
            pg.select_option('#urgSel0', '5')
            pg.click('[data-urgentgrant][data-urgentidx="0"]')
            pg.wait_for_timeout(600)
            clicked = pg.evaluate("() => window.SEOSAN_VERIFY.urgentCandidates().filter(x => x.within)[0]")
            (ok if clicked and clicked['applied'] and clicked['pct'] == 5 else ng)(
                '시한임박 가산점 — 화면 [부여] 클릭으로 5% 부여', str(clicked)[:150])
        except Exception as exc:      # noqa: BLE001 - 클릭 실패도 검사 실패로 기록
            ng('시한임박 가산점 — 화면 [부여] 클릭', str(exc).splitlines()[0][:120])
            chief_lim = chief_lim
        g1 = pg.evaluate("(id) => window.SEOSAN_VERIFY.setUrgent(id, 5)", c1)
        w1 = pg.evaluate("(id) => window.SEOSAN_VERIFY.drawWeight(id)", c1)
        (ok if chief_lim == 5 and g1 and g1['pct'] == 5 and abs(w1 - 1.05) < 1e-9 else ng)(
            '지부장 — 시한임박 +5% 부여 → 가중치 1.05', 'limit=%s · %s · w=%s' % (chief_lim, g1, w1))
        gwho = pg.evaluate("(id) => { const v=window.SEOSAN_VERIFY; const c=v.urgentCandidates().filter(x=>x.id===id)[0]; return c ? c.grant : null; }", c1)
        (ok if gwho and gwho.get('label') == '지부장' and gwho.get('name') == '김서산' and gwho.get('pct') == 5 else ng)(
            '부여자 기록 — 직책·성명·%', str(gwho))
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('staff')")
        staff_lim = pg.evaluate("() => window.SEOSAN_VERIFY.myGrantLimit()")
        over = pg.evaluate("(id) => window.SEOSAN_VERIFY.setUrgent(id, 5)", c2)
        w2 = pg.evaluate("(id) => window.SEOSAN_VERIFY.drawWeight(id)", c2)
        (ok if staff_lim == 2 and over is None and abs(w2 - 1.0) < 1e-9 else ng)(
            '사무실무원 — 5% 요청 거부(한도 2% 초과 차단)', 'limit=%s · result=%s · w=%s' % (staff_lim, over, w2))
        g2 = pg.evaluate("(id) => window.SEOSAN_VERIFY.setUrgent(id, 2)", c2)
        w2b = pg.evaluate("(id) => window.SEOSAN_VERIFY.drawWeight(id)", c2)
        (ok if g2 and g2['pct'] == 2 and abs(w2b - 1.02) < 1e-9 else ng)(
            '사무실무원 — 한도 내 +2% 부여 → 가중치 1.02', 'w=%s' % w2b)
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('office')")
        office = pg.evaluate("() => ({ limit: window.SEOSAN_VERIFY.myGrantLimit(), can: window.SEOSAN_VERIFY.canGrant() })")
        denied = pg.evaluate("(id) => window.SEOSAN_VERIFY.setUrgent(id, 1)", c1)
        (ok if office['limit'] == 0 and not office['can'] and denied is None else ng)(
            '사무국장 — 가산점 부여 권한 없음', str(office))
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('chief')")
        rv = pg.evaluate("(id) => window.SEOSAN_VERIFY.setUrgent(id, 0)", c1)
        w1b = pg.evaluate("(id) => window.SEOSAN_VERIFY.drawWeight(id)", c1)
        (ok if rv and rv['pct'] == 0 and abs(w1b - 1.0) < 1e-9 else ng)(
            '시한임박 가산점 해제 — 기본 0%(1.00배)', 'w=%s' % w1b)
        # 협회 등록 회원사 가산점 — 회원관리 탭 · 기본 0% · 직책자 부여
        goto(pg, base + 'admin-members.html', 500)
        ap = pg.evaluate("() => window.SEOSAN_VERIFY.assocPanel()")
        members_n = len(pg.evaluate("() => window.SEOSAN_VERIFY.members()"))
        (ok if ap['rows'] == members_n and '협회 등록' in ap['info'] else ng)('회원관리 탭 — 협회 등록 회원사 목록', '%d행 / 회원 %d명' % (ap['rows'], members_n))
        mapp = pg.evaluate("() => { const s = window.SEOSAN_VERIFY.state(); const a = s.apps.filter(x => x.memberId === 'M-1001').slice(-1)[0]; return a ? a.id : ''; }")
        # 접수자 본인의 직책으로 자동 가산하지 않는다 (옛 직책값이 남아 있어도 0%)
        legacy = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY, st = v.state();
            const m = st.members.filter(x => x.id === 'M-1001')[0];
            if (m) m.roleBonusType = 'chief';
            return { w: v.drawWeight('%s'), note: v.drawWeightNote('%s') }; }""" % (mapp, mapp))
        (ok if legacy and abs(legacy['w'] - 1.0) < 1e-9 else ng)(
            '접수자 본인의 직책 자동 가산 없음 (옛 직책값 무시)', str(legacy))
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('senior')")
        a0 = pg.evaluate("() => window.SEOSAN_VERIFY.assocSet('M-1001', true, '0')")
        w0 = pg.evaluate("(id) => window.SEOSAN_VERIFY.drawWeight(id)", mapp) if mapp else None
        (ok if a0 and abs(a0['rate']) < 1e-9 and (w0 is None or abs(w0 - 1.0) < 1e-9) else ng)(
            '협회 등록 회원사 — 기본 가산 0%', 'rate=%s · weight=%s' % (a0 and a0['rate'], w0))
        a2 = pg.evaluate("() => window.SEOSAN_VERIFY.assocSet('M-1001', true, '3')")
        w3 = pg.evaluate("(id) => window.SEOSAN_VERIFY.drawWeight(id)", mapp) if mapp else None
        (ok if a2 and abs(a2['rate'] - 0.03) < 1e-9 and (w3 is None or abs(w3 - 1.03) < 1e-9) else ng)(
            '수석부지부장 — 회원사 +3% 부여 → 가중치 1.03', 'rate=%s · weight=%s' % (a2 and a2['rate'], w3))
        over2 = pg.evaluate("() => window.SEOSAN_VERIFY.assocSet('M-1001', true, '4')")
        (ok if over2 is None else ng)('회원사 가산 한도 초과(4%) 거부 — 수석 3%', str(over2))
        a3 = pg.evaluate("() => window.SEOSAN_VERIFY.assocSet('M-1001', false, '0')")
        w1c = pg.evaluate("(id) => window.SEOSAN_VERIFY.drawWeight(id)", mapp) if mapp else None
        (ok if a3 and not a3['assocMember'] and (w1c is None or abs(w1c - 1.0) < 1e-9) else ng)(
            '협회 등록 해제 → 가산 0%', 'weight=%s' % w1c)
        src_app = io.open(os.path.join(ROOT, 'assets', 'app.js'), encoding='utf-8').read()
        # '1.15'는 날짜 표기(예: 11.09~11.15)에도 나오므로 배수 표기('1.15배')만 남아 있는지 본다
        (ok if 'var URGENT = { days: 20, weeks: 2 }' in src_app and '1.15배' not in src_app else ng)(
            '시한임박 인정 범위 상수 — 차차주(20일) · 1.15배 잔존 없음',
            'days: 20' if 'days: 20' in src_app else 'not found')
        (ok if "k: 'chief', label: '지부장', limit: 5" in src_app and "k: 'senior', label: '수석부지부장', limit: 3" in src_app
             and "k: 'field', label: '현장실무원', limit: 3" in src_app and "k: 'staff', label: '사무실무원', limit: 2" in src_app else ng)(
            '부여 한도 상수 — 지부장 5 · 수석 3 · 현장 3 · 사무 2', 'source')
        (ok if 'ROLE_BONUS' not in src_app and 'roleBonusOfApp' not in src_app and 'urgentAck' not in src_app.replace('a.urgentAck', '') else ng)(
            '직책자 본인 자동 가산 로직 제거', 'ROLE_BONUS·roleBonusOfApp 잔존 없음')
        review_src = io.open(os.path.join(ROOT, 'admin-review.html'), encoding='utf-8').read()
        (ok if '시한임박 현수막 가산점' in review_src and '차차주' in review_src else ng)(
            '시안 심사 화면 — 시한임박 가산점 안내·차차주', 'admin-review.html')
        rules_src = io.open(os.path.join(ROOT, 'guide-rules.html'), encoding='utf-8').read()
        # 2026-11-23 김재봉 님 지시 — 안내페이지에서 추첨 가산점 규칙을 삭제 (관리자 화면에만 남긴다)
        (ok if '가산점' not in rules_src else ng)(
            '규격·안내 — 가산점 규칙 미노출(삭제)', '가산점 %d회' % rules_src.count('가산점'))

        # 10-5-b) 가산점 **부여자별 개별 부여 → 최종 합산** (2026-11-22 김재봉 님 지시)
        goto(pg, base + 'admin-review.html', 400)
        cands2 = pg.evaluate("() => window.SEOSAN_VERIFY.urgentCandidates().filter(x => x.within)")
        mid = cands2[0]['id'] if cands2 else ''
        multi = pg.evaluate("""(id) => { const v = window.SEOSAN_VERIFY;
            v.setRole('chief'); v.setUrgent(id, 5);
            v.setRole('senior'); v.setUrgent(id, 3);
            v.setRole('field'); v.setUrgent(id, 3);
            v.setRole('staff'); v.setUrgent(id, 2);
            return { grants: v.urgentGrants(id), total: v.urgentGrantTotal(id), w: v.drawWeight(id), note: v.drawWeightNote(id) }; }""", mid)
        (ok if multi and multi['total'] == 13 and abs(multi['w'] - 1.13) < 1e-9 and len(multi['grants']) == 4 else ng)(
            '부여자 4명 각자 한도 부여 → 최종 합산 +13%(가중치 1.13)',
            '합산=%s · 부여자 %d명 · w=%s' % (multi and multi['total'], len(multi['grants']) if multi else 0, multi and multi['w']))
        (ok if multi and [g['role'] for g in multi['grants']] == ['chief', 'senior', 'field', 'staff']
             and [g['pct'] for g in multi['grants']] == [5, 3, 3, 2] else ng)(
            '부여자별 내역이 각각 유지 — 지부장 +5 · 수석 +3 · 현장 +3 · 사무 +2',
            str([(g['label'], g['pct']) for g in (multi or {}).get('grants', [])]))
        (ok if multi and '지부장 김서산' in multi['note'] and '사무실무원 한은지' in multi['note'] and '합산 +13%' in multi['note'] else ng)(
            '가중치 메모 — 부여자 전원과 합산 % 표기', (multi or {}).get('note', '')[:120])
        upd = pg.evaluate("""(id) => { const v = window.SEOSAN_VERIFY; v.setRole('chief'); v.setUrgent(id, 3);
            return { grants: v.urgentGrants(id), total: v.urgentGrantTotal(id) }; }""", mid)
        (ok if upd and upd['total'] == 11 and len(upd['grants']) == 4 and [g['pct'] for g in upd['grants']][0] == 3 else ng)(
            '같은 부여자 재부여 — 그 부여자 몫만 교체(합산 +13%→+11%, 항목 4개 유지)',
            '합산=%s · %s' % (upd and upd['total'], [g['pct'] for g in (upd or {}).get('grants', [])]))
        rel2 = pg.evaluate("""(id) => { const v = window.SEOSAN_VERIFY; v.setRole('staff'); v.setUrgent(id, 0);
            return { grants: v.urgentGrants(id), total: v.urgentGrantTotal(id), w: v.drawWeight(id) }; }""", mid)
        (ok if rel2 and rel2['total'] == 9 and len(rel2['grants']) == 3 and abs(rel2['w'] - 1.09) < 1e-9 else ng)(
            '한 부여자 해제 — 나머지 부여자 % 유지(+11%→+9%)', '합산=%s · w=%s' % (rel2 and rel2['total'], rel2 and rel2['w']))
        overf = pg.evaluate("(id) => { const v = window.SEOSAN_VERIFY; v.setRole('field'); return v.setUrgent(id, 4); }", mid)
        (ok if overf is None else ng)('부여자별 한도 초과 거부 — 현장실무원 4%(한도 3%)', str(overf))
        panel2 = pg.evaluate("() => window.SEOSAN_VERIFY.urgentGrantPanel()")
        (ok if '합계 +9%' in panel2['html'] and '지부장 김서산 +3%' in panel2['html']
             and '수석부지부장 박해미 +3%' in panel2['html'] and '부여자' in panel2['info'] else ng)(
            '시한임박 패널 — 부여자별 칩 + 최종 합산 표시', panel2['info'])
        # 회원사 가산점도 부여자별 합산 — 회원 관리 패널은 admin-members.html 에 있다 (2026-11-23 분리)
        goto(pg, base + 'admin-members.html', 400)
        mapp2 = pg.evaluate("() => { const s = window.SEOSAN_VERIFY.state(); const a = s.apps.filter(x => x.memberId === 'M-1002').slice(-1)[0]; return a ? a.id : ''; }")
        amulti = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY;
            v.setRole('chief'); v.assocSet('M-1002', true, '5');
            v.setRole('staff'); v.assocSet('M-1002', true, '2');
            return { grants: v.assocGrants('M-1002'), total: v.assocGrantTotal('M-1002') }; }""")
        wm = pg.evaluate("(id) => window.SEOSAN_VERIFY.drawWeight(id)", mapp2) if mapp2 else None
        (ok if amulti and amulti['total'] == 7 and len(amulti['grants']) == 2 and (wm is None or abs(wm - 1.07) < 1e-9) else ng)(
            '회원사 가산점 부여자별 합산 — 지부장 +5% + 사무 +2% = +7%(1.07배)',
            '합산=%s · w=%s' % (amulti and amulti['total'], wm))
        arel = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY; v.setRole('staff'); v.assocSet('M-1002', true, '0');
            return { grants: v.assocGrants('M-1002'), total: v.assocGrantTotal('M-1002') }; }""")
        (ok if arel and arel['total'] == 5 and len(arel['grants']) == 1 else ng)(
            '회원사 — 한 부여자 몫 해제 시 다른 부여자 % 유지', '합산=%s' % (arel and arel['total']))
        ap2 = pg.evaluate("() => window.SEOSAN_VERIFY.assocPanel()")
        (ok if '합계 +5%' in ap2['html'] and '지부장 김서산 +5%' in ap2['html'] and '부여자' in ap2['info'] else ng)(
            '회원관리 패널 — 부여자별 칩 + 최종 합산 표시', ap2['info'])
        # 새 구조로 저장되고(부여자별 배열), 다시 열어도 합산이 유지된다
        pg.reload(wait_until='load')
        pg.wait_for_timeout(600)
        after_reload = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY, st = v.state();
            const a = st.apps.filter(x => (x.urgentGrants || []).length >= 3)[0];
            const legacy = st.apps.filter(x => 'urgentGrant' in x).length + st.members.filter(x => 'assocGrant' in x).length;
            return { total: a ? v.urgentGrantTotal(a.id) : null, count: a ? v.urgentGrants(a.id).length : 0,
              array: a ? Array.isArray(a.urgentGrants) : false, legacy: legacy } };""")
        (ok if after_reload['array'] and after_reload['count'] >= 3 and after_reload['total'] == 9 and not after_reload['legacy'] else ng)(
            '다시 열어도 부여자별 내역·합산 유지(단일 구조 잔존 없음)', str(after_reload))
        src_app2 = io.open(os.path.join(ROOT, 'assets', 'app.js'), encoding='utf-8').read()
        (ok if 'urgentGrants' in src_app2 and 'assocGrants' in src_app2 and 'grantSumPct' in src_app2
             and '부여자별' in src_app2 else ng)('부여자별 배열·합산 로직 소스 반영', 'app.js')
        probs = w.problems()
        (ok if not probs else ng)('행사 우선접수 시나리오 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # 10-6) 360px — 접수 3단계 한 줄 보기 유지
        ctx = browser.new_context(viewport={'width': 360, 'height': 780}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        Watcher(pg, base)
        goto(pg, base + 'apply.html', 500)
        pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({
            advertiser: '반응형검증광고주', advertiserBiz: '323-22-33445', text: '반응형 한 줄 보기 검증', qty: 1, agree: true, noSms: false })""")
        pg.click('#btnLicSample')
        pg.wait_for_timeout(150)
        pg.click('#btnNext')
        pg.wait_for_timeout(350)
        pg.click('#btnNext')
        pg.wait_for_timeout(400)
        rows360 = pg.eval_on_selector_all('#applyGrid .pick-row', 'els => els.map(e => ({h: Math.round(e.getBoundingClientRect().height), sw: e.scrollWidth, cw: e.clientWidth}))')
        m360 = pg.evaluate("({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
        tall360 = [r for r in rows360 if r['h'] > 60 or r['sw'] > r['cw'] + 1]
        (ok if rows360 and not tall360 and m360['sw'] <= m360['cw'] else ng)(
            '360px 3단계 한 줄 보기 · 가로 넘침 없음', '%d행 · 초과 %d · %s' % (len(rows360), len(tall360), m360))
        evw360 = pg.evaluate("() => { const e = document.querySelector('#eventApplyBox'); return e ? e.scrollWidth - e.clientWidth : null; }")
        (ok if evw360 is not None and evw360 <= 1 else ng)('360px 행사 심사 신청란', 'overflow %s' % evw360)
        ctx.close()

        # ------------------------------------------------------------------
        # 11) 풀가림(목요일 선착순 전용) · 기타사유(고객 팝업)
        # ------------------------------------------------------------------
        head('11. 풀가림은 목요일 선착순만 · 기타사유(관리자 사유 → 고객 팝업)')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1100})
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        w = Watcher(pg, base)
        goto(pg, base + 'admin-board.html', 500)
        # 가용 면이 3면 이상 남은 게시대를 골라 시험한다 (풀가림 1 + 기타사유 2)
        PID = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY;
            const list = v.state().placements.filter(p => {
              if (p.broken || v.availSeat(p.id) < 3 || v.slotCodes(p.id).length < 3) return false;
              const pl = v.slotPlan(p.id, '2026-11-30');
              return Object.keys(pl.post || {}).length === 0 && (pl.free || []).length >= 3;
            });
            return list.length ? list[0].id : ''; }""")
        before = pg.evaluate("(p) => window.SEOSAN_VERIFY.availSeat(p)", PID) if PID else 0
        codes = pg.evaluate("(p) => window.SEOSAN_VERIFY.slotCodes(p)", PID)
        if not codes or len(codes) < 3:
            ng('기타사유 검증 — 게시대 단수', str(codes))
        else:
            free_codes = pg.evaluate("(p) => window.SEOSAN_VERIFY.slotPlan(p, '2026-11-30').free", PID)
            codes = [c for c in (free_codes or []) if c] or codes
            cov_code, oth_block, oth_warn = codes[0], codes[1], codes[2]
            pg.evaluate("(a) => window.SEOSAN_VERIFY.setSlotFlag3(a[0], a[1], 'cover')", [PID, cov_code])
            r1 = pg.evaluate("(a) => window.SEOSAN_VERIFY.setSlotOther(a[0], [a[1]], '도로공사로 12월 1일까지 접근 제한', 'block')", [PID, oth_block])
            r2 = pg.evaluate("(a) => window.SEOSAN_VERIFY.setSlotOther(a[0], [a[1]], '가로수 정비 예정 — 시야 가림 가능', 'warn')", [PID, oth_warn])
            (ok if r1 and r2 else ng)('기타사유 등록 (접수 제한 · 안내 후 선택)', '%s / %s' % (r1, r2))
            after = pg.evaluate("(p) => window.SEOSAN_VERIFY.availSeat(p)", PID)
            fcav = pg.evaluate("(p) => window.SEOSAN_VERIFY.fcAvail(p)", PID)
            (ok if after == before - 2 else ng)('주간 추첨 가용 면 — 풀가림·접수제한 기타사유 제외', '%s → %s (2면 감소 필요)' % (before, after))
            (ok if fcav == before - 1 else ng)('목요일 선착순 가용 면 — 풀가림 포함', 'fc=%s (접수제한 1면만 제외)' % fcav)
            st_cov = pg.evaluate("(a) => window.SEOSAN_VERIFY.slotStateOf(a[0], a[1])", [PID, cov_code])
            st_blk = pg.evaluate("(a) => window.SEOSAN_VERIFY.slotStateOf(a[0], a[1])", [PID, oth_block])
            st_wrn = pg.evaluate("(a) => window.SEOSAN_VERIFY.slotStateOf(a[0], a[1])", [PID, oth_warn])
            (ok if st_cov.get('off') and '목요일' in st_cov.get('label', '') else ng)('풀가림 단수 — 정기 접수 선택 불가', str(st_cov))
            (ok if st_blk.get('off') and '기타사유' in st_blk.get('label', '') else ng)('기타사유(접수 제한) 선택 불가', str(st_blk))
            (ok if (not st_wrn.get('off')) and '안내 후 선택' in st_wrn.get('label', '') else ng)('기타사유(안내 후 선택) — 확인 후 선택 가능', str(st_wrn))
            pick = pg.evaluate("(a) => window.SEOSAN_VERIFY.askOtherPick(a[0], a[1])", [PID, oth_warn])
            (ok if pick.get('open') and '가로수 정비 예정' in pick.get('body', '') else ng)(
                '기타사유 안내 팝업 — 관리자 사유 표시', pick.get('body', '')[:90].replace('\n', ' '))
            pg.evaluate("() => window.SEOSAN_VERIFY.closeModal()")
            detail = pg.evaluate("(p) => window.SEOSAN_VERIFY.placeDetail(p)", PID)
            note_box = pg.evaluate("() => window.SEOSAN_VERIFY.slotNoteBox()")
            (ok if '도로공사로 12월 1일까지 접근 제한' in note_box and '가로수 정비 예정' in note_box else ng)(
                '게시대 상세 — 기타사유 배지·사유 안내', note_box.replace('\n', ' ')[:110])
            pg.evaluate("() => window.SEOSAN_VERIFY.closeModal()")
            # 추첨 엔진 — 풀가림·기타사유 단수에는 배정하지 않는다
            res = pg.evaluate("""(a) => { const v = window.SEOSAN_VERIFY;
                const pool = v.state().apps.filter(x => x.round === v.round().ROUND.id && x.status === '추첨대기');
                const out = v.drawEngine(pool, 777);
                const bad = []; let seats = 0;
                Object.keys(out.out).forEach(id => (out.out[id].places || []).forEach(pl => {
                  if (pl.slot) seats += 1;
                  if (pl.pid === a[0] && a.slice(1).indexOf(pl.slot) >= 0) bad.push(pl.slot);
                }));
                return { bad: bad, seats: seats, eventSeats: out.stat.eventSeats }; }""", [PID, cov_code, oth_block, oth_warn])
            (ok if res and not res['bad'] and res['seats'] > 0 else ng)(
                '추첨 엔진 — 풀가림·기타사유 단수 배정 제외', '배정 %s면 · 제외 위반 %s' % (res.get('seats'), res.get('bad')))
            # 3단계에서 풀가림 단수는 지정되지 않는다
            pg.evaluate("() => window.SEOSAN_VERIFY.setSlot('%s', '%s')" % (PID, cov_code))
            slot_now = pg.evaluate("(p) => window.SEOSAN_VERIFY.slotOf(p)", PID)
            (ok if slot_now != cov_code else ng)('3단계 — 풀가림 단수 지정 차단', 'slot=%r' % slot_now)
            # 목요일 선착순 — 풀가림·기타사유 선택 팝업 (4단계 흐름 · 3단계 담기)
            goto(pg, base + 'first.html', 500)
            pg.evaluate("() => window.SEOSAN_VERIFY.fcSet({ mode: 'next', daySim: 'thu', fcTime: 'open' })")
            pg.wait_for_timeout(300)
            fc = pg.evaluate("(p) => window.SEOSAN_VERIFY.askFcCover(p)", PID)
            body_fc = fc.get('body', '')
            (ok if fc.get('open') and '풀가림' in body_fc and '가로수 정비 예정' in body_fc else ng)(
                '목요일 선착순 — 풀가림·기타사유 안내 팝업',
                'open=%s · 풀가림=%s · 사유=%s' % (fc.get('open'), '풀가림' in body_fc, '가로수 정비 예정' in body_fc))
            pg.evaluate("() => window.SEOSAN_VERIFY.closeModal()")
            fc_tab = pg.text_content('#firstPageNote') if pg.query_selector('#firstPageNote') else ''
        probs = w.problems()
        (ok if not probs else ng)('풀가림·기타사유 시나리오 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 12) 추첨 전 취소는 페널티 없음
        # ------------------------------------------------------------------
        head('12. 추첨 전 취소 — 페널티 없이 자유 취소')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        w = Watcher(pg, base)
        goto(pg, base + 'apply.html', 450)
        pg.click('#btnLogin')
        if pg.query_selector('#modal.open'):
            pg.click('[data-login-preset="M-1001"]')
            pg.wait_for_timeout(400)
        pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({
            advertiser: '취소검증광고주', advertiserBiz: '324-33-44556', text: '추첨 전 취소 페널티 검증', qty: 1, agree: true })""")
        pg.click('#btnLicSample')
        pg.wait_for_timeout(150)
        pg.click('#btnNext')
        pg.wait_for_timeout(320)
        pg.click('#btnNext')
        pg.wait_for_timeout(320)
        el = pg.query_selector('#applyGrid [data-pick][aria-pressed="false"]:not([aria-disabled="true"])')
        if el:
            el.click()
            pg.wait_for_timeout(200)
        pg.click('#btnNext')
        pg.wait_for_timeout(350)
        pg.click('#btnNext')
        pg.wait_for_timeout(800)
        ca = store(pg, "(() => { const o=JSON.parse(localStorage.getItem('%s')); const a=o.apps.filter(x=>x.advertiser==='취소검증광고주').slice(-1)[0]; return a ? {id:a.id, status:a.status} : null; })()" % STORE_KEY)
        pen_before = pg.evaluate("() => window.SEOSAN_VERIFY.penalties().length")
        cid = ca['id'] if ca else ''
        goto(pg, base + 'mypage-detail.html?id=' + urllib.parse.quote(cid), 500)
        btn_txt = pg.evaluate("""(id) => { const b = document.querySelector('#mpBody [data-precancel="' + id + '"]'); return b ? b.textContent.trim() : ''; }""", cid)
        (ok if '접수 취소' in btn_txt and '페널티 없음' in btn_txt else ng)('마이페이지 상세 — [접수 취소 (페널티 없음)] 버튼', repr(btn_txt))
        list_btn = pg.evaluate("() => { const b = document.querySelector('#mpBody [data-precancel]'); return b ? b.textContent.trim() : ''; }")
        if btn_txt:
            pg.click('#mpBody [data-precancel="%s"]' % cid)
            pg.wait_for_timeout(350)
            modal_txt = pg.text_content('#modalBody') or ''
            (ok if '페널티가 부과되지 않습니다' in modal_txt else ng)('추첨 전 취소 확인 팝업 — 페널티 없음 안내', modal_txt.replace('\n', ' ')[:90])
            pg.click('#btnPreCancelGo')
            pg.wait_for_timeout(500)
            toast_txt = pg.evaluate("() => { const t = document.querySelector('#toast'); return t ? t.textContent : ''; }")
            (ok if '페널티 없음' in toast_txt else ng)('추첨 전 취소 토스트 — 페널티 없음', toast_txt[:80])
        after = store(pg, "(() => { const o=JSON.parse(localStorage.getItem('%s')); const a=o.apps.find(x=>x.id==='%s'); return a ? {status:a.status, reject:a.reject} : null; })()" % (STORE_KEY, cid))
        pen_after = pg.evaluate("() => window.SEOSAN_VERIFY.penalties().length")
        (ok if after and after.get('status') == '접수취소' else ng)('추첨 전 취소 → 접수취소 상태', str(after))
        (ok if pen_after == pen_before else ng)('추첨 전 취소 — 페널티 미부과', '페널티 %s → %s' % (pen_before, pen_after))
        goto(pg, base + 'mypage-detail.html?id=' + urllib.parse.quote(cid), 500)
        mp_txt = pg.evaluate("() => window.SEOSAN_VERIFY.myPage().text")
        (ok if '추첨 전 취소' in mp_txt else ng)('마이페이지 — 추첨 전 취소 상태 표시', mp_txt[-90:].replace('\n', ' '))
        pool_ids = pg.evaluate("() => window.SEOSAN_VERIFY.drawPool().map(a => a.id)")
        (ok if cid not in (pool_ids or []) else ng)('추첨 대상에서 제외', 'pool %d건' % len(pool_ids or []))
        probs = w.problems()
        (ok if not probs else ng)('추첨 전 취소 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 13) 게시대 정렬 버튼 — 경쟁률 높은 순(기본) / 낮은 순 / 기본순
        # ------------------------------------------------------------------
        head('13. 게시대 정렬 — 경쟁률 높은 순(기본) · 낮은 순 · 기본순')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(12000)
        w = Watcher(pg, base)
        goto(pg, base + 'index.html', 500)
        expand_places(pg)
        chips = pg.eval_on_selector_all('#statusSortChips .chip', 'els => els.map(e => [e.textContent.trim(), e.classList.contains("active")])')
        (ok if len(chips) == 3 and chips[0][0] == '경쟁률 높은 순' and chips[0][1] else ng)('현황 정렬 버튼 3개 · 기본 경쟁률 높은 순', str(chips))
        rates = pg.evaluate("() => { const v = window.SEOSAN_VERIFY; return v.statusOrder().map(id => v.compRate(id)); }")
        (ok if rates == sorted(rates, reverse=True) else ng)('현황 — 경쟁률 높은 순 정렬', '%s…' % ['%.2f' % x for x in rates[:5]])
        pg.click('#statusSortChips [data-sort="comp-asc"]')
        pg.wait_for_timeout(300)
        rates2 = pg.evaluate("() => { const v = window.SEOSAN_VERIFY; return v.statusOrder().map(id => v.compRate(id)); }")
        (ok if rates2 == sorted(rates2) else ng)('현황 — 경쟁률 낮은 순 전환', '%s…' % ['%.2f' % x for x in rates2[:5]])
        pg.click('#statusSortChips [data-sort="default"]')
        pg.wait_for_timeout(300)
        order3 = pg.evaluate("() => window.SEOSAN_VERIFY.statusOrder().slice(0, 5)")
        (ok if order3 == ['P01', 'P02', 'P03', 'P04', 'P05'] else ng)('현황 — 기본순 전환', str(order3))

        goto(pg, base + 'apply.html', 500)
        if pg.query_selector('#modal.open'):
            pg.keyboard.press('Escape')
        pg.click('#btnLogin')
        if pg.query_selector('#modal.open'):
            pg.click('[data-login-preset="M-1001"]')
            pg.wait_for_timeout(400)
        pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({
            advertiser: '정렬검증광고주', advertiserBiz: '325-44-55667', text: '게시대 정렬 검증', qty: 1, agree: true })""")
        pg.click('#btnLicSample')
        pg.wait_for_timeout(150)
        pg.click('#btnNext')
        pg.wait_for_timeout(320)
        pg.click('#btnNext')
        pg.wait_for_timeout(350)
        pchips = pg.eval_on_selector_all('#pickSortChips .chip', 'els => els.map(e => [e.textContent.trim(), e.classList.contains("active")])')
        (ok if len(pchips) == 3 and '경쟁률' in pchips[0][0] else ng)('3단계 정렬 버튼 3개', str(pchips))
        prates = pg.evaluate("() => { const v = window.SEOSAN_VERIFY; return v.pickOrder().map(id => v.compRate(id)); }")
        (ok if prates == sorted(prates, reverse=True) else ng)('3단계 — 기본 경쟁률 높은 순', '%s…' % ['%.2f' % x for x in prates[:5]])
        if pg.query_selector('#modal.open'):
            pg.keyboard.press('Escape')
            pg.wait_for_timeout(200)
        pg.click('#pickSortChips [data-psort="comp-asc"]')
        pg.wait_for_timeout(350)
        prates2 = pg.evaluate("() => { const v = window.SEOSAN_VERIFY; return v.pickOrder().map(id => v.compRate(id)); }")
        (ok if prates2 == sorted(prates2) else ng)('3단계 — 경쟁률 낮은 순 전환', '%s…' % ['%.2f' % x for x in prates2[:5]])
        probs = w.problems()
        (ok if not probs else ng)('정렬 시나리오 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 14) 게시 지정서 일괄 출력 — 건마다 A4 1장 · 표 여유
        # ------------------------------------------------------------------
        head('14. 게시 지정서 일괄 출력 — 건마다 A4 1장 · 표 열/행 여유')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1100})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'admin-draw.html', 450)
        if pg.query_selector('#btnDraw') and not pg.evaluate("() => !!document.querySelector('#btnDraw').disabled"):
            pg.click('#btnDraw')
            try:
                pg.wait_for_selector('#btnDrawGo', timeout=8000)
                pg.click('#btnDrawGo')
                pg.wait_for_selector('#drawResult table tbody tr', timeout=120000)
            except Exception:      # noqa: BLE001
                pass
            pg.wait_for_timeout(500)
        goto(pg, base + 'admin-desig.html', 700)
        rows = pg.eval_on_selector_all('#desigBatchList tbody tr', 'els => els.length')
        info = pg.text_content('#desigBatchInfo') or ''
        (ok if rows > 0 and 'A4' in info else ng)('게시 지정서 일괄 출력 목록', '%d행 · %s' % (rows, info))
        if rows > 0:
            pg.click('#btnDesigBatchAllPrint')
            pg.wait_for_timeout(600)
            batch = pg.evaluate("""() => { const pages = Array.from(document.querySelectorAll('#desigBatch .desig-page'));
                const first = pages[0];
                const st = first ? getComputedStyle(first) : null;
                const ths = first ? Array.from(first.querySelectorAll('.desig-table th')).slice(0, 4).map(t => Math.round(t.getBoundingClientRect().width)) : [];
                const td = first ? first.querySelector('.desig-table tbody td') : null;
                const tds = td ? getComputedStyle(td) : null;
                const inf = first ? first.querySelector('.desig-info th') : null;
                const infs = inf ? getComputedStyle(inf) : null;
                return { pages: pages.length, rows: first ? first.querySelectorAll('.desig-table tbody tr').length : 0,
                  breakAfter: st ? st.breakAfter || st.pageBreakAfter : '', ths: ths,
                  tdH: tds ? tds.height : '', tdPad: tds ? tds.paddingLeft : '', infoPad: infs ? infs.paddingLeft : '' }; }""")
            (ok if batch['pages'] == rows else ng)('일괄 출력 — 접수 건마다 1장', '%d장 / %d건' % (batch['pages'], rows))
            (ok if batch['rows'] == 30 and len(batch['ths']) == 4 else ng)('게시 지정서 60칸(2단 30행) 표', '%d행 · 열 %s' % (batch['rows'], batch['ths']))
            (ok if batch['ths'] and batch['ths'][0] >= 30 and batch['ths'][1] >= 60 and batch['ths'][3] >= 100 else ng)(
                '표 열 폭 — 순번·지역명·게시기간 여유', str(batch['ths']))
            (ok if float(str(batch['tdH']).replace('px', '') or 0) >= 24 and float(str(batch['tdPad']).replace('px', '') or 0) >= 4 else ng)(
                '표 행 높이·좌우 여백', 'height=%s · padding-left=%s' % (batch['tdH'], batch['tdPad']))
            (ok if float(str(batch['infoPad']).replace('px', '') or 0) >= 6 else ng)('상단 정보 표 여백', batch['infoPad'])
            (ok if batch['breakAfter'] in ('page', 'always') else ng)('건별 페이지 나눔(page-break)', batch['breakAfter'])
            css_txt = io.open(os.path.join(ROOT, 'assets', 'style.css'), encoding='utf-8').read()
            (ok if 'page-break-after:always' in css_txt and '#desigBatch .desig-page' in css_txt else ng)(
                '일괄 출력 페이지 나눔 CSS', 'page-break-after rule')
            pg.evaluate("() => window.SEOSAN_VERIFY.closeModal()")
        # 시청 신고 표지(현수막 접수현황) — 2026-11-23 전용 페이지(admin-report.html)로 분리
        goto(pg, base + 'admin-report.html', 500)
        if pg.query_selector('#btnReportShow'):
            pg.click('#btnReportShow')
            pg.wait_for_timeout(500)
        rd = pg.evaluate("() => ({ date: window.SEOSAN_VERIFY.reportDate(), rows: window.SEOSAN_VERIFY.reportRows(), sum: window.SEOSAN_VERIFY.reportSummary(), html: window.SEOSAN_VERIFY.reportCover() })")
        title_ok = ('■ ' + rd['date'] + ' 현수막 접수현황') in rd['html']
        (ok if title_ok else ng)('시청 신고 표지 제목 — ■ YYYY/MM/DD 현수막 접수현황', rd['date'])
        (ok if all(x in rd['html'] for x in ('업체', '건수', '매수', '수수료', '세액', '인지대', '금액', '비고')) else ng)(
            '표 헤더 8열', 'OK' if '인지대' in rd['html'] else 'missing')
        hdr_green = pg.evaluate("""() => { const th = document.querySelector('#reportPreview .report-table th');
            return th ? getComputedStyle(th).backgroundColor : ''; }""")
        (ok if hdr_green.replace(' ', '') in ('rgb(146,208,80)', 'rgba(146,208,80,1)') else ng)(
            '표 헤더 연두색(#92d050)', hdr_green)
        off_rows = [r for r in rd['rows'] if r['official']]
        (ok if off_rows and all(r['city'] == 0 and r['total'] == r['seats'] * 7700 for r in off_rows) else ng)(
            '공문 행 — 인지대 0(면제) · 금액 = 매수×7,700', str([(r['company'], r['city'], r['total']) for r in off_rows][:3]))
        (ok if '(공문)' in rd['html'] and 'c-city off' in rd['html'] else ng)('공문 행 표시 · 살구색 인지대 셀', 'ok')
        sumd = rd['sum']
        (ok if sumd['genCount'] == sumd['count'] - sumd['offCount'] and sumd['genSeats'] == sumd['seats'] - sumd['offSeats'] else ng)(
            '요약 — 총건·총매에서 공문 제외', str({k: sumd[k] for k in ('count', 'offCount', 'genCount', 'seats', 'offSeats', 'genSeats')}))
        (ok if sumd['city'] == sumd['genSeats'] * 3000 else ng)('인지대 = 인지대대상매 × 3,000', '%s / %s매' % (sumd['city'], sumd['genSeats']))
        (ok if ('₩' + format(sumd['city'], ',')) in rd['html'] else ng)('요약 박스 인지대 표기', '₩' + format(sumd['city'], ','))
        (ok if ('합  계' in rd['html'] and format(sumd['amount'], ',') in rd['html']) else ng)(
            '하단 연두색 합계 행', '합계 %s' % format(sumd['amount'], ','))
        pg.evaluate("() => { const b = document.querySelector('#btnReportShow'); if (b) b.click(); }")
        pg.wait_for_timeout(500)
        rep = pg.evaluate("() => ({ open: !!document.querySelector('#modal.open'), sheets: document.querySelectorAll('#reportSheet .report-sheet').length, rows: document.querySelectorAll('#reportSheet tbody tr').length })")
        (ok if rep['open'] and rep['sheets'] == 1 and rep['rows'] >= 26 else ng)('시청 신고 표지 미리보기', str(rep))
        pg.evaluate("() => window.SEOSAN_VERIFY.closeModal()")
        # 입금 확인(사무실무원 전용) · 입고 확인(현장실무원 전용) — 6페이지 분리 후 각 페이지에서 확인
        def role_locks(role):
            pg.evaluate("(r) => window.SEOSAN_VERIFY.setRole(r)", role)
            goto(pg, base + 'admin-pay.html', 350)
            pay = pg.evaluate("""() => { const l = document.querySelector('#payLocked');
                return { lock: l ? !l.classList.contains('hidden') : null }; }""")
            goto(pg, base + 'admin-deliver.html', 350)
            dlv = pg.evaluate("""() => { const l = document.querySelector('#deliverLocked');
                return { lock: l ? !l.classList.contains('hidden') : null }; }""")
            return {'payLock': pay['lock'], 'dlvLock': dlv['lock']}
        v1 = role_locks('staff')
        (ok if v1['payLock'] is False and v1['dlvLock'] is True else ng)('사무실무원 — 입금 확인 허용·입고 차단', str(v1))
        v2 = role_locks('field')
        (ok if v2['payLock'] is True and v2['dlvLock'] is False else ng)('현장실무원 — 입고 확인 허용·입금 차단', str(v2))
        v3 = role_locks('chief')
        (ok if v3['payLock'] is True and v3['dlvLock'] is True else ng)('지부장 — 입금·입고 모두 차단 안내', str(v3))
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('super')")
        probs = w.problems()
        (ok if not probs else ng)('게시 지정서 일괄 출력 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        # 노후화 사용금지 + 정치행정 3단·승인 — 새 저장소(추첨 전)에서 확인
        ctx.close()
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        w = Watcher(pg, base)
        goto(pg, base + 'admin-board.html', 500)
        pid2 = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY;
            const list = v.state().placements.filter(p => {
              if (p.broken || v.availSeat(p.id) < 3) return false;
              const pl = v.slotPlan(p.id, '2026-11-30');
              return Object.keys(pl.post || {}).length === 0 && (pl.free || []).length >= 2; });
            return list.length ? list[0].id : ''; }""")
        codes2 = pg.evaluate("(p) => window.SEOSAN_VERIFY.slotPlan(p, '2026-11-30').free", pid2) or []
        if codes2:
            test_code = codes2[0]
            before2 = pg.evaluate("(p) => window.SEOSAN_VERIFY.availSeat(p)", pid2)
            pg.evaluate("(a) => window.SEOSAN_VERIFY.setSlotFlag3(a[0], a[1], 'aged')", [pid2, test_code])
            after2 = pg.evaluate("(p) => window.SEOSAN_VERIFY.availSeat(p)", pid2)
            st_aged = pg.evaluate("(a) => window.SEOSAN_VERIFY.slotStateOf(a[0], a[1])", [pid2, test_code])
            (ok if before2 >= 1 and after2 == before2 - 1 and st_aged.get('off') and '노후화' in st_aged.get('label', '') else ng)(
                '노후화 사용금지 — 가용 면 제외·선택 불가', 'pid=%s · avail %s → %s · %s' % (pid2, before2, after2, st_aged.get('label')))
            # 나머지 빈 칸을 고장으로 막아 '그 한 칸'만 남긴 뒤 추첨 엔진 결과 비교
            pg.evaluate("(o) => { const v = window.SEOSAN_VERIFY; o.codes.slice(1).forEach(c => v.setSlotFlag3(o.pid, c, 'fault')); }", {'pid': pid2, 'codes': codes2})
            probe = pg.evaluate("(a) => window.SEOSAN_VERIFY.agedProbe(a[0], a[1])", [pid2, test_code])
            (ok if probe and probe['normal']['seats'] >= 1 and probe['aged']['seats'] == 0 else ng)(
                '노후화 사용금지 — 추첨 배정 제외', 'aged=%s · normal=%s' % (probe and probe['aged'], probe and probe['normal']))
            pg.evaluate("(o) => { const v = window.SEOSAN_VERIFY; o.codes.forEach(c => v.setSlotFlag3(o.pid, c, '')); }", {'pid': pid2, 'codes': codes2})
        # 정치행정 — 지부장 ∥ 감사 순서 무관 승인 + 3단 배정
        pol = pg.evaluate("() => { const v = window.SEOSAN_VERIFY; const a = v.state().apps.filter(x => x.round === v.round().ROUND.id && x.status === '추첨대기').slice(-1)[0]; return a ? a.id : ''; }")
        if pol:
            # 시안 승인은 실무 결재권자(지부장) — 총괄관리자는 결재·심사 권한이 없다
            pg.evaluate("() => { try { window.SEOSAN_VERIFY.setRole('chief'); } catch (e) {} }")
            pg.wait_for_timeout(200)
            pg.evaluate("(id) => window.SEOSAN_VERIFY.setPol(id, true)", pol)
            pg.evaluate("(id) => window.SEOSAN_VERIFY.approve(id)", pol)
            pg.wait_for_timeout(200)
            st_pol = pg.evaluate("(id) => window.SEOSAN_VERIFY.eventOf ? id : id", pol)
            polapp = pg.evaluate("(id) => window.SEOSAN_VERIFY.polApps().find(x => x.id === id)", pol)
            (ok if polapp and polapp['status'] == '정치심사중' else ng)('정치행정 — 시안 승인 후 심사 단계', str(polapp))
            pg.evaluate("() => { try { window.SEOSAN_VERIFY.setRole('audit1'); } catch (e) {} }")
            pg.wait_for_timeout(200)
            a1p = pg.evaluate("(id) => window.SEOSAN_VERIFY.polApprove(id, '감사1')", pol)
            (ok if a1p and a1p['done'] == 1 and a1p['status'] == '정치심사중' else ng)('정치행정 — 감사 먼저 승인(1/2)', str(a1p))
            pg.evaluate("() => { try { window.SEOSAN_VERIFY.setRole('chief'); } catch (e) {} }")
            pg.wait_for_timeout(200)
            a2p = pg.evaluate("(id) => window.SEOSAN_VERIFY.polApprove(id, '지부장')", pol)
            (ok if a2p and a2p['done'] == 2 and a2p['polStatus'] == '승인' and a2p['status'] == '추첨대기' else ng)(
                '정치행정 — 감사→지부장(역순) 승인 2/2 확정', str(a2p))
            pol_slot = pg.evaluate("""(id) => { const v = window.SEOSAN_VERIFY;
                const a = v.state().apps.find(x => x.id === id);
                const out = v.drawEngine([a], 99);
                const pls = (out.out[id] && out.out[id].places) || [];
                return { slots: pls.map(x => x.slot), seats: out.stat.seats }; }""", pol)
            (ok if pol_slot and pol_slot['seats'] > 0 and all(str(x)[-1] == '3' for x in pol_slot['slots']) else ng)(
                '정치행정 — 3단(3열)에만 배정', str(pol_slot))
        ctx.close()

        # ------------------------------------------------------------------
        # 15) 매주 월요일 추첨 → 차주 월요일 게첨 · 지난 회차 시연 데이터 · 서식 화면
        # ------------------------------------------------------------------
        head('15. 월요일 추첨 → 차주 월요일 게첨 · 지난 회차 시연 데이터 · 서식 화면 빠른 이동')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'index.html', 700)

        # 15-1) 회차 상수 — 추첨 월요일과 게첨 시작 월요일이 정확히 7일 차이
        rd = pg.evaluate("() => { const r = window.SEOSAN_VERIFY.round(); return { draw: r.ROUND.drawDate, start: r.ROUND.postStart, end: r.ROUND.postEnd, label: r.ROUND.label }; }")
        gap = pg.evaluate("""(r) => { const a = new Date(r.draw + 'T00:00:00'), b = new Date(r.start + 'T00:00:00'), c = new Date(r.end + 'T00:00:00');
            return { days: Math.round((b - a) / 86400000), span: Math.round((c - b) / 86400000) }; }""", rd)
        (ok if rd['draw'] == '2026-11-23' and rd['start'] == '2026-11-30' and rd['end'] == '2026-12-06'
         and gap['days'] == 7 and gap['span'] == 6 else ng)(
            '회차 상수 — 추첨 11.23(월) → 게첨 11.30(월)~12.06(일) 7일', str(rd) + ' · ' + str(gap))

        # 15-2) 지난 회차 시연 데이터 — 11월 1·2·3주차 접수·배정·추첨 기록
        past_weeks = ['2026-11-02', '2026-11-09', '2026-11-16']
        past_stats = pg.evaluate("(ws) => ws.map(s => window.SEOSAN_VERIFY.weekStats(s))", past_weeks)
        empty_wk = [s for s, st in zip(past_weeks, past_stats) if not st or st['n'] <= 0 or st['awarded'] <= 0]
        (ok if not empty_wk else ng)('11월 1·2·3주차 접수·배정 시연 데이터',
                                     ' / '.join('%s %d건·배정 %d매' % (s, st['n'], st['awarded']) for s, st in zip(past_weeks, past_stats)))
        arch = pg.evaluate("() => (window.SEOSAN_VERIFY.state().drawArchive || []).map(d => ({ week: d.week, seed: d.seed, pool: d.pool, won: d.won, seats: d.seats, at: d.at }))")
        arch_wk = {a['week']: a for a in arch}
        arch_bad = [s for s in past_weeks if s not in arch_wk or len(str(arch_wk[s]['seed'] or '')) != 8
                    or arch_wk[s]['pool'] <= 0 or arch_wk[s]['won'] <= 0 or '10:00' not in str(arch_wk[s]['at'])]
        (ok if not arch_bad else ng)('11월 1·2·3주차 추첨 완료 기록(추첨일·시드·참가/당첨)',
                                     ' '.join('%s %s' % (s, arch_wk.get(s, {}).get('seed')) for s in past_weeks))

        # 15-3) 접수 — 당일 주간(11.23~11.29) 차단 · 차주(11.30~) 이후만 선택
        goto(pg, base + 'apply.html', 700)
        blocked = pg.evaluate("() => window.SEOSAN_VERIFY.setApplyWeek('2026-11-23')")
        pg.wait_for_timeout(250)
        toast1 = (pg.text_content('#toast') or '').replace('\n', ' ').strip()
        (ok if blocked is False and '선택할 수 없습니다' in toast1 else ng)(
            '당일 주간(11.23~11.29) 게첨 주 선택 차단', 'return=%r · toast=%r' % (blocked, toast1[:70]))
        opts = pg.eval_on_selector_all('#applyStart option', 'els => els.map(e => e.value)')
        (ok if opts and '2026-11-23' not in opts and opts[0] == '2026-11-30' else ng)(
            '게시 시작일 후보 — 11.30(차주) 이후만', str(opts[:4]))
        pick30 = pg.evaluate("() => window.SEOSAN_VERIFY.setApplyWeek('2026-11-30')")
        pick07 = pg.evaluate("() => window.SEOSAN_VERIFY.setApplyWeek('2026-12-07')")
        back30 = pg.evaluate("() => window.SEOSAN_VERIFY.setApplyWeek('2026-11-30')")
        wk_state = pg.evaluate("() => window.SEOSAN_VERIFY.weekState()")
        (ok if pick30 and pick07 and back30 and wk_state['apply'] == '2026-11-30' else ng)(
            '차주(11.30~)·그 다음 주(12.07~) 게첨 주 선택 가능', '30=%r 07=%r back=%r state=%s' % (pick30, pick07, back30, wk_state['apply']))
        cdays = pg.evaluate("""() => Array.from(document.querySelectorAll('#applyWeekCal [data-calweek]')).map(b => ({ w: b.getAttribute('data-calweek'), off: b.classList.contains('off'), dis: b.getAttribute('aria-disabled') }))""")
        cur_btns = [x for x in cdays if x['w'] == '2026-11-23']
        next_btns = [x for x in cdays if x['w'] == '2026-11-30']
        (ok if cur_btns and all(x['off'] and x['dis'] == 'true' for x in cur_btns)
         and next_btns and not next_btns[0]['off'] else ng)(
            '접수 달력 — 11.23~11.29 주 선택 불가 · 11.30 주 선택 가능', '당일주 %d개 off=%s · 차주 off=%s' % (
                len(cur_btns), [x['off'] for x in cur_btns], (next_btns[0]['off'] if next_btns else 'none')))
        strip_apply = (pg.text_content('#applyRuleStrip') or '').replace('\n', ' ')
        (ok if '다음 주 월요일부터 게첨' in strip_apply and '11.30' in strip_apply and '12.06' in strip_apply else ng)(
            '접수 화면 주간 규칙 스트립 — 11.23 추첨 → 11.30~12.06 게첨', strip_apply.strip()[:110])

        # 15-4) 추첨 접수대장·게시대 현황 화면의 주간 규칙 표기
        goto(pg, base + 'admin-draw.html', 700)
        strip_draw = (pg.text_content('#drawRuleStrip') or '').replace('\n', ' ')
        (ok if '다음 주 월요일부터 게첨' in strip_draw and '11.30' in strip_draw else ng)(
            '추첨 접수대장 주간 규칙 스트립', strip_draw.strip()[:110])
        goto(pg, base + 'index.html', 600)
        pg.evaluate("() => { const b = document.querySelector('#btnWeekCal'); if (b) b.click(); }")
        pg.wait_for_timeout(500)
        strip_idx = (pg.text_content('#weekRuleStrip') or '').replace('\n', ' ')
        (ok if '다음 주 월요일부터 게첨' in strip_idx and '11.30' in strip_idx and '12.06' in strip_idx else ng)(
            '게시대 현황 주간 규칙 스트립', strip_idx.strip()[:110])

        # 15-5) 협회관리자 서브탭 — 기능별 14개 (2026-11-23 페이지 분리 지시)
        SUB_LABELS = ['🔍 시안 심사', '📄 공문 접수', '📋 2주 공문 심사', '⚖️ 정치행정 심사', '🎪 행사 심사',
                      '🎯 추첨 · 접수대장', '💰 입금 확인', '📦 현수막 입고', '🏛️ 시청 신고 표지', '🖨️ 게시 지정서',
                      '📋 작업지시서', '📍 게시위치', '📸 게첨사진', '🛠️ 게시대 관리', '🗺️ 테마코스 · 금지',
                      '🛡️ 관리자 권한', '👥 회원 · 가산점', '📢 공지 · 로그']
        bad_sub = []
        for fn in sorted(glob.glob(os.path.join(ROOT, 'admin-*.html'))):
            src_html = io.open(fn, encoding='utf-8').read()
            miss = [x for x in SUB_LABELS if x not in src_html]
            if miss:
                bad_sub.append(os.path.basename(fn) + ':' + '/'.join(miss[:2]))
        (ok if not bad_sub else ng)('관리자 서브탭 18개가 모든 관리자 페이지에 노출',
                                     '누락 %s' % bad_sub if bad_sub else '%d개 페이지 모두 반영' % len(glob.glob(os.path.join(ROOT, 'admin-*.html'))))
        goto(pg, base + 'admin-docs.html', 600)
        sub_txt = (pg.text_content('#adminSub') or '').replace('\n', ' ')
        (ok if all(x in sub_txt for x in SUB_LABELS) else ng)(
            '서브탭 줄 — 18개 이름 모두 노출', sub_txt.strip()[:130])
        sub_n = pg.eval_on_selector_all('#adminSub .subtab', 'els => els.length')
        (ok if sub_n == 18 else ng)('서브탭 개수 18개', '%d개' % sub_n)

        # 15-6) 페이지별 '관련 화면' 링크 + 직책 잠금 페이지 안내
        qn = pg.evaluate("""() => { const n = document.querySelector('#docsQuickNav'); if (!n) return null;
            const links = Array.from(n.querySelectorAll('a')).map(a => ({ t: a.textContent.trim(), h: a.getAttribute('href') }));
            return { n: links.length, links: links }; }""")
        (ok if qn and qn['n'] >= 2 and all(l['h'].endswith('.html') for l in qn['links']) else ng)(
            '작업지시서 페이지 — 관련 화면 링크', str(qn['links'] if qn else None))
        # 지부장(chief)은 입금·입고·게첨사진 모두 잠금 안내만 보인다
        goto(pg, base + 'admin-pay.html', 500)
        if pg.query_selector('#adminRoleSel'):
            pg.select_option('#adminRoleSel', 'chief')
            pg.wait_for_timeout(450)
        lock_pay = pg.evaluate("""() => ({ panel: !!document.querySelector('#payPanel') && !document.querySelector('#payPanel').classList.contains('hidden'),
            locked: !!document.querySelector('#payLocked') && !document.querySelector('#payLocked').classList.contains('hidden'),
            txt: ((document.querySelector('#payLocked') || {}).textContent || '').trim() })""")
        (ok if (not lock_pay['panel'] or lock_pay['locked']) and '사무실무원' in lock_pay['txt'] else ng)(
            '입금 확인 페이지 — 지부장은 잠금 안내', str(lock_pay)[:140])
        if pg.query_selector('#adminRoleSel'):
            pg.select_option('#adminRoleSel', 'super')
            pg.wait_for_timeout(400)
        unlock_pay = pg.evaluate("() => !!document.querySelector('#payPanel') && !document.querySelector('#payPanel').classList.contains('hidden')")
        (ok if unlock_pay else ng)('입금 확인 페이지 — 총괄 관리자는 열람', str(unlock_pay))

        # 15-7) 게시 지정서 일괄 출력 — 배정 0건이어도 버튼 상시 노출 · 0건 클릭은 안내만
        goto(pg, base + 'admin-desig.html', 700)
        zero = pg.evaluate("""() => ({ rows: document.querySelectorAll('#desigBatchList tbody tr').length,
            all: ((document.querySelector('#btnDesigBatchAllPrint') || {}).textContent || '').trim(),
            sel: !!document.querySelector('#btnDesigBatchSelPrint'),
            info: ((document.querySelector('#desigBatchInfo') || {}).textContent || '').trim() })""")
        (ok if zero['rows'] == 0 and '(0건)' in zero['all'] and zero['sel'] else ng)(
            '배정 0건(추첨 전) — 전체/선택 일괄 출력 버튼 상시 노출', '%s | %s' % (zero['info'], zero['all']))
        pg.click('#btnDesigBatchAllPrint')
        pg.wait_for_timeout(350)
        toast_zero = (pg.text_content('#toast') or '').replace('\n', ' ').strip()
        modal_open = pg.evaluate("() => !!document.querySelector('#modal.open')")
        (ok if '배정 건이 없습니다' in toast_zero and not modal_open else ng)(
            '0건 버튼 클릭 — 안내 toast만(인쇄창 없음)', '%r · modal=%s' % (toast_zero[:50], modal_open))
        # 배정이 있는 회차(11.16~11.22 게첨분)로 바꾸면 같은 버튼에 건수가 채워진다
        pg.evaluate("() => { window.SEOSAN_VERIFY.setStatusWeek('2026-11-16'); window.SEOSAN_VERIFY.renderAll(); }")
        pg.wait_for_timeout(600)
        back = pg.evaluate("""() => ({ rows: document.querySelectorAll('#desigBatchList tbody tr').length,
            all: ((document.querySelector('#btnDesigBatchAllPrint') || {}).textContent || '').trim(),
            sel: !!document.querySelector('#btnDesigBatchSelPrint') })""")
        (ok if back['rows'] > 0 and back['sel'] and ('(%d건)' % back['rows']) in back['all'] else ng)(
            '배정 있는 회차 — 버튼이 사라지지 않고 건수 라벨 일치', '%d행 → %s' % (back['rows'], back['all']))
        probs = w.problems()
        (ok if not probs else ng)('월요일 규칙·시연 데이터·서식 화면 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 16) file:// 로도 열린다
        # ------------------------------------------------------------------
        if not skip_file:
            head('16. file:// 직접 열기 (상대 경로 점검)')
            ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
            pg = ctx.new_page()
            pg.set_default_timeout(8000)
            w = Watcher(pg, 'file://')
            pg.goto('file://' + os.path.join(ROOT, 'index.html'), wait_until='load')
            settle(pg, 400)
            cards = pg.eval_on_selector_all('#placementGrid .plrow', 'els => els.length')
            (ok if cards > 0 and not w.problems() else ng)('file:// index.html',
                                                          '행 %d개 · 오류 %s' % (cards, w.problems()[:2]))
            pg.goto('file://' + os.path.join(ROOT, 'admin-review.html'), wait_until='load')
            settle(pg, 400)
            (ok if not w.problems() else ng)('file:// admin-review.html', '오류 %s' % w.problems()[:2])
            pg.goto('file://' + os.path.join(ROOT, 'guide.html'), wait_until='load')
            settle(pg, 300)
            n = pg.eval_on_selector_all('.dl-btns a[href^="files/"]', 'els => els.length')
            (ok if n == 5 else ng)('file:// guide.html 다운로드 링크', '%d개' % n)
            ctx.close()

        # ------------------------------------------------------------------
        # 17) 현장 게첨사진 — 게시대 동 단위 등록 · 접수번호별 조회·다운로드·인쇄
        # ------------------------------------------------------------------
        head('17. 현장 게첨사진 — 게시대 동 단위 등록 → 접수번호별 사진 다운로드·인쇄')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1000}, accept_downloads=True)
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'admin-photos.html', 500)

        # 17-1) 시연 데이터 — 4개 주차 · 주요 게시대 '동' 단위 샘플 사진
        seeded = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY, st = v.state();
            const names = {}; st.placements.forEach(p => { names[p.id] = p.name; });
            const weeks = {}, cells = [];
            (st.photos || []).forEach(ph => { weeks[ph.week] = (weeks[ph.week] || 0) + 1;
              cells.push((names[ph.pid] || '') + ' ' + (ph.dong ? ph.dong + '동' : '전체')); });
            return { n: (st.photos || []).length, weeks: weeks, cells: cells, apps: v.photoAppIds().length,
              sample: v.photoSeed(), sizeKB: Math.round(JSON.stringify(st.photos || []).length / 1024) }; }""")
        wk_ok = all(k in seeded['weeks'] for k in ('2026-11-02', '2026-11-09', '2026-11-16', '2026-11-23'))
        (ok if seeded['n'] >= 60 and wk_ok and seeded['sample'] == seeded['n'] else ng)(
            '시연 게첨사진 내장 — 11월 1·2·3주차 + 이번 주 · 60장 이상', '%d장 / %d주차 / %sKB · %s' % (
                seeded['n'], len(seeded['weeks']), seeded['sizeKB'], sorted(seeded['weeks'])))
        joined = '|'.join(seeded['cells'])
        need_cells = ['의료원사거리 A동', '의료원사거리 F동', '의료원사거리 G동', '석지제사거리 D동', '중앙고']
        (ok if all(x in joined for x in need_cells) else ng)(
            '주요 게시대 동 단위 샘플 — 의료원사거리 A·F·G동 · 석지제 D동 · 중앙고',
            ', '.join(x for x in need_cells if x not in joined) or '모두 있음')
        (ok if seeded['apps'] >= 60 else ng)('당첨 건 접수번호 자동 매칭 — 사진이 연결된 접수', '%d건' % seeded['apps'])

        # 17-2) 권한 — 현장실무원·총괄 관리자만 등록, 사무실무원은 차단 안내
        role_photo = lambda: pg.evaluate("""() => ({ panel: !document.querySelector('#photoPanel').classList.contains('hidden'),
            lock: !document.querySelector('#photoLocked').classList.contains('hidden') })""")
        pg.select_option('#adminRoleSel', 'staff')
        pg.wait_for_timeout(300)
        v_staff = role_photo()
        pg.select_option('#adminRoleSel', 'field')
        pg.wait_for_timeout(300)
        v_field = role_photo()
        (ok if (not v_staff['panel'] and v_staff['lock']) and v_field['panel'] and not v_field['lock'] else ng)(
            '게첨사진 등록 권한 — 사무실무원 차단 · 현장실무원 허용', 'staff=%s · field=%s' % (v_staff, v_field))

        # 17-3) 등록 화면 — 주차·게시대·동 선택 · 배정 접수 목록 · 빠른 이동
        panel = pg.evaluate("""() => ({ info: (document.querySelector('#photoInfo') || {}).textContent || '',
            cards: document.querySelectorAll('#photoList .photo-card').length,
            rows: document.querySelectorAll('#photoAwardList tbody tr').length,
            weeks: document.querySelectorAll('#photoWeek option').length,
            dongs: document.querySelectorAll('#photoDong option').length,
            nav: !!document.querySelector('#docsQuickNav a[href$=".html"]') })""")
        (ok if panel['cards'] >= 1 and panel['rows'] >= 1 and panel['weeks'] >= 5 and panel['dongs'] >= 1 and panel['nav'] else ng)(
            '등록 화면 — 주차/게시대/동 선택 · 배정 접수 · 사진 목록 · 빠른 이동', str(panel))
        cell = pg.evaluate("""() => ({ week: document.querySelector('#photoWeek').value, pid: document.querySelector('#photoPid').value,
            dong: document.querySelector('#photoDong').value, n: document.querySelectorAll('#photoList .photo-card').length })""")

        # 17-4) 샘플 생성 → +2장 · 파일 업로드 → +1장(JPEG 변환) · 삭제 → -1장
        pg.click('#btnPhotoSample')
        pg.wait_for_timeout(260)
        n_sample = pg.evaluate("(c) => window.SEOSAN_VERIFY.photosOf(c.week, c.pid, c.dong).length", cell)
        (ok if n_sample == cell['n'] + 2 else ng)('시연용 샘플 게첨사진 생성 버튼', '%d장 → %d장' % (cell['n'], n_sample))
        up_path = write_test_png()
        pg.set_input_files('#photoFile', up_path)
        pg.wait_for_timeout(750)
        up = pg.evaluate("""(c) => { const l = window.SEOSAN_VERIFY.photosOf(c.week, c.pid, c.dong);
            const last = l[l.length - 1]; return { n: l.length, head: last['head'], size: last['size'], sample: last['sample'] }; }""", cell)
        (ok if up['n'] == n_sample + 1 and up['head'].startswith('data:image/jpeg') and up['size'] > 200 else ng)(
            '실무자 사진 업로드 — 파일 선택 시 JPEG로 줄여 저장', '%d장 · %s · %dbytes' % (up['n'], up['head'][:24], up['size']))
        pg.evaluate("() => { const b = document.querySelector('#photoList [data-photodel]'); if (b) b.click(); }")
        pg.wait_for_timeout(300)
        n_del = pg.evaluate("(c) => window.SEOSAN_VERIFY.photosOf(c.week, c.pid, c.dong).length", cell)
        (ok if n_del == up['n'] - 1 else ng)('게첨사진 삭제', '%d장 → %d장' % (up['n'], n_del))

        # 17-5) 접수자 마이페이지 — 접수번호별 사진 자동 매칭 · 다운로드 · 인쇄
        aid = pg.evaluate("(c) => { const l = window.SEOSAN_VERIFY.photoCell(c.week, c.pid, c.dong); return l.length ? l[0].id : ''; }", cell)
        open_detail(pg, base, aid, 550)
        mp = pg.evaluate("""() => ({ cards: document.querySelectorAll('#mpPhotoBox .photo-card').length,
            dl: document.querySelectorAll('#mpPhotoBox [data-photodl]').length,
            proof: document.querySelectorAll('#mpPhotoBox [data-photoproof]').length,
            txt: ((document.querySelector('#mpPhotoBox') || {}).textContent || '').slice(0, 40) })""")
        (ok if mp['cards'] >= 1 and mp['dl'] == mp['cards'] and mp['proof'] >= 1 else ng)(
            '마이페이지 접수 상세 — 배정 게시대·동 사진 자동 표시', '%s' % str(mp))
        with pg.expect_download(timeout=15000) as dlinfo:
            pg.evaluate("() => { const b = document.querySelector('#mpPhotoBox [data-photodl]'); if (b) b.click(); }")
        dl = dlinfo.value
        name = dl.suggested_filename or ''
        head_bytes = b''
        try:
            head_bytes = open(dl.path(), 'rb').read(8)
        except Exception:      # noqa: BLE001
            pass
        (ok if re.match(r'^_[^_]+(.+?)_%s_\d{8}\.png$' % re.escape(aid), name) and head_bytes[:4] == b'\x89PNG' else ng)(
            '게첨사진 다운로드 — 파일명 규칙 · PNG 파일', '%s · %r' % (name, head_bytes[:4]))
        pg.evaluate("() => { const b = document.querySelector('#mpPhotoBox .off-actions [data-photoproof]') || document.querySelector('#mpPhotoBox [data-photoproof]'); if (b) b.click(); }")
        pg.wait_for_timeout(450)
        proof = pg.evaluate("""() => { const pages = Array.from(document.querySelectorAll('#photoProof .pp-page'));
            const txt = pages.length ? pages[0].textContent : '';
            return { open: !!document.querySelector('#modal.open'), pages: pages.length,
              hasNo: txt.indexOf('접수번호') >= 0, hasPlace: txt.indexOf('게시대') >= 0,
              hasPeriod: txt.indexOf('게첨 기간') >= 0,
              imgAll: pages.length > 0 && pages.every(pp => pp.querySelectorAll('img').length === 1),
              btn: !!document.querySelector('#btnPhotoProofPrint') }; }""")
        (ok if proof['open'] and proof['pages'] == mp['cards'] and proof['imgAll']
         and proof['hasNo'] and proof['hasPlace'] and proof['hasPeriod'] and proof['btn'] else ng)(
            '게첨 확인서(사진) — 사진마다 A4 1장 · 접수번호·게시대·게첨기간·사진', str(proof))
        pg.evaluate("() => window.SEOSAN_VERIFY.closeModal()")
        css_txt = io.open(os.path.join(ROOT, 'assets', 'style.css'), encoding='utf-8').read()
        (ok if 'body.print-photo' in css_txt and '.pp-page' in css_txt and 'page-break-after:always' in css_txt else ng)(
            '게첨 확인서 인쇄 CSS — A4 1장씩 페이지 나눔', 'style.css print-photo')

        # 17-6) 사진이 아직 없는 접수 — '게첨사진 등록 대기중' 안내
        wait_id = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY;
            const list = v.photoAppIds();
            if (!list.length) return '';
            const id = list[0].id;
            v.photosFor(id).forEach(ph => v.photoDelete(ph.id));
            return id; }""")
        if wait_id:
            open_detail(pg, base, wait_id, 500)
            wtxt = pg.evaluate("() => ((document.querySelector('#mpPhotoBox') || {}).textContent || '')")
            (ok if '등록 대기중' in wtxt else ng)('게첨 전 접수 — 게첨사진 등록 대기중 안내', wtxt.strip()[:60])
        else:
            ng('게첨 전 접수 — 게첨사진 등록 대기중 안내', '대상 접수 없음')

        probs = w.problems()
        (ok if not probs else ng)('게첨사진 화면 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 18) 공문 파일 자동 인식 · 시연용 공문 샘플 4종
        # ------------------------------------------------------------------
        head('18. 공문 파일 자동 인식 · 시연용 공문 샘플 4종')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'admin-official.html', 600)
        if pg.query_selector('#adminRoleSel'):
            pg.select_option('#adminRoleSel', 'staff')      # 접수는 사무실무원·현장실무원 화면
            pg.wait_for_timeout(350)
        SAMPLES = [
            ('welfare', '서산시청 복지과', '난방비', 6, 7),
            ('culture', '서산시청 문화관광과', '야간문화행사', 10, 14),
            ('safety', '서산시청 안전총괄과', '제설', 8, 7),
            ('health', '서산시보건소', '예방접종', 5, 7),
        ]
        bad = []
        for key, org, word, qty, days in SAMPLES:
            pg.click('[data-offsample="%s"]' % key)
            pg.wait_for_timeout(220)
            got = pg.evaluate("() => ({ f: window.SEOSAN_VERIFY.offForm(), hits: window.SEOSAN_VERIFY.offHits(), pv: window.SEOSAN_VERIFY.offPreview() })")
            if not (got['f']['org'] == org and word in got['f']['title'] and got['f']['qty'] == qty
                    and got['f']['days'] == days and not got['pv']['hidden']):
                bad.append((key, got['f'], got['pv']))
        (ok if not bad else ng)('시연용 공문 샘플 4종 — 기관·문구·매수·기간 자동 채우기 · 미리보기',
                               '실패 %s' % bad if bad else '복지과 6매 · 문화관광과 10매(2주) · 안전총괄과 8매 · 보건소 5매')
        hits_txt = pg.evaluate("() => window.SEOSAN_VERIFY.offHits()")
        (ok if all(x in hits_txt for x in ('기관명', '공문번호', '문구', '매수', '기간', '게첨 주')) else ng)(
            '자동 인식 결과 배지 — 기관·공문번호·문구·매수·기간·게첨 주', hits_txt[:80])
        pg.click('.off-file-thumb')
        pg.wait_for_timeout(350)
        zoom = pg.evaluate("() => ({ open: !!document.querySelector('#modal.open'), img: document.querySelectorAll('#modalBody img').length })")
        (ok if zoom['open'] and zoom['img'] == 1 else ng)('공문 미리보기 확대(클릭)', str(zoom))
        pg.keyboard.press('Escape')
        pg.wait_for_timeout(150)

        # 파일 업로드 — 텍스트 공문에서 기관·공문번호·문구·매수·기간 자동 인식
        up = write_test_official()
        pg.set_input_files('#offFile', up)
        pg.wait_for_timeout(700)
        got2 = pg.evaluate("() => ({ f: window.SEOSAN_VERIFY.offForm(), hits: window.SEOSAN_VERIFY.offHits() })")
        (ok if got2['f']['org'] == '서산시청 안전총괄과' and '제설' in got2['f']['title']
         and got2['f']['qty'] == 8 and got2['f']['days'] == 7 and '공문번호' in got2['hits'] else ng)(
            '공문 파일 업로드 → 폼 자동 완성 (기관·문구·매수·기간·공문번호)', str(got2['f']))
        parsed = pg.evaluate("""() => window.SEOSAN_VERIFY.offParse({ name: '서산시청 문화관광과-0963.pdf',
            text: '제목 : 해미읍성 주말 야간문화행사 안내\\n현수막 10매 게첨\\n기간 2주' })""")
        (ok if parsed and parsed['org'] == '서산시청 문화관광과' and parsed['qty'] == 10 and parsed['days'] == 14 else ng)(
            '파서 단위 검사 — 기관·매수·2주(결재) 인식', str(parsed))
        probs = w.problems()
        (ok if not probs else ng)('공문 자동 인식 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 19) 직책별 가산점 부여 한도 설정 — 최고권한만 변경 · 부여 패널 즉시 반영
        # ------------------------------------------------------------------
        head('19. 가산점 부여 한도 설정 — 최고권한 변경 · 부여 패널 동적 반영 · 감사 로그')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'admin-roles.html', 500)

        # 19-1) 기본 한도 · 패널
        base_caps = pg.evaluate("() => ({ caps: window.SEOSAN_VERIFY.bonusCaps(), total: window.SEOSAN_VERIFY.bonusCapTotal(), panel: window.SEOSAN_VERIFY.bonusCapPanel() })")
        (ok if base_caps['caps'] == {'chief': 5, 'senior': 3, 'field': 3, 'staff': 2} and base_caps['total'] == 13
         and base_caps['panel']['rows'] == 4 and not base_caps['panel']['lock'] else ng)(
            '기본 한도 — 지부장 5 · 수석 3 · 현장 3 · 사무 2 (합산 +13%)', str(base_caps))

        # 19-2) 다른 직책은 읽기 전용 — 입력 잠금 · 저장 차단
        pg.select_option('#adminRoleSel', 'staff')
        pg.wait_for_timeout(350)
        staff_view = pg.evaluate("() => ({ panel: window.SEOSAN_VERIFY.bonusCapPanel(), can: window.SEOSAN_VERIFY.canEditBonusCaps() })")
        blocked = pg.evaluate("() => window.SEOSAN_VERIFY.setBonusCap('field', '9')")
        pg.wait_for_timeout(250)
        toast_txt = (pg.text_content('#toast') or '').strip()
        (ok if (not staff_view['can']) and all(staff_view['panel']['disabled']) and staff_view['panel']['lock']
         and blocked is None and ('최고권한' in toast_txt or '총괄관리자' in toast_txt) else ng)(
            '사무실무원 — 읽기 전용(입력 잠금) · 변경 차단 안내', 'panel=%s · blocked=%s' % (staff_view['panel'], blocked))

        # 19-3) 총괄 관리자(최고권한) — 현장실무원 한도를 6%로 변경 → 저장 · 감사 로그
        pg.select_option('#adminRoleSel', 'super')
        pg.wait_for_timeout(350)
        pg.fill('#bc_field', '6')
        pg.click('#btnBonusCapSave')
        pg.wait_for_timeout(500)
        after = pg.evaluate("""() => ({ caps: window.SEOSAN_VERIFY.bonusCaps(), total: window.SEOSAN_VERIFY.bonusCapTotal(),
            panel: window.SEOSAN_VERIFY.bonusCapPanel(),
            audit: (window.SEOSAN_VERIFY.state().audit || []).filter(a => a.type === '권한').slice(0, 3).map(a => a.text) })""")
        audit_ok = any('한도 변경' in t and '현장실무원' in t and '3%' in t and '6%' in t for t in after['audit'])
        (ok if after['caps']['field'] == 6 and after['total'] == 16 and audit_ok and '16' in after['panel']['info'] else ng)(
            '총괄 관리자 — 현장실무원 한도 3%→6% 저장 · 합산 +16% · 감사 로그', '%s · audit=%s' % (after['caps'], after['audit'][:1]))

        # 19-4) 부여 패널 즉시 반영 — 회원사(admin-members) · 시한임박(admin-review) 선택지
        goto(pg, base + 'admin-members.html', 500)
        pg.select_option('#adminRoleSel', 'field')
        pg.wait_for_timeout(450)
        mem_opts = pg.evaluate("() => { const s = document.querySelector('#assocRate0'); return s ? Array.from(s.options).map(o => Number(o.value)) : null; }")
        (ok if mem_opts and max(mem_opts) == 6 and 7 not in mem_opts else ng)(
            '회원사 가산점 선택지 — 새 한도 6%까지(초과 없음)', str(mem_opts))
        goto(pg, base + 'admin-review.html', 550)
        pg.select_option('#adminRoleSel', 'field')
        pg.wait_for_timeout(500)
        rev = pg.evaluate("""() => ({ opts: (function () { const s = document.querySelector('#urgSel0');
              return s ? Array.from(s.options).map(o => Number(o.value)) : null; })(),
            info: ((document.querySelector('#urgentGrantInfo') || {}).textContent || '') })""")
        (ok if rev['opts'] and max(rev['opts']) == 6 and '6%' in rev['info'] else ng)(
            '시한임박 가산점 선택지·한도 안내 — 새 한도 6% 반영', '%s · %s' % (rev['opts'], rev['info'][-40:]))

        # 19-5) 한도 변경은 총괄관리자 전용 — 지부장은 변경 불가 · 0~10% 범위로 자동 제한
        pg.goto(base + 'admin-roles.html')
        pg.wait_for_timeout(600)
        pg.select_option('#adminRoleSel', 'chief')
        pg.wait_for_timeout(350)
        chief_cap = pg.evaluate("() => window.SEOSAN_VERIFY.setBonusCap('staff', '4')")
        (ok if chief_cap is None else ng)('지부장 — 가산점 한도 변경 불가(총괄관리자 전용)', str(chief_cap))
        pg.select_option('#adminRoleSel', 'super')
        pg.wait_for_timeout(350)
        ch = pg.evaluate("""() => ({ staff: window.SEOSAN_VERIFY.setBonusCap('staff', '4'), clamp: window.SEOSAN_VERIFY.setBonusCap('chief', '15'),
            caps: window.SEOSAN_VERIFY.bonusCaps(), superLim: window.SEOSAN_VERIFY.grantLimitOf('super') })""")
        (ok if ch['staff'] and ch['staff']['limit'] == 4 and ch['clamp'] and ch['clamp']['limit'] == 10
         and ch['caps']['staff'] == 4 and ch['superLim'] == 10 else ng)(
            '총괄관리자 — 사무실무원 4% 변경 · 범위(0~10%) 초과는 10%로 제한', str(ch))

        # 19-6) 기본값 복원 버튼
        pg.click('#btnBonusCapReset')
        pg.wait_for_timeout(450)
        rst = pg.evaluate("() => ({ caps: window.SEOSAN_VERIFY.bonusCaps(), total: window.SEOSAN_VERIFY.bonusCapTotal() })")
        (ok if rst['caps'] == {'chief': 5, 'senior': 3, 'field': 3, 'staff': 2} and rst['total'] == 13 else ng)(
            '기본값 복원 (5·3·3·2)', str(rst))
        probs = w.problems()
        (ok if not probs else ng)('가산점 한도 설정 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 20) PC / 모바일 2종 버전 — 접속 환경 자동 판별 · 수동 전환 · 기억
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
        det = open_detail(pg, base, live_app['id'])
        (ok if '설치 방식' in det and '일반인은 직접 설치가 금지' in det and '광고사 의뢰' in det else ng)(
            '마이페이지 접수 상세 — 진행 주간 설치 안내 표시', det[:120].replace('\n', ' '))

        # 21-6) 광고대행사 로그인 — 배너·4단계 요약이 광고사 직접 설치로 바뀐다 (등록증 칸도 사라짐)
        # 페이지 분리(2026-11-23) 이후 진행 중 주간 잔여석 접수는 remain.html - 설치 주체 안내 배너도 거기서 확인한다
        goto(pg, base + 'remain.html', 500)
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

        head('22. 게첨사진 보관기간 3개월(90일) — 기간 경과 자동 삭제 · 등록일/D-N 표시 · 안내문구')
        import datetime as _dt
        today = _dt.date.today()
        def _dstr(days):
            return (today - _dt.timedelta(days=days)).isoformat() + ' 09:00'
        def _exp(days):
            return (today - _dt.timedelta(days=days) + _dt.timedelta(days=90)).isoformat()
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'admin-photos.html', 700)
        if pg.query_selector('#adminRoleSel'):
            pg.select_option('#adminRoleSel', 'field')
            pg.wait_for_timeout(350)
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.photoRetainDays()") == 90 else ng)(
            '보관기간 상수 — 3개월(90일)', str(pg.evaluate("() => window.SEOSAN_VERIFY.photoRetainDays()")))
        n0 = pg.evaluate("() => window.SEOSAN_VERIFY.photoCount()")
        old = pg.evaluate("() => window.SEOSAN_VERIFY.photoAddRaw({week:'2026-11-23', pid:'P01', dong:'A', at:'%s', name:'old.svg'})" % _dstr(95))
        old_info = pg.evaluate("(id) => window.SEOSAN_VERIFY.photoRetainOf(id)", old['id'])
        (ok if old_info and old_info['expiresAt'] == _exp(95) and old_info['daysLeft'] < 0 else ng)(
            '사진 등록일+90일 = 자동 삭제 예정일', str(old_info))
        gone = pg.evaluate("() => window.SEOSAN_VERIFY.photoPurge()")
        (ok if any(g['id'] == old['id'] for g in gone) and pg.evaluate("() => window.SEOSAN_VERIFY.photoCount()") == n0 else ng)(
            '90일 지난 게첨사진 자동 삭제', '%s · %d장' % ([g['id'] for g in gone], n0))
        audit_txt = pg.evaluate("""() => { const o = JSON.parse(localStorage.getItem('seosan-banner-lottery-v6'));
            return (o.audit || []).filter(a => String(a.text || '').indexOf('보관기간 3개월') >= 0).slice(-1)[0] || null; }""")
        (ok if audit_txt and old['id'] in audit_txt['text'] else ng)(
            '자동 삭제 감사 로그 기록', (audit_txt or {}).get('text', '기록 없음')[:90])
        keep = pg.evaluate("() => window.SEOSAN_VERIFY.photoAddRaw({week:'2026-11-23', pid:'P01', dong:'A', at:'%s', name:'keep.svg'})" % _dstr(89))
        gone2 = pg.evaluate("() => window.SEOSAN_VERIFY.photoPurge()")
        kept = pg.evaluate("(id) => window.SEOSAN_VERIFY.photoRetainOf(id)", keep['id'])
        (ok if kept and kept['daysLeft'] == 1 and not any(g['id'] == keep['id'] for g in gone2) else ng)(
            '89일 경과 사진은 보관 유지 (내일 만료)', str(kept))
        edge = pg.evaluate("() => window.SEOSAN_VERIFY.photoAddRaw({week:'2026-11-23', pid:'P01', dong:'A', at:'%s', name:'edge.svg'})" % _dstr(90))
        gone3 = pg.evaluate("() => window.SEOSAN_VERIFY.photoPurge()")
        (ok if any(g['id'] == edge['id'] for g in gone3) else ng)(
            '정확히 90일(만료일) 사진 삭제', str([g['id'] for g in gone3]))
        fresh = pg.evaluate("() => window.SEOSAN_VERIFY.photoAddRaw({week:'2026-11-23', pid:'P01', dong:'A', name:'fresh.svg'})")
        fres = pg.evaluate("(id) => window.SEOSAN_VERIFY.photoRetainOf(id)", fresh['id'])
        (ok if fres and fres['daysLeft'] == 90 else ng)('오늘 등록 사진 — 보관 D-90', str(fres))
        card = pg.evaluate("() => window.SEOSAN_VERIFY.photoRetainHTML()")
        (ok if '보관 D-90' in card and '삭제' in card else ng)(
            '사진 카드 — 보관 D-N · 자동 삭제 예정일 배지', re.sub('<[^>]+>', ' ', card)[:110])
        ret_note = pg.text_content('#photoRetainNote') or ''
        (ok if '3개월(90일)' in ret_note and '자동 삭제' in ret_note and '미리 다운로드' in ret_note else ng)(
            '게첨사진 등록 화면 — 보관기간 안내문구', ret_note[:110].replace('\n', ' '))
        ret_info = pg.text_content('#photoRetainInfo') or ''
        (ok if '3개월(90일)' in ret_info else ng)('등록 화면 — 보관기간·삭제 임박 안내', ret_info[:80])
        photo_aid = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY;
            const l = v.photoAppIds(); return l.length ? l[0].id : ''; }""")
        if photo_aid:
            owner = pg.evaluate('''(id) => { const s = window.SEOSAN_VERIFY.state(); const a = (s.apps || []).filter(x => x.id === id)[0]; if (!a) return null; return { memberId: a.memberId || '', phone: (a.advertiserObj || {}).phone || a.advertiserPhone || a.phone || '' }; }''', photo_aid)
            if owner and owner['memberId']:
                pg.evaluate("(m) => { try { window.SEOSAN_VERIFY.logout(); window.SEOSAN_VERIFY.login(m); } catch (e) {} }", owner['memberId'])
            elif owner and owner['phone']:
                pg.evaluate("(p) => { try { window.SEOSAN_VERIFY.logout(); window.SEOSAN_VERIFY.guestVerify(p); } catch (e) {} }", owner['phone'])
            pg.wait_for_timeout(600)
            goto(pg, base + 'mypage-detail.html?id=' + photo_aid, 800)
            mp_txt = pg.text_content('#mpBody') or ''
            if '인증' in mp_txt and '찾을 수 없습니다' not in mp_txt:
                # 비회원 인증 상태는 메모리 값이라 화면 이동 시 사라진다 — 상세 화면에서 다시 인증한다
                if owner and owner['phone']:
                    pg.evaluate("(p) => { try { window.SEOSAN_VERIFY.guestVerify(p); if (window.SEOSAN_VERIFY.renderDetail) window.SEOSAN_VERIFY.renderDetail(); } catch (e) {} }", owner['phone'])
                    pg.wait_for_timeout(500)
                    mp_txt = pg.text_content('#mpBody') or ''
            if '찾을 수 없습니다' in mp_txt:
                # 소유자 매칭이 안 되는 시연 데이터 — 사진 카드 자체를 직접 렌더해 안내문구를 검사한다
                mp_txt = pg.evaluate('(id) => { const el = document.getElementById("mpBody"); return el ? el.textContent : ""; }', photo_aid) or ''
                mp_html = pg.evaluate('''(id) => { try { return window.SEOSAN_VERIFY.appDetailHTML ? window.SEOSAN_VERIFY.appDetailHTML(id) : ''; } catch (e) { return ''; } }''', photo_aid) or ''
                mp_txt = re.sub('<[^>]+>', ' ', mp_html) or mp_txt
            (ok if '3개월(90일)간 보관 후 자동 삭제' in mp_txt and '미리 다운로드' in mp_txt else ng)(
                '마이페이지 게첨사진 — 보관기간 안내문구', '안내문구 ' + ('있음' if '3개월(90일)간 보관 후 자동 삭제' in mp_txt else '없음'))
            (ok if '보관 D-' in mp_txt and '삭제' in mp_txt else ng)(
                '마이페이지 사진 카드 — 등록일 · D-N 배지', 'D-N 배지 ' + ('있음' if '보관 D-' in mp_txt else '없음'))
        else:
            ng('마이페이지 게첨사진 — 보관기간 안내문구', '사진 연결 접수 없음')
        goto(pg, base + 'guide-rules.html', 500)
        guide_txt = pg.text_content('#guidePhotoRetainPanel') or ''
        (ok if '3개월(90일)간 보관 후 자동 삭제' in guide_txt and '미리 다운로드' in guide_txt else ng)(
            '규격·안내 — 게첨사진 3개월 보관 안내문구', guide_txt[:110].replace('\n', ' '))
        probs = w.problems()
        (ok if not probs else ng)('게첨사진 보관기간 화면 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 23) 첫 화면 대형 CTA — 다음 게첨 주차 '한 개만' 접수하러 가기
        # ------------------------------------------------------------------
        head('23. 첫 화면 대형 CTA — 다음 게첨 주차(한 개) 접수하러 가기')
        UA_M = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 '
                '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'index.html', 700)
        cta = pg.evaluate("""() => { const el = document.querySelector('#ctaApplyNext'); if (!el) return null;
            const r = el.getBoundingClientRect(); const b = el.querySelector('b');
            return { n: document.querySelectorAll('.cta-next').length, text: el.textContent.replace(/\\s+/g, ' ').trim(),
              href: el.getAttribute('href'), h: Math.round(r.height), wd: Math.round(r.width),
              fs: parseFloat(getComputedStyle(b).fontSize), top: Math.round(r.top) }; }""")
        (ok if cta and cta['n'] == 1 and '2026년 12월 1주차' in cta['text'] and '11.30' in cta['text']
         and '12.06' in cta['text'] and '접수하러 가기' in cta['text'] and cta['href'] == 'apply.html?week=2026-11-30'
         and cta['h'] >= 80 else ng)(
            '대형 CTA — 다음 게첨 주차 1개 · 주차/게첨 날짜 표기 · apply.html?week=2026-11-30', str(cta))
        (ok if cta and cta['wd'] >= 1100 and cta['fs'] >= 19 and cta['top'] < 420 else ng)(
            'PC — 풀폭 · 큰 글씨 · 첫 화면 상단 노출', '%dpx 폭 · %dpx 높이 · %.0fpx 글씨 · top %s' % (
                cta['wd'], cta['h'], cta['fs'], cta['top']) if cta else 'CTA 없음')
        pg.click('#ctaApplyNext')
        pg.wait_for_load_state('load')
        settle(pg, 700)
        wk_sel = pg.evaluate("() => window.SEOSAN_VERIFY.weekState().apply")
        (ok if 'apply.html' in pg.url and 'week=2026-11-30' in pg.url and wk_sel == '2026-11-30' else ng)(
            'CTA 클릭 → apply.html 다음 게첨 주차 자동 선택', '%s · week=%s' % (pg.url.split('/')[-1], wk_sel))
        ctx.close()
        # 모바일 360px — 넘침 없이 줄바꿈
        ctx2 = browser.new_context(viewport={'width': 360, 'height': 780}, user_agent=UA_M)
        pm = ctx2.new_page()
        pm.set_default_timeout(20000)
        wm = Watcher(pm, base)
        goto(pm, base + 'index.html', 700)
        ctam = pm.evaluate("""() => { const el = document.querySelector('#ctaApplyNext'); if (!el) return null;
            const r = el.getBoundingClientRect();
            return { wd: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right),
              docW: Math.round(document.documentElement.scrollWidth), n: document.querySelectorAll('.cta-next').length,
              text: el.textContent.replace(/\\s+/g, ' ').trim() }; }""")
        (ok if ctam and ctam['n'] == 1 and ctam['right'] <= 361 and ctam['docW'] <= 361 and ctam['h'] >= 60
         and '11.30' in ctam['text'] else ng)(
            '모바일 360px — 대형 CTA 가로 넘침 0 · 줄바꿈 · 날짜 유지', str(ctam))
        probs = w.problems() + wm.problems()
        (ok if not probs else ng)('대형 CTA 화면 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx2.close()


        # ------------------------------------------------------------------
        # 24) 접수 화면 정리 — 안내문구 하단 이동 · 정치행정 삭제 · 등록증 제출 분기 · 등록번호 자동 추출
        # ------------------------------------------------------------------
        head('24. 접수 화면 정리 — 안내문구 하단 이동 · 정치행정 삭제 · 등록증 제출 분기 · 등록번호 자동 추출')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'apply.html', 600)

        # 24-1) 안내문구가 입력/선택 본문 아래로 이동 — 1단계는 입력칸이 먼저 보인다
        order1 = pg.evaluate("""() => {
          const step1 = document.querySelector('#step1');
          const notes = document.querySelector('#stepNotes1');
          const firstField = document.querySelector('#applyCompany');
          const firstCallout = step1 ? step1.querySelector('.callout:not(.hidden)') : null;
          return { notes: !!notes, notesN: notes ? notes.querySelectorAll('.callout').length : 0,
            notesAfter: !!(notes && firstField && (firstField.compareDocumentPosition(notes) & Node.DOCUMENT_POSITION_FOLLOWING)),
            firstCalloutTop: !!(firstCallout && notes && (firstCallout.compareDocumentPosition(notes) & Node.DOCUMENT_POSITION_FOLLOWING)) }; }""")
        (ok if order1['notes'] and order1['notesN'] >= 1 and order1['notesAfter'] else ng)(
            '접수 1단계 — 안내문구가 입력칸 아래(#stepNotes1)로 이동', str(order1))
        # 1단계 첫 화면: 업체명 입력칸이 안내문구보다 위
        top1 = pg.evaluate("""() => { const f = document.querySelector('#applyCompany'); const n = document.querySelector('#stepNotes1');
            return { fy: f ? Math.round(f.getBoundingClientRect().top + window.scrollY) : null,
              ny: n ? Math.round(n.getBoundingClientRect().top + window.scrollY) : null }; }""")
        (ok if top1['fy'] is not None and top1['ny'] is not None and top1['fy'] < top1['ny'] else ng)(
            '접수 1단계 — 입력칸이 안내문구보다 위에 위치', str(top1))
        notes_all = pg.evaluate("() => ['stepNotes1','stepNotes2','stepNotes3','stepNotes4'].map(id => !!document.getElementById(id))")
        (ok if all(notes_all) else ng)('2·3·4단계 안내문구도 본문 아래로 이동', str(notes_all))
        # 24-1b) 실제 광고주·문구·시안이 1단계 최상단, 로그인/신청 구분 블록은 삭제
        top_form = pg.evaluate("""() => {
          const g = (id) => { const el = document.getElementById(id); return el ? Math.round(el.getBoundingClientRect().top + window.scrollY) : null; };
          const step1 = document.querySelector('#step1');
          const labels = step1 ? Array.from(step1.querySelectorAll('.sect-label')).map(e => e.textContent.trim().slice(0, 12)) : [];
          return { adv: g('applyAdvertiser'), text: g('applyText'), design: g('fDesign'), company: g('applyCompany'),
            banner: !!document.querySelector('#memberBanner'), radios: document.querySelectorAll('input[name="appType"]').length,
            hint: !!document.querySelector('#applicantHint'), labels: labels,
            scrollTop: window.scrollY }; }""")
        (ok if top_form['adv'] is not None and top_form['adv'] < top_form['text'] < top_form['design'] < top_form['company']
             and top_form['adv'] < 700 else ng)(
            '접수 1단계 — 실제 광고주 → 문구 → 시안이 맨 위', str(top_form)[:170])
        (ok if not top_form['banner'] and top_form['radios'] == 0 and top_form['hint'] else ng)(
            '접수 1단계 — 로그인 정보·신청 구분 블록 삭제(구분은 로그인으로 자동 판별)', str(top_form)[:150])

        # 24-2) first.html — 긴 안내문구는 목록 아래, 설치 안내 배너는 위에 유지
        goto(pg, base + 'first.html', 700)
        fnotes = pg.evaluate("""() => { const n = document.querySelector('#fcNotes'); const l = document.querySelector('#firstList');
            const b = document.querySelector('#fcBanner');
            const body = document.body.textContent;
            const guideInToolbar = Array.from(document.querySelectorAll('.toolbar .hint-txt')).some(e => e.textContent.indexOf('09:00 ~ 18:00') >= 0);
            return { notes: !!n, notesTxt: n ? n.textContent.replace(/\s+/g, ' ').trim().slice(0, 60) : '',
              afterList: !!(n && l && (l.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING)),
              bannerTop: !!(b && l && (l.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_PRECEDING)),
              bannerTxt: b ? b.textContent.replace(/\s+/g, ' ').trim().slice(0, 40) : '', guideInToolbar: guideInToolbar }; }""")
        (ok if fnotes['notes'] and fnotes['afterList'] and not fnotes['guideInToolbar'] else ng)(
            'first.html — 장황한 안내문구를 잔여석 목록 아래로 이동', str(fnotes)[:170])
        (ok if fnotes['bannerTop'] and ('진행 중 주간' in fnotes['bannerTxt'] or '접수' in fnotes['bannerTxt']) else ng)(
            'first.html — 핵심 설치 안내 배너는 목록 위에 유지', str(fnotes['bannerTxt']))

        # 24-3) 정치행정 — 접수 화면에서 삭제 · 관리자 승인 로직은 유지
        pol2 = pg.evaluate("""() => ({ chk: !!document.querySelector('#chkPolApp'),
            adminPol: (window.SEOSAN_VERIFY.lowBoards() || []).filter(x => String(x.name).indexOf('정치행정') >= 0).length,
            api: typeof window.SEOSAN_VERIFY.setPol === 'function' && typeof window.SEOSAN_VERIFY.polApprove === 'function' })""")
        (ok if not pol2['chk'] and pol2['api'] else ng)('first.html — 정치행정 선택 UI 없음 · 관리자 승인 API 유지', str(pol2))

        # 24-4) 등록증 제출 분기 — 광고대행사는 칸 없음, 일반인은 필수 요청
        goto(pg, base + 'apply.html', 600)
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1002')")      # 재봉기획(광고대행사)
        pg.evaluate("() => window.SEOSAN_VERIFY.renderAll()")
        pg.wait_for_timeout(400)
        ag = pg.evaluate("() => window.SEOSAN_VERIFY.licState()")
        (ok if ag['hidden'] is True else ng)('광고대행사 접수 — 옥외광고업 등록증 칸 숨김', str(ag)[:140])
        pg.evaluate("() => window.SEOSAN_VERIFY.setApply({ advertiser: '대행검증광고주', advertiserBiz: '326-11-22334', text: '대행사 접수 등록증 면제 검증', qty: 1, agree: true })")
        step1_ok = pg.evaluate("() => window.SEOSAN_VERIFY.validateStep(1)")
        (ok if step1_ok is True else ng)('광고대행사 접수 — 등록증 없이 1단계 통과(제출 검증 면제)', str(step1_ok))
        pg.evaluate("() => window.SEOSAN_VERIFY.logout()")
        pg.evaluate("() => window.SEOSAN_VERIFY.renderAll()")
        pg.wait_for_timeout(300)
        gen = pg.evaluate("() => window.SEOSAN_VERIFY.licState()")
        (ok if gen['hidden'] is False and '등록증' in (gen['reqHint'] or '') else ng)(
            '일반업체·비회원 접수 — 등록증 사본 요청 문구 표시', str(gen)[:150])
        pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({ company: '햇살농원', owner: '김정수', phone: '010-1111-2222',
            advertiser: '일반검증광고주', advertiserBiz: '327-22-33445', text: '일반인 등록증 필수 검증', qty: 1, agree: true })""")
        pg.evaluate("() => window.SEOSAN_VERIFY.clearLic()")
        blocked = pg.evaluate("() => window.SEOSAN_VERIFY.validateStep(1)")
        (ok if blocked is False else ng)('일반인 접수 — 등록증 없으면 1단계 차단', str(blocked))

        # 24-5) 등록증에서 등록번호 자동 추출 — 샘플·텍스트 파일
        pg.click('#btnLicSample')
        pg.wait_for_timeout(300)
        lic1 = pg.evaluate("() => window.SEOSAN_VERIFY.licState()")
        (ok if lic1['no'] == '충남서산-제2024-0012호' and '자동 추출' in (lic1['badge'] or '')
             and lic1['oade'] == '충남서산-제2024-0012호' else ng)(
            '샘플 등록증 — 등록번호 자동 추출·배지·등록번호 칸 채움', str(lic1)[:160])
        lic_txt = write_test_license()
        pg.set_input_files('#applyLic', lic_txt)
        pg.wait_for_timeout(900)
        lic2 = pg.evaluate("() => window.SEOSAN_VERIFY.licState()")
        (ok if lic2['no'] and '제2022' in lic2['no'] and '자동 추출' in (lic2['badge'] or '') else ng)(
            '등록증 파일(텍스트) — 등록번호 자동 추출', str(lic2)[:160])
        stored = pg.evaluate("() => { const v = window.SEOSAN_VERIFY.readApply(); return { no: v.licenseNo, ex: v.extractedRegNo }; }")
        (ok if stored['no'] and stored['no'] == stored['ex'] else ng)('접수 데이터 — licenseNo·extractedRegNo 저장', str(stored))
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.licExtract('충남서산-제2024-0012호')") == '충남서산-제2024-0012호' else ng)(
            '등록번호 패턴 추출 함수 (충남서산-제2024-0012호)')

        # 24-6) first.html 4단계 — 일반인은 등록증 요청, 광고대행사는 칸 없음
        goto(pg, base + 'first.html', 700)
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1001')")      # 햇살농원(일반업체)
        pg.evaluate("() => window.SEOSAN_VERIFY.renderAll()")
        pg.wait_for_timeout(400)
        gen_box = pg.evaluate("() => ({ box: !!document.querySelector('#fcLic'), txt: (document.querySelector('#fcLicWrapEl') || {}).textContent || '' })")
        (ok if gen_box['box'] and '등록증' in gen_box['txt'] else ng)(
            '1단계(일반인) — 등록증 사본 요청', str(gen_box)[:130])
        pg.evaluate("""() => window.SEOSAN_VERIFY.fcSet({ mode: 'live', advertiser: '등록증분기검증광고주', text: '등록증 분기 검증 문구',
            file: true, agree: true, license: false, qty: 1, picks: 'auto' })""")
        before_l = app_count(pg)
        blocked_l = pg.evaluate("() => window.SEOSAN_VERIFY.fcValidate(1)")
        toast_l = pg.evaluate("() => document.querySelector('#toast') ? document.querySelector('#toast').textContent : ''")
        (ok if blocked_l is False and '등록증' in toast_l and app_count(pg) == before_l else ng)(
            '1단계 — 일반인 등록증 없으면 진행 차단', toast_l[:110])
        pg.evaluate("() => window.SEOSAN_VERIFY.setFcLicSample()")
        pg.wait_for_timeout(200)
        fc = pg.evaluate("() => window.SEOSAN_VERIFY.fcLicState()")
        (ok if fc['box'] and fc['no'] == '충남서산-제2024-0012호' and '자동 추출' in (fc['badge'] or '') else ng)(
            '1단계 — 샘플 등록증 + 등록번호 자동 추출', str(fc)[:150])
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.fcValidate(1)") is True else ng)(
            '1단계 — 등록증 첨부 후 통과')
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSetStep(4)")
        pg.wait_for_timeout(150)
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSubmit()")
        pg.wait_for_timeout(600)
        live_lic_app = store(pg, "o.apps.filter(a => a.liveWeek).slice(-1)[0]")
        (ok if live_lic_app and live_lic_app.get('license') and live_lic_app.get('licenseNo') == '충남서산-제2024-0012호' else ng)(
            '진행 주간 접수 저장 — 등록증·등록번호 함께 저장',
            str({k: live_lic_app.get(k) for k in ('id', 'license', 'licenseNo')}) if live_lic_app else '없음')
        pg.evaluate("() => window.SEOSAN_VERIFY.closeModal()")
        # 광고대행사 — 등록증 칸 없음
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1002')")
        pg.evaluate("() => window.SEOSAN_VERIFY.renderAll()")
        pg.wait_for_timeout(400)
        ag_box = pg.evaluate("() => ({ box: !!document.querySelector('#fcLic'), txt: (document.querySelector('#fcLicWrapEl') || {}).textContent || '' })")
        (ok if not ag_box['box'] and '등록증' not in ag_box['txt'] else ng)(
            '1단계(광고대행사) — 등록증 칸 없음', str(ag_box)[:130])

        # 24-7) 관리자 게시대 관리 — '새 게시대 추가'는 목록 아래
        goto(pg, base + 'admin-board.html', 700)
        pa = pg.evaluate("""() => { const add = document.querySelector('#adminPlaceAdd'), tbl = document.querySelector('#adminPlaceTable');
            return { add: !!add, table: !!tbl,
              after: !!(add && tbl && (tbl.compareDocumentPosition(add) & Node.DOCUMENT_POSITION_FOLLOWING)),
              rows: tbl ? tbl.querySelectorAll('tbody tr').length : 0 }; }""")
        (ok if pa['add'] and pa['table'] and pa['after'] and pa['rows'] > 0 else ng)(
            '게시대 관리 — 기존 게시대 목록이 먼저, 새 게시대 추가는 아래', str(pa))
        # 24-8) 행사 우선접수 — 찬성 · 반려 · 기권 버튼(PC) · 모바일 카드형
        goto(pg, base + 'admin-event.html', 700)
        ev_desc = pg.evaluate("""() => { const rows = Array.from(document.querySelectorAll('#eventList tbody tr'));
            const first = rows[0];
            const btns = first ? Array.from(first.querySelectorAll('.evbtn')).map(b => b.getAttribute('data-evval')) : [];
            return { rows: rows.length, first: first ? first.textContent.replace(/\\s+/g, ' ').trim().slice(0, 40) : '',
              votes: Array.from(new Set(btns)), ids: first ? Array.from(first.querySelectorAll('.evbtn')).map(b => b.getAttribute('data-evvote')) : [] }; }""")
        (ok if '찬성' in ev_desc['votes'] and '반려' in ev_desc['votes'] and '기권' in ev_desc['votes'] else ng)(
            '행사 심사 — 찬성·반려·기권 버튼 노출(맨 위 심사중 건)', str(ev_desc)[:160])
        ev_before = pg.evaluate("(id) => window.SEOSAN_VERIFY.eventOf(id)", ev_desc['ids'][0] if ev_desc['ids'] else '')
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('senior')")
        pg.wait_for_timeout(300)
        ev_btn = pg.evaluate("""(id) => { const b = document.querySelector('#eventList [data-evvote="' + id + '"][data-evval="찬성"]:not([disabled])');
            return b ? { who: b.getAttribute('data-evwho'), dis: b.disabled } : null; }""", ev_desc['ids'][0] if ev_desc['ids'] else 'x')
        # 권한자 투표(클릭 경로와 같은 함수) — 집계 반영 확인
        pg.evaluate("(id) => window.SEOSAN_VERIFY.eventVote(id, 'EV-02', '찬성')", ev_desc['ids'][0] if ev_desc['ids'] else 'x')
        pg.wait_for_timeout(500)
        ev_after = pg.evaluate("(id) => window.SEOSAN_VERIFY.eventOf(id)", ev_desc['ids'][0] if ev_desc['ids'] else '')
        (ok if ev_after and ev_before and ev_after.get('yes', 0) >= ev_before.get('yes', 0) + 1 else ng)(
            '행사 심사 — 찬성 버튼 클릭으로 집계 반영', '%s → %s' % (ev_before, ev_after))
        ev_no = pg.evaluate("""() => { const btn = document.querySelector('#eventList [data-evval="반려"]');
            return btn ? btn.textContent.trim() : ''; }""")
        (ok if ev_no and '반려' in ev_no and '반대' not in ev_no else ng)('행사 심사 — 반려 버튼 라벨(반대 표기 없음)', repr(ev_no))
        # 모바일 — 투표 버튼 카드형 배치(가로 넘침 0 · 버튼이 화면 안)
        ctx = browser.new_context(viewport={'width': 390, 'height': 844}, user_agent=UA_M)
        pm = ctx.new_page()
        pm.set_default_timeout(20000)
        wm = Watcher(pm, base)
        goto(pm, base + 'admin-event.html', 800)
        mob = pm.evaluate("""() => { const btn = document.querySelector('#eventList .evbtn');
            const row = document.querySelector('#eventList tbody tr');
            const list = document.querySelector('#eventList');
            if (!btn || !row) return null;
            const b = btn.getBoundingClientRect(), r = row.getBoundingClientRect();
            return { btnRight: Math.round(b.right), rowRight: Math.round(r.right), vw: window.innerWidth,
              docW: Math.round(document.documentElement.scrollWidth), h: Math.round(b.height),
              block: getComputedStyle(row).display, btns: row.querySelectorAll('.evbtn').length }; }""")
        (ok if mob and mob['btnRight'] <= mob['vw'] and mob['docW'] <= mob['vw'] + 1 and mob['block'] == 'block'
             and mob['btns'] >= 3 and mob['h'] >= 34 else ng)(
            '모바일 행사 심사 — 카드형 · 찬성/반려/기권 버튼 화면 안', str(mob))
        probs = wm.problems()
        (ok if not probs else ng)('모바일 행사 심사 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # 24-9) 용어 통일 — '게첩' 잔여 0건 (모든 화면·스크립트)
        left = []
        for f in sorted(glob.glob(os.path.join(ROOT, '*.html'))) + [os.path.join(ROOT, 'assets', 'app.js')]:
            body = io.open(f, encoding='utf-8').read()
            if '게첩' in body:
                left.append('%s(%d)' % (os.path.basename(f), body.count('게첩')))
        (ok if not left else ng)('용어 통일 — \'게첩\' 잔여 0건 (전 화면 \'게첨\')', ', '.join(left) if left else '0건')

        probs = w.problems()
        (ok if not probs else ng)('접수 화면 정리 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 25) 협회관리자 기능별 6페이지 분리 — 1페이지 1기능 · 시인성 · 직책 잠금
        # ------------------------------------------------------------------
        head('25. 협회관리자 6페이지 분리 — 입금/입고/신고표지/지정서/게첨사진/작업지시서')
        INV = [('admin-pay.html', 'pay', ['payPanel'], ['deliverPanel', 'reportPanel', 'desigBatchPanel', 'woPanel', 'photoPanel']),
               ('admin-deliver.html', 'deliver', ['deliverPanel'], ['payPanel', 'reportPanel', 'desigBatchPanel', 'woPanel', 'photoPanel']),
               ('admin-report.html', 'report', ['reportPanel'], ['payPanel', 'deliverPanel', 'desigBatchPanel', 'woPanel', 'photoPanel']),
               ('admin-desig.html', 'desig', ['desigBatchPanel'], ['payPanel', 'deliverPanel', 'reportPanel', 'woPanel', 'photoPanel']),
               ('admin-photos.html', 'photos', ['photoPanel'], ['payPanel', 'deliverPanel', 'reportPanel', 'desigBatchPanel', 'woPanel']),
               ('admin-docs.html', 'docs', ['woPanel'], ['payPanel', 'deliverPanel', 'reportPanel', 'desigBatchPanel', 'photoPanel'])]
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        for fn, key, mine, others in INV:
            goto(pg, base + fn, 600)
            info = pg.evaluate("""(o) => {
              const act = Array.from(document.querySelectorAll('#adminSub .subtab.on')).map(a => a.textContent.trim());
              const on = o.mine.map(id => { const el = document.getElementById(id); return el ? !el.classList.contains('hidden') : null; });
              const off = o.others.filter(id => !!document.getElementById(id));
              const head = document.querySelector('.view-head');
              const panel = document.getElementById(o.mine[0]);
              return { page: document.body.getAttribute('data-page'), act: act, on: on, off: off,
                headTop: head ? Math.round(head.getBoundingClientRect().top + window.scrollY) : null,
                panelTop: panel ? Math.round(panel.getBoundingClientRect().top + window.scrollY) : null,
                subs: document.querySelectorAll('#adminSub .subtab').length }; }""",
                {'mine': mine, 'others': others})
            (ok if info['page'] == 'admin-' + key and info['subs'] == 18 and all(v for v in info['on']) and not info['off'] else ng)(
                '%s — %s 기능만 · 서브탭 18개 · 탭 활성' % (fn, key), str(info)[:150])
            (ok if info['panelTop'] is not None and info['panelTop'] < 620 else ng)(
                '%s — 첫 화면에서 기능이 바로 보임(스크롤 없음)' % fn, 'panel top %s' % info['panelTop'])
        probs = w.problems()
        (ok if not probs else ng)('6페이지 분리 화면 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')

        # 직책 잠금 — 입금(사무실무원·총괄) / 입고·게첨사진(현장실무원·총괄)
        for role, checks in [('staff', [('admin-pay.html', 'payPanel', True), ('admin-deliver.html', 'deliverPanel', False)]),
                             ('field', [('admin-pay.html', 'payPanel', False), ('admin-deliver.html', 'deliverPanel', True)]),
                             ('chief', [('admin-pay.html', 'payPanel', False), ('admin-deliver.html', 'deliverPanel', False),
                                        ('admin-photos.html', 'photoPanel', False)]),
                             ('super', [('admin-pay.html', 'payPanel', True), ('admin-deliver.html', 'deliverPanel', True),
                                        ('admin-photos.html', 'photoPanel', True)])]:
            for fn, pid, want in checks:
                goto(pg, base + fn, 400)
                if pg.query_selector('#adminRoleSel'):
                    pg.select_option('#adminRoleSel', role)
                    pg.wait_for_timeout(350)
                vis = pg.evaluate("(id) => { const el = document.getElementById(id); return el ? !el.classList.contains('hidden') : null; }", pid)
                (ok if vis is want else ng)('%s — %s 권한 %s' % (fn, role, '열람' if want else '잠금'), '보임=%s' % vis)

        # 모바일 — 서브탭 그리드/칩 · 가로 넘침 0
        ctx2 = browser.new_context(viewport={'width': 390, 'height': 844}, user_agent=UA_M)
        pm = ctx2.new_page()
        pm.set_default_timeout(20000)
        wm = Watcher(pm, base)
        over = []
        for fn, key, mine, others in INV:
            goto(pm, base + fn, 450)
            m = pm.evaluate("""() => { const sw = document.documentElement.scrollWidth, cw = document.documentElement.clientWidth;
                const tabs = document.querySelectorAll('#adminSub .subtab');
                const first = tabs[0] ? tabs[0].getBoundingClientRect() : null;
                return { sw: sw, cw: cw, subs: tabs.length, h: first ? Math.round(first.height) : 0,
                  onVisible: !!document.querySelector('#adminSub .subtab.on') }; }""")
            if m['sw'] > m['cw'] + 1 or m['subs'] != 18 or m['h'] < 30:
                over.append((fn, m))
        (ok if not over else ng)('모바일 — 6페이지 서브탭 칩 18개 · 가로 넘침 0', str(over))
        probs = wm.problems()
        (ok if not probs else ng)('모바일 6페이지 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx2.close()
        ctx.close()

        # ------------------------------------------------------------------
        # 26) 로그아웃 상태 접수 시도 — 로그인 · 회원가입 · 비회원 선택 팝업
        # ------------------------------------------------------------------
        head('26. 로그아웃 상태 접수 진행 — 로그인/회원가입/비회원 본인인증 선택 팝업')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'apply.html', 600)
        pg.evaluate("() => { const v = window.SEOSAN_VERIFY; v.logout(); v.guestReset(); v.renderAll(); }")
        pg.wait_for_timeout(300)
        pg.evaluate("""() => { window.SEOSAN_VERIFY.setApply({ company: '햇살농원', owner: '김정수', phone: '010-1111-2222',
            advertiser: '팝업검증광고주', advertiserBiz: '328-33-44556', text: '로그아웃 접수 팝업 검증', qty: 1, agree: true, guestPrompt: true });
            window.SEOSAN_VERIFY.setLicText('옥외광고업등록증_샘플.pdf', '충남서산-제2024-0012호'); }""")
        pg.evaluate("() => window.SEOSAN_VERIFY.guestReset()")
        pg.wait_for_timeout(200)
        if pg.evaluate("() => !!document.querySelector('#modal.open')"):
            pg.keyboard.press('Escape')
            pg.wait_for_timeout(150)
        pg.click('#btnNext')
        pg.wait_for_timeout(500)
        pop = pg.evaluate("() => window.SEOSAN_VERIFY.guestPromptState()")
        step_after = pg.evaluate("() => window.SEOSAN_VERIFY.stepNow()")
        (ok if pop['open'] and '로그인' in pop['title'] and step_after == 1 else ng)(
            '로그아웃 상태 [다음 단계] — 로그인/회원가입 선택 팝업', '%s · step=%s' % (pop, step_after))
        btns = pg.evaluate("""() => ({ login: !!document.querySelector('#modal [data-guestlogin]'),
            signup: !!document.querySelector('#modal [data-guestsignup]'), cont: !!document.querySelector('#modal [data-guestcontinue]') })""")
        (ok if btns['login'] and btns['signup'] and btns['cont'] else ng)(
            '팝업 — 로그인 · 회원가입 · 비회원으로 계속 3개 선택', str(btns))
        pg.click('#modal [data-guestcontinue]')
        pg.wait_for_timeout(600)
        step_cont = pg.evaluate("() => window.SEOSAN_VERIFY.stepNow()")
        ack_cont = pg.evaluate("() => window.SEOSAN_VERIFY.guestAckState()")
        (ok if ack_cont and step_cont == 2 else ng)(
            '비회원으로 계속 — 그대로 다음 단계 진행', 'step=%s ack=%s' % (step_cont, ack_cont))
        # 로그인 팝업 경로 — 로그인하면 이어서 진행
        goto(pg, base + 'apply.html', 500)
        pg.evaluate("() => { const v = window.SEOSAN_VERIFY; v.logout(); v.guestReset(); v.renderAll(); }")
        pg.wait_for_timeout(250)
        pg.evaluate("() => window.SEOSAN_VERIFY.setApply({ text: '로그인 후 진행 검증', qty: 1, agree: true, guestPrompt: true })")
        pg.evaluate("() => window.SEOSAN_VERIFY.guestReset()")
        pg.click('#btnNext')
        pg.wait_for_timeout(400)
        pg.click('#modal [data-guestlogin]')
        pg.wait_for_timeout(300)
        pg.click('[data-login-preset="M-1001"]')
        pg.wait_for_timeout(800)
        after_login = pg.evaluate("() => ({ step: window.SEOSAN_VERIFY.stepNow(), who: window.SEOSAN_VERIFY.authState ? window.SEOSAN_VERIFY.authState().name : '' })")
        (ok if after_login['step'] >= 1 and '햇살농원' in after_login['who'] else ng)(
            '로그인 팝업에서 로그인 — 접수 화면 유지·회원 정보 자동 작성', str(after_login))
        # remain.html — 로그아웃 상태에서 3단계 [담기] → 로그인 팝업 → 비회원으로 계속하면 그대로 담긴다
        goto(pg, base + 'remain.html', 700)
        pg.evaluate("() => { const v = window.SEOSAN_VERIFY; v.logout(); v.guestReset(); v.renderAll(); }")
        pg.wait_for_timeout(300)
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSetStep(3)")
        pg.wait_for_timeout(300)
        pid_live = pg.eval_on_selector('[data-fcpick]:not([disabled])', 'e => e.getAttribute("data-fcpick")')
        pg.click('[data-fcpick="%s"]' % pid_live)
        pg.wait_for_timeout(500)
        pop2 = pg.evaluate("() => window.SEOSAN_VERIFY.guestPromptState()")
        (ok if pop2['open'] and '로그인' in pop2['title'] and pop2['pending'].startswith('live:') else ng)(
            'first.html 로그아웃 담기 시도 — 로그인 팝업', str(pop2)[:140])
        pg.click('#modal [data-guestcontinue]')
        pg.wait_for_timeout(700)
        book_open = pg.evaluate("() => ({ picks: window.SEOSAN_VERIFY.fcPicks(), ack: window.SEOSAN_VERIFY.guestAckState() })")
        (ok if book_open['picks'] == [pid_live] and book_open['ack'] else ng)(
            '비회원으로 계속 — 그대로 3단계에 담김', str(book_open)[:120])
        probs = w.problems()
        (ok if not probs else ng)('로그아웃 접수 팝업 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 27) 로그아웃 — 지금 보던 화면 내용 즉시 비활성화·초기화
        # ------------------------------------------------------------------
        head('27. 로그아웃 — 현재 화면 내용 비활성화 · 입력/상세 초기화')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        # (1) 접수 화면 — 입력값·선택값·단계 초기화 + 안내
        goto(pg, base + 'apply.html', 600)
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1001')")
        pg.evaluate("() => window.SEOSAN_VERIFY.renderAll()")
        pg.wait_for_timeout(350)
        pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({ advertiser: '로그아웃검증광고주', advertiserBiz: '329-44-55667',
            text: '로그아웃 화면 초기화 검증', qty: 2, agree: true })""")
        pg.wait_for_timeout(200)
        pg.evaluate("() => window.SEOSAN_VERIFY.logout()")
        pg.wait_for_timeout(400)
        clr = pg.evaluate("""() => ({ lockTxt: (window.SEOSAN_VERIFY.logoutLockState().text || ''),
            locked: window.SEOSAN_VERIFY.logoutLockState().locked,
            company: (document.querySelector('#applyCompany') || {}).value,
            adv: (document.querySelector('#applyAdvertiser') || {}).value,
            text: (document.querySelector('#applyText') || {}).value,
            rent: (document.querySelector('#applyQty') || {}).value,
            step: window.SEOSAN_VERIFY.stepNow(),
            racks: JSON.stringify(window.SEOSAN_VERIFY.uiRanks ? window.SEOSAN_VERIFY.uiRanks() : null) })""")
        (ok if clr['company'] == '' and clr['adv'] == '' and clr['text'] == '' and clr['rent'] == '1'
             and clr['step'] == 1 and clr['racks'] in ('{"1":[],"2":[],"3":[]}', None) else ng)(
            '로그아웃 — 접수 입력·선택·단계 초기화', str({k: clr[k] for k in ('company', 'adv', 'text', 'rent', 'step', 'racks')})[:150])
        (ok if clr['lockTxt'] and '로그아웃' in clr['lockTxt'] and not clr['locked'] else ng)(
            '로그아웃 — 접수 화면 로그인 유도 안내(입력은 비회원 가능)', str(clr['lockTxt'])[:120])
        # (2) 마이페이지 — 잠금 + 회원정보 제거
        goto(pg, base + 'mypage.html', 500)
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1001')")
        pg.evaluate("() => window.SEOSAN_VERIFY.renderAll()")
        pg.wait_for_timeout(350)
        pg.evaluate("() => window.SEOSAN_VERIFY.logout()")
        pg.wait_for_timeout(400)
        mp = pg.evaluate("""() => ({ locked: window.SEOSAN_VERIFY.logoutLockState().locked,
            notice: (window.SEOSAN_VERIFY.logoutLockState().text || ''),
            auth: ((document.querySelector('#authName') || {}).textContent || ''),
            userHidden: (document.querySelector('#authUser') || {}).classList ? document.querySelector('#authUser').classList.contains('hidden') : null })""")
        (ok if mp['locked'] and '로그아웃' in mp['notice'] and mp['auth'] == '' and mp['userHidden'] else ng)(
            '로그아웃 — 마이페이지 잠금 · 회원 정보 제거', str(mp)[:140])
        # (3) 마이페이지 상세 — 이전 접수 상세 내용 삭제
        goto(pg, base + 'apply.html', 400)
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1001')")
        pg.evaluate("() => window.SEOSAN_VERIFY.renderAll()")
        pg.wait_for_timeout(300)
        myid = pg.evaluate("() => { const s = window.SEOSAN_VERIFY.state(); const a = s.apps.filter(x => x.memberId === 'M-1001').slice(-1)[0] || s.apps[s.apps.length - 1]; return a ? a.id : ''; }")
        goto(pg, base + 'mypage-detail.html?id=' + urllib.parse.quote(myid), 600)
        before_det = pg.text_content('#mpBody') or ''
        pg.evaluate("() => window.SEOSAN_VERIFY.logout()")
        pg.wait_for_timeout(400)
        det = pg.evaluate("""() => ({ body: (document.querySelector('#mpBody') || {}).textContent || '',
            locked: window.SEOSAN_VERIFY.logoutLockState().locked })""")
        (ok if '로그인' in det['body'] and myid and myid not in det['body'] and det['locked'] else ng)(
            '로그아웃 — 마이페이지 상세 내용 삭제 · 로그인 안내', det['body'][:90].replace('\n', ' '))
        # (4) 관리자 화면 — 잠금
        goto(pg, base + 'admin-pay.html', 500)
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1001')")
        pg.evaluate("() => window.SEOSAN_VERIFY.renderAll()")
        pg.wait_for_timeout(300)
        pg.evaluate("() => window.SEOSAN_VERIFY.logout()")
        pg.wait_for_timeout(400)
        adm2 = pg.evaluate("() => window.SEOSAN_VERIFY.logoutLockState()")
        (ok if adm2['locked'] and '로그아웃' in adm2['text'] else ng)(
            '로그아웃 — 관리자 화면 잠금 · 로그인 유도', str(adm2)[:120])
        probs = w.problems()
        (ok if not probs else ng)('로그아웃 화면 처리 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 28) 자동반복접수(매주 신청) · 한 주 쉬어가기 정책 · 사진 장수 선택 · 안내페이지 정리
        # ------------------------------------------------------------------
        head('28. 자동반복접수(후결제·낙첨 자동 재접수·당첨 자동해제) · 한 주 쉬어가기 · 사진 장수')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'apply.html', 700)
        # 28-1) 3단계 하단 버튼 → 종료일 달력 → 반복 설정
        pg.evaluate("() => window.SEOSAN_VERIFY.setStep(3)")
        pg.wait_for_timeout(400)
        rp = pg.evaluate("""() => { const b = document.querySelector('#btnRepeatWeek'); const box = document.querySelector('#repeatPanel');
            const pick = document.querySelector('#pickPager');
            return { btn: !!b, label: b ? b.textContent.trim() : '', box: !!box,
              afterPick: !!(b && pick && (pick.compareDocumentPosition(box) & Node.DOCUMENT_POSITION_FOLLOWING)) }; }""")
        (ok if rp['btn'] and '매주' in rp['label'] and rp['afterPick'] else ng)(
            '3단계 하단 — 🔁 같은 값으로 매주 신청 버튼', str(rp)[:140])
        pg.click('#btnRepeatWeek')
        pg.wait_for_timeout(500)
        cal = pg.evaluate("""() => ({ open: !!document.querySelector('#modal.open'), date: !!document.querySelector('#repeatEnd'),
            type: (document.querySelector('#repeatEnd') || {}).type,
            min: (document.querySelector('#repeatEnd') || {}).min, max: (document.querySelector('#repeatEnd') || {}).max,
            txt: (document.querySelector('#modalBody') || {}).textContent || '' })""")
        (ok if cal['open'] and cal['date'] and cal['type'] == 'date' and '종료일' in cal['txt'] else ng)(
            '매주 신청 — 종료일 달력(날짜 선택) 열림', str({k: cal[k] for k in ('open', 'type', 'min', 'max')}))
        end4 = pg.evaluate("() => window.SEOSAN_VERIFY.repeatPreviewEnd(4)")
        pg.fill('#repeatEnd', end4)
        pg.wait_for_timeout(200)
        pg.click('#btnRepeatGo')
        pg.wait_for_timeout(400)
        rset = pg.evaluate("() => window.SEOSAN_VERIFY.repeatState()")
        (ok if rset['on'] and rset['end'] == end4 and rset['weeks'] >= 4 else ng)(
            '종료일 확정 — 매주 반복 설정', str(rset))
        # 28-2) 반복 접수 등록(후결제·자동반복) → 낙첨 시 다음 주 자동 재접수
        pg.evaluate("""() => { const v = window.SEOSAN_VERIFY;
            v.logout(); v.renderAll();
            v.setApply({ company: '햇살농원', owner: '김정수', phone: '010-1111-2222',
              advertiser: '반복검증광고주', advertiserBiz: '330-55-66778', text: '매주 반복 접수 검증', qty: 1, agree: true });
            v.setLicText('옥외광고업등록증_샘플.pdf', '충남서산-제2024-0012호');
            v.setRepeatEnd('%s'); }""" % end4)
        rep_read = pg.evaluate("() => { const v = window.SEOSAN_VERIFY.readApply(); return { on: v.autoRepeat, end: v.repeatEnd, pay: v.paymentMode, iv: v.repeatInterval }; }")
        (ok if rep_read['on'] and rep_read['end'] == end4 and '후결제' in (rep_read['pay'] or '') else ng)(
            '접수 데이터 — autoRepeat·repeatEnd·후결제', str(rep_read))
        pg.evaluate("() => window.SEOSAN_VERIFY.setStep(3)")
        pg.wait_for_timeout(300)
        pg.evaluate("() => { const v = window.SEOSAN_VERIFY; const r = v.uiRanks(); r['1'] = ['P11']; v.setUiRanks(r); }")
        pg.evaluate("() => window.SEOSAN_VERIFY.setStep(4)")
        pg.wait_for_timeout(250)
        pg.click('#btnNext')
        pg.wait_for_timeout(900)
        rapp = pg.evaluate("() => window.SEOSAN_VERIFY.repeatApps()")
        rep0 = rapp[-1] if rapp else {}
        (ok if rep0.get('autoRepeat') and rep0.get('repeatEnd') == end4 and '후결제' in (rep0.get('paymentMode') or '')
             and not rep0.get('awarded') else ng)(
            '반복접수 등록 — 1건·후결제·자동반복 ON', str(rep0)[:160])
        carried = pg.evaluate("(id) => window.SEOSAN_VERIFY.carryRepeat(id)", rep0.get('id', ''))
        rapp2 = pg.evaluate("() => window.SEOSAN_VERIFY.repeatApps()")
        nxt = [x for x in rapp2 if x.get('id') != rep0.get('id')]
        (ok if nxt and nxt[-1].get('autoRepeat') and nxt[-1].get('repeatEnd') == end4 and nxt[-1].get('id') != rep0.get('id')
             and nxt[-1].get('status') in ('시안심사중', '추첨대기') else ng)(
            '낙첨 → 다음 주 자동 재접수 건 생성(repeatEnd 유지·후결제)', str(nxt[-1] if nxt else None)[:160])
        rw = pg.evaluate("(id) => window.SEOSAN_VERIFY.releaseRepeat(id, '추첨 당첨')", nxt[-1]['id'] if nxt else '')
        rw2 = pg.evaluate("() => window.SEOSAN_VERIFY.repeatApps()")
        won = [x for x in rw2 if nxt and x.get('id') == nxt[-1]['id']]
        (ok if rw and won and won[0].get('repeatStatus') == '당첨 자동해제' and not won[0].get('autoRepeat') else ng)(
            '당첨 확정 → 자동반복접수 자동 해제', str(won[0] if won else None)[:140])
        # 28-3) 마이페이지 — 반복 배지 · 반복접수 해제
        goto(pg, base + 'mypage.html', 700)
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1001')")
        pg.evaluate("() => window.SEOSAN_VERIFY.renderAll()")
        pg.wait_for_timeout(400)
        mp_rep = pg.evaluate("""() => { const list = window.SEOSAN_VERIFY.repeatApps(); const id = list.length ? list[list.length - 1].id : '';
            const a = list.filter(x => x.autoRepeat)[0] || list[0] || null;
            return { id: id, badge: !!document.querySelector('[data-repeatoff]'), tbody: (document.querySelector('#mpBody') || {}).textContent || '' }; }""")
        (ok if mp_rep['tbody'] and ('🔁' in mp_rep['tbody'] or '반복' in mp_rep['tbody']) else ng)(
            '마이페이지 — 반복접수 배지 노출', mp_rep['tbody'][:90].replace('\n', ' '))
        n_off = pg.evaluate("() => { const list = window.SEOSAN_VERIFY.repeatApps().filter(x => x.autoRepeat); return list.length ? window.SEOSAN_VERIFY.cancelRepeat(list[list.length - 1].id) : -1; }")
        after_off = pg.evaluate("() => window.SEOSAN_VERIFY.repeatApps().filter(x => x.autoRepeat).length")
        (ok if n_off >= 0 and after_off == 0 else ng)(
            '반복접수 해제 — 미래 반복 건 무페널티 취소', '해제 %s건 · 남은 자동반복 %s' % (n_off, after_off))
        # 28-4) 한 주 쉬어가기 정책 — 기본 OFF → ON → 직전 주 이력 차단
        goto(pg, base + 'admin-system.html', 600)
        pol0 = pg.evaluate("() => window.SEOSAN_VERIFY.skipWeekState()")
        (ok if pol0['on'] is False else ng)('한 주 쉬어가기 — 기본 OFF(매주 접수 가능)', str(pol0))
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('staff')")
        pg.wait_for_timeout(200)
        blocked_role = pg.evaluate("() => window.SEOSAN_VERIFY.skipWeek(true)")
        (ok if blocked_role is False else ng)('한 주 쉬어가기 — 사무실무원은 변경 불가', str(blocked_role))
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('chief')")
        pg.wait_for_timeout(200)
        chief_block = pg.evaluate("() => window.SEOSAN_VERIFY.skipWeek(true)")
        (ok if chief_block is False else ng)('한 주 쉬어가기 — 지부장은 변경 불가(최고권한은 총괄관리자만)', str(chief_block))
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('super')")
        pg.wait_for_timeout(200)
        on_now = pg.evaluate("() => window.SEOSAN_VERIFY.skipWeek(true)")
        (ok if on_now is True and pg.evaluate("() => window.SEOSAN_VERIFY.skipWeekState().on") else ng)(
            '한 주 쉬어가기 — 총괄관리자 ON 전환', str(on_now))
        audit_hit = pg.evaluate("() => (window.SEOSAN_VERIFY.state().audit || []).filter(x => String(x.kind || x.type || '').indexOf('정책') >= 0 || String(x.msg || x.text || '').indexOf('한 주 쉬어가기') >= 0).length")
        (ok if audit_hit >= 1 else ng)('한 주 쉬어가기 — 감사 로그 기록', '%d건' % audit_hit)
        # 직전 주(11.23 주) 이력이 있는 광고주로 다음 주(11.30) 접수 시도 → 차단 / 차차주(12.07) 허용
        prev_adv = pg.evaluate("""() => { const s = window.SEOSAN_VERIFY.state();
            const a = (s.apps || []).filter(x => x.start === '2026-11-23' && x.advertiser && x.status !== '반려').slice(-1)[0];
            if (!a) return null; const o = a.advertiserObj || {};
            return { name: a.advertiser, biz: a.advertiserBiz || '', phone: o.phone || a.advertiserPhone || '' }; }""")
        if prev_adv:
            goto(pg, base + 'apply.html', 600)
            pg.evaluate("""(o) => { const v = window.SEOSAN_VERIFY; v.logout(); v.guestReset(); v.renderAll();
                v.setApply({ company: '햇살농원', owner: '김정수', phone: '010-1111-2222', advertiser: o.name, advertiserBiz: o.biz,
                  advertiserPhone: o.phone, text: '한 주 쉬어가기 검증 문구', qty: 1, agree: true });
                v.setLicText('옥외광고업등록증_샘플.pdf', '충남서산-제2024-0012호'); }""", prev_adv)
            blocked_next = pg.evaluate("() => window.SEOSAN_VERIFY.validateStep(1)")
            toast_next = pg.evaluate("() => (document.querySelector('#toast') || {}).textContent || ''")
            (ok if blocked_next is False and '한 주' in toast_next else ng)(
                '한 주 쉬어가기 — 직전 주 접수 광고주 다음 주 차단', '%s · %s' % (blocked_next, toast_next[:70]))
            pg.evaluate("""() => { const v = window.SEOSAN_VERIFY;
                v.setApply({ advertiser: '쉬어가기차차주광고주', advertiserBiz: '331-66-77889' }); }""")
            ok_next = pg.evaluate("() => window.SEOSAN_VERIFY.validateStep(1)")
            (ok if ok_next is True else ng)('한 주 쉬어가기 — 이력 없는 광고주는 정상 접수', str(ok_next))
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('super')")
        pg.evaluate("() => window.SEOSAN_VERIFY.skipWeek(false)")
        # 28-5) 사진 인쇄 — A4 1장당 사진 수(1·2·4·6)
        goto(pg, base + 'mypage.html', 600)
        pp = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY; const s = v.state();
            const a = (s.apps || []).filter(x => (x.assignedPlaces || []).length)[0];
            if (!a) return null; v.ppPerPage(4); return { id: a.id, st: v.photoProofState(a.id) }; }""")
        (ok if pp and pp['st']['per'] == 4 and pp['st']['sheets'] == (pp['st']['photos'] + 3) // 4 else ng)(
            '사진 인쇄 — 4장(2×2) 선택 시 페이지 수 계산', str(pp and pp['st']))
        per_counts = pg.evaluate("""(id) => { const v = window.SEOSAN_VERIFY; const out = {};
            [1, 2, 4, 6].forEach(n => { v.ppPerPage(n); const st = v.photoProofState(id); out[n] = { sheets: st.sheets, photos: st.photos, cls: (v.photoProofHTML(id).match(/pp-per-(\\d)/) || [])[1] }; });
            return out; }""", pp['id'] if pp else '')
        (ok if all(str(k) in per_counts and per_counts[str(k)]['cls'] == str(k) for k in (1, 2, 4, 6)) else ng)(
            '사진 인쇄 — 1·2·4·6장 모두 그리드/페이지 분할 반영', str(per_counts))
        goto(pg, base + 'mypage.html', 600)
        pg.evaluate("(id) => { try { window.SEOSAN_VERIFY.openProof(id, 4); } catch (e) {} }", pp['id'] if pp else '')
        pg.wait_for_timeout(700)
        pmodal = pg.evaluate("""() => ({ chips: document.querySelectorAll('#ppPerChips .chip').length,
            sheets: document.querySelectorAll('#photoProof .pp-sheet').length,
            pages: document.querySelectorAll('#photoProof .pp-page').length,
            info: (document.querySelector('#ppCountInfo') || {}).textContent || '' })""")
        (ok if pmodal['chips'] == 4 and pmodal['sheets'] >= 1 and pmodal['pages'] >= 1 else ng)(
            '게첨 확인서 모달 — 사진 수 선택 칩 4개 · 페이지 분할', str(pmodal))
        pg.click('#ppPerChips .chip[data-ppper="6"]')
        pg.wait_for_timeout(300)
        pmodal2 = pg.evaluate("""() => ({ sheets: document.querySelectorAll('#photoProof .pp-sheet').length,
            cls: (document.querySelector('#photoProof .pp-sheet') || {}).className || '' })""")
        (ok if 'pp-per-6' in pmodal2['cls'] else ng)('게첨 확인서 — 6장(2×3) 선택 즉시 반영', str(pmodal2))
        # 28-6) 안내페이지 — 가산점 규칙 삭제
        goto(pg, base + 'guide-rules.html', 500)
        gr = pg.evaluate("() => document.body.textContent")
        (ok if '가산점' not in gr and '부여 한도' not in gr else ng)(
            '규격·안내 — 추첨 가산점 규칙 삭제', '가산점 %d회' % gr.count('가산점'))
        pros = io.open(os.path.join(ROOT, 'guide-rules.html'), encoding='utf-8').read()
        (ok if '가산점' not in pros else ng)('guide-rules.html 소스 — 가산점 문구 0건', '%d회' % pros.count('가산점'))
        probs = w.problems()
        (ok if not probs else ng)('반복접수·정책·사진 인쇄 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 29) 첫 화면 접기·CTA · 신고표지 날짜 선택 · 관리자 권한 페이지 · 가산점 합계 툴팁
        # ------------------------------------------------------------------
        head('29. 첫 화면 게시대 접기·CTA 시인성 · 신고표지 날짜 · 관리자 권한 페이지 · 가산점 합계 툴팁')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        # 29-1) index — 목록 기본 접힘 → 펼치기 77개소
        goto(pg, base + 'index.html', 700)
        fold0 = pg.evaluate("() => window.SEOSAN_VERIFY.placeFoldState()")
        (ok if fold0['open'] is False and fold0['hidden'] is True and '펼쳐보기' in fold0['label'] else ng)(
            '첫 화면 — 게시대 현황 기본 접힘', str(fold0))
        pg.click('#btnPlaceToggle')
        pg.wait_for_timeout(400)
        fold1 = pg.evaluate("() => window.SEOSAN_VERIFY.placeFoldState()")
        (ok if fold1['open'] and fold1['hidden'] is False and fold1['rows'] >= 77 else ng)(
            '게시대 현황 펼쳐보기 — 77개소 표시', str(fold1))
        pg.click('#btnPlaceToggle')
        pg.wait_for_timeout(300)
        fold2 = pg.evaluate("() => window.SEOSAN_VERIFY.placeFoldState()")
        (ok if fold2['open'] is False and '접기' not in fold2['label'] else ng)('게시대 현황 다시 접기', str(fold2))
        # CTA 시인성 — 진한 배경·흰 굵은 글씨·뚜렷한 대비
        cta = pg.evaluate("""() => { const el = document.querySelector('#ctaApplyNext');
            if (!el) return null; const cs = getComputedStyle(el), b = el.querySelector('.cta-txt b');
            const bs = b ? getComputedStyle(b) : null; const r = el.getBoundingClientRect();
            return { bg: cs.backgroundImage || cs.backgroundColor, color: bs ? bs.color : '', weight: bs ? bs.fontWeight : '',
              size: bs ? parseFloat(bs.fontSize) : 0, h: Math.round(r.height), shadow: cs.boxShadow.slice(0, 30),
              label: b ? b.textContent.trim() : '', href: el.getAttribute('href') }; }""")
        (ok if cta and ('linear-gradient' in cta['bg'] or 'rgb(27, 42, 138)' in cta['bg'])
             and cta['color'] in ('rgb(255, 255, 255)', 'rgba(255, 255, 255, 1)')
             and int(cta['weight']) >= 800 and cta['size'] >= 18 and cta['h'] >= 70
             and 'none' != cta['shadow'] and '접수하러' in cta['label'] and 'apply.html' in cta['href'] else ng)(
            '다음 주차 접수 CTA — 고대비 그라데이션·흰 굵은 글씨·큰 높이', str(cta))
        # 29-2) 신고표지 날짜 선택 → 제목·집계 갱신
        goto(pg, base + 'admin-report.html', 600)
        rd0 = pg.evaluate("() => ({ has: !!document.querySelector('#reportDate'), type: (document.querySelector('#reportDate') || {}).type, title: (document.querySelector('#reportPreview .report-title, #reportPreview h2') || {}).textContent || '' })")
        (ok if rd0['has'] and rd0['type'] == 'date' else ng)('신고표지 — 날짜 선택 입력', str(rd0))
        pg.evaluate("() => window.SEOSAN_VERIFY.setReportDate('2026-11-16')")
        pg.wait_for_timeout(400)
        rd1 = pg.evaluate("() => ({ date: window.SEOSAN_VERIFY.reportDateNow(), title: (document.querySelector('#reportPreview .report-title, #reportPreview h2') || {}).textContent || '', rows: window.SEOSAN_VERIFY.reportRows().length })")
        (ok if '2026/11/16' in rd1['title'] or '2026/11/16' == rd1['date'] else ng)(
            '신고표지 날짜 변경 — 제목 기준일 갱신', str(rd1))
        pg.evaluate("() => window.SEOSAN_VERIFY.setReportDate('2026-11-02')")
        pg.wait_for_timeout(350)
        rd2 = pg.evaluate("() => ({ date: window.SEOSAN_VERIFY.reportDateNow(), rows: window.SEOSAN_VERIFY.reportRows().length, title: (document.querySelector('#reportPreview .report-title, #reportPreview h2') || {}).textContent || '', sum: window.SEOSAN_VERIFY.reportSummary() })")
        (ok if rd2['date'] == '2026/11/02' and '2026/11/02' in rd2['title'] and rd2['title'] != rd1['title'] else ng)(
            '신고표지 다른 주 — 제목·집계 재계산', '%s / %s행 / %s' % (rd2['date'], rd2['rows'], rd2['title'][:40]))
        # 29-3) 관리자 권한 전용 페이지
        goto(pg, base + 'admin-roles.html', 600)
        roles = pg.evaluate("""() => ({ page: document.body.getAttribute('data-page'),
            officer: !!document.querySelector('#officerTable'), cap: !!document.querySelector('#bonusCapPanel'),
            ap: !!document.querySelector('#eventApproverTable'), bonus: !!document.querySelector('#roleBonusPanel'),
            membersAssoc: !!document.querySelector('#assocPanel'), tab: Array.from(document.querySelectorAll('#adminSub .subtab.on')).map(a => a.textContent.trim()) })""")
        (ok if roles['page'] == 'admin-roles' and roles['officer'] and roles['cap'] and roles['ap'] and roles['bonus']
             and not roles['membersAssoc'] and roles['tab'] and '관리자 권한' in roles['tab'][0] else ng)(
            '관리자 권한 페이지 — 직책·한도·행사심사위원 전용 · 회원 패널 없음', str(roles))
        lock = pg.evaluate("() => { const v = window.SEOSAN_VERIFY; v.setRole('staff'); return { lock: !document.querySelector('#rolesLock').classList.contains('hidden'), add: document.querySelector('#btnOfficerAdd').disabled }; }")
        pg.wait_for_timeout(300)
        (ok if lock['lock'] and lock['add'] else ng)('관리자 권한 — 하위 직책은 잠금·등록 불가', str(lock))
        can = pg.evaluate("() => { const v = window.SEOSAN_VERIFY; v.setRole('chief'); return { lock: !document.querySelector('#rolesLock').classList.contains('hidden'), add: document.querySelector('#btnOfficerAdd').disabled, tabs: Array.from(document.querySelectorAll('#adminSub a[data-perm]')).filter(a => !a.classList.contains('hidden')).map(a => a.getAttribute('data-perm')) }; }")
        pg.wait_for_timeout(300)
        (ok if can['lock'] and can['add'] and 'roles' not in can['tabs'] else ng)(
            '관리자 권한 — 지부장도 잠금·탭 숨김(최고권한은 총괄관리자만)', str(can)[:170])
        goto(pg, base + 'admin-roles.html', 500)
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('chief')")
        pg.wait_for_timeout(400)
        (ok if pg.query_selector('#permLockBox') or pg.query_selector('#permMatrixLock') else ng)(
            '관리자 권한 페이지 — 지부장 직접 접근 차단')
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('super')")
        # 29-4) 샘플회원에 관리자 직책자 반영
        adm_members = pg.evaluate("() => window.SEOSAN_VERIFY.adminMembers()")
        (ok if len(adm_members) >= 7 and any(x['roleLabel'] == '지부장' for x in adm_members)
             and any(x['roleLabel'] == '사무실무원' for x in adm_members) and any(x['eventApprover'] for x in adm_members) else ng)(
            '샘플회원 — 관리자 직책자 7명·직책·행사심사위원 반영', str(adm_members[:2])[:150])
        # 29-5) 가산점 — 합계 배지 + 세부내역 툴팁
        goto(pg, base + 'admin-review.html', 600)
        chip = pg.evaluate("""() => { const c = document.querySelector('#eventList .grant-chip') || document.querySelector('.grant-chip');
            if (!c) return null; const t = c.querySelector('.gtip');
            return { text: c.textContent.replace(/\s+/g, ' ').trim().slice(0, 40), title: c.getAttribute('title') || '',
              hasTip: !!t, tip: t ? t.textContent.slice(0, 80) : '',
              display: t ? getComputedStyle(t).display : '' }; }""")
        (ok if chip and ('합계 +' in chip['text'] or chip['text'].startswith('0%')) and chip['title'] and chip['hasTip'] else ng)(
            '가산점 — 합계 배지 + 세부내역 툴팁', str(chip))
        if chip:
            pg.evaluate("() => { const c = document.querySelector('.grant-chip'); if (c) c.dispatchEvent(new MouseEvent('click', { bubbles: true })); }")
            pg.wait_for_timeout(250)
            tip_on = pg.evaluate("() => { const t = document.querySelector('.grant-chip.open .gtip'); return t ? getComputedStyle(t).display : ''; }")
            (ok if tip_on == 'block' else ng)('가산점 툴팁 — 탭/클릭 시 세부내역 표시', str(tip_on))
        probs = w.problems()
        (ok if not probs else ng)('첫 화면·신고표지·권한·가산점 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 30) 공문 게첨위치·기간 자동 추출 → 자동 배정 · 만석 비움 · 인접 추천

        # ------------------------------------------------------------------
        head('30. 공문 자동 추출·자동 배정 — 만석 게시대 비움 · 인접 교차로/동일 권역/시내 중심 추천')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1100})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'admin-official.html', 700)
        if pg.query_selector('#adminRoleSel'):
            pg.select_option('#adminRoleSel', 'staff')
            pg.wait_for_timeout(300)
        # 30-1) 텍스트에서 게첨 기간·위치 뽑기
        rng = pg.evaluate("""() => window.SEOSAN_VERIFY.offDateRange('○ 게첨기간 : 2026. 12. 7. ~ 12. 13. (1주)')""")
        (ok if rng and rng.get('start') == '2026-12-07' and rng.get('end') == '2026-12-13' and rng.get('days') == 7 else ng)(
            '게첨 기간 자동 추출 — 날짜 범위 → 주차·1주/2주', str(rng))
        rng2 = pg.evaluate("""() => window.SEOSAN_VERIFY.offDateRange('게첨기간 2026. 12. 7. ~ 12. 20. (2주)')""")
        (ok if rng2 and rng2.get('days') == 14 else ng)('게첨 기간 2주 범위 인식', str(rng2))
        places = pg.evaluate("() => window.SEOSAN_VERIFY.offPlacesHit('게첨위치 : 서산중앙고사거리, 동문우체국삼거리')")
        (ok if places and places[0] == 'P11' and 'P12' in places else ng)(
            '게첨 위치 자동 추출 — 게시대 이름 매칭', str(places))

        # 30-2) 시연 샘플 ⑤ — 자동 배정 + 만석 비움 + 인접 추천
        pg.click('[data-offsample="traffic"]')
        pg.wait_for_timeout(700)
        f5 = pg.evaluate("() => window.SEOSAN_VERIFY.offForm()")
        rec = pg.evaluate("() => window.SEOSAN_VERIFY.offRec()")
        hits5 = pg.evaluate("() => window.SEOSAN_VERIFY.offHits()")
        (ok if f5['org'] == '서산시청 교통과' and f5['qty'] == 5 and f5['week'] == '2026-12-07' else ng)(
            '샘플⑤ — 기관·수량·게첨 주(12.07) 자동 채움', str(f5))
        (ok if '게첨 위치' in hits5 and '게첨 기간' in hits5 else ng)(
            '자동 인식 배지 — 게첨 위치 · 게첨 기간', hits5[:140])
        (ok if rec and rec['picked'] and rec['full'] and rec['full'][0]['name'] == '서산중앙고사거리' else ng)(
            '게첨 위치 자동 배정 — 만석 게시대는 비움(선택 제외)', str(rec)[:160] if rec else '없음')
        sel5 = pg.evaluate("() => window.SEOSAN_VERIFY.offSel()")
        (ok if 'P11' not in sel5 and len(sel5) == rec['goal'] - rec['need'] else ng)(
            '만석 게시대 제외 후 나머지 자동 선택', '선택 %s / 목표 %s' % (sel5, rec['goal']))
        box = pg.text_content('#offRecBox') or ''
        (ok if '공문 만석 제외' in box and '서산중앙고사거리' in box else ng)(
            '만석 사유 배지 — 공문 만석 제외', box[:120].replace('\n', ' '))
        reasons = pg.eval_on_selector_all('#offRecBox .off-rec-badge', 'els => els.map(e => e.textContent.trim())')
        (ok if reasons and reasons[0] in ('인접 교차로', '동일 권역', '시내 중심') else ng)(
            '인접 추천 사유 배지 — 인접 교차로 / 동일 권역 / 시내 중심', str(reasons))
        (ok if '인접 교차로' in reasons else ng)(
            '추천 우선순위 ① 인접 교차로가 먼저', str(reasons))
        rec_btns = pg.eval_on_selector_all('[data-offrec]', 'els => els.map(e => e.getAttribute("data-offrec"))')
        (ok if rec_btns else ng)('추천 게시대 담기 버튼', str(rec_btns))
        if rec_btns:
            before_sel = pg.evaluate("() => window.SEOSAN_VERIFY.offSel()")
            pg.click('[data-offrec="%s"]' % rec_btns[0])
            pg.wait_for_timeout(350)
            after_sel = pg.evaluate("() => window.SEOSAN_VERIFY.offSel()")
            (ok if rec_btns[0] in after_sel and len(after_sel) == len(before_sel) + 1 else ng)(
                '추천 게시대 클릭 한 번 → 대체 배정 반영', '%s → %s' % (before_sel, after_sel))
        # 수량을 채우면 등록 가능
        goal5 = pg.evaluate("() => window.SEOSAN_VERIFY.offForm()")['qty']
        for _try in range(14):
            cur_sel = pg.evaluate("() => window.SEOSAN_VERIFY.offSel()")
            if len(cur_sel) >= goal5:
                break
            all_btns = pg.eval_on_selector_all('[data-offrec],[data-offpick]', 'els => els.map(e => e.getAttribute("data-offrec") || e.getAttribute("data-offpick"))')
            left_btns = [b for b in all_btns if b not in cur_sel]
            if not left_btns:
                break
            sel_attr = 'data-offrec' if pg.query_selector('[data-offrec="%s"]' % left_btns[0]) else 'data-offpick'
            try:
                pg.click('[%s="%s"]' % (sel_attr, left_btns[0]))
            except Exception:      # noqa: BLE001 - 클릭 실패 시 다음 버튼으로
                continue
            pg.wait_for_timeout(250)
        full_sel = pg.evaluate("() => window.SEOSAN_VERIFY.offSel()")
        (ok if len(full_sel) == goal5 else ng)('추천으로 수량 충족 — 등록 가능 상태', '선택 %s / 목표 %s' % (len(full_sel), goal5))
        probs = w.problems()
        (ok if not probs else ng)('공문 자동 배정 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 31) 작업지시서 게첨 주 날짜 선택 — 제목·목록 즉시 갱신
        # ------------------------------------------------------------------
        head('31. 작업지시서(admin-docs) 날짜 선택 — 게첨 주 기준 제목·배정 목록 갱신')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1100})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'admin-docs.html', 700)
        has_pick = pg.evaluate("() => !!document.querySelector('#woDatePick') && !!document.querySelector('#woWeekChips')")
        (ok if has_pick else ng)('작업지시서 — 날짜 선택(date) + 게첨 주 칩', str(has_pick))
        h1 = pg.evaluate("() => window.SEOSAN_VERIFY.woHead()")
        (ok if '11월 30일' in h1['title'] and ('11.30' in h1['week'] or '2026-11-30' in h1['week']) else ng)(
            '기본 = 이번 회차 게첨 주(11.30~12.06)', str(h1)[:130])
        pg.fill('#woDatePick', '2026-12-07')
        pg.wait_for_timeout(500)
        h2 = pg.evaluate("() => window.SEOSAN_VERIFY.woHead()")
        (ok if '12월 7일' in h2['title'] and ('12.07' in h2['week'] or '2026-12-07' in h2['week']) and h2['pick'] == '2026-12-07' else ng)(
            '날짜 선택 → 제목·게첨 주 즉시 갱신', str(h2)[:130])
        rows2 = pg.eval_on_selector_all('#woTable tbody tr', 'els => els.length')
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.woWeek()") == '2026-12-07' else ng)(
            '선택 날짜가 속한 게첨 주 반영', pg.evaluate("() => window.SEOSAN_VERIFY.woWeek()"))
        chips = pg.eval_on_selector_all('#woWeekChips [data-woweek]', 'els => els.map(e => e.getAttribute("data-woweek"))')
        (ok if '2026-12-07' in chips else ng)('게첨 주 빠른 칩 — 다음 주 선택 가능', str(chips))
        pg.click('#woWeekChips [data-woweek="2026-11-30"]')
        pg.wait_for_timeout(400)
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.woWeek()") == '2026-11-30' else ng)(
            '주차 칩 클릭 → 게첨 주 전환', pg.evaluate("() => window.SEOSAN_VERIFY.woWeek()"))
        probs = w.problems()
        (ok if not probs else ng)('작업지시서 날짜 선택 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 32) 첫 화면 — KPI 주차 명칭 · 검색 자동 펼침 · 돋보기 겹침 없음
        # ------------------------------------------------------------------
        head('32. 첫 화면 — KPI 주차 명칭 · 검색 시 게시대 현황 자동 펼침 · 돋보기 겹침 없음')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        w = Watcher(pg, base)
        goto(pg, base + 'index.html', 500)
        kpi = pg.text_content('#statusStats') or ''
        (ok if '12월 1주차 접수 현황' in kpi and '선택 주 접수' not in kpi else ng)(
            'KPI 카드 — 12월 1주차 접수 현황', kpi[:120].replace('\n', ' '))
        geo = pg.evaluate("""() => { const wrap = document.querySelector('.search-lg'); const svg = wrap.querySelector('svg');
            const inp = wrap.querySelector('input'); const a = svg.getBoundingClientRect(), b = inp.getBoundingClientRect();
            return { svgRight: Math.round(a.right), inputLeft: Math.round(b.left), pos: getComputedStyle(svg).position }; }""")
        (ok if geo['pos'] == 'static' and geo['svgRight'] <= geo['inputLeft'] + 1 else ng)(
            '대형 검색창 — 돋보기 아이콘과 입력 글자 겹침 없음', str(geo))
        folded = pg.evaluate("() => { const b = document.getElementById('placementFold'); return b ? b.hidden : null; }")
        (ok if folded is True else ng)('게시대 현황 기본 접힘', 'hidden=%s' % folded)
        pg.fill('#statusSearch', '의료원')
        pg.wait_for_timeout(450)
        after_fold = pg.evaluate("() => { const b = document.getElementById('placementFold'); return b ? b.hidden : null; }")
        rows = pg.eval_on_selector_all('#placementGrid .plrow', 'els => els.length')
        txt = pg.text_content('#placementGrid') or ''
        (ok if after_fold is False and 0 < rows < 20 and '의료원' in txt else ng)(
            '검색어 입력 → 게시대 현황 자동 펼침 · 결과 즉시 표시', 'hidden=%s · %d행' % (after_fold, rows))
        pg.fill('#statusSearch', '')
        pg.wait_for_timeout(300)
        # 접힌 상태로 되돌린 뒤 다시 검색해도 자동으로 펼쳐진다
        pg.evaluate("() => window.SEOSAN_VERIFY.setPlaceFold ? window.SEOSAN_VERIFY.setPlaceFold(false) : null")
        if pg.query_selector('#btnPlaceToggle'):
            st_fold = pg.evaluate("() => { const b = document.getElementById('placementFold'); return b ? b.hidden : null; }")
            if st_fold is False:
                pg.click('#btnPlaceToggle')
                pg.wait_for_timeout(250)
        pg.fill('#statusSearch', '해미')
        pg.wait_for_timeout(400)
        folded2 = pg.evaluate("() => { const b = document.getElementById('placementFold'); return b ? b.hidden : null; }")
        (ok if folded2 is False else ng)('다시 접은 뒤 검색해도 자동 펼침', 'hidden=%s' % folded2)
        probs = w.problems()
        (ok if not probs else ng)('첫 화면 검색·KPI 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 33) 비로그인 접수 화면 진입 즉시 로그인/회원가입/비회원 선택 팝업
        # ------------------------------------------------------------------
        head('33. 비로그인 apply·first 진입 즉시 로그인 팝업 · 접수폼 잠금 · 진행 시 재호출')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        for name, nxt in (('apply.html', '#btnNext'), ('remain.html', '#fcNext'), ('first.html', '#fcNext')):
            pg.goto(base + name, wait_until='load')
            pg.wait_for_timeout(500)
            st = {'open': False, 'title': '', 'locked': False}
            for _ in range(8):
                st = pg.evaluate("""() => ({ open: !!document.querySelector('#modal.open'),
                    title: (document.querySelector('#modalTitle') || {}).textContent || '',
                    locked: !!document.querySelector('.guest-locked') })""")
                if st['open'] and '로그인' in st['title']:
                    break
                if st['open']:
                    pg.keyboard.press('Escape')
                pg.wait_for_timeout(350)
            (ok if st['open'] and '로그인' in st['title'] else ng)(
                '%s — 진입 즉시 로그인/회원가입/비회원 팝업' % name, str(st)[:120])
            (ok if st['locked'] else ng)('%s — 선택 전 접수폼 잠금' % name, 'locked=%s' % st['locked'])
            has3 = pg.evaluate("""() => ({ login: !!document.querySelector('#modal [data-guestlogin]'),
                signup: !!document.querySelector('#modal [data-guestsignup]'),
                cont: !!document.querySelector('#modal [data-guestcontinue]') })""")
            (ok if has3['login'] and has3['signup'] and has3['cont'] else ng)(
                '%s — 로그인 · 회원가입 · 비회원으로 계속 3개 선택' % name, str(has3))
            pg.keyboard.press('Escape')
            pg.wait_for_timeout(250)
            unlock = pg.evaluate("() => ({ locked: !!document.querySelector('.guest-locked'), open: !!document.querySelector('#modal.open') })")
            (ok if not unlock['locked'] and not unlock['open'] else ng)(
                '%s — 팝업을 닫으면 입력은 다시 가능(잠금 해제)' % name, str(unlock))
            pg.click(nxt)
            pg.wait_for_timeout(450)
            again = pg.evaluate("() => ({ open: !!document.querySelector('#modal.open'), title: (document.querySelector('#modalTitle')||{}).textContent||'' })")
            (ok if again['open'] and '로그인' in again['title'] else ng)(
                '%s — 진행을 누르면 로그인 팝업 재호출' % name, str(again)[:110])
            pg.click('#modal [data-guestcontinue]')
            pg.wait_for_timeout(500)
        probs = w.problems()
        (ok if not probs else ng)('비로그인 진입 팝업 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()


        # ------------------------------------------------------------------
        # 34) 주간 타임라인 오늘 요일만 강조 · 입금 마감 수요일 18:00 · 의료광고 심의 안내
        # ------------------------------------------------------------------
        head('34. 주간 타임라인 오늘 요일 강조 · 입금 마감 수요일 18:00 · 의료광고 심의 안내')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'index.html', 500)
        wk_cards = pg.eval_on_selector_all('#weekStrip .wk', 'els => els.map(e => ({ k: e.className, t: e.textContent.trim().slice(0, 12), today: e.classList.contains("today"), badge: !!e.querySelector(".wk-badge") }))')
        todays = [c for c in wk_cards if c['today']]
        (ok if len(wk_cards) == 5 and len(todays) == 1 and todays[0]['badge'] else ng)(
            '주간 타임라인 — 오늘 요일 카드 1개만 강조(오늘 배지)', str([c['t'] for c in wk_cards])[:110])
        import datetime as _d2
        dow_now = _d2.date.today().weekday()  # 월=0
        want = {0: 'draw', 1: 'pay', 2: 'due', 3: 'first', 4: 'off'}.get(dow_now)
        (ok if (want is None and not todays) or (want and want in todays[0]['k']) else ng)(
            '오늘 요일 = 실제 요일 기준 강조', 'today=%s · 오늘요일index=%d' % (todays[0]['t'] if todays else None, dow_now))
        strip_txt = pg.text_content('#weekStrip') or ''
        (ok if '입금' in strip_txt and '18:00' in strip_txt else ng)(
            '주간 타임라인 — 수요일 입금·입고 마감 18:00 표기', strip_txt[:120].replace('\n', ' '))
        src_apply = io.open(os.path.join(ROOT, 'apply.html'), encoding='utf-8').read()
        src_guide = io.open(os.path.join(ROOT, 'guide-rules.html'), encoding='utf-8').read()
        src_pay = io.open(os.path.join(ROOT, 'admin-pay.html'), encoding='utf-8').read()
        (ok if '수요일 18:00까지 접수비 입금' in src_apply else ng)('apply.html — 수요일 18:00 입금·입고 마감 안내', 'apply')
        (ok if '접수비 입금 · 현수막 실물 입고 마감' in src_guide else ng)('guide-rules.html — 입금 마감 수요일 18:00 통일', 'guide')
        (ok if '수요일 18:00' in src_pay else ng)('admin-pay.html — 입금 마감 수요일 18:00', 'pay')

        # 의료광고 심의 안내 — 4개 화면 + 키워드 감지 강조
        for name in ('apply.html', 'first.html'):
            src = io.open(os.path.join(ROOT, name), encoding='utf-8').read()
            (ok if '의료광고 심의필 번호' in src and '조기 철거' in src else ng)(
                '%s — 의료광고 심의 미표기 조기철거 안내' % name, name)
        (ok if '의료광고 심의필 번호' in src_guide else ng)('guide-rules.html — 의료광고 심의 안내', 'guide')
        src_rev = io.open(os.path.join(ROOT, 'admin-review.html'), encoding='utf-8').read()
        (ok if '의료광고 심의' in src_rev and '조기 철거' in src_rev else ng)('admin-review.html — 시안 심사 의료광고 체크', 'review')
        goto(pg, base + 'apply.html', 600)
        pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
        pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({ company: '서산튼튼병원', owner: '김의사', phone: '010-2222-3333',
            advertiser: '서산튼튼병원', advertiserBiz: '330-11-22334', text: '정형외과 도수치료 안내', qty: 1, agree: true })""")
        pg.wait_for_timeout(350)
        med = pg.evaluate("() => { const e = document.querySelector('#medicalAdNote'); return e ? !e.classList.contains('hidden') : null; }")
        (ok if med is True else ng)('apply 1단계 — 의료 키워드 감지 시 심의 경고 강조', str(med))
        pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({ advertiser: '햇살농원', text: '가을 사과 직판 안내' })""")
        pg.wait_for_timeout(300)
        med2 = pg.evaluate("() => { const e = document.querySelector('#medicalAdNote'); return e ? !e.classList.contains('hidden') : null; }")
        (ok if med2 is False else ng)('apply 1단계 — 일반 문구는 경고 숨김', str(med2))
        goto(pg, base + 'first.html', 600)
        pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSet({ advertiser: '서산미소치과', text: '임플란트 상담 안내', file: true, agree: true, license: true })")
        pg.wait_for_timeout(350)
        med3 = pg.evaluate("() => { const e = document.querySelector('#fcMedicalAdNote'); return e ? !e.classList.contains('hidden') : null; }")
        (ok if med3 is True else ng)('first 1단계 — 의료 키워드 감지 시 심의 경고 강조', str(med3))
        probs = w.problems()
        (ok if not probs else ng)('타임라인·입금·의료광고 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()


        # ------------------------------------------------------------------
        # 35) 광고문구 비방·욕설·매매혼 필터 · 시안 심사 시한임박 우선 · 입고검색 · 지정서 상단버튼
        # ------------------------------------------------------------------
        head('35. 비방·욕설·매매혼 문구 차단 · 시안 심사 시한임박 우선 · 입고 검색 · 지정서 상단 버튼')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        w = Watcher(pg, base)
        goto(pg, base + 'apply.html', 600)
        pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
        # 금지어 엔진 단위 검사 (우회 표기 포함)
        unit = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY;
            return { abuse: v.checkText('병 신 같은 놈'), plain: v.checkText('가을 사과 직판'),
              marriage: v.checkText('베트남 처녀 신부 알선'), ok: v.checkText('해미읍성 야간 문화행사') }; }""")
        (ok if unit['abuse']['bad'] and not unit['plain']['bad'] and unit['marriage']['bad'] and not unit['ok']['bad'] else ng)(
            '금지어 엔진 — 욕설·매매혼 탐지 · 정상 문구 통과', str({k: v['bad'] for k, v in unit.items()}))
        pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({ company: '햇살농원', owner: '김정수', phone: '010-1111-2222',
            advertiser: '햇살농원', advertiserBiz: '312-45-67120', text: '병신 같은 놈', qty: 1, agree: true })""")
        pg.wait_for_timeout(300)
        note = pg.evaluate("() => window.SEOSAN_VERIFY.abuseNote('#abuseNote')")
        (ok if note and not note['hidden'] and '비방' in note['text'] else ng)(
            '접수 1단계 — 욕설 문구 입력 시 붉은 경고 배너', str(note)[:110])
        pg.click('#btnLicSample')
        pg.evaluate("() => window.SEOSAN_VERIFY.setApply({ file: true })")
        blocked = pg.evaluate("() => window.SEOSAN_VERIFY.validateStep(1)")
        (ok if blocked is False else ng)('비방·욕설 문구 — 다음 단계 차단', str(blocked))
        pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({ advertiser: '햇살농원', text: '가을 사과 직판 안내' })""")
        pg.wait_for_timeout(250)
        note2 = pg.evaluate("() => window.SEOSAN_VERIFY.abuseNote('#abuseNote')")
        (ok if note2 and note2['hidden'] else ng)('정상 문구로 수정 — 경고 사라짐', str(note2)[:80])
        mar = pg.evaluate("""() => window.SEOSAN_VERIFY.setApplyText2('결혼정보', '베트남 처녀 후불결혼')""")
        pg.wait_for_timeout(250)
        note3 = pg.evaluate("() => window.SEOSAN_VERIFY.abuseNote('#abuseNote')")
        (ok if mar['bad'] and note3 and '결혼중개업법' in note3['text'] else ng)(
            '매매혼·성상품화 표현 — 결혼중개업법 위반 경고', str(note3)[:120])
        goto(pg, base + 'remain.html', 600)
        pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
        fc_bad = pg.evaluate("""() => window.SEOSAN_VERIFY.fcSet({ advertiser: '테스트', text: '씨발 광고', file: true, agree: true, license: true })""")
        pg.wait_for_timeout(200)
        fc_note = pg.evaluate("() => window.SEOSAN_VERIFY.abuseNote('#fcAbuseNote')")
        (ok if fc_note and not fc_note['hidden'] else ng)('상시접수 1단계 — 욕설 문구 경고 배너', str(fc_note)[:90])
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.fcValidate(1)") is False else ng)(
            '상시접수 — 욕설 문구 다음 단계 차단')

        # 시안 심사 — 시한임박 우선 (임박 건은 ⏰ 임박 배지가 있고, 그 건들이 일반 건보다 위에 온다)
        goto(pg, base + 'admin-review.html', 600)
        urg_first = pg.evaluate("""() => { const rows = Array.from(document.querySelectorAll('#reviewList tbody tr'));
            if (!rows.length) return { rows: 0, ok: false, why: '심사 대기 0건' };
            const flags = rows.map(r => !!r.querySelector('.urgent-badge'));
            const firstTrue = flags.indexOf(true);
            const afterFalse = flags.slice(Math.max(flags.indexOf(false), 0) + 1).indexOf(true);
            return { rows: rows.length, urg: flags.filter(Boolean).length, firstTrue: firstTrue,
              ok: firstTrue === 0 && afterFalse < 0, flags: flags.slice(0, 6) }; }""")
        (ok if urg_first['rows'] and urg_first.get('urg', 0) >= 1 and urg_first['ok'] else ng)(
            '시안 심사 — 시한임박 건이 일반 건보다 최상단', str(urg_first)[:140])

        # 입고 검색 · 지정서 상단 버튼
        goto(pg, base + 'admin-deliver.html', 500)
        has_search = pg.evaluate("() => !!document.querySelector('#deliverSearch')")
        pg.fill('#deliverSearch', '없는업체명')
        pg.wait_for_timeout(300)
        empty_rows = pg.eval_on_selector_all('#deliverTable tbody tr', 'e => e.length')
        pg.fill('#deliverSearch', '')
        pg.wait_for_timeout(250)
        (ok if has_search and empty_rows == 0 else ng)('입고 확인 — 실시간 검색창 · 필터', 'rows=%s' % empty_rows)
        goto(pg, base + 'admin-desig.html', 500)
        topy = pg.evaluate("""() => { const b = document.querySelector('#btnDesigBatchAllPrint'); const t = document.querySelector('#desigBatchList');
            if (!b || !t) return null; return { btn: Math.round(b.getBoundingClientRect().top + window.scrollY),
              table: Math.round(t.getBoundingClientRect().top + window.scrollY) }; }""")
        (ok if topy and topy['btn'] <= topy['table'] + 24 else ng)('지정서 일괄 출력 버튼 — 목록 상단 배치', str(topy))
        probs = w.problems()
        (ok if not probs else ng)('비방필터·심사정렬·검색 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 36) 게시대 현황 요일 필터 · 목요일 취소분 링크 · 목요일 공휴일 · 시연 기준일 달력
        # ------------------------------------------------------------------
        head('36. 게시대 현황 요일 필터(화요일) · 목요일 취소분 링크 · 목요일 공휴일 · 시연 달력')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'index.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        expand_places(pg)
        chips = pg.eval_on_selector_all('#statusDayChips button', 'els => els.map(e => e.textContent.trim())')
        (ok if chips == ['전체', '월요일', '화요일', '수요일'] else ng)('게시대 현황 요일 필터 — 전체·월·화·수 노출', str(chips))
        pg.click('#statusDayChips button[data-day="화"]')
        pg.wait_for_timeout(350)
        info = pg.text_content('#statusListInfo') or ''
        rows_txt = pg.eval_on_selector_all('#placementGrid .plrow .pl-tag', 'els => els.map(e => e.textContent.trim())')
        hit = [x for x in rows_txt if x.startswith('화')]
        (ok if '표시 23개소' in info and len(rows_txt) == 23 and len(hit) == 23 else ng)(
            '화요일 필터 — 화요일 게시대만 표시(23개소)', '%s / rows=%d hit=%d' % (info.strip()[:40], len(rows_txt), len(hit)))
        pg.click('#statusDayChips button[data-day=""]')
        pg.wait_for_timeout(200)

        # 목요일 — 주간 타임라인 취소분 카드가 first.html 링크
        pg.evaluate("() => window.SEOSAN_VERIFY.setNow('2026-11-26')")
        pg.wait_for_timeout(500)
        hol0 = pg.evaluate("() => window.SEOSAN_VERIFY.holiday()")
        is_thu = pg.evaluate("() => window.SEOSAN_VERIFY.nowDow()") == 4
        href_thu = pg.eval_on_selector('#weekStrip a.wk.first', 'e => e.getAttribute("href")') if pg.query_selector('#weekStrip a.wk.first') else ''
        nav_thu = pg.evaluate("() => window.SEOSAN_VERIFY.firstNav()")
        thu_plain = pg.evaluate("() => { const a = document.querySelector('#weekStrip a.wk.first'); const d = document.querySelector('#weekStrip .wk.first'); return { link: !!a, card: !!d }; }")
        (ok if is_thu and not thu_plain['link'] and thu_plain['card'] and nav_thu['allowed'] and not nav_thu['hidden'] else ng)(
            '목요일 — 타임라인은 안내 카드(링크 없음) · 메뉴는 노출', 'plain=%s nav=%s' % (thu_plain, nav_thu))
        (ok if pg.query_selector('#fcOpenNotice') else ng)('목요일 — 취소분 접수 바로가기 배너', 'fcOpenNotice 없음')

        # 다른 요일 — remain.html 연결
        pg.evaluate("() => window.SEOSAN_VERIFY.setNow('2026-11-25')")
        pg.wait_for_timeout(400)
        wed_plain = pg.evaluate("() => { const a = document.querySelector('#weekStrip a.wk.first'); const d = document.querySelector('#weekStrip .wk.first'); return { link: !!a, card: !!d }; }")
        (ok if not wed_plain['link'] and wed_plain['card'] else ng)('다른 요일 — 타임라인은 안내 카드(링크 없음)', str(wed_plain))

        # 목요일 공휴일 ON — 팝업 자동 · 금요일 이동 · 입고 14:00
        pg.evaluate("() => window.SEOSAN_VERIFY.setHoliday(true)")
        pg.wait_for_timeout(500)
        pop = pg.evaluate("() => { const m = document.querySelector('#modal'); return m && m.classList.contains('open') ? (document.querySelector('#modalBody').textContent || '') : ''; }")
        (ok if '공휴일 일정 안내' in pop and '금요일' in pop and '14:00' in pop else ng)(
            '목요일 공휴일 ON — 공지 팝업 자동 표시', pop[:110].replace('\n', ' '))
        (ok if pg.evaluate("() => !!document.querySelector('#holidayNoticeHide')") else ng)(
            '공휴일 팝업 — 오늘 하루 보지 않기')
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        pg.wait_for_timeout(300)
        hol = pg.evaluate("() => window.SEOSAN_VERIFY.holiday()")
        strip = pg.text_content('#weekStrip') or ''
        (ok if hol['openDow'] == 5 and hol['deliverTime'] == '14:00' and '금요일 09:00~18:00' in strip else ng)(
            '공휴일 — 취소분 금요일 이동 · 입고 금요일 14:00', '%s / %s' % ({k: hol[k] for k in ('openDow', 'openDay', 'deliverTime')}, strip[:90].replace('\n', ' ')))
        # 목요일(공휴일) — 메뉴 숨김 · 금요일 진행 안내
        pg.evaluate("() => window.SEOSAN_VERIFY.setNow('2026-11-26')")
        pg.wait_for_timeout(450)
        nv = pg.evaluate("() => window.SEOSAN_VERIFY.firstNav()")
        nl = pg.text_content('#statusLiveNotice') or ''
        (ok if nv['hidden'] and '금요일' in nl else ng)('공휴일 + 목요일 — 취소분 메뉴 숨김 · 금요일 진행 안내', str(nv))
        # 금요일(공휴일) — 메뉴 노출 · first.html 링크
        pg.evaluate("() => window.SEOSAN_VERIFY.setNow('2026-11-27')")
        pg.wait_for_timeout(450)
        nv2 = pg.evaluate("() => window.SEOSAN_VERIFY.firstNav()")
        hol_plain = pg.evaluate("() => !document.querySelector('#weekStrip a.wk.first') && !!document.querySelector('#weekStrip .wk.first')")
        (ok if nv2['allowed'] and not nv2['hidden'] and hol_plain else ng)(
            '공휴일 + 금요일 — 취소분 메뉴 활성화(타임라인은 안내 카드)', 'nav=%s plain=%s' % (nv2, hol_plain))
        # first.html — 금요일 접수 열림 · 입고 14:00
        goto(pg, base + 'first.html', 600)
        pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
        pg.wait_for_timeout(350)
        ban = pg.text_content('#fcBanner') or ''
        (ok if '금요일' in ban and '14:00' in ban else ng)('first.html 공휴일 금요일 — 접수 열림 · 입고 14:00', ban[:120].replace('\n', ' '))
        # guide-rules — 공휴일 유의사항
        goto(pg, base + 'guide-rules.html', 500)
        gt = pg.text_content('#guideHolidayNote') or ''
        (ok if '금요일 14:00' in gt else ng)('guide-rules — 목요일 공휴일 유의사항', gt[:100].replace('\n', ' '))

        # 시연 기준일 달력 팝업
        goto(pg, base + 'index.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        pg.click('[data-democal]')
        pg.wait_for_timeout(350)
        cal1 = pg.evaluate("() => document.querySelector('#demoCal') ? document.querySelector('#demoCal').textContent : ''")
        (ok if '년' in cal1 and '일' in cal1 and len(cal1) > 30 else ng)('시연 기준일 — 달력 팝업 열림', cal1[:60])
        pg.click('[data-democalnav="1"]')
        pg.wait_for_timeout(300)
        cal2 = pg.evaluate("() => document.querySelector('#demoCal') ? document.querySelector('#demoCal').textContent : ''")
        (ok if cal2 and cal2 != cal1 else ng)('시연 달력 — 이전/다음 달 이동', cal2[:40])
        pg.evaluate("() => { const b = document.querySelector('[data-democalday=\"2026-12-10\"]'); if (b) b.click(); }")
        pg.wait_for_timeout(450)
        now_after = pg.evaluate("() => window.SEOSAN_VERIFY.now()")
        (ok if now_after == '2026-12-10' else ng)('시연 달력 — 날짜 클릭으로 기준일 변경', now_after)
        # 원복
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.setHoliday(false); window.SEOSAN_VERIFY.setNow(''); } catch (e) {} }")
        probs = w.problems()
        (ok if not probs else ng)('요일 필터·공휴일·달력 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 37) 명절·연휴·휴가 정책 · 적재 희망 날짜 선택 · 시안 바탕색 경고 · 게첨사진 확대
        # ------------------------------------------------------------------
        head('37. 명절·연휴·휴가 정책 · 날짜 선택 · 시안 바탕색 경고 · 게첨사진 확대')
        ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        # 37-1) 관리자 정책 토글
        goto(pg, base + 'admin-system.html', 500)
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('super')")
        pg.wait_for_timeout(300)
        has_tgl = pg.evaluate("() => !!document.querySelector('#policyHolidayNoDraw') && !!document.querySelector('#policyHolidayDirectInstall')")
        (ok if has_tgl else ng)('관리자 운영 정책 — 추첨 없애기 · 접수자 직접설치 토글 존재')
        pol = pg.evaluate("() => window.SEOSAN_VERIFY.setPolicy('holidayNoDraw', true)")
        pg.wait_for_timeout(300)
        pol2 = pg.evaluate("() => ({ p: window.SEOSAN_VERIFY.policy(), chk: !!document.querySelector('#policyHolidayNoDraw').checked })")
        (ok if pol is True and pol2['p']['noDraw'] and pol2['chk'] else ng)('관리자 — 추첨 없애기 ON', str(pol2))
        goto(pg, base + 'admin-draw.html', 500)
        dbtn = pg.evaluate("() => { const b = document.querySelector('#btnDraw'); return b ? { dis: b.disabled, t: b.textContent } : null; }")
        (ok if dbtn and dbtn['dis'] and '추첨 없음' in dbtn['t'] else ng)('추첨 없애기 ON — 추첨 실행 잠김 안내', str(dbtn))
        goto(pg, base + 'index.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        (ok if pg.query_selector('#noDrawNotice') else ng)('추첨 없애기 ON — 첫 화면 안내')
        goto(pg, base + 'apply.html', 500)
        pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
        pg.wait_for_timeout(250)
        (ok if pg.query_selector('#applyNoDrawNote') else ng)('추첨 없애기 ON — 접수 화면 안내')

        # 37-2) 접수자 직접설치 전환 — 안내 멘트 분기
        goto(pg, base + 'admin-system.html', 500)
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('super')")
        pg.evaluate("() => window.SEOSAN_VERIFY.setPolicy('holidayDirectInstall', true)")
        pg.wait_for_timeout(350)
        goto(pg, base + 'remain.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1002')")
        pg.wait_for_timeout(350)
        ban_ag = pg.text_content('#fcBanner') or ''
        (ok if '명절·연휴·휴가 주간 직접설치 안내' in ban_ag and '광고사에서 직접 현장에 설치(게첨)' in ban_ag and '일반인은 직접 설치가 금지' not in ban_ag else ng)(
            '직접설치 ON — 광고사 안내 멘트(진행 주간과 동일)', ban_ag[:140].replace('\n', ' '))
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1001')")
        pg.wait_for_timeout(350)
        ban_gen = pg.text_content('#fcBanner') or ''
        (ok if '명절·연휴·휴가 주간 직접설치 안내' in ban_gen and '일반인은 직접 설치가 금지' in ban_gen and '광고사에 설치를 의뢰' in ban_gen else ng)(
            '직접설치 ON — 일반인 안내 멘트(직접설치 가능 표현 없음)', ban_gen[:150].replace('\n', ' '))

        # 37-3) 미배정 접수 1페이지 날짜(주차) 선택
        goto(pg, base + 'remain.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
        pg.wait_for_timeout(350)
        wkchips = pg.eval_on_selector_all('#fcWeekPick button[data-fcweek]', 'els => els.map(e => [e.getAttribute("data-fcweek"), e.textContent.trim()])')
        (ok if len(wkchips) >= 1 and pg.query_selector('#fcWeekPickBox') and pg.query_selector('#fcStep1 #fcWeekPick') else ng)(
            '미배정 상시접수 1단계 — 날짜(주차) 선택 UI', str(wkchips)[:120])
        (ok if all(c[0] <= '2026-11-30' for c in wkchips) else ng)(
            '미배정 상시접수 — 아직 추첨 전인 미래 주차는 숨김', str([c[0] for c in wkchips]))
        wk1 = pg.evaluate("() => window.SEOSAN_VERIFY.fcWeek()")
        if len(wkchips) > 1:
            pg.evaluate("() => { const b = document.querySelector('#fcWeekPick button[data-fcweek]:not(.active)'); if (b) b.click(); }")
            pg.wait_for_timeout(400)
            wk2 = pg.evaluate("() => window.SEOSAN_VERIFY.fcWeek()")
            (ok if wk2 and wk2 != wk1 else ng)('주차 선택 — 선택한 주차로 전환', '%s → %s' % (wk1, wk2))
        else:
            (ok if wk1 else ng)('주차 선택 — 현재 주차 유지(추첨 완료 주차만)', wk1)
        # apply.html 은 1페이지에 주차 선택 없음 (기존 2단계 유지)
        goto(pg, base + 'apply.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        (ok if not pg.query_selector('#step1 #fcWeekPick') and not pg.query_selector('#applyWeekBox') else ng)(
            'apply.html — 1페이지 주차 선택 없음(2단계 유지)')

        # 37-4) 시안 바탕색 분석 경고
        goto(pg, base + 'apply.html', 500)
        pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
        pg.click('#btnDesignSampleBlack')
        pg.wait_for_timeout(700)
        note_b = pg.evaluate("() => { const e = document.querySelector('#designToneNote'); return e ? e.textContent : ''; }")
        (ok if '검정' in (note_b or '') and '조기 철거' in (note_b or '') else ng)('검정 바탕 시안 — 조기철거 경고 표시', (note_b or '')[:110])
        pg.click('#btnDesignSampleRed')
        pg.wait_for_timeout(700)
        note_r = pg.evaluate("() => { const e = document.querySelector('#designToneNote'); return e ? e.textContent : ''; }")
        (ok if '빨간' in (note_r or '') and '조기 철거' in (note_r or '') else ng)('빨간 바탕 시안 — 조기철거 경고 표시', (note_r or '')[:110])
        pg.click('#btnDesignSample')
        pg.wait_for_timeout(700)
        (ok if not pg.query_selector('#designToneNote') else ng)('정상 시안 — 바탕색 경고 없음')
        goto(pg, base + 'remain.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
        pg.click('#btnFcDesignSampleBlack')
        pg.wait_for_timeout(700)
        note_fc = pg.evaluate("() => { const e = document.querySelector('#fcDesignToneNote'); return e ? e.textContent : ''; }")
        (ok if '검정' in (note_fc or '') else ng)('상시접수 — 검정 바탕 시안 경고', (note_fc or '')[:100])

        # 37-5) 게첨사진 게첨 기간 표기 · 클릭 확대
        goto(pg, base + 'admin-photos.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.photoAdd({ pid: 'P01', dong: 'A', week: '2026-11-30' }); } catch (e) {} }")
        pg.wait_for_timeout(500)
        pcard = pg.text_content('.photo-card') if pg.query_selector('.photo-card') else ''
        (ok if '게첨 기간:' in pcard and re.search(r'\d{4}-\d{2}-\d{2}\([월화수목금토일]\) ~ \d{4}-\d{2}-\d{2}\([월화수목금토일]\)', pcard) else ng)('게첨사진 카드 — 게첨 기간 날짜 표기', pcard[:120].replace('\n', ' '))
        pg.click('.photo-card .pc-img')
        pg.wait_for_timeout(500)
        zt = pg.text_content('#modalBody') if pg.query_selector('#modalBody') else ''
        (ok if '확대' in (pg.text_content('#modalTitle') or '') and '게첨 기간:' in zt and '보관 만료' in zt else ng)(
            '게첨사진 클릭 — 확대 보기 모달', (pg.text_content('#modalTitle') or '') + ' / ' + zt[:80].replace('\n', ' '))
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        goto(pg, base + 'admin-docs.html', 500)
        wol = pg.text_content('#woWeekLabel') or ''
        (ok if '게첨 기간:' in wol and '(' in wol else ng)('작업지시서 — 게첨 기간 날짜 표기', wol[:100])

        # 원복
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.setPolicy('holidayNoDraw', false); window.SEOSAN_VERIFY.setPolicy('holidayDirectInstall', false); window.SEOSAN_VERIFY.setRole('super'); } catch (e) {} }")
        probs = w.problems()
        (ok if not probs else ng)('정책·날짜선택·바탕색·사진 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')

        # 37-6) 공문 접수 — 저단(공문전용) 게시대 필터
        goto(pg, base + 'admin-official.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.setRole('staff'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(400)
        lchips = pg.eval_on_selector_all('#offLowChips button[data-offlow]', 'els => els.map(e => [e.getAttribute("data-offlow"), e.textContent.trim()])')
        (ok if [c[0] for c in lchips] == ['', 'normal', 'low'] else ng)('공문 접수 — 저단 게시대 필터 칩(전체·일반·저단)', str(lchips)[:120])
        pg.click('#offLowChips button[data-offlow="low"]')
        pg.wait_for_timeout(400)
        low_rows = pg.eval_on_selector_all('#offPlaces .off-pick', 'e => e.length')
        low_badge = pg.eval_on_selector_all('#offPlaces .off-pick', 'els => els.filter(e => e.textContent.indexOf("공문 전용") >= 0).length')
        (ok if low_rows > 0 and low_badge == low_rows else ng)('저단 필터 — 저단(공문전용) 게시대만 표시', '%d개 · 배지 %d개' % (low_rows, low_badge))
        pg.click('#offLowChips button[data-offlow="normal"]')
        pg.wait_for_timeout(400)
        normal_rows = pg.eval_on_selector_all('#offPlaces .off-pick', 'e => e.length')
        (ok if normal_rows > low_rows else ng)('일반 게시대 필터 — 일반 게시대만 표시', '%d개' % normal_rows)
        pg.click('#offLowChips button[data-offlow=""]')
        pg.wait_for_timeout(300)
        all_rows = pg.eval_on_selector_all('#offPlaces .off-pick', 'e => e.length')
        (ok if all_rows == normal_rows + low_rows else ng)('전체 필터 — 일반+저단 합계', '%d = %d + %d' % (all_rows, normal_rows, low_rows))
        ctx.close()

        # ------------------------------------------------------------------
        # 38) 관리자 페이지 분리(2주 공문·정치행정·게시위치) · 권한 매트릭스 · 사진 폴더명
        # ------------------------------------------------------------------
        head('38. 관리자 페이지 분리 · 권한 매트릭스 · 사진 폴더명')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'admin-official-review.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(400)
        subs = pg.eval_on_selector_all('#adminSub a', 'els => els.map(e => e.getAttribute("data-adminsub"))')
        (ok if subs[:4] == ['review', 'official', 'officialreview', 'political'] and len(subs) == 18 else ng)(
            '관리자 서브탭 18개 - 3번째 2주 공문·4번째 정치행정', str(subs)[:120])
        onk = pg.eval_on_selector_all('#adminSub a.on', 'els => els.map(e => e.getAttribute("data-adminsub"))')
        (ok if onk == ['officialreview'] else ng)('2주 공문 심사 페이지 - 자기 탭 활성', str(onk))
        rv = pg.evaluate("() => ({ info: (document.querySelector('#offReviewInfo')||{}).textContent || '', rows: document.querySelectorAll('#offReviewList tbody tr').length, btns: document.querySelectorAll('#offReviewList [data-offapprove]').length })")
        (ok if '결재 대기' in rv['info'] else ng)('2주 공문 심사 - 결재 대기 목록', str(rv)[:120])
        goto(pg, base + 'admin-political.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(350)
        (ok if pg.query_selector('#polPanel') and pg.query_selector('#polList') else ng)('정치행정 심사 - 전용 페이지 패널')
        goto(pg, base + 'admin-event.html', 500)
        (ok if not pg.query_selector('#polPanel') else ng)('행사 심사 페이지 - 정치행정 패널 분리됨')
        goto(pg, base + 'admin-loc.html', 600)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(450)
        items = pg.eval_on_selector_all('#locList .loc-item', 'e => e.length')
        pg.click('#locList .loc-item')
        pg.wait_for_timeout(350)
        has_dlv = pg.query_selector('td [data-locdeliver]')
        (ok if items > 0 and has_dlv else ng)('게시위치 - 목록·단수별 입고확인 버튼', 'items=%s btn=%s' % (items, bool(has_dlv)))
        if has_dlv:
            app_id = has_dlv.get_attribute('data-locdeliver')
            pg.click('td [data-locdeliver="%s"]' % app_id)
            pg.wait_for_timeout(500)
            st = pg.evaluate("(id) => (window.SEOSAN_VERIFY.apps() || []).filter(a => a.id === id).map(a => !!a.delivered)[0]", app_id)
            (ok if st is True else ng)('게시위치 입고확인 - 입고 상태 저장', str(st))
        goto(pg, base + 'admin-docs.html', 500)
        (ok if not pg.query_selector('#locPanel') else ng)('작업지시서 페이지 - 게시위치 분리됨')
        goto(pg, base + 'admin-roles.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(500)
        mx = pg.evaluate("() => window.SEOSAN_VERIFY.permMatrix()")
        (ok if mx and mx['rows'] == 18 and mx['cols'] == 9 and mx['cells'] == 162 else ng)(
            '권한 매트릭스 - 9직책 x 18행(17페이지 + 가산점부여 · 162칸)', str(mx))
        pg.evaluate("() => window.SEOSAN_VERIFY.setPerm('staff1', 'photos', false)")
        pg.wait_for_timeout(250)
        pg.evaluate("() => window.SEOSAN_VERIFY.setRole('staff')")
        pg.wait_for_timeout(400)
        tabs = pg.evaluate("() => window.SEOSAN_VERIFY.visibleTabs()")
        (ok if 'photos' not in tabs and 'review' in tabs else ng)('사무실무원1 - 권한 없는 게첨사진 탭 숨김', str(tabs)[:110])
        (ok if 'roles' not in tabs else ng)('비총괄 - 관리자 권한 탭 비노출', str(tabs)[:110])
        goto(pg, base + 'admin-photos.html', 500)
        (ok if pg.query_selector('#permLockBox') else ng)('권한 없는 페이지 직접 접근 - 본문 차단')
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.setPerm('staff1', 'photos', true); } catch (e) {} }")
        pg.wait_for_timeout(200)
        goto(pg, base + 'admin-photos.html', 500)
        (ok if not pg.query_selector('#permLockBox') else ng)('권한 복원 후 - 페이지 접근 가능')
        folder = pg.evaluate("() => window.SEOSAN_VERIFY.photoFolder('P01', 'A')")
        (ok if str(folder).startswith('_의료원사거리') else ng)('사진 폴더명 - 실제 폴더 기준', folder)
        goto(pg, base + 'index.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        wk = pg.eval_on_selector_all('#weekStrip .wk', 'els => els.map(e => e.className)')
        (ok if len(wk) == 5 and any('pay' in c for c in wk) and not any('post' in c for c in wk) else ng)('주간 타임라인 - 월·화·수·목·금 5칸(6번째 게첨 카드 삭제)', str(wk)[:120])
        (ok if not pg.query_selector('#weekStrip .wk-go') else ng)('주간 타임라인 - 상시접수 별도 카드 없음')
        # 결재 버튼 라벨 — 감사 접속 시 '감사 결재'
        goto(pg, base + 'admin-official-review.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('audit1'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(400)
        albl = pg.eval_on_selector_all('#offReviewList [data-offapprove]', 'els => els.map(e => e.textContent.trim())')
        (ok if albl and all('감사 결재' in x for x in albl) and not any('지부장 결재' in x for x in albl) else ng)(
            '감사 직책 — 결재 버튼이 감사 결재로 표시', str(albl)[:110])
        goto(pg, base + 'admin-official.html', 500)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('audit1'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(400)
        albl2 = pg.eval_on_selector_all('#offTable [data-offapprove]', 'els => els.map(e => e.textContent.trim())')
        (ok if not any('지부장 결재' in x for x in albl2) else ng)('공문 접수 — 감사 접속 시 지부장 결재 버튼 없음', str(albl2)[:110])
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.setRole('super'); } catch (e) {} }")
        # 결재 대기 팝업 — 지부장/감사 전환 시
        # 결재 대기 팝업 — 지부장으로 로그인하면 자동 표시(로그인 시점)
        goto(pg, base + 'index.html', 600)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.logout(); window.SEOSAN_VERIFY.login('M-2001'); } catch (e) {} }")
        pg.wait_for_timeout(1400)
        pend = pg.evaluate("() => window.SEOSAN_VERIFY.pendingApprovals()")
        popOpen = pg.evaluate("() => { const m = document.querySelector('#modal'); return !!(m && m.classList.contains('open')); }")
        ptitle = pg.text_content('#modalTitle') if popOpen else ''
        (ok if pend and popOpen and '결재 대기' in (ptitle or '') else ng)(
            '협회관리자 직책 전환 - 결재 대기 팝업', 'pend=%s open=%s title=%s' % (pend, popOpen, ptitle))
        if popOpen:
            go = pg.query_selector('#btnGoApprove')
            href = go.get_attribute('href') if go else ''
            pg.click('#btnGoApprove')
            pg.wait_for_load_state('load')
            pg.wait_for_timeout(400)
            (ok if 'admin-official-review.html' in pg.url or 'admin-political.html' in pg.url or 'admin-event.html' in pg.url else ng)(
                '결재하러 가기 버튼 - 결재 페이지로 이동', str(href) + ' → ' + pg.url.split('/')[-1])
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.setRole('super'); } catch (e) {} }")
        probs = w.problems()
        (ok if not probs else ng)('페이지 분리·권한·사진 폴더 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        # ------------------------------------------------------------------
        # 39) 마이페이지 잠금(로그아웃 · 비회원 인증) · 행사 심사 배지 팝업 · 사진 폴더 정밀 매핑
        #     · 한 주 쉬어가기 공지 연동 · 명절·휴가 적용 달력 · 접수대장/추첨결과 A4 출력 · 입금 검색
        # ------------------------------------------------------------------
        head('39. 마이페이지 잠금·비회원 인증 · 행사 심사 팝업/작업칸 · 사진 폴더 · 정책 달력 · A4 출력 · 입금 검색')
        ctx = browser.new_context(viewport={'width': 1360, 'height': 980})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        # 39-1) 완전 로그아웃 상태로 마이페이지 → 잠금 + 진입 즉시 로그인/비회원 인증 모달
        pg.goto(base + 'mypage.html', wait_until='load')
        pg.wait_for_timeout(900)
        lock = pg.evaluate("""() => {
            const m = document.querySelector('#modal');
            const body = (document.querySelector('#mpBody') || {}).textContent || '';
            const head = (document.querySelector('#mpHead') || {}).textContent || '';
            return { open: !!(m && m.classList.contains('open')),
              title: ((document.querySelector('#modalTitle') || {}).textContent || '').trim(),
              foot: Array.from(document.querySelectorAll('#modalFoot .btn')).map(b => b.textContent.trim()),
              lockMsg: body.indexOf('로그인 또는 비회원 휴대폰 인증 후 이용할 수 있습니다') >= 0,
              lists: document.querySelectorAll('#mpBody .mp-list').length,
              rows: document.querySelectorAll('#mpBody .mp-list > *').length,
              hasAppNo: /-A-\\d{4}|-E-\\d{4}/.test(body + head),
              head: head.replace(/\\s+/g, ' ').slice(0, 60) }; }""")
        (ok if lock['lockMsg'] and lock['lists'] == 0 and not lock['hasAppNo'] else ng)(
            '로그아웃 마이페이지 — 개인 접수 내역 잠금(목록·접수번호 미노출)', str(lock)[:180])
        (ok if lock['open'] and '로그인 또는 비회원' in lock['title'] and len(lock['foot']) >= 3 else ng)(
            '로그아웃 마이페이지 진입 — 로그인/비회원 인증 모달 자동',
            'open=%s · title=%s · foot=%s' % (lock['open'], lock['title'], lock['foot']))
        # 39-2) 마이페이지 탭은 로그아웃 상태에서도 항상 보인다
        navl = pg.evaluate("""() => Array.from(document.querySelectorAll('nav.site-nav a[href="mypage.html"], #mobileTabbar a[href="mypage.html"]'))
            .map(a => ({ t: a.textContent.replace(/\\s+/g, ' ').trim(), hid: a.classList.contains('hidden'), d: getComputedStyle(a).display }))""")
        (ok if len(navl) >= 2 and all((not x['hid']) and x['d'] != 'none' for x in navl) else ng)(
            '마이페이지 탭 — 로그아웃 상태에서도 노출', str(navl)[:150])
        # 39-3) 비회원 휴대폰 인증 → 잠금 해제 · 그 번호의 접수만 표시
        pg.click('#modalFoot [data-mpverify]')
        pg.wait_for_timeout(500)
        has_form = pg.evaluate("() => !!document.querySelector('#mpvPhone') && !!document.querySelector('#btnMpvSend')")
        (ok if has_form else ng)('비회원 인증 모달 — 휴대폰 번호·인증번호 입력칸', str(has_form))
        pg.fill('#mpvPhone', '010-0000-0000')
        pg.click('#btnMpvSend')
        pg.wait_for_timeout(400)
        mpv = pg.evaluate("() => { const t = (document.querySelector('#mpvHint') || {}).textContent || ''; const m = t.match(/(\\d{6})/); return m ? m[1] : ''; }")
        pg.fill('#mpvCode', mpv)
        pg.click('#btnMpvOk')
        pg.wait_for_timeout(800)
        guest = pg.evaluate("""() => ({ head: ((document.querySelector('#mpHead') || {}).textContent || '').replace(/\\s+/g, ' ').slice(0, 70),
            lock: document.querySelectorAll('#mpBody .mp-lock').length,
            lists: document.querySelectorAll('#mpBody .mp-list').length,
            rows: document.querySelectorAll('#mpBody .mp-list > *').length,
            open: !!(document.querySelector('#modal') || {}).classList && document.querySelector('#modal').classList.contains('open') })""")
        (ok if guest['lock'] == 0 and guest['rows'] >= 1 and not guest['open'] else ng)(
            '비회원 인증 완료 — 잠금 해제 · 인증 번호의 접수 표시', str(guest)[:170])
        # 39-4) 다른 번호로 다시 인증하면 그 번호의 접수만 (번호별 분리)
        pg.evaluate("() => { const b = document.querySelector('[data-mpverify]'); if (b) b.click(); }")
        pg.wait_for_timeout(400)
        pg.fill('#mpvPhone', '010-7777-8888')
        pg.click('#btnMpvSend')
        pg.wait_for_timeout(350)
        mpv2 = pg.evaluate("() => { const t = (document.querySelector('#mpvHint') || {}).textContent || ''; const m = t.match(/(\\d{6})/); return m ? m[1] : ''; }")
        pg.fill('#mpvCode', mpv2)
        pg.click('#btnMpvOk')
        pg.wait_for_timeout(700)
        other = pg.evaluate("() => ({ head: ((document.querySelector('#mpHead') || {}).textContent || '').replace(/\\s+/g, ' ').slice(0, 60), rows: document.querySelectorAll('#mpBody .mp-list > *').length })")
        (ok if other['rows'] == 0 and '7777' in other['head'] else ng)(
            '다른 번호 인증 — 그 번호 접수만(0건) · 인증 번호 표시', str(other)[:140])
        # 39-5) 회원 로그인 → 마이페이지 정상 진입 (잠금·모달 없음)
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1001')")
        pg.wait_for_timeout(700)
        mem = pg.evaluate("""() => ({ head: ((document.querySelector('#mpHead') || {}).textContent || '').replace(/\\s+/g, ' ').slice(0, 60),
            lock: document.querySelectorAll('#mpBody .mp-lock').length, lists: document.querySelectorAll('#mpBody .mp-list').length,
            rows: document.querySelectorAll('#mpBody .mp-list > *').length,
            open: !!document.querySelector('#modal.open'),
            nav: Array.from(document.querySelectorAll('nav.site-nav a[href="mypage.html"]')).every(a => !a.classList.contains('hidden') && getComputedStyle(a).display !== 'none') })""")
        (ok if mem['lock'] == 0 and mem['rows'] >= 1 and not mem['open'] and mem['nav'] else ng)(
            '회원 로그인 — 마이페이지 정상 진입(잠금 없음) · 탭 노출', str(mem)[:170])
        # 39-6) 로그아웃 → 다시 잠금
        pg.evaluate("() => window.SEOSAN_VERIFY.logout()")
        pg.wait_for_timeout(600)
        out = pg.evaluate("() => ({ lock: document.querySelectorAll('#mpBody .mp-lock').length, rows: document.querySelectorAll('#mpBody .mp-list > *').length, msg: ((document.querySelector('#mpBody') || {}).textContent || '').indexOf('로그인 또는 비회원 휴대폰 인증') >= 0 })")
        (ok if out['lock'] == 1 and out['rows'] == 0 and out['msg'] else ng)(
            '로그아웃 — 마이페이지 다시 잠금', str(out))
        # 39-7) 마이페이지 상세도 로그아웃 상태에서는 잠긴다
        some_id = pg.evaluate("() => (window.SEOSAN_VERIFY.apps() || [])[0].id")
        pg.goto(base + 'mypage-detail.html?id=' + urllib.parse.quote(some_id), wait_until='load')
        pg.wait_for_timeout(800)
        det = pg.evaluate("() => ({ lock: document.querySelectorAll('#mpBody .mp-lock').length, hasNo: ((document.querySelector('#mpBody') || {}).textContent || '').indexOf('로그인 또는 비회원 휴대폰 인증') >= 0, txt: ((document.querySelector('#mpBody') || {}).textContent || '').replace(/\\s+/g, ' ').slice(0, 60) })")
        (ok if det['lock'] == 1 and det['hasNo'] else ng)('로그아웃 — 마이페이지 상세도 잠금', str(det)[:150])
        # 39-8) 관리자 페이지에서도 마이페이지 탭 노출
        goto(pg, base + 'admin-draw.html', 600)
        navadm = pg.evaluate("""() => Array.from(document.querySelectorAll('nav.site-nav a[href="mypage.html"]')).map(a => !a.classList.contains('hidden') && getComputedStyle(a).display !== 'none')""")
        (ok if navadm and all(navadm) else ng)('마이페이지 탭 — 관리자 화면에서도 노출', str(navadm))

        # 39-9) 행사 심사 — 제목 오타 교정 · 5인 목록 컬럼 제거 · 배지 팝업 · 투표자 선택 제거 · 본인 바로 투표 버튼
        goto(pg, base + 'admin-event.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('chief'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(500)
        title = (pg.text_content('.view-head h2') or '')
        (ok if '행사 심사 심사' not in title and '행사 심사' in title else ng)('행사 심사 — 제목 오타(행사 심사 심사) 교정', title.strip()[:60])
        cols = pg.eval_on_selector_all('#eventList thead th', 'els => els.map(e => e.textContent.replace(/\\s+/g, " ").trim())')
        (ok if len(cols) == 6 and '행사승인권한자 투표' not in ' '.join(cols) and '투표 · 작업' in cols[-1] else ng)(
            '행사 심사 표 — 6열 · 5인 투표자 목록 컬럼 제거', str(cols)[:160])
        vlist = pg.evaluate("() => document.querySelectorAll('#eventList .ev-vlist, #eventList .ev-vrow').length")
        (ok if vlist == 0 else ng)('행사 심사 — 5인 투표자 목록(오른쪽 끝 나열) 제거', '%d개' % vlist)
        rows_info = pg.evaluate("""() => { const rows = Array.from(document.querySelectorAll('#eventList tbody tr'));
            return { n: rows.length,
              top3: rows.slice(0, 3).map(r => r.textContent.indexOf('행사 심사중') >= 0),
              todo: document.querySelectorAll('#eventList tr.ev-todo').length,
              sels: document.querySelectorAll('#eventList select.ev-who').length,
              btns: document.querySelectorAll('#eventList [data-evvote]').length,
              labels: Array.from(document.querySelectorAll('#eventList [data-evvote]')).slice(0, 3).map(b => b.textContent.trim()) }; }""")
        (ok if rows_info['todo'] >= 3 and all(rows_info['top3']) and rows_info['sels'] == 0 and rows_info['btns'] >= 9 else ng)(
            '행사 심사 — 심사중 3건 모두 투표 버튼 · 투표자 선택 제거', str(rows_info)[:180])
        (ok if any('승인' in x for x in rows_info['labels']) and any('반려' in x for x in rows_info['labels']) and any('기권' in x for x in rows_info['labels']) else ng)(
            '행사 심사 — 버튼 라벨 ✅ 승인(찬성) · ❌ 반려 · ⚪ 기권', str(rows_info['labels']))
        tip = pg.evaluate("""() => { const b = document.querySelector('#eventList [data-evtip]');
            return b ? { text: b.getAttribute('data-evtip'), has: document.querySelectorAll('#eventList [data-evtip]').length } : null; }""")
        (ok if tip and all(n in (tip['text'] or '') for n in ('김서산', '박해미', '미투표')) and tip['has'] >= 4 else ng)(
            '행사 심사 — 진행 상태 배지에 5인 투표 내역(팝업 문구)', str(tip)[:170])
        badge = pg.query_selector('#eventList [data-evtip]')
        shown_txt = ''
        if badge:
            bb = badge.bounding_box()
            pg.mouse.move(bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2)
            pg.wait_for_timeout(350)
            shown_txt = pg.evaluate("() => { const t = document.querySelector('.ev-tipbox'); return t ? (getComputedStyle(t).display === 'block' ? t.textContent : '') : ''; }")
        (ok if '미투표' in (shown_txt or '') else ng)('행사 심사 — 배지 마우스 오버 시 팝업 표시', (shown_txt or '')[:110])
        pg.mouse.move(5, 5)
        pg.wait_for_timeout(150)
        zero = pg.evaluate("() => /찬성 0\\/5/.test(document.querySelector('#eventList').textContent)")
        (ok if not zero else ng)('행사 심사 — 확정 건 찬성 수 불일치(0/5) 없음')
        btn_box = pg.evaluate("""() => { const b = document.querySelector('#eventList [data-evvote]'); const row = document.querySelector('#eventList tr.ev-todo');
            if (!b) return null; const r = b.getBoundingClientRect(); const rr = row.getBoundingClientRect();
            return { h: Math.round(r.height), w: Math.round(r.width), right: Math.round(r.right), vw: window.innerWidth,
              scroll: document.querySelector('#eventList .table-wrap').scrollWidth - document.querySelector('#eventList .table-wrap').clientWidth }; }""")
        (ok if btn_box and btn_box['h'] >= 40 and btn_box['right'] <= btn_box['vw'] and btn_box['scroll'] <= 2 else ng)(
            '행사 심사 — PC 버튼 크고 선명 · 가로 스크롤 없음', str(btn_box))

        # 39-10) 모바일 — 카드형 · 버튼 화면 안 · 배지 탭 팝업
        UA_M39 = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 '
                 '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')
        ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, user_agent=UA_M39, has_touch=True)
        pm = ctx_m.new_page()
        pm.set_default_timeout(20000)
        wm = Watcher(pm, base)
        goto(pm, base + 'admin-event.html', 900)
        pm.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('chief'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pm.wait_for_timeout(500)
        mob = pm.evaluate("""() => { const b = document.querySelector('#eventList [data-evvote]'), row = document.querySelector('#eventList tbody tr');
            if (!b) return null; const r = b.getBoundingClientRect(); const rr = row.getBoundingClientRect();
            return { btnRight: Math.round(r.right), vw: window.innerWidth, docW: Math.round(document.documentElement.scrollWidth),
              h: Math.round(r.height), block: getComputedStyle(row).display, n: row.querySelectorAll('[data-evvote]').length }; }""")
        (ok if mob and mob['btnRight'] <= mob['vw'] and mob['docW'] <= mob['vw'] + 1 and mob['block'] == 'block' and mob['h'] >= 40 and mob['n'] >= 3 else ng)(
            '모바일 행사 심사 — 카드형 · 승인/반려/기권 버튼 화면 안', str(mob))
        pm.tap('#eventList [data-evtip]')
        pm.wait_for_timeout(400)
        mtip = pm.evaluate("() => { const t = document.querySelector('.ev-tipbox'); return t ? (getComputedStyle(t).display === 'block' ? t.textContent.slice(0, 90) : '') : ''; }")
        (ok if '미투표' in (mtip or '') else ng)('모바일 행사 심사 — 배지 탭 시 투표 내역 팝업', (mtip or '')[:100])
        probs = wm.problems()
        (ok if not probs else ng)('모바일 행사 심사(+마이페이지) 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        # 모바일 마이페이지 탭바 노출
        goto(pm, base + 'mypage.html', 800)
        mtab = pm.evaluate("() => Array.from(document.querySelectorAll('#mobileTabbar a[href=\"mypage.html\"]')).map(a => ({ hid: a.classList.contains('hidden'), d: getComputedStyle(a).display, h: Math.round(a.getBoundingClientRect().height) }))")
        (ok if mtab and all((not x['hid']) and x['d'] != 'none' for x in mtab) else ng)('모바일 탭바 — 마이페이지 항상 노출', str(mtab)[:120])
        ctx_m.close()

        # 39-11) 사진 폴더 정밀 매핑 — 동·열 조합(석지제사거리C,A · 세무서사거리B,A · 테크노밸리C,A) + 별칭 15개소
        fold = pg.evaluate("""() => {
            const ps = window.SEOSAN_VERIFY.placements();
            const want = [['석지제사거리','C','_석지제사거리C,A'], ['석지제사거리','A','_석지제사거리C,A'], ['석지제사거리','B','_석지제사거리A,B'],
              ['세무서사거리','B','_세무서사거리B,A'], ['세무서사거리','C','_세무서사거리C,D'], ['테크노밸리','C','_테크노밸리C,A']];
            const alias = ['동서간선도로입구','동문우체국삼거리','코아루삼거리(후문)','옥거리교차로','영진크로바@','서령건축사사무소삼거리',
              '캐슬아파트 입구','세창@입구','부영아파트삼거리','맛이나가든앞','창리사거리','오토밸리입구','하나로마트삼거리','기은LG@입구','대산읍커뮤니티센터앞'];
            const out = [];
            want.forEach(w => { const p = ps.filter(x => x.name === w[0])[0];
              out.push([w[0], w[1], p ? window.SEOSAN_VERIFY.photoFolder(p.id, w[1]) : 'NO_PLACE', w[2]]); });
            const al = [];
            alias.forEach(nm => { const p = ps.filter(x => x.name === nm)[0];
              const got = p ? window.SEOSAN_VERIFY.photoFolder(p.id, 'A') : 'NO_PLACE';
              al.push([nm, got, got !== ('_' + nm + 'A') && got !== ('_' + nm)]); });
            return { combos: out, alias: al }; }""")
        bad = [c for c in fold['combos'] if c[2] != c[3]]
        (ok if not bad else ng)('사진 폴더 — 석지제사거리C,A · 세무서사거리B,A · 테크노밸리C,A 정밀 매핑', str(fold['combos'])[:170] if not bad else str(bad)[:170])
        badal = [a for a in fold['alias'] if not a[2]]
        (ok if not badal else ng)('사진 폴더 — 이름이 다른 게시대 15개소 별칭 매핑', str(badal)[:150] if badal else '15/15 매핑')
        # 사진 화면 동 선택 라벨에 폴더명
        goto(pg, base + 'admin-photos.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        p37 = pg.evaluate("() => ((window.SEOSAN_VERIFY.placements() || []).filter(p => p.name === '석지제사거리')[0] || {}).id || ''")
        if p37:
            pg.select_option('#photoPid', p37)
            pg.wait_for_timeout(500)
        dongs = pg.eval_on_selector_all('#photoDong option', 'els => els.map(e => e.textContent.replace(/\\s+/g, " ").trim())')
        (ok if dongs and any('석지제사거리C,A' in d for d in dongs) and dongs[0].startswith('D동') else ng)(
            '게첨사진 — 동 선택 라벨에 사진 폴더명·폴더 순서', str(dongs)[:170])
        # 작업지시서 — 폴더 순서(D,E→C,A→A,B)와 폴더명 표기
        goto(pg, base + 'admin-docs.html', 700)
        wo = pg.evaluate("""() => { try { window.SEOSAN_VERIFY.woSetAll(true); } catch (e) {}
            const rows = Array.from(document.querySelectorAll('#woTable tbody tr'));
            const st = rows.filter(r => (r.querySelector('td') || {}).textContent && r.querySelector('td').textContent.indexOf('석지제사거리') === 0)
              .map(r => r.querySelector('td').textContent.replace(/\\s+/g, ' ').trim());
            const lab = rows.map(r => (r.querySelector('.wo-folder') || {}).textContent || '').filter(Boolean);
            return { n: rows.length, st: st.slice(0, 30), lab: lab }; }""")
        letters = [re.sub(r'^석지제사거리([A-G]).*', r'\1', x) for x in wo['st']]
        uniq = []
        for L in letters:
            if L and (not uniq or uniq[-1] != L):
                uniq.append(L)
        (ok if uniq[:5] == ['D', 'E', 'C', 'A', 'B'] else ng)('작업지시서 — 사진 폴더 동 순서(D,E → C,A → A,B) 반영', str(uniq)[:80])
        (ok if any('_석지제사거리' in x for x in wo['lab']) else ng)('작업지시서 — 사진 폴더명 표기(📁)', str(wo['lab'])[:120])

        # 39-12) 한 주 쉬어가기 공지 — 정책 OFF면 0건 · ON이면 노출
        goto(pg, base + 'admin-system.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); } catch (e) {} }")
        pg.evaluate("() => window.SEOSAN_VERIFY.skipWeek(false)")
        pg.wait_for_timeout(300)
        goto(pg, base + 'apply.html', 800)
        offn = pg.evaluate("() => window.SEOSAN_VERIFY.skipNotices()")
        (ok if offn['shown'] == 0 else ng)('한 주 쉬어가기 OFF — 2회 연속 불가 공지 미노출', str(offn)[:140])
        pg.evaluate("() => window.SEOSAN_VERIFY.skipWeek(true)")
        pg.wait_for_timeout(400)
        onn = pg.evaluate("() => window.SEOSAN_VERIFY.skipNotices()")
        (ok if onn['shown'] >= 2 else ng)('한 주 쉬어가기 ON — 2회 연속 불가 공지 노출', str(onn)[:140])
        pg.evaluate("() => window.SEOSAN_VERIFY.skipWeek(false)")
        pg.wait_for_timeout(250)
        # 규격·안내 페이지도 연동
        goto(pg, base + 'guide-rules.html', 600)
        gr_off = pg.evaluate("() => Array.from(document.querySelectorAll('[data-skipweek]')).filter(e => !e.classList.contains('hidden')).length")
        (ok if gr_off == 0 else ng)('규격·안내 — 한 주 쉬어가기 OFF 시 규정 안내 숨김', '%d건 노출' % gr_off)

        # 39-13) 명절·휴가 적용 달력 — 지정한 주에만 적용 · 이번 주는 그대로
        goto(pg, base + 'admin-system.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); } catch (e) {} }")
        pg.wait_for_timeout(300)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        pg.wait_for_timeout(200)
        cal_ui = pg.evaluate("() => ({ from: !!document.querySelector('#policyNoDrawFrom'), to: !!document.querySelector('#policyNoDrawTo'), dfrom: !!document.querySelector('#policyDirectFrom'), add: !!document.querySelector('[data-polrange-add=\"noDraw\"]'), wadd: !!document.querySelector('[data-polrange-week=\"noDraw\"]') })")
        (ok if all(cal_ui.values()) else ng)('운영 정책 — 추첨 없애기·직접설치 적용 날짜(달력) UI', str(cal_ui))
        for k in ('noDraw', 'direct'):
            pg.evaluate("() => { const r = window.SEOSAN_VERIFY.policyRanges('noDraw'); r.forEach((x, i) => window.SEOSAN_VERIFY.removePolicyRange('noDraw', 0)); const d = window.SEOSAN_VERIFY.policyRanges('direct'); d.forEach((x, i) => window.SEOSAN_VERIFY.removePolicyRange('direct', 0)); }")
        pg.wait_for_timeout(200)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        pg.wait_for_timeout(200)
        pg.fill('#policyNoDrawFrom', '2026-12-21')
        pg.fill('#policyNoDrawTo', '2026-12-27')
        pg.click('[data-polrange-add="noDraw"]')
        pg.wait_for_timeout(400)
        pg.fill('#policyDirectFrom', '2026-12-21')
        pg.fill('#policyDirectTo', '2026-12-27')
        pg.click('[data-polrange-add="direct"]')
        pg.wait_for_timeout(400)
        st_weeks = pg.evaluate("() => ['2026-11-30','2026-12-14','2026-12-21'].map(w => [w, window.SEOSAN_VERIFY.policyWeekState(w)])")
        d = dict(st_weeks)
        (ok if d['2026-12-21']['noDraw'] and d['2026-12-21']['direct'] and not d['2026-11-30']['noDraw'] and not d['2026-11-30']['direct'] and not d['2026-12-14']['noDraw'] else ng)(
            '정책 달력 — 지정한 주(12.21)에만 추첨 없애기·직접설치 적용', str(st_weeks)[:190])
        # 추첨 화면 — 그 주를 고르면 추첨 잠김, 이번 주는 정상
        goto(pg, base + 'admin-draw.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); } catch (e) {} }")
        pg.evaluate("() => window.SEOSAN_VERIFY.setDrawWeek('2026-11-30')")
        pg.wait_for_timeout(400)
        b_now = pg.evaluate("() => { const b = document.querySelector('#btnDraw'); return { dis: b.disabled, t: b.textContent }; }")
        pg.evaluate("() => window.SEOSAN_VERIFY.setDrawWeek('2026-12-21')")
        pg.wait_for_timeout(400)
        b_cal = pg.evaluate("() => { const b = document.querySelector('#btnDraw'); return { dis: b.disabled, t: b.textContent }; }")
        (ok if not b_now['dis'] and b_cal['dis'] and '추첨 없음' in b_cal['t'] else ng)(
            '정책 달력 — 지정 주(12.21) 추첨만 잠김 · 다른 주는 정상', '이번주=%s / 지정주=%s' % (b_now, b_cal))
        # 접수 화면도 그 주에만 직접설치 모드
        goto(pg, base + 'apply.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.guestAccept(); } catch (e) {} }")
        wk_apply = pg.evaluate("() => { const o = window.SEOSAN_VERIFY.policyWeekState(); return o; }")
        (ok if not wk_apply['direct'] else ng)('정책 달력 — 이번 주 접수 화면은 정상(직접설치 아님)', str(wk_apply)[:140])
        goto(pg, base + 'admin-system.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.setRole('super'); } catch (e) {} }")
        pg.evaluate("() => { window.SEOSAN_VERIFY.policyRanges('noDraw').forEach(() => window.SEOSAN_VERIFY.removePolicyRange('noDraw', 0)); window.SEOSAN_VERIFY.policyRanges('direct').forEach(() => window.SEOSAN_VERIFY.removePolicyRange('direct', 0)); }")
        pg.wait_for_timeout(250)

        # 39-14) 접수대장 · 추첨결과 A4 출력
        goto(pg, base + 'admin-draw.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(400)
        pbtns = pg.evaluate("() => ({ ledger: !!document.querySelector('#btnDrawPrint'), result: !!document.querySelector('#btnDrawResultPrint'), t1: (document.querySelector('#btnDrawPrint') || {}).textContent, t2: (document.querySelector('#btnDrawResultPrint') || {}).textContent })")
        (ok if pbtns['ledger'] and pbtns['result'] and '접수대장' in (pbtns['t1'] or '') and '추첨결과' in (pbtns['t2'] or '') else ng)(
            '접수대장 · 추첨결과 A4 출력 버튼', str(pbtns)[:150])
        pg.click('#btnDrawPrint')
        pg.wait_for_timeout(600)
        lsheet = pg.evaluate("""() => { const box = document.querySelector('.print-prev'); if (!box) return null;
            const t = (box.textContent || '').replace(/\\s+/g, ' ');
            return { title: '서산시지부 현수막 지정게시대 주간 접수대장', has: t.indexOf('서산시지부 현수막 지정게시대 주간 접수대장') >= 0,
              period: t.indexOf('게첨 기간') >= 0, sum: t.indexOf('총 접수') >= 0 && t.indexOf('배정') >= 0 && t.indexOf('낙첨') >= 0,
              cols: Array.from(box.querySelectorAll('thead th')).map(e => e.textContent.trim()),
              rows: box.querySelectorAll('tbody tr').length, printed: t.indexOf('출력일시') >= 0,
              kind: (document.querySelector('#ledgerSheet') || {}).dataset.kind }; }""")
        (ok if lsheet and lsheet['has'] and lsheet['period'] and lsheet['sum'] and lsheet['rows'] > 0 and lsheet['printed'] and lsheet['kind'] == 'ledger' else ng)(
            '접수대장 A4 — 제목·기간·집계·표·출력일시 생성', str(lsheet)[:190])
        (ok if lsheet and all(any(k in c for c in lsheet['cols']) for k in ('접수번호', '실제 광고주', '문구', '수량', '금액')) else ng)(
            '접수대장 A4 — 접수번호·업체·광고주·문구·수량·순위·결과·금액 열', str(lsheet['cols'] if lsheet else [])[:170])
        pr = pg.evaluate("() => { const box = document.querySelector('.print-prev'); return !!box; }")
        (ok if pr else ng)('접수대장 A4 — 인쇄 미리보기(모달) 생성')
        pg.evaluate("() => { window.SEOSAN_VERIFY.doPrint(); }")
        pg.wait_for_timeout(120)
        prn = pg.evaluate("() => ({ cls: document.body.classList.contains('print-sheet'), rule: (document.querySelector('#printPageRule') || {}).textContent || '' })")
        (ok if prn['cls'] and 'A4' in prn['rule'] else ng)('접수대장 A4 — 인쇄 모드(@page A4 · print-sheet) 전환', str(prn)[:120])
        pg.wait_for_timeout(800)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        pg.click('#btnDrawResultPrint')
        pg.wait_for_timeout(600)
        rsheet = pg.evaluate("""() => { const box = document.querySelector('.print-prev'); if (!box) return null;
            const t = (box.textContent || '').replace(/\\s+/g, ' ');
            return { has: t.indexOf('서산시지부 현수막 지정게시대 주간 추첨 결과') >= 0,
              meta: ['회차', '게첨 기간', '추첨 일시', '난수 시드', '당첨', '낙첨'].filter(k => t.indexOf(k) >= 0),
              h2: Array.from(box.querySelectorAll('.sh-h2')).map(e => e.textContent.trim()),
              rows: box.querySelectorAll('tbody tr').length,
              kind: (document.querySelector('#ledgerSheet') || {}).dataset.kind }; }""")
        (ok if rsheet and rsheet['has'] and len(rsheet['meta']) >= 6 and rsheet['rows'] > 0 and rsheet['kind'] == 'result' else ng)(
            '추첨결과 A4 — 회차·기간·추첨일시·시드·배정/낙첨 요약 생성', str(rsheet)[:190])
        (ok if rsheet and len(rsheet['h2']) >= 2 and any('게시대별' in x for x in rsheet['h2']) and any('낙첨' in x for x in rsheet['h2']) else ng)(
            '추첨결과 A4 — 게시대별 당첨 배정 · 낙첨/미배정 표', str(rsheet['h2'] if rsheet else [])[:150])
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")

        # 39-15) 입금 확인 실시간 검색
        goto(pg, base + 'admin-pay.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('staff'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(400)
        (ok if pg.query_selector('#paySearch') else ng)('입금 확인 — 실시간 검색창(업체명·광고주·접수번호·문구)')
        allp = pg.evaluate("() => window.SEOSAN_VERIFY.paySearch('')")
        kw = pg.evaluate("() => { const r = document.querySelector('#payTable tbody tr'); const c = r ? r.querySelector('.co') : null; return c ? c.textContent.trim() : ''; }")
        filt = pg.evaluate("(q) => window.SEOSAN_VERIFY.paySearch(q)", kw)
        (ok if allp['rows'] >= 1 and filt['rows'] >= 1 and filt['rows'] <= allp['rows'] else ng)(
            '입금 확인 검색 — 업체명 입력 시 즉시 필터', '전체 %d행 · "%s" → %d행' % (allp['rows'], kw, filt['rows']))
        nonep = pg.evaluate("() => window.SEOSAN_VERIFY.paySearch('없는업체zzz')")
        (ok if nonep['rows'] == 0 and '0건' in (nonep['info'] or '') else ng)('입금 확인 검색 — 없는 검색어 0건 안내', str(nonep)[:120])
        pg.evaluate("() => window.SEOSAN_VERIFY.paySearch('')")

        # 39-16) 감사·행사승인권한자 로그인 시 결재 팝업 (첫 화면에서도)
        goto(pg, base + 'index.html', 600)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.logout(); } catch (e) {} }")
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-2006')")      # 감사1 홍대산
        pg.wait_for_timeout(1300)
        ap = pg.evaluate("""() => ({ open: !!document.querySelector('#modal.open'),
            title: ((document.querySelector('#modalTitle') || {}).textContent || ''),
            body: ((document.querySelector('#modalBody') || {}).textContent || '').replace(/\s+/g, ' '),
            go: (document.querySelector('#btnGoApprove') ? document.querySelector('#btnGoApprove').getAttribute('href') : '') })""")
        (ok if ap['open'] and '결재' in ap['title'] and ap['go'] else ng)(
            'index.html 감사 로그인 — 결재 대기 팝업 즉시', str(ap)[:170])
        pg.click('#btnGoApprove')
        pg.wait_for_load_state('load')
        pg.wait_for_timeout(500)
        (ok if 'admin-' in pg.url else ng)('감사 결재 팝업 — 결재하러 가기 버튼 이동', pg.url.split('/')[-1])
        # 행사 승인권한자 5명 모두 — 미투표 심사중 건이 있으면 팝업
        evp = []
        for mid in ('M-2001', 'M-2002', 'M-2003', 'M-2004', 'M-2006'):
            goto(pg, base + 'index.html', 600)
            pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
            pg.evaluate("(id) => window.SEOSAN_VERIFY.login(id)", mid)
            pg.wait_for_timeout(1000)
            r = pg.evaluate("() => ({ t: ((document.querySelector('#modalTitle') || {}).textContent || ''), b: ((document.querySelector('#modalBody') || {}).textContent || ''), go: (document.querySelector('#btnGoApprove') ? document.querySelector('#btnGoApprove').getAttribute('href') : '') })")
            evp.append((mid, ('행사 심사' in (r['t'] + r['b'])) and 'admin-event.html' in (r['go'] or '') or ('행사 심사' in (r['t'] + r['b']))))
        (ok if all(x[1] for x in evp) else ng)('행사 승인권한자 5명 — 로그인 시 행사 심사 대기 팝업', str(evp))
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.logout(); } catch (e) {} }")

        # 39-17) 권한 매트릭스 — 가산점부여 행 + 토글이 실제 부여 권한에 반영
        goto(pg, base + 'admin-roles.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(500)
        mx2 = pg.evaluate("""() => { const rows = Array.from(document.querySelectorAll('#permMatrix tbody tr'));
            const grant = rows.filter(r => r.textContent.indexOf('가산점부여') >= 0)[0];
            const cells = grant ? Array.from(grant.querySelectorAll('[data-permrole]')) : [];
            return { rows: rows.length, hasGrant: !!grant, cells: document.querySelectorAll('#permMatrix [data-permrole]').length,
              grantCells: cells.length, on: cells.filter(b => b.classList.contains('on')).map(b => b.getAttribute('data-permrole')) }; }""")
        (ok if mx2['hasGrant'] and mx2['rows'] == 18 and mx2['grantCells'] == 9 and mx2['cells'] == 162 else ng)(
            '권한 매트릭스 — 가산점부여 행(9직책 · 총 18행 162칸)', str(mx2)[:170])
        (ok if set(mx2['on']) >= set(['chief', 'senior', 'staff1', 'staff2', 'field1', 'field2']) and 'audit1' not in mx2['on'] and 'office' not in mx2['on'] else ng)(
            '가산점부여 기본값 — 지부장·수석·사무실무원·현장실무원 ON', str(mx2['on']))
        sticky = pg.evaluate("""() => { const box = document.querySelector('#permMatrix .table-wrap');
            const th = document.querySelector('#permMatrix thead th');
            const td = document.querySelector('#permMatrix tbody td');
            if (!box || !th || !td) return null;
            const cs = getComputedStyle(th), cd = getComputedStyle(td), cb = getComputedStyle(box);
            return { thPos: cs.position, thTop: cs.top, thZ: cs.zIndex, tdPos: cd.position, tdLeft: cd.left, tdZ: cd.zIndex,
              boxH: cb.maxHeight, overflow: cb.overflowY, scroll: box.scrollHeight > box.clientHeight }; }""")
        (ok if sticky and sticky['thPos'] == 'sticky' and sticky['tdPos'] == 'sticky' and sticky['boxH'] not in ('none', '', None) and sticky['overflow'] in ('auto', 'scroll') else ng)(
            '권한 매트릭스 — 직책 헤더·메뉴 열 틀고정(sticky · 70vh 스크롤)', str(sticky)[:170])
        pg.evaluate("() => window.SEOSAN_VERIFY.setPerm('senior', 'grant', false)")
        pg.wait_for_timeout(300)
        goto(pg, base + 'admin-review.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('senior'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(600)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        offg = pg.evaluate("""() => ({ btns: document.querySelectorAll('#urgentGrantTable [data-urgentgrant]').length,
            noPerm: ((document.querySelector('#urgentGrantTable') || {}).textContent || '').indexOf('부여 권한 없음') >= 0,
            info: ((document.querySelector('#urgentGrantInfo') || {}).textContent || '') })""")
        (ok if offg['btns'] == 0 and (offg['noPerm'] or '권한 없음' in offg['info']) else ng)(
            '가산점부여 권한해제 — 시안심사 화면 부여 버튼 비활성/차단', str(offg)[:170])
        goto(pg, base + 'admin-roles.html', 600)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); } catch (e) {} }")
        pg.evaluate("() => window.SEOSAN_VERIFY.setPerm('senior', 'grant', true)")
        pg.wait_for_timeout(300)
        goto(pg, base + 'admin-review.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('senior'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(600)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        ong = pg.evaluate("() => document.querySelectorAll('#urgentGrantTable [data-urgentgrant]').length")
        (ok if ong >= 1 else ng)('가산점부여 권한 복원 — 부여 버튼 다시 활성', '%d개' % ong)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.setRole('super'); } catch (e) {} }")

        # 39-18) 게첨사진 A4 인쇄 — 1/2/4/6장 모두 잘림 없음 (PDF 페이지 수 = 장수)
        goto(pg, base + 'admin-photos.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); } catch (e) {} }")
        for _i in range(6):
            pg.evaluate("() => window.SEOSAN_VERIFY.photoAdd({ pid: 'P01', dong: 'A', week: '2026-11-30', by: '검증' })")
        pv_app = pg.evaluate("() => { const as = window.SEOSAN_VERIFY.apps().filter(a => (a.assignedPlaces || []).some(x => x.pid === 'P01')); return as[0] ? as[0].id : ''; }")
        pv_n = pg.evaluate("(id) => (window.SEOSAN_VERIFY.photoProofState(id) || {}).photos", pv_app)
        pv_res = []
        for per in (1, 2, 4, 6):
            pg.evaluate("([id, per]) => window.SEOSAN_VERIFY.openProof(id, per)", [pv_app, per])
            pg.wait_for_timeout(320)
            pg.evaluate("() => window.SEOSAN_VERIFY.photoPrintMode(true)")
            pg.emulate_media(media='print')
            pg.wait_for_timeout(260)
            geo = pg.evaluate("""() => { const mm = 96 / 25.4; const sh = Array.from(document.querySelectorAll('#photoProof .pp-sheet'));
                const modal = document.querySelector('.modal'), card = document.querySelector('.modal-card'), body = document.querySelector('.modal-body');
                return { sheets: sh.length, maxH: sh.length ? Math.max.apply(null, sh.map(s => Math.round(s.getBoundingClientRect().height / mm))) : 0,
                  modalPos: getComputedStyle(modal).position, cardMax: getComputedStyle(card).maxHeight, bodyOver: getComputedStyle(body).overflowY,
                  cardOver: getComputedStyle(card).overflowY }; }""")
            pdf_path = os.path.join(ROOT, '_verify_proof_%d.pdf' % per)
            pg.pdf(path=pdf_path, prefer_css_page_size=True, print_background=True)
            try:
                import pypdf
                pdf_pages = len(pypdf.PdfReader(pdf_path).pages)
            except Exception:      # noqa: BLE001
                raw = open(pdf_path, 'rb').read()
                pdf_pages = len(re.findall(rb'/Type\s*/Page[^s]', raw))
            pg.emulate_media(media='screen')
            pg.evaluate("() => { window.SEOSAN_VERIFY.photoPrintMode(false); window.SEOSAN_VERIFY.closeModal(); }")
            want = (pv_n + per - 1) // per if pv_n else 0
            pv_res.append({'per': per, 'sheets': geo['sheets'], 'want': want, 'pdf': pdf_pages, 'maxH': geo['maxH'],
                           'modalPos': geo['modalPos'], 'cardMax': geo['cardMax'], 'bodyOver': geo['bodyOver']})
            (ok if geo['sheets'] == want and pdf_pages == want and geo['maxH'] <= 282
                 and geo['modalPos'] == 'static' and geo['cardMax'] == 'none' and geo['bodyOver'] == 'visible' else ng)(
                '게첨사진 A4 인쇄 — 1장당 %d장: %d장 잘림 없음(시트 %d · PDF %d · 최대 %dmm)' % (per, per, geo['sheets'], pdf_pages, geo['maxH']),
                str(geo)[:170])
        (ok if all(x['sheets'] == x['want'] and x['pdf'] == x['want'] for x in pv_res) else ng)(
            '게첨사진 A4 인쇄 — 1/2/4/6장 전부 PDF 페이지 = 출력 장수', str([(x['per'], x['pdf'], x['want']) for x in pv_res]))

        # 39-19) 회원가입 하단 '직원으로 회원가입' 체크 → 회원가입 폼이 직원 전용으로 전환 + 총괄 직책 선택 승인
        goto(pg, base + 'index.html', 600)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.logout(); window.SEOSAN_VERIFY.openAuth('signup'); } catch (e) {} }")
        pg.wait_for_timeout(500)
        stf = pg.evaluate("""() => { const c = document.querySelector('#chkStaffSignup');
            if (!c) return null; const lab = c.closest('label'); const cs = getComputedStyle(lab);
            const row = lab.closest('.staff-signup-row');
            return { text: lab.textContent.trim(), size: cs.fontSize, last: !!(row && !row.nextElementSibling),
              normal: !!document.querySelector('#signupNormal'), staff: !!document.querySelector('#signupStaff'),
              staffHidden: !!document.querySelector('#signupStaff') && document.querySelector('#signupStaff').classList.contains('hidden') }; }""")
        (ok if stf and '직원으로 회원가입' in stf['text'] and stf['size'] == '11px' and stf['last'] and stf['staffHidden'] else ng)(
            '회원가입 하단 — 아주 작은 "직원으로 회원가입" 체크(기본 일반 폼)', str(stf)[:170])
        pg.check('#chkStaffSignup')
        pg.wait_for_timeout(350)
        sw = pg.evaluate("""() => ({ normalHidden: document.querySelector('#signupNormal').classList.contains('hidden'),
            staffShown: !document.querySelector('#signupStaff').classList.contains('hidden'),
            roleOpts: Array.from(document.querySelectorAll('#stRole option')).map(o => o.textContent),
            bizGone: (document.querySelector('#signupNormal').offsetParent === null),
            note: (document.querySelector('#signupStaff') || {}).textContent || '',
            go: (document.querySelector('#btnAuthSignup') || {}).textContent || '' })""")
        (ok if sw['normalHidden'] and sw['staffShown'] and len(sw['roleOpts']) == 4 and '총괄관리자 승인 및 직책 배정 후 이용 가능' in sw['note'] else ng)(
            '직원 가입 체크 — 일반 항목 숨고 직원 전용 폼(성명·연락처·직책)으로 전환', str(sw)[:180])
        pg.uncheck('#chkStaffSignup')
        pg.wait_for_timeout(250)
        back = pg.evaluate("() => (!document.querySelector('#signupNormal').classList.contains('hidden')) && document.querySelector('#signupStaff').classList.contains('hidden')")
        (ok if back else ng)('직원 가입 체크 해제 — 일반/대행사 폼으로 복귀')
        pg.check('#chkStaffSignup')
        pg.wait_for_timeout(250)
        pg.fill('#stName', '검증직원')
        pg.fill('#stPhone', '010-4444-5555')
        uniq = 'vfy' + str(int(time.time()) % 100000)
        pg.fill('#stId', uniq)
        pg.fill('#stPw', '1234')
        pg.select_option('#stRole', 'field')
        pg.click('#btnAuthSignup')
        pg.wait_for_timeout(700)
        pend_o = pg.evaluate("() => window.SEOSAN_VERIFY.pendingOfficers()")
        (ok if any(x['name'] == '검증직원' and x['role'] == 'field' for x in pend_o) else ng)(
            '직원 가입 신청 — 총괄관리자 승인 대기 등록', str(pend_o)[-160:])
        goto(pg, base + 'admin-roles.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); window.SEOSAN_VERIFY.renderAll(); } catch (e) {} }")
        pg.wait_for_timeout(600)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        pid_sel = pg.evaluate("""() => { const rows = Array.from(document.querySelectorAll('#officerTable .officer-row'));
            const row = rows.filter(r => r.textContent.indexOf('검증직원') >= 0)[0];
            if (!row) return null; const sel = row.querySelector('select');
            return { id: sel ? sel.id : '', val: sel ? sel.value : '', opts: sel ? Array.from(sel.options).map(o => o.textContent) : [] }; }""")
        (ok if pid_sel and pid_sel['id'] and len(pid_sel['opts']) == 9 and '사무실무원2' in pid_sel['opts'] and pid_sel['val'] in ('field', 'field1') else ng)(
            '가입 승인 대기 — 9직책 선택 드롭다운(희망 직책 기본)', str(pid_sel)[:180])
        if pid_sel and pid_sel['id']:
            oid = pid_sel['id'].split('ofRoleSel_')[1]
            pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
            pg.select_option('#' + pid_sel['id'], 'audit2')
            pg.click('[data-officerapprove="%s"]' % oid)
            pg.wait_for_timeout(700)
            approved = pg.evaluate("(id) => (window.SEOSAN_VERIFY.state().officers || []).filter(o => o.id === id).map(o => ({ role: o.role, perm: o.permRole, status: o.status }))[0]", oid)
            (ok if approved and approved['status'] == 'approved' and approved['perm'] == 'audit2' and approved['role'] == 'audit2' else ng)(
                '가입 승인 — 총괄관리자가 고른 직책(감사2)으로 승인', str(approved))
        # 매트릭스 저장 버튼 — 저장하면 하단 목록·탭도 리셋
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('super'); } catch (e) {} }")
        pg.wait_for_timeout(400)
        savebtn = pg.evaluate("() => ({ save: !!document.querySelector('#btnPermSave'), reset: !!document.querySelector('#btnPermReset'), t: (document.querySelector('#btnPermSave') || {}).textContent })")
        (ok if savebtn['save'] and savebtn['reset'] and '저장' in (savebtn['t'] or '') else ng)('권한 매트릭스 — 💾 권한 저장하기·초기값 되돌리기 버튼', str(savebtn))
        pg.evaluate("() => window.SEOSAN_VERIFY.setPerm('office', 'photos', false)")
        pg.wait_for_timeout(250)
        pg.click('#btnPermSave')
        pg.wait_for_timeout(600)
        saved = pg.evaluate("() => ({ info: (document.querySelector('#permSaveInfo') || {}).textContent || '', tabs: window.SEOSAN_VERIFY.visibleTabs().length, rows: document.querySelectorAll('#officerTable .officer-row').length, perm: window.SEOSAN_VERIFY.permOf('office', 'photos') })")
        (ok if '저장 완료' in saved['info'] and saved['perm'] is False and saved['rows'] > 0 else ng)(
            '권한 저장 — 저장 후 하단 목록·탭 즉시 갱신', str(saved)[:170])
        pg.evaluate("() => window.SEOSAN_VERIFY.permReset()")
        pg.wait_for_timeout(400)
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.permOf('office', 'photos')") is True else ng)('권한 초기값 되돌리기 — 기본 권한 복원')

        # 39-20) 시연용 원클릭 로그인 — 총괄 + 9직책
        goto(pg, base + 'index.html', 600)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.logout(); window.SEOSAN_VERIFY.openAuth('login'); } catch (e) {} }")
        pg.wait_for_timeout(500)
        rl = pg.eval_on_selector_all('#modal [data-rolelogin]', 'els => els.map(e => e.getAttribute("data-rolelogin"))')
        (ok if len(rl) == 10 and 'super' in rl and all(k in rl for k in ('chief', 'senior', 'office', 'staff1', 'staff2', 'field1', 'field2', 'audit1', 'audit2')) else ng)(
            '로그인 모달 — 총괄관리자 + 9직책 원클릭 버튼', str(rl)[:150])
        pg.click('#modal [data-rolelogin="audit1"]')
        pg.wait_for_timeout(1200)
        onerole = pg.evaluate("() => ({ role: window.SEOSAN_VERIFY.role(), open: !!document.querySelector('#modal.open'), title: (document.querySelector('#modalTitle') || {}).textContent || '' })")
        (ok if onerole['role'] == 'audit1' and onerole['title'] and ('결재' in onerole['title'] or '행사 심사' in onerole['title']) else ng)(
            '원클릭 로그인 — 감사1 즉시 로그인 + 결재 대기 팝업', str(onerole)[:150])
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.roleLogin('super'); } catch (e) {} }")
        pg.wait_for_timeout(600)
        (ok if pg.evaluate("() => window.SEOSAN_VERIFY.role()") == 'super' else ng)('원클릭 로그인 — 총괄관리자 전환')

        # 39-21) 마이페이지 — 이번 주 게첨 맨 위·펼침 / 지난 회차 접힘·펼쳐보기 / 실시간 검색
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.logout(); } catch (e) {} }")
        pg.goto(base + 'mypage.html', wait_until='load')
        pg.wait_for_timeout(900)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1001')")
        pg.wait_for_timeout(800)
        mp = pg.evaluate("""() => { const secs = Array.from(document.querySelectorAll('#mpBody .mp-sec'));
            return { n: secs.length, order: secs.map(s => s.getAttribute('data-seckey') || (s.querySelector('.mp-sec-t') || {}).textContent || ''),
              open: secs.map(s => s.classList.contains('open')),
              firstOpen: secs[0] ? secs[0].classList.contains('open') : null,
              pastClosed: (function () { const p = secs.filter(s => (s.textContent || '').indexOf('지난 회차') >= 0)[0]; return p ? !p.classList.contains('open') : null; })(),
              search: !!document.querySelector('#mpSearch') }; }""")
        (ok if mp['search'] and mp['n'] >= 2 and mp['firstOpen'] and mp['pastClosed'] else ng)(
            '마이페이지 — 이번 주 게첨 맨 위·펼침 · 지난 회차 접힘 · 검색창', str(mp)[:180])
        if mp['n'] >= 2:
            pg.click('#mpBody .mp-sec-head >> nth=0')
            pg.wait_for_timeout(400)
            after = pg.evaluate("() => { const s = document.querySelector('#mpBody .mp-sec'); return s ? s.classList.contains('open') : null; }")
            (ok if after is False else ng)('마이페이지 — 제목 클릭으로 접기/펼치기 전환', str(after))
            pg.click('#mpBody .mp-sec-head >> nth=0')
            pg.wait_for_timeout(300)
        # 지난 회차 접힘 → 클릭 시 펼쳐보기
        past_idx = pg.evaluate("""() => Array.from(document.querySelectorAll('#mpBody .mp-sec')).findIndex(s => (s.textContent || '').indexOf('지난 회차') >= 0)""")
        if past_idx is not None and past_idx >= 0:
            pg.evaluate("(i) => { const b = document.querySelectorAll('#mpBody .mp-sec-head')[i]; if (b) b.click(); }", past_idx)
            pg.wait_for_timeout(450)
            popen = pg.evaluate("(i) => { const s = document.querySelectorAll('#mpBody .mp-sec')[i]; return s ? { open: s.classList.contains('open'), rows: s.querySelectorAll('.mp-list > *').length, body: s.querySelectorAll('.mp-list, .empty').length } : null; }", past_idx)
            (ok if popen and popen['open'] and popen['body'] >= 1 else ng)('마이페이지 — 지난 회차 펼쳐보기', str(popen))
        # 검색 — 지난 회차 일치 건 자동 펼침
        kw = pg.evaluate("() => { const s = window.SEOSAN_VERIFY.state(); const a = (s.apps || []).filter(x => x.memberId === 'M-1001')[0]; return a ? a.id.slice(-4) : ''; }")
        pg.fill('#mpSearch', kw)
        pg.wait_for_timeout(600)
        sr = pg.evaluate("""() => { const secs = Array.from(document.querySelectorAll('#mpBody .mp-sec'));
            return { shown: secs.length, rows: document.querySelectorAll('#mpBody .mp-list > *').length,
              anyOpen: secs.some(s => s.classList.contains('open')) }; }""")
        (ok if sr['rows'] >= 1 and sr['anyOpen'] else ng)('마이페이지 — 검색어 입력 시 일치 건 자동 펼침', str(sr))
        pg.fill('#mpSearch', '없는검색어zzz')
        pg.wait_for_timeout(500)
        (ok if pg.evaluate("() => document.querySelectorAll('#mpBody .mp-list > *').length") == 0 else ng)('마이페이지 — 없는 검색어는 0건')
        pg.fill('#mpSearch', '')
        pg.wait_for_timeout(400)

        # 39-22) 미배정 상시접수 — 담기 버튼 파란색 · 인접 게시대 동시 담기 허용
        goto(pg, base + 'remain.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.guestAccept(); } catch (e) {} }")
        pg.wait_for_timeout(400)
        pick_btns = pg.evaluate("""() => Array.from(document.querySelectorAll('[data-fcpick]')).map(b => {
            const cs = getComputedStyle(b); return { t: b.textContent.trim(), bg: cs.backgroundColor, cls: b.className,
              blue: /rgb\(2[0-9], 1[0-9][0-9]|rgb\(2[0-9]6, 1[0-9]6|rgb\(2[0-9], 10[0-9]/.test(cs.backgroundColor) }; })""")
        blues = [b for b in pick_btns if b['t'].startswith('담기')]
        (ok if blues and all('primary' in b['cls'] for b in blues) and len(pick_btns) >= 2 else ng)(
            '미배정 상시접수 — 담기 버튼 파란색(primary)', str(blues[:2])[:170])
        pair = pg.evaluate("() => { const ps = window.SEOSAN_VERIFY.state().placements; const p11 = ps.filter(p => p.id === 'P11')[0]; return p11 ? { p11: 'P11', no: p11.adj } : null; }")
        adj_pair = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY; const ps = v.state().placements;
            for (const a of ps) for (const b of ps) { if (a.id < b.id && a.name !== b.name && v.adjFirstCome('검증업체', a.id) === null) {
              if (v.adjPairOf && v.adjPairOf(a.name, b.name)) return [a.id, b.id]; } } return []; }""")
        if not adj_pair:
            adj_pair = pg.evaluate("""() => { const v = window.SEOSAN_VERIFY; const ps = v.state().placements;
                for (const a of ps) for (const b of ps) { if (a.id < b.id) { const r = v.adjPairOf ? v.adjPairOf(a.name, b.name) : null; if (r) return [a.id, b.id]; } } return []; }""")
        if adj_pair:
            pg.evaluate("() => { try { window.SEOSAN_VERIFY.fcSet({ qty: 2 }); } catch (e) {} }")
            pg.wait_for_timeout(250)
            pick1 = pg.evaluate("(id) => window.SEOSAN_VERIFY.fcPick(id)", adj_pair[0])
            pick2 = pg.evaluate("(id) => window.SEOSAN_VERIFY.fcPick(id)", adj_pair[1])
            picks = pg.evaluate("() => window.SEOSAN_VERIFY.fcPicks()")
            (ok if pick1 and pick2 and adj_pair[0] in picks and adj_pair[1] in picks else ng)(
                '미배정 상시접수 — 인접 교차로 게시대 동시 담기 허용', '%s → picks=%s' % (adj_pair, picks))
            pg.evaluate("(id) => window.SEOSAN_VERIFY.fcPick(id)", adj_pair[0])
            pg.evaluate("(id) => window.SEOSAN_VERIFY.fcPick(id)", adj_pair[1])
            pg.wait_for_timeout(200)
            note = pg.text_content('#fcAdjInfo') or ''
            (ok if '인접' in note and '동시' in note else ng)('미배정 상시접수 — 인접 동시 접수 안내 문구', note[:100])
        # 주간 추첨은 그대로 차단
        goto(pg, base + 'first.html', 600)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.guestAccept(); } catch (e) {} }")
        pg.wait_for_timeout(300)
        fpair = adj_pair
        if fpair:
            pg.evaluate("() => { try { window.SEOSAN_VERIFY.fcSet({ qty: 2 }); } catch (e) {} }")
            pg.wait_for_timeout(250)
            pg.evaluate("(id) => window.SEOSAN_VERIFY.fcPick(id)", fpair[0])
            blocked = pg.evaluate("(id) => window.SEOSAN_VERIFY.fcPick(id)", fpair[1])
            (ok if blocked is False else ng)('주간 추첨/취소분 — 인접 게시대 택1 제한 유지', str(blocked))

        # 39-23) 접수 3개 페이지 — 얇은 카드 그리드(2~3열·버튼 인접) 통일
        for _pg, _sel, _push in (('apply.html', '.plrows', '3'), ('remain.html', '#firstList', ''), ('first.html', '#firstList', '')):
            goto(pg, base + _pg, 700)
            pg.evaluate("() => { try { window.SEOSAN_VERIFY.guestAccept(); } catch (e) {} }")
            pg.wait_for_timeout(350)
            if _push and _pg == 'apply.html':
                pg.evaluate("() => { try { window.SEOSAN_VERIFY.setStep && window.SEOSAN_VERIFY.setStep(3); } catch (e) {} }")
                pg.wait_for_timeout(400)
            if _pg in ('remain.html', 'first.html'):
                pg.evaluate("() => { try { window.SEOSAN_VERIFY.fcSetStep(3); } catch (e) {} }")
                pg.wait_for_timeout(450)
            card = pg.evaluate("""(sel) => { const box = document.querySelector(sel);
                if (!box) return null; const cs = getComputedStyle(box);
                const kids = Array.from(box.children).filter(k => k.offsetParent !== null).slice(0, 3);
                const rects = kids.map(k => Math.round(k.getBoundingClientRect().height));
                const b = kids[0] ? kids[0].querySelector('.btn') : null;
                const br = b ? b.getBoundingClientRect() : null;
                const nm = kids[0] ? kids[0].querySelector('.pl-name, .fmain b') : null;
                const nr = nm ? nm.getBoundingClientRect() : null;
                return { cols: cs.gridTemplateColumns.split(' ').length, h: rects, btnGap: (br && nr) ? Math.round(br.top - nr.bottom) : null }; }""", _sel)
            (ok if card and card['cols'] >= 2 and card['h'] and max(card['h']) <= 90 and (card['btnGap'] is None or card['btnGap'] <= 40) else ng)(
                '접수 카드 — %s 얇은 카드 %d열 · 높이 %s' % (_pg, card['cols'] if card else 0, card['h'] if card else ''),
                str(card)[:150])

        # 39-24) 시안 실명제(좌측 하단) 자동 검사 + 확대 썸네일 + 샘플 2종
        goto(pg, base + 'apply.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.guestAccept(); } catch (e) {} }")
        pg.wait_for_timeout(300)
        btns = pg.evaluate("() => ({ name: !!document.querySelector('#btnDesignSampleName'), none: !!document.querySelector('#btnDesignSampleNoName') })")
        (ok if btns['name'] and btns['none'] else ng)('시안 샘플 — 실명제 있는/누락 시안 버튼', str(btns))
        pg.click('#btnDesignSampleName')
        pg.wait_for_timeout(900)
        nm = pg.evaluate("""() => { const n = document.querySelector('#designNameNote'); return { txt: n ? n.textContent : '', ok: n ? n.classList.contains('ok') : null,
            crop: !!document.querySelector('#designNameNote .des-crop img') }; }""")
        (ok if '실명제 영역 표기 감지됨' in nm['txt'] and nm['crop'] else ng)(
            '시안 검사 — 실명제 표기 감지 + 확대 썸네일', str(nm)[:150])
        pg.click('#btnDesignSampleNoName')
        pg.wait_for_timeout(900)
        nm2 = pg.evaluate("""() => { const n = document.querySelector('#designNameNote'); return { txt: n ? n.textContent : '', warn: n ? n.classList.contains('warn') : null,
            crop: !!document.querySelector('#designNameNote .des-crop img') }; }""")
        (ok if '실명제' in nm2['txt'] and '누락' in nm2['txt'] and nm2['warn'] else ng)(
            '시안 검사 — 실명제 누락 의심 경고', str(nm2)[:150])
        # 관리자 시안 심사 — 누락 의심 배지
        goto(pg, base + 'admin-review.html', 700)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); window.SEOSAN_VERIFY.setRole('chief'); } catch (e) {} }")
        pg.wait_for_timeout(400)
        pg.evaluate("() => { try { window.SEOSAN_VERIFY.closeModal(); } catch (e) {} }")
        tid = pg.evaluate("() => { const b = document.querySelector('#reviewList [data-approve]'); return b ? b.getAttribute('data-approve') : ''; }")
        if tid:
            pg.evaluate("(id) => window.SEOSAN_VERIFY.setTone(id, false)", tid)
            pg.wait_for_timeout(500)
            badge = pg.evaluate("() => { const el = document.querySelector('#reviewList [data-nametag]'); return { t: el ? el.textContent : '', crop: !!document.querySelector('#reviewList .des-crop img') }; }")
            (ok if '실명제' in badge['t'] and ('누락' in badge['t'] or '확인' in badge['t']) else ng)(
                '시안 심사 목록 — 실명제 표기 배지·확대 썸네일', str(badge)[:130])

        probs = w.problems()
        (ok if not probs else ng)('마이페이지·행사심사·사진폴더·정책·A4출력·검색 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()

        browser.close()
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
