  /* ══════════════════════════════════════════════════════════════════════
     공문 자동 배정 — 게첨 위치·기간 자동 추출 → 게시대 자동 선택
     · 만석(공문 상한 도달) 게시대는 비우고, 인접 추천
       ① 인접 교차로(ADJ_LIMITS 택1 상대) → ② 동일 권역(같은 읍면동) → ③ 시내 중심
     (2026-11-23 김재봉 님 지시 "공문에 게첨위치 기간이 있으면 자동추출 자동 배정 …
      공문이 꽉찬 게시대는 비워두고 인접한 게시대 추천 / 동일권역·시내 중심")
     ══════════════════════════════════════════════════════════════════════ */
  var CITY_CENTER_DONGS = ['석림동', '수석동', '동문1동', '동문2동', '잠홍동', '온석동', '예천동', '석남동', '읍내동', '갈산동', '죽성동'];
  function officialBoardName(p) { return String((p && p.name) || '').replace(/^(저\)|정치행정\))/, ''); }
  function officialAllBoards() { return db.placements.concat(LOW_BOARDS); }

  /* 게첨 기간 뽑기 — 2026.12.7.~12.13. / 2026-12-07 ~ 2026-12-13 / 12월 1주 / '2주' */
  function officialDateRange(text) {
    var t = String(text || '');
    var m = t.match(/(\d{4})\s*[.\-\/]\s*(\d{1,2})\s*[.\-\/]\s*(\d{1,2})\s*\.?\s*(?:\([^)]{0,8}\))?\s*(?:[~∼～]|부터|에서)\s*(?:(\d{4})\s*[.\-\/]\s*)?(\d{1,2})\s*[.\-\/]\s*(\d{1,2})/);
    if (m) {
      var y1 = Number(m[1]), mo1 = Number(m[2]), d1 = Number(m[3]);
      var y2 = Number(m[4] || m[1]), mo2 = Number(m[5]), d2 = Number(m[6]);
      var a = new Date(y1, mo1 - 1, d1), b = new Date(y2, mo2 - 1, d2);
      if (!isNaN(a.getTime()) && !isNaN(b.getTime()) && b >= a) {
        var days = Math.round((b.getTime() - a.getTime()) / 86400000) + 1;
        return { start: dstr2iso(a), end: dstr2iso(b), days: days, text: dstr2iso(a) + ' ~ ' + dstr2iso(b), kind: 'range' };
      }
    }
    /* '12월 1주' 형태 — 그 달 1~7일이 포함된 주의 월요일 */
    var w = t.match(/(\d{1,2})\s*월\s*(\d)\s*주/);
    if (w) {
      var mo = Number(w[1]), nth = Number(w[2]);
      if (mo >= 1 && mo <= 12 && nth >= 1 && nth <= 5) {
        var y = (mo < 10 ? 2027 : 2026);
        var firstMon = new Date(y, mo - 1, 1);
        var shift = ((firstMon.getDay() + 6) % 7);
        var mon = new Date(y, mo - 1, 1 + (7 - shift) % 7 + (nth - 1) * 7);
        if (nth === 1) mon = new Date(y, mo - 1, 1 + ((8 - (firstMon.getDay() || 7)) % 7));
        return { start: dstr2iso(mon), end: isoOfDate(new Date(mon.getTime() + 6 * 86400000)), days: 7,
          text: mo + '월 ' + nth + '주', kind: 'monthweek' };
      }
    }
    if (/2\s*주|14\s*일|이주|2주간/.test(t)) return { start: '', end: '', days: 14, text: '2주', kind: 'days' };
    if (/1\s*주|7\s*일|일주|1주간/.test(t)) return { start: '', end: '', days: 7, text: '1주', kind: 'days' };
    return null;
  }
  function isoOfDate(d) { return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()); }

  /* 게첨 위치 뽑기 — 본문·파일명에서 게시대 이름을 그대로 찾고, 없으면 읍면동으로 찾는다 */
  function officialPlaceHits(text) {
    var txt = String(text || ''), hits = [];
    officialAllBoards().forEach(function (p) {
      var nm = officialBoardName(p);
      if (nm.length < 2) return;
      var idx = txt.indexOf(nm);
      if (idx >= 0) hits.push({ pid: p.id, idx: idx, name: p.name, by: '게시대' });
    });
    hits.sort(function (a, b) { return a.idx - b.idx; });
    var out = hits.map(function (h) { return h.pid; });
    if (!out.length) {
      /* 읍면동 이름(예: 해미면·동문2동)으로만 적힌 경우 — 그 권역 게시대를 순서대로 */
      db.placements.forEach(function (p) {
        var d = String(p.dong || '');
        if (d.length < 2) return;
        if (txt.indexOf(d) >= 0 && out.indexOf(p.id) < 0) out.push(p.id);
      });
    }
    return out;
  }
  function officialPlaceNames(ids) {
    return (ids || []).map(function (pid) { var p = boardById(pid); return p ? p.name : pid; });
  }

  /* 인접 추천 — ① 인접 교차로 → ② 동일 권역 → ③ 시내 중심 */
  function officialRecCandidates(pid) {
    var base = boardById(pid);
    if (!base) return [];
    var out = [], seen = {};
    seen[base.id] = 1;
    function add(p, rank, reason) {
      if (!p || seen[p.id] || p.broken) return;
      if (officialCapLeft(p.id) <= 0) return;
      if (officialBlock(p.id)) return;
      seen[p.id] = 1;
      out.push({ pid: p.id, name: p.name, dong: p.dong, rank: rank, reason: reason,
        left: officialCapLeft(p.id), cap: officialCapOf(p) });
    }
    adjPartnerNames(officialBoardName(base)).forEach(function (nm) {
      officialAllBoards().forEach(function (p) { if (officialBoardName(p) === nm) add(p, 1, '인접 교차로'); });
    });
    db.placements.forEach(function (p) { if (p.dong === base.dong) add(p, 2, '동일 권역'); });
    db.placements.forEach(function (p) { if (CITY_CENTER_DONGS.indexOf(p.dong) >= 0) add(p, 3, '시내 중심'); });
    out.sort(function (a, b) { return a.rank - b.rank; });
    return out;
  }

  /* 자동 배정 — 추출된 위치·기간을 그대로 선택 목록에 넣고, 만석은 비우고 추천을 띄운다 */
  function officialAutoAssign(p) {
    p = p || {};
    var ids = (p.placeIds || []).filter(function (pid) { return !!boardById(pid); });
    ui.offRec = null;
    if (!ids.length) { renderOffRecBox(); return null; }
    var week = weekStartOf(p.week || ui.offWeek || ROUND.postStart);
    ui.offWeek = week;
    var goal = Math.max(1, Math.min(QTY_MAX, Number(p.qty) || offQtyVal()));
    ui.offSel = {};
    var picked = [], full = [], blocked = [];
    ids.forEach(function (pid) {
      var pb = boardById(pid);
      if (!pb) return;
      if (officialCapLeft(pid) <= 0) { full.push({ pid: pid, name: pb.name, cap: officialCapOf(pb), off: officialSeatsOf(pid) }); return; }
      if (picked.length >= goal) return;
      var blk = officialBlock(pid);
      if (blk) { blocked.push({ pid: pid, name: pb.name, by: blk.name, no: blk.no }); return; }
      ui.offSel[pid] = 1;
      picked.push(pid);
    });
    var need = Math.max(0, goal - picked.length), recs = [], seen = {};
    if (need > 0) {
      var pools = [];
      full.forEach(function (f) { officialRecCandidates(f.pid).forEach(function (c) { pools.push(c); }); });
      if (!pools.length) {
        var anchor = picked[0] || ids[0];
        if (anchor) pools = officialRecCandidates(anchor);
      }
      pools.forEach(function (c) {
        if (recs.length >= 3 || seen[c.pid]) return;
        seen[c.pid] = 1;
        recs.push(c);
      });
    }
    ui.offRec = { goal: goal, picked: picked.slice(), full: full, blocked: blocked, recs: recs, need: need, week: week };
    renderOffRecBox();
    return ui.offRec;
  }

  function renderOffRecBox() {
    var box = $('#offRecBox');
    if (!box) return;
    var r = ui.offRec;
    if (!r || (!r.full.length && !r.blocked.length && !r.recs.length)) { box.innerHTML = ''; box.classList.add('hidden'); return; }
    box.classList.remove('hidden');
    var picked = offSelList();
    var recs = (r.recs || []).filter(function (c) { return picked.indexOf(c.pid) < 0; });
    var html = '<div class="off-rec-head"><b>🔁 자동 배정 결과</b>' +
      '<span>게첨 위치 <b>' + r.picked.length + '</b>/' + r.goal + '곳 자동 선택' +
      (r.full.length ? ' · 만석 ' + r.full.length + '곳 제외' : '') +
      (r.need > 0 ? ' · <b style="color:#b4690e">' + r.need + '곳 더 필요</b>' : ' → 수량 충족') + '</span></div>';
    if (r.full.length) {
      html += '<div class="off-rec-full">' + r.full.map(function (f) {
        return '<span class="off-rec-chip full">🚫 공문 만석 제외 · <b>' + esc(f.name) + '</b> (공문 ' + f.off + '/' + f.cap + '면)</span>';
      }).join('') + '</div>';
    }
    if (r.blocked.length) {
      html += '<div class="off-rec-full">' + r.blocked.map(function (f) {
        return '<span class="off-rec-chip blocked">↔ 인접 택1 제외 · <b>' + esc(f.name) + '</b> (' + esc(f.no) + ' 구역 · ' + esc(f.by) + ' 선택 중)</span>';
      }).join('') + '</div>';
    }
    if (recs.length) {
      html += '<div class="off-rec-list">' + recs.map(function (c) {
        return '<div class="off-rec-card">' +
          '<span class="off-rec-badge r' + c.rank + '">' + esc(c.reason) + '</span>' +
          '<b>' + esc(c.name) + '</b><span class="sm">' + esc(c.dong) + ' · 공문 여유 ' + c.left + '/' + c.cap + '면</span>' +
          '<button class="btn sm primary" type="button" data-offrec="' + esc(c.pid) + '">+ 추천 게시대 담기</button></div>';
      }).join('') + '</div>';
      html += '<div class="hint-txt" style="margin:8px 0 0">추천 순서 — <b>① 인접 교차로</b> → <b>② 동일 권역(같은 읍면동)</b> → <b>③ 시내 중심</b>. 만석 게시대는 억지로 채우지 않고 비워 둡니다.</div>';
    }
    box.innerHTML = html;
  }

