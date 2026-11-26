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


PAGES = ['index.html', 'apply.html', 'first.html', 'guide-rules.html', 'guide-faq.html', 'guide.html',
         'mypage.html', 'mypage-detail.html', 'admin-review.html', 'admin-event.html', 'admin-draw.html',
         'admin-official.html', 'admin-pay.html', 'admin-deliver.html', 'admin-report.html',
         'admin-desig.html', 'admin-photos.html', 'admin-docs.html', 'admin-board.html', 'admin-course.html',
         'admin-roles.html', 'admin-members.html', 'admin-system.html']
ADMIN_PAGES = [p2 for p2 in PAGES if p2.startswith('admin-')]

NAV_EXPECT = [('게시대 현황', 'index.html'), ('주간 추첨 접수', 'apply.html'), ('미배정 선착순', 'first.html'),
              ('규격·안내', 'guide-rules.html'), ('마이페이지', 'mypage.html'), ('협회 관리자', 'admin-draw.html')]
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
        while len(pg.evaluate("() => window.SEOSAN_VERIFY.offSel()")) < goal5:
            left_btns = pg.eval_on_selector_all('[data-offrec]', 'els => els.map(e => e.getAttribute("data-offrec"))')
            if not left_btns:
                break
            pg.click('[data-offrec="%s"]' % left_btns[0])
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
        (ok if '11월 30일' in h1['title'] and '11.30' in h1['week'] else ng)(
            '기본 = 이번 회차 게첨 주(11.30~12.06)', str(h1)[:130])
        pg.fill('#woDatePick', '2026-12-07')
        pg.wait_for_timeout(500)
        h2 = pg.evaluate("() => window.SEOSAN_VERIFY.woHead()")
        (ok if '12월 7일' in h2['title'] and '12.07' in h2['week'] and h2['pick'] == '2026-12-07' else ng)(
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
        for name, nxt in (('apply.html', '#btnNext'), ('first.html', '#fcNext')):
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
        want = {0: 'draw', 2: 'due', 3: 'first', 4: 'off'}.get(dow_now)
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
