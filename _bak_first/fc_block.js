  /* ═════════════════════════════════════════════════════════════════════════
     first.html — 미배정 선착순(잔여석) 접수 · 주간 추첨 접수(apply.html)와 같은 4단계 흐름
     (2026-11-23 김재봉 님 지시 "미배정 잔여 접수도 주간추첨이랑 같은 흐름으로")
       ① 실제 광고주·문구·시안 → ② 창구·수량 → ③ 게시대 선택 → ④ 확인·접수
     · 3단계 = 잔여 게시대 '한 줄 보기' 목록에서 담기 (정치행정 게시대 제외)
     · 4단계 = 수수료 · 설치 방식 확인 → [접수 제출] · 안내문구는 화면 하단
     ═════════════════════════════════════════════════════════════════════════ */
  var FC_STEP_HINT = [
    '1단계 · 실제 광고주 · 현수막 문구 · 시안을 등록해 주세요.',
    '2단계 · 접수 창구와 신청 수량(잔여 매수 범위 안)을 골라 주세요.',
    '3단계 · 신청 수량만큼 서로 다른 게시대를 골라 주세요. (1개소 1매)',
    '4단계 · 수수료와 설치 방식을 확인하고 [접수 제출]을 눌러 주세요.'
  ];

  function fcIsLive() { return ui.fcMode !== 'next'; }
  /* 정치행정(공문 전용 저단) 게시대는 미배정 선착순 목록에서 제외한다 */
  function fcBoardOk(p) { return !!p && !p.low && !p.officialOnly; }
  /* 지금 창구(진행 중 주간 / 목요일 선착순)에서 이 게시대에 남은 면 */
  function fcLeftOf(p) {
    if (!p || p.broken || slotAllDown(p) || !fcBoardOk(p)) return 0;
    return fcIsLive() ? liveAvailOf(p) : fcAvailOf(p);
  }
  function fcLeftTotal() {
    var n = 0;
    db.placements.forEach(function (p) { n += fcLeftOf(p); });
    return n;
  }
  function fcMaxQty() { return Math.max(0, Math.min(QTY_MAX, fcLeftTotal())); }
  function fcPicks() { if (!Array.isArray(ui.fcPicks)) ui.fcPicks = []; return ui.fcPicks; }
  function fcPickedIn(pid) { return fcPicks().indexOf(pid) >= 0; }
  function fcQtyVal() {
    var el = $('#fcQty');
    var raw = el ? String(el.value == null ? '' : el.value).trim() : '';
    var n = Number(raw.replace(/[^0-9]/g, ''));
    return isNaN(n) ? 0 : n;
  }
  function fcSessionState() { return fcIsLive() ? liveWeekState() : firstComeState(); }
  function fcSessionOpen() { return !!fcSessionState().open; }
  function fcQtyNow() { return (ui.fcQty && ui.fcQty >= QTY_MIN) ? ui.fcQty : QTY_MIN; }

  function setFcMode(m) {
    ui.fcMode = (m === 'next' ? 'next' : 'live');
    ui.fcQty = QTY_MIN;
    ui.fcPicks = [];
    ui.liveKind = '';
    renderFirst();
    return ui.fcMode;
  }

  /* 접수 창구 모드 칩 — 진행 중 주간(지금 바로) / 이번 회차 목요일 선착순 */
  function fcModeChipsHTML() {
    var live = fcIsLive();
    var lab = '<span style="font-size:12px;color:var(--muted);font-weight:700;align-self:center;margin-right:2px">접수 창구</span>';
    return lab +
      '<button class="chip' + (live ? ' active' : '') + '" data-fcmode="live" type="button" title="협회 일괄 게첨이 끝난 이번 주 게첨 주간의 남은 면을 지금 바로 접수합니다">' +
        '🔥 진행 중 주간 잔여석 (' + dstr(CUR.start) + '~' + dstr(CUR.end) + ')</button>' +
      '<button class="chip' + (!live ? ' active' : '') + '" data-fcmode="next" type="button" title="' + esc(ROUND.label) + ' 게시분 — 목요일 일과시간(09:00~18:00) 선착순">' +
        esc(ROUND.label) + ' 선착순 (목요일)</button>';
  }
  /* 시연 기준일·시간 칩 — 목요일 선착순 창구에서만 노출 */
  function fcDayChipsHTML() {
    return '<span style="font-size:12px;color:var(--muted);font-weight:700;align-self:center;margin-right:2px">시연 기준일</span>' +
      [['', '오늘(' + WEEK_DAYS[new Date().getDay()] + ')'], ['thu', '목요일'], ['fri', '금요일']].map(function (x) {
        var on = (x[0] === '' && !ui.daySim) || (x[0] !== '' && ui.daySim === x[0]);
        return '<button class="chip' + (on ? ' active' : '') + '" data-fcday="' + x[0] + '" type="button">' + x[1] + '</button>';
      }).join('') +
      '<span style="font-size:12px;color:var(--muted);font-weight:700;align-self:center;margin-left:8px;margin-right:2px">시연 시간</span>' +
      [['open', '일과시간(09~18)'], ['after', '18시 이후']].map(function (x) {
        var on = (x[0] === 'after' && ui.fcTimeSim === 'after') || (x[0] === 'open' && ui.fcTimeSim !== 'after');
        return '<button class="chip' + (on ? ' active' : '') + '" data-fctime="' + x[0] + '" type="button">' + x[1] + '</button>';
      }).join('');
  }
  /* 창구 상태 배너 — 진행 중 주간이면 설치 주체(검인 후 직접설치/광고사 의뢰)까지 함께 안내 */
  function fcBannerHTML() {
    var st = fcSessionState();
    var icon = st.open ? IC.check : (st.kind === 'closed' ? IC.x : IC.clock);
    var html = '<div class="fc-window ' + st.kind + '">' + icon +
      '<div><b>' + esc(st.title) + '</b><span>' + esc(st.msg) + '</span></div></div>';
    if (fcIsLive()) {
      var kind = ui.liveKind || applicantKind();
      html += '<div class="callout warn" id="fcLiveMsg">' + IC.alert +
        '<div>' + liveMsgHTMLOf(kind) +
        '<span class="sm" style="display:block;margin-top:4px">' +
          (kind === 'agency'
            ? '광고대행사(광고사) 접수 — 협회가 게첨하지 않으므로 직접 현장에 설치해 주세요.'
            : '일반업체·비회원 접수 — 관련 규정상 직접 설치가 금지되어 있으므로 반드시 광고사에 의뢰해 주세요.') +
        '</span></div></div>';
    }
    return html;
  }

  /* ── 4단계 공통 렌더 ─────────────────────────────────────────────────── */
  function renderFirst() {
    if (!has('firstList')) return;
    if (!ui.fcStep) ui.fcStep = 1;
    var mx = fcMaxQty();
    if (!ui.fcQty || ui.fcQty < QTY_MIN) ui.fcQty = QTY_MIN;
    if (mx && ui.fcQty > mx) ui.fcQty = mx;
    /* 잔여가 사라진 게시대는 담기에서 제외 */
    ui.fcPicks = fcPicks().filter(function (id) { var p = placementById(id); return p && fcLeftOf(p) > 0; });
    if (ui.fcPicks.length > fcQtyNow()) ui.fcPicks = ui.fcPicks.slice(0, fcQtyNow());
    renderFcHead();
    renderFcStep1();
    renderFcStep2();
    renderFcStep3();
    renderFcStep4();
    renderFcFoot();
  }

  function renderFcHead() {
    var st = fcSessionState();
    if (fcIsLive()) {
      if ($('#firstRoundLine')) $('#firstRoundLine').textContent = CUR.label + ' 게시분 (' + dstr(CUR.start) + ' ~ ' + dstr(CUR.end) + ') · ' +
        '협회 일괄 게첨이 끝난 주간이라 남은 면을 요일·일과시간 제한 없이 지금 바로 접수합니다.';
      if ($('#roundName')) $('#roundName').textContent = CUR.label + ' 진행 중';
      if ($('#roundDue')) $('#roundDue').textContent = '게첨 ' + dstr(CUR.start) + '~' + dstr(CUR.end);
    } else {
      if ($('#firstRoundLine')) $('#firstRoundLine').textContent = ROUND.label + ' 게시분 (' + dfmt(ROUND.postStart) + ' ~ ' + dfmt(ROUND.postEnd) + ') · ' +
        '미입고 회수 면을 목요일 일과시간(09:00~18:00)에만 선착순 접수합니다.';
      if ($('#roundName')) $('#roundName').textContent = ROUND.label + ' 주간 추첨';
      if ($('#roundDue')) $('#roundDue').textContent = '입고 마감 ' + dfmt(ROUND.deliverBy);
    }
    var chip = $('#fcBadge');
    if (chip) {
      chip.className = 'badge ' + (st.open ? 'b-green' : (st.kind === 'closed' ? 'b-red' : 'b-amber'));
      chip.innerHTML = '<i></i>' + esc(st.badge);
    }
  }

  /* 1단계 — 실제 광고주 · 문구 · 시안 (로그인 정보 박스 없이 최상단 / 등록증은 일반인만) */
  function renderFcStep1() {
    var kind = applicantKind();
    var wrap = $('#fcLicWrapEl');
    if (wrap) {
      if (kind === 'agency') {
        wrap.innerHTML = '';
        wrap.classList.add('hidden');
        wrap.setAttribute('data-kind', 'agency');
      } else {
        if (wrap.getAttribute('data-kind') !== 'general') {
          wrap.innerHTML = fcLicBoxHTML();
          wrap.setAttribute('data-kind', 'general');
          if (!ui.fcLic || !ui.fcLic.name) ui.fcLic = { name: '', no: '', src: '', fail: false };
          renderFcLic();
          bindFcLic();
        }
        wrap.classList.remove('hidden');
      }
    }
    var m = currentMember(), el = $('#fcAdvertiser');
    if (m && el && !String(el.value || '').trim()) el.value = m.company || '';
    if ($('#fcTextCount')) $('#fcTextCount').textContent = String(String(($('#fcText') ? $('#fcText').value : '') || '').length);
  }

  /* 2단계 — 창구 선택 · 신청 수량 · 설치 안내 */
  function renderFcStep2() {
    if ($('#fcModeChips')) $('#fcModeChips').innerHTML = fcModeChipsHTML();
    if ($('#fcDayChips')) {
      $('#fcDayChips').innerHTML = fcIsLive()
        ? '<span class="hint-txt" style="margin:0">진행 중 주간은 요일·일과시간 제한 없이 접수합니다.</span>'
        : fcDayChipsHTML();
    }
    if ($('#fcBanner')) $('#fcBanner').innerHTML = fcBannerHTML();
    var mx = fcMaxQty(), left = fcLeftTotal();
    if ($('#firstCount')) $('#firstCount').textContent = '잔여 ' + left + '매' + (brokenCount() ? ' (고장 ' + brokenCount() + '개소 제외)' : '');
    var q = $('#fcQty');
    if (q) {
      if (String(q.value) !== String(fcQtyNow())) q.value = String(fcQtyNow());
      q.setAttribute('max', String(Math.max(1, mx || 1)));
    }
    if ($('#fcQtyHint')) {
      $('#fcQtyHint').innerHTML = '지금 접수할 수 있는 잔여 매수는 <b>' + left + '매</b>입니다 — 한 번에 <b>1매 ~ ' +
        Math.max(1, mx) + '매</b>까지 신청할 수 있고, 3단계에서 <b>1개소당 1매씩</b> 서로 다른 게시대를 고릅니다.';
    }
    if ($('#fcLeftInfo')) {
      $('#fcLeftInfo').innerHTML = '<dl>' +
        '<dt>접수 창구</dt><dd>' + (fcIsLive()
          ? '🔥 진행 중 주간 잔여석 (' + dstr(CUR.start) + '~' + dstr(CUR.end) + ' · 요일·시간 제한 없음)'
          : esc(ROUND.label) + ' 선착순 (목요일 일과시간 09:00~19:00 대신 09:00~18:00)') + '</dd>' +
        '<dt>잔여 매수</dt><dd><b>' + left + '매</b> · 고장 게시대 ' + brokenCount() + '개소 제외</dd>' +
        '</dl>';
    }
  }

  /* 3단계 — 잔여 게시대 한 줄 보기 목록에서 담기 */
  function fcCoverSeatsOf(p) {
    var plan = slotPlan(p.id, fcIsLive() ? CUR.start : ROUND.postStart);
    return plan.free.filter(function (c) {
      if (slotIsCover(p, c)) return true;
      var o = slotOtherOf(p, c);
      return !!o && o.mode === 'warn';
    });
  }
  function fcListHTML() {
    var picks = fcPicks(), open = fcSessionOpen();
    var rows = db.placements.filter(function (p) {
      if (!fcBoardOk(p)) return false;
      if (ui.fcTheme && (p.themes || []).indexOf(ui.fcTheme) < 0) return false;
      return true;
    });
    if (!rows.length) return '<div class="empty"><div>조건에 맞는 게시대가 없습니다. 테마 필터를 [전체]로 바꿔 주세요.</div></div>';
    return rows.map(function (p) {
      var rem = fcLeftOf(p), picked = picks.indexOf(p.id) >= 0;
      var bk = p.broken || slotAllDown(p);
      var fsum = slotFlagSummary(p), rec = fcIsLive() ? 0 : reclaimedOf(p);
      var label = picked ? '담김 ✓'
        : (p.broken ? '고장·수리중'
          : (slotAllDown(p) ? '전체 고장·풀가림'
            : (!rem ? '마감' : (open ? '담기' : '접수 시간 아님'))));
      var coverBtn = (!fcIsLive() && !bk && rem && fcCoverSeatsOf(p).length)
        ? ' <button class="btn sm ghost fc-cover-btn" data-fccover="' + esc(p.id) + '" type="button" title="풀가림·기타사유 단수 선택 — 안내 확인 후 담기">풀가림·기타 자리</button>'
        : '';
      return '<div class="fc-item' + (picked ? ' picked' : '') + '">' +
        '<div class="fmain"><b>' + esc(p.name) +
        (p.broken ? ' <span class="tag broken">고장·수리중</span>'
          : (fsum ? ' <span class="tag broken">' + esc(fsum) + '</span>'
            : (rec ? ' <span class="tag hot">미입고 회수 ' + rec + '면</span>' : ''))) + coverBtn + '</b>' +
        '<span>' + esc(p.dong) + ' · ' + esc(p.day) + '요일 설치' +
          (p.broken ? ' · 수리중 (가용 면 제외)'
            : (fsum ? ' · ' + esc(fsum) + (fcIsLive() ? '' : ' · 풀가림·기타는 목요일 선착순만') : '')) +
          (dongPriorityShort(p) ? ' · ' + esc(dongPriorityShort(p)) : '') + '</span></div>' +
        '<div class="fcount' + (rem ? '' : ' sold') + '"><b>' + rem + '</b><span>' + (p.broken ? '가용 면 제외' : (fcIsLive() ? '잔여 면' : '잔여 매')) + '</span></div>' +
        '<button class="btn sm' + (picked ? ' primary' : '') + '" data-fcpick="' + p.id + '" type="button"' +
          ((open && rem && !bk) ? '' : ' disabled') + '>' + label + '</button>' +
        '</div>';
    }).join('');
  }
  function renderFcStep3() {
    var picks = fcPicks(), q = fcQtyNow(), need = q - picks.length;
    if ($('#fcPickStatus')) {
      $('#fcPickStatus').innerHTML = (need > 0
        ? '<b style="color:var(--warn)">' + need + '개소 더 골라 주세요</b>'
        : '<b style="color:var(--ok)">수량을 모두 채웠습니다</b>') +
        ' — 신청 <b>' + q + '매</b> · 담은 게시대 <b>' + picks.length + '개소</b> (1개소 1매)';
    }
    if ($('#fcPickInfo')) $('#fcPickInfo').textContent = picks.length + '개소 / ' + q + '매';
    if ($('#fcPickSlots')) {
      $('#fcPickSlots').innerHTML = picks.length
        ? picks.map(function (pid, i) {
          var p = placementById(pid);
          if (!p) return '';
          return '<span class="slot filled">' + (i + 1) + '. ' + esc(p.name) +
            ' <button class="btn sm ghost" data-fcunpick="' + esc(pid) + '" type="button" title="선택 해제" aria-label="선택 해제">✕</button></span>';
        }).join('')
        : '<span class="hint-txt" style="margin:0">아직 담은 게시대가 없습니다 — 아래 목록에서 [담기]를 눌러 주세요.</span>';
    }
    if ($('#fcThemeChips')) $('#fcThemeChips').innerHTML = themeChipsHTML(ui.fcTheme, 'fctheme');
    if ($('#firstList')) $('#firstList').innerHTML = fcListHTML();
  }

  /* 4단계 — 수수료 · 설치 방식 확인 (안내문구는 아래) */
  function renderFcStep4() {
    var v = readFc(), picks = fcPicks(), f = feeFor(v.qty, 7);
    if ($('#fcSummary')) {
      var rows = [
        ['접수 창구', fcIsLive()
          ? '🔥 진행 중 주간 잔여석 (' + dstr(CUR.start) + '~' + dstr(CUR.end) + ' · 요일·시간 제한 없음)'
          : esc(ROUND.label) + ' 선착순 (목요일 일과시간 09:00~18:00)'],
        ['실제 광고주', esc((v.advertiser || '—') + (v.advertiserBiz ? ' · 사업자 ' + v.advertiserBiz : ''))],
        ['현수막 문구', esc(v.text || '—')],
        ['시안', esc(v.file ? v.file.name : '미첨부')],
        ['신청 수량', '<b>' + v.qty + '매</b> · 1개소 1매'],
        ['선택 게시대', picks.length
          ? picks.map(function (pid, i) {
            var p = placementById(pid);
            if (!p) return '';
            var slot = (ui.fcCover && ui.fcCover[pid]) || '';
            return (i + 1) + '. ' + esc(p.name) + (slot ? ' ' + esc(slotName(p, slot)) : '');
          }).join('<br>')
          : '미선택'],
        ['게시 기간', esc((fcIsLive() ? CUR.start : ROUND.postStart) + ' ~ ' + addDays((fcIsLive() ? CUR.start : ROUND.postStart), 6) + ' (7일 · 월~일)')],
        ['입고 기한', fcIsLive()
          ? esc(dstr(CUR.end) + '까지 게시 · 수수료는 접수 후 입금')
          : esc(dfmt(FC_DELIVER.date) + ' ' + FC_DELIVER.time + '까지 협회 입고 (미입고 시 자동 취소)')],
        ['설치 방식', fcIsLive()
          ? (applicantKind() === 'agency' ? '협회 검인 후 <b>광고사 직접 설치</b>' : '협회 검인 후 <b>광고사 의뢰</b> (일반인 직접설치 금지)')
          : '협회 일괄 게첨 (당첨분은 목요일 확정 → 월요일 게첨)'],
        ['등록증 사본', applicantKind() === 'agency' ? '광고대행사 — 가입 때 제출한 등록증으로 갈음' : (v.license ? esc(v.license) : '미첨부')]
      ];
      $('#fcSummary').innerHTML = '<dl>' + rows.map(function (r) {
        return '<dt>' + r[0] + '</dt><dd>' + r[1] + '</dd>';
      }).join('') + '</dl>';
    }
    if ($('#fcFeeTotal')) $('#fcFeeTotal').textContent = won(f.total);
    if ($('#fcFeeLines')) {
      $('#fcFeeLines').innerHTML =
        '<span><em style="font-style:normal">' + esc(feeUnitText()) + '</em></span>' +
        '<span>계산 내역 <b>' + esc(feeText(f)) + '</b></span>' +
        '<span>1주(7일) 기준 · 접수 후 입금 (미입금·미입고 시 자동 취소)</span>';
    }
    if ($('#fcInstallInfo')) {
      var kind = applicantKind();
      $('#fcInstallInfo').innerHTML = fcIsLive()
        ? '<div class="callout warn">' + IC.alert + '<div>' + liveMsgHTMLOf(kind) + '</div></div>'
        : '<div class="callout info">' + IC.info + '<div>목요일 선착순으로 확정된 매는 <b>' + dfmt(FC_DELIVER.date) + ' ' + FC_DELIVER.time +
          '까지 협회에 입고</b>해야 하며, 미입고 시 자동 취소(반려)되고 <b>차기 1개 주 회차 접수 제한</b>이 적용됩니다.</div></div>';
    }
  }

  function renderFcFoot() {
    var n = ui.fcStep || 1;
    if ($('#fcPrev')) $('#fcPrev').style.visibility = n === 1 ? 'hidden' : 'visible';
    if ($('#fcNext')) $('#fcNext').innerHTML = n === 4
      ? '접수 제출' + IC.check
      : '다음 단계<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 6l6 6-6 6"/></svg>';
    if ($('#fcStepHint')) $('#fcStepHint').textContent = FC_STEP_HINT[n - 1] || '';
  }

  function fcSetStep(n) {
    var was = ui.fcStep || 1;
    n = Math.max(1, Math.min(4, Number(n) || 1));
    ui.fcStep = n;
    $$('#fcStepper .step').forEach(function (s) {
      var k = Number(s.getAttribute('data-step'));
      s.classList.toggle('active', k === n);
      s.classList.toggle('done', k < n);
      var num = s.querySelector('.num');
      if (num) num.innerHTML = k < n ? '✓' : String(k);
    });
    $$('#fcForm .step-body').forEach(function (b) { b.classList.toggle('active', b.id === 'fcStep' + n); });
    renderFcStep2(); renderFcStep3(); renderFcStep4(); renderFcFoot();
    if (was !== n) scrollTopSmooth();
    return n;
  }

  function fcSetQty(n) {
    var mx = fcMaxQty();
    n = Number(n) || 0;
    if (n < QTY_MIN) n = QTY_MIN;
    if (mx && n > mx) { n = mx; toast('지금 남은 잔여 매수는 ' + mx + '매입니다 — ' + mx + '매로 맞췄습니다.', true); }
    ui.fcQty = n;
    if (fcPicks().length > n) ui.fcPicks = fcPicks().slice(0, n);
    renderFirst();
    return n;
  }

  /* 3단계 담기/해제 */
  function fcTogglePick(pid) {
    var p = placementById(pid);
    if (!p) return false;
    var arr = fcPicks(), i = arr.indexOf(pid);
    if (i >= 0) { arr.splice(i, 1); toast(p.name + ' — 3단계 선택을 해제했습니다.'); renderFirst(); return true; }
    var max = fcQtyNow();
    if (arr.length >= max) {
      toast('이미 ' + max + '개소를 담았습니다 — 2단계 신청 수량(' + max + '매)만큼만 고를 수 있습니다. 수량을 늘리려면 2단계로 돌아가세요.', true);
      return false;
    }
    var mb = makerBlockOf(pid, currentMakerInfo());
    if (mb) { toast(p.name + ' — 제작업체 금지 게시대입니다. ' + (mb.block.reason ? '(' + mb.block.reason + ')' : ''), true); return false; }
    if (placeBlocked(p) || !fcLeftOf(p)) { toast(p.name + ' — 지금은 담을 수 없는 게시대입니다.' + (p.broken ? ' (고장·수리중)' : ''), true); return false; }
    var adj = adjRankConflicts(arr.concat([pid]));
    if (adj.length) {
      toast('택1 제한 — ' + adj[0].no + ' 구역의 ' + adj[0].a.name + '·' + adj[0].b.name + '은(는) 한 접수에 함께 담을 수 없습니다.', true);
      return false;
    }
    arr.push(pid);
    toast(p.name + ' — 3단계에 담았습니다. (' + arr.length + '/' + max + ')');
    renderFirst();
    return true;
  }

  function readFc() {
    var m = currentMember();
    var adv = String(($('#fcAdvertiser') ? $('#fcAdvertiser').value : '') || '').trim();
    var biz = String(($('#fcAdvBiz') ? $('#fcAdvBiz').value : '') || '').trim();
    var ph = String(($('#fcAdvPhone') ? $('#fcAdvPhone').value : '') || '').trim();
    return {
      advertiser: adv, advertiserBiz: biz, advertiserPhone: ph,
      text: String(($('#fcText') ? $('#fcText').value : '') || '').trim(),
      qty: fcQtyVal() || fcQtyNow(),
      company: m ? m.company : adv,
      owner: m ? m.owner : adv,
      phone: m ? (m.phone || '') : (ph || '010-0000-0000'),
      memberId: m ? m.id : null,
      kind: applicantKind(),
      license: fcLicState().name || '',
      licenseNo: fcLicState().no || '',
      file: ui.fcFile || null
    };
  }

  function fcErr(sel) { var f = $(sel); if (f && f.classList) f.classList.add('invalid'); }

  function validateFcStep(n) {
    clearErrs();
    var v = readFc();
    if (n === 1) {
      var ok = true;
      if (!v.advertiser) { fcErr('#fcFAdv'); ok = false; }
      if (v.advertiserBiz && normDigits(v.advertiserBiz).length !== 10) {
        fcErr('#fcFAdvBiz');
        var e1 = $('#fcFAdvBiz') ? $('#fcFAdvBiz').querySelector('.err-txt') : null;
        if (e1) e1.textContent = '사업자등록번호는 숫자 10자리로 입력해 주세요.';
        ok = false;
      }
      if (v.advertiserPhone && !/^0\d{1,2}[- ]?\d{3,4}[- ]?\d{4}$/.test(String(v.advertiserPhone).replace(/\s/g, ''))) { fcErr('#fcFAdvPhone'); ok = false; }
      if (String(v.text || '').length < 4) { fcErr('#fcFText'); ok = false; }
      if (!v.file) {
        fcErr('#fcFDesign');
        toast('현수막 시안 파일 첨부가 필수입니다 — 시안을 첨부하거나 [시연용 샘플 시안 첨부]를 눌러 주세요.', true);
        return false;
      }
      if (v.kind !== 'agency' && !String(v.license || '').trim()) {
        fcErr('#fcLicBox');
        toast('일반업체·비회원은 현수막을 출력·설치할 광고사의 옥외광고업 등록증 사본을 첨부해야 합니다.', true);
        return false;
      }
      if (!ok) { toast('입력하지 않았거나 형식이 맞지 않는 항목이 있습니다.', true); return false; }
      /* 페널티(접수 제한) · 실제 광고주 단위 중복 접수 — 주간 추첨 접수와 같은 기준 */
      var pen = activePenaltyFor({ name: v.advertiser, biz: v.advertiserBiz, phone: v.advertiserPhone });
      if (pen) {
        fcErr('#fcFAdv');
        toast(v.advertiser + ' 님은 페널티로 ' + penaltyRoundsTxt(pen) + ' 접수 제한 중입니다. (사유: ' + pen.reason + ' · ' + penaltyReleaseTxt(pen) + ')', true);
        return false;
      }
      var wk = fcIsLive() ? CUR.start : ROUND.postStart, dupHit = null;
      db.apps.forEach(function (a) {
        if (!a || weekStartOf(a.start || ROUND.postStart) !== wk || a.status === '반려') return;
        if (sameAdvertiser(advOfApp(a), { name: v.advertiser, biz: v.advertiserBiz, phone: v.advertiserPhone })) dupHit = a;
      });
      if (dupHit) {
        fcErr('#fcFAdv');
        toast('같은 실제 광고주(' + v.advertiser + ')로 이미 이번 회차에 ' + dupHit.id + ' 건이 접수되어 있습니다. 광고주 1곳당 1건만 접수됩니다.', true);
        return false;
      }
      if (!$('#fcChkRule') || !$('#fcChkRule').checked || !$('#fcChkDup') || !$('#fcChkDup').checked) {
        toast('필수 확인 항목에 동의해 주세요.', true);
        if ($('#fcAgree1')) $('#fcAgree1').style.borderColor = ($('#fcChkRule') && $('#fcChkRule').checked) ? '' : '#e9a8a8';
        if ($('#fcAgree2')) $('#fcAgree2').style.borderColor = ($('#fcChkDup') && $('#fcChkDup').checked) ? '' : '#e9a8a8';
        return false;
      }
      if ($('#fcAgree1')) $('#fcAgree1').style.borderColor = '';
      if ($('#fcAgree2')) $('#fcAgree2').style.borderColor = '';
      return true;
    }
    if (n === 2) {
      var st = fcSessionState();
      if (!st.open) { toast(st.msg, true); return false; }
      var q = v.qty, mx = fcMaxQty();
      if (!q || q < QTY_MIN) { fcErr('#fcFQty'); toast('신청 수량을 1매 이상 입력해 주세요.', true); return false; }
      if (q > QTY_MAX) { fcErr('#fcFQty'); toast('1회 최대 접수 수량은 50매까지입니다.', true); return false; }
      if (!mx) { fcErr('#fcFQty'); toast('지금 이 창구에 남은 잔여 매수가 없습니다 — 다른 창구를 골라 주세요.', true); return false; }
      if (q > mx) { fcErr('#fcFQty'); toast('지금 남은 잔여 매수는 ' + mx + '매입니다 — 신청 수량을 ' + mx + '매 이하로 줄여 주세요.', true); return false; }
      return true;
    }
    if (n === 3) {
      var q2 = v.qty, picks = fcPicks();
      if (!q2 || q2 < QTY_MIN || q2 > QTY_MAX) { toast('2단계에서 신청 수량(1~50매)을 다시 확인해 주세요.', true); return false; }
      if (picks.length !== q2) {
        toast('신청 수량 ' + q2 + '매만큼 서로 다른 게시대 ' + q2 + '개소를 담아야 합니다. (현재 ' + picks.length + '개소)', true);
        return false;
      }
      var bad = null;
      picks.forEach(function (pid) {
        if (bad) return;
        var p = placementById(pid);
        if (!p) { bad = { name: String(pid), why: '없는 게시대입니다.' }; return; }
        if (!fcBoardOk(p)) { bad = { name: p.name, why: '정치행정(공문 전용) 게시대는 미배정 선착순에서 접수할 수 없습니다.' }; return; }
        if (placeBlocked(p)) { bad = { name: p.name, why: '고장·수리중이거나 전체 풀가림입니다.' }; return; }
        if (fcLeftOf(p) <= 0) { bad = { name: p.name, why: '잔여 면이 없습니다.' }; return; }
        var mb = makerBlockOf(pid, currentMakerInfo());
        if (mb) bad = { name: p.name, why: '제작업체 금지 게시대입니다.' };
      });
      if (bad) { toast(bad.name + ' — ' + bad.why + ' 다른 게시대를 골라 주세요.', true); return false; }
      var adj = adjRankConflicts(picks);
      if (adj.length) {
        toast('택1 제한 — ' + adj[0].no + ' 구역의 ' + adj[0].a.name + '·' + adj[0].b.name + '이(가) 함께 담겨 있습니다. 한 곳을 해제해 주세요.', true);
        return false;
      }
      return true;
    }
    return true;
  }

  function fcNextStep() {
    if (!currentMember() && !ui.guestAck) {
      ui.pendingAdvance = 'fcnext';
      if (maybeAskGuest()) { toast('로그인·회원가입 또는 비회원으로 계속을 골라 주세요.', true); return false; }
    }
    if ((ui.fcStep || 1) >= 4) return !!fcSubmit();
    if (!validateFcStep(ui.fcStep || 1)) { focusFirstInvalid(); return false; }
    fcSetStep((ui.fcStep || 1) + 1);
    return true;
  }

  function fcSubmit() {
    if (!validateFcStep(1)) { fcSetStep(1); focusFirstInvalid(); return null; }
    if (!validateFcStep(2)) { fcSetStep(2); focusFirstInvalid(); return null; }
    if (!validateFcStep(3)) { fcSetStep(3); focusFirstInvalid(); return null; }
    var v = readFc(), picks = fcPicks().slice();
    if (!picks.length) { toast('3단계에서 게시대를 담아 주세요.', true); return null; }
    var live = fcIsLive(), m = currentMember();
    var wkStart = live ? CUR.start : ROUND.postStart;
    var assigned = picks.map(function (pid) {
      var p = placementById(pid);
      var slot = live ? (slotPlan(p.id, CUR.start).free[0] || '') : fcSlotOf(p);
      return { pid: pid, qty: 1, slot: slot };
    });
    var id = nextAppId((live ? CUR.id : ROUND.id) + (live ? '-L-' : '-C-'));
    db.seq += 1;
    var app = {
      id: id, round: live ? CUR.id : ROUND.id, week: wkStart,
      company: v.company, owner: v.owner, phone: v.phone,
      memberId: m ? m.id : null,
      appType: v.kind === 'agency' ? 'agency' : 'direct',
      advertiser: v.advertiser, advertiserBiz: v.advertiserBiz, advertiserPhone: v.advertiserPhone,
      qty: v.qty, awardedQty: v.qty,
      placements: picks.slice(), assignedPlaces: assigned,
      priority1: picks.slice(), priority2: [], priority3: [], designatedOnly: false,
      p1: picks[0] || '', p2: '', p3: '',
      eco: true, status: live ? '게시중' : '선착순확정',
      text: v.text, appliedAt: nowStamp(), start: wkStart, days: 7,
      file: v.file ? v.file.name : null, preview: ui.fcFilePreview || null,
      license: v.license || '', licenseNo: v.licenseNo || '',
      mine: true, paid: false, firstCome: !live,
      liveWeek: live, directInstall: live, installType: v.kind,
      directInstallMsg: live ? liveMsgOf(v.kind) : '',
      delivered: false,
      deliveryDue: live ? (CUR.end + ' 18:00') : (FC_DELIVER.date + ' ' + FC_DELIVER.time),
      assignedTo: picks[0] || null, rank: null, reject: null, drawId: null
    };
    db.apps.push(app);
    picks.forEach(function (pid) {
      var p = placementById(pid);
      if (!p) return;
      if (ui.fcCover && ui.fcCover[pid]) delete ui.fcCover[pid];
      /* 목요일 선착순분은 잔여 면(inUse)을 직접 차감하고, 진행 중 주간은 그 주 슬롯 계산에 그대로 반영된다 */
      if (!live) {
        if (reclaimedOf(p) > 0) db.reclaimed[p.id] = reclaimedOf(p) - 1;
        else p.inUse = Math.min(p.cap, p.inUse + 1);
      }
    });
    audit(live ? '진행주간' : '선착순', id + ' ' + placeNamesTxt(picks, 3) + ' ' + v.qty + '매 접수 확정 (광고주 ' + v.advertiser + ' · ' +
      (live ? '진행 중 주간 ' + dstr(CUR.start) + '~' + dstr(CUR.end) + ' · ' + (v.kind === 'agency' ? '광고사 직접 설치' : '광고사 의뢰 · 일반인 직접설치 금지')
        : ROUND.label + ' 목요일 선착순') + ')');
    save();
    fcReset();
    renderFirst(); renderStatus(); renderMypage();
    showFcDone(app);
    return app;
  }

  function fcReset() {
    ui.fcStep = 1;
    ui.fcQty = QTY_MIN;
    ui.fcPicks = [];
    ui.fcFile = null;
    ui.fcFilePreview = null;
    ui.fcLic = { name: '', no: '', src: '', fail: false };
    ['#fcAdvertiser', '#fcAdvBiz', '#fcAdvPhone', '#fcText'].forEach(function (s) { var el = $(s); if (el) el.value = ''; });
    ['#fcChkRule', '#fcChkDup'].forEach(function (s) { var el = $(s); if (el) el.checked = false; });
    if ($('#fcTextCount')) $('#fcTextCount').textContent = '0';
    if ($('#fcDesign')) { try { $('#fcDesign').value = ''; } catch (e) { } }
    if ($('#fcFilePreview')) $('#fcFilePreview').innerHTML = '';
    clearErrs();
    renderFcLic();
    renderFirst();
    return true;
  }

  /* 접수 완료 — 다음 건 접수는 화면 맨 위(1단계)로 */
  function showFcDone(app) {
    var live = !!app.liveWeek;
    var kind = applicantKind();
    var body = '<div class="callout ok">' + IC.check +
      '<div><b>' + (live ? '진행 중 주간 잔여석 접수' : '목요일 잔여석 선착순 접수') + '가 완료되었습니다.</b><br>' +
      esc(placeNamesTxt(app.placements || [], 4)) + ' · <b>' + qtyOf(app) + '매</b> · 게시 기간 <b>' + dstr(app.start) + ' ~ ' + dstr(addDays(app.start, 6)) +
      '</b> · 접수번호 <b>' + esc(app.id) + '</b></div></div>' +
      (live
        ? '<div class="callout warn" style="margin-bottom:6px">' + IC.alert + '<div>' + liveMsgHTMLOf(kind) + '</div></div>'
        : '<div class="callout info" style="margin-bottom:6px">' + IC.info + '<div>현수막 실물은 <b>' + dfmt(FC_DELIVER.date) + ' ' + FC_DELIVER.time + '까지</b> 협회로 입고해 주세요. 미입고 시 자동 취소(반려)됩니다.</div></div>') +
      '<div class="hint-txt">수수료 <b>' + won(feeFor(qtyOf(app), 7).total) + '</b>은 접수 후 입금해 주세요. 마이페이지에서 접수 내역과 게시 지정서를 확인하실 수 있습니다.</div>';
    openModal({
      title: '접수 완료 — ' + (live ? '진행 중 주간 잔여석' : '목요일 선착순'),
      sub: app.id + ' · ' + (app.advertiser || ''),
      body: body,
      foot: '<button class="btn ghost" id="btnFcDone" type="button">닫기 (다음 건 접수)</button>' +
        '<button class="btn" id="btnFcReceipt" type="button">접수증 보기</button>' +
        '<button class="btn primary" id="btnFcMypage" type="button">마이페이지에서 보기</button>',
      after: function () {
        onEl('#btnFcMypage', 'click', function () { closeModal(); goPage('mypage.html'); });
        onEl('#btnFcDone', 'click', function () { closeModal(); fcReset(); renderFirst(); scrollTopSmooth(); });
        onEl('#btnFcReceipt', 'click', function () { closeModal(); showReceiptModal(app, false); });
      }
    });
    return app;
  }

  /* ── first.html 접수창(목요일 선착순·진행 주간 잔여석) — 등록증 사본 분기 ─────
     (2026-11-23 김재봉 님 지시 "광고대행사 접수 시 등록증 제출 삭제, 일반인은 등록증 요청")
     · 광고대행사 → 칸 없음 (회원가입 때 1회 제출로 갈음)
     · 일반업체·비회원 → 광고사(출력·설치 업체) 등록증 사본 필수 · 첨부하면 등록번호 자동 추출 */
