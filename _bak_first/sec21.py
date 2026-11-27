        head('21. 진행 중 주간(11.23~11.29) 잔여석 접수 · 4단계 흐름 통일 · 광고사 직접설치 / 일반인 광고사 의뢰 안내')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        w = Watcher(pg, base)
        goto(pg, base + 'first.html', 600)
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
        (ok if order['notes'] is not None and order['list'] is not None and order['notes'] > order['list'] else ng)(
            '4단계 — 장황한 안내문구는 게시대 목록보다 아래(하단)', 'notes=%s list=%s' % (order['notes'], order['list']))

        # 21-2) 1단계 검증 — 광고주·문구·시안·동의가 없으면 다음 단계로 가지 않는다
        pg.evaluate("() => { const v = window.SEOSAN_VERIFY; v.guestAccept(); v.fcSet({ mode: 'live', advertiser: '', text: '', file: false, agree: false, license: false }); }")
        blocked = pg.evaluate("() => window.SEOSAN_VERIFY.fcValidate(1)")
        step_blocked = pg.evaluate("() => window.SEOSAN_VERIFY.fcNext()")
        (ok if blocked is False and step_blocked is False and pg.evaluate("() => window.SEOSAN_VERIFY.fcStep()") == 1 else ng)(
            '1단계 — 필수 미입력 시 다음 단계 차단 · 1단계 유지', 'validate=%s next=%s' % (blocked, step_blocked))
        inv = pg.evaluate("""() => { const el = document.querySelector('#fcForm .field.invalid');
            return el ? { id: el.id, scroll: Math.round(el.getBoundingClientRect().top + window.scrollY) } : null; }""")
        (ok if inv and inv['id'] == 'fcFAdv' else ng)('필수 미입력 칸 강조(자동 스크롤·포커스 대상)', str(inv)))

        # 21-3) 2단계 — 창구 chips · 설치 안내 배너 · 신청 수량(잔여 매수 범위)
        pg.evaluate("""() => window.SEOSAN_VERIFY.fcSet({ mode: 'live', advertiser: '검증진행주간광고주', text: '진행 중 주간 잔여석 접수 검증',
            file: true, agree: true, license: true, qty: 1, picks: [] })""")
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSetStep(2)")
        pg.wait_for_timeout(250)
        chips = pg.text_content('#fcModeChips') or ''
        (ok if '진행 중 주간 잔여석' in chips and '선착순 (목요일)' in chips else ng)(
            '2단계 — 창구 선택 chips(진행 중 주간 / 목요일 선착순)', chips[:120].replace('\n', ' '))
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
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSet({ mode: 'live' })")
        pg.wait_for_timeout(300)
        ban_a = pg.text_content('#fcBanner') or ''
        (ok if '광고사에서 직접 현장에 설치(게첨)' in ban_a and '일반인은 직접 설치가 금지' not in ban_a else ng)(
            '광고대행사 로그인 — 배너가 광고사 직접 설치 안내로 분기', ban_a[:130].replace('\n', ' '))
        (ok if not pg.query_selector('#fcLic') else ng)('광고대행사 — 1단계 등록증 칸 없음', 'fcLic=%s' % bool(pg.query_selector('#fcLic')))
        pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1001')")
        pg.evaluate("() => window.SEOSAN_VERIFY.fcSet({ mode: 'live' })")
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
        live_row = pg.eval_on_selector_all('#placementGrid [data-fclive]:not([disabled])', 'e => e.length')
        (ok if live_row > 0 else ng)('게시대 현황(이번 주) — [잔여석 접수] 버튼', '%d개' % live_row)
        go_pid = pg.eval_on_selector('#placementGrid [data-fclive]:not([disabled])', 'e => e.getAttribute("data-fclive")')
        pg.click('#placementGrid [data-fclive="%s"]' % go_pid)
        pg.wait_for_load_state('load')
        pg.wait_for_timeout(900)
        (ok if 'first.html' in pg.url and 'mode=live' in pg.url and ('place=' + go_pid) in pg.url else ng)(
            '현황 [잔여석 접수] → first.html?mode=live&place= 연결', pg.url.split('/')[-1])
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
