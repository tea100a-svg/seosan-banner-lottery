
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
