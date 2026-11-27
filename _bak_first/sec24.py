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
