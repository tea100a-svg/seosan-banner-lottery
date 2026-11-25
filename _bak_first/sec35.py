
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

        # 시안 심사 — 시한임박 우선
        goto(pg, base + 'admin-review.html', 600)
        first_row = pg.evaluate("() => { const t = document.querySelector('#reviewList tbody tr'); return t ? t.innerHTML : ''; }")
        (ok if '임박' in (first_row or '') else ng)('시안 심사 — 시한임박 건 최상단 노출', (first_row or '')[:100])

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
        (ok if topy and topy['btn'] <= topy['table'] + 4 else ng)('지정서 일괄 출력 버튼 — 목록 상단 배치', str(topy))
        probs = w.problems()
        (ok if not probs else ng)('비방필터·심사정렬·검색 콘솔 오류', '; '.join(probs[:3]) if probs else '0건')
        ctx.close()
