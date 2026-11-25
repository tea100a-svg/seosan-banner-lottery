
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
