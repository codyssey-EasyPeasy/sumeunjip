/*
 * 1단계 서류 점검: 브라우저에서만 동작하는 정규식 기반 스팬 탐지.
 * 순수 함수. 부작용 없음. 정규식은 매 호출 새로 만든다.
 */
(function () {
  'use strict';

  function suggestFor(label, raw) {
    switch (label) {
      case '학교': {
        var who = '자녀(학생)';
        if (raw.indexOf('초등학교') !== -1) who = '자녀(초등학생)';
        else if (raw.indexOf('중학교') !== -1) who = '자녀(중학생)';
        else if (raw.indexOf('고등학교') !== -1) who = '자녀(고등학생)';
        else if (raw.indexOf('어린이집') !== -1 || raw.indexOf('유치원') !== -1) who = '자녀(영유아)';
        return who + ' 등 비식별 표현으로 대체';
      }
      case '직장':
        return '원고의 직장 등 비식별 표현으로 대체';
      case '주소':
        return '주소 비공개 신청과 함께 기재(주소 대신 송달 가능한 비공개 방식 사용)';
      case '전화':
        return '연락처 비공개 처리 또는 가림';
      case '주민번호':
        return '앞 6자리 이외 가림 또는 삭제';
      case '차량':
        return '차량번호 가림';
      case '이메일':
        return '이메일 가림';
      case '생활권':
        return '반복 방문·집/학교/직장과의 관계를 지우고 장소를 비식별 표현으로 대체';
      default:
        return '비식별 처리';
    }
  }

  // 우선순위: 배열 인덱스가 작을수록 우선
  function buildPatterns() {
    return [
      ['주민번호', /\d{6}-?[1-4]\d{6}/g],
      ['전화', /(01[016789]|0\d{1,2})[-.\s]?\d{3,4}[-.\s]?\d{4}/g],
      ['이메일', /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g],
      ['차량', /\d{2,3}[가-힣]\s?\d{4}/g],
      ['주소', /(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)[가-힣]*(특별시|광역시|특별자치시|도|특별자치도)?\s?[가-힣]+(시|군|구)\s?[가-힣0-9]+(로|길|동|읍|면)(\s?\d+(-\d+)?)?(\s?\d+동)?(\s?\d+호)?/g],
      ['주소', /[가-힣]+(구|시|군)\s[가-힣0-9]+(로|길|동)\s?\d+(-\d+)?(번지)?/g],
      ['주소', /\d+동\s?\d+호/g],
      ['학교', /[가-힣]+(초등학교|중학교|고등학교|어린이집|유치원)(\s?\d+학년)?(\s?\d+반)?/g],
      ['직장', /[가-힣A-Za-z0-9]+(주식회사|회사)/g],
      ['직장', /㈜\s?[가-힣A-Za-z0-9]+/g],
      ['직장', /주식회사\s?[가-힣A-Za-z0-9]+/g],
      ['직장', /[가-힣]{1,10}팀/g],
      ['직장', /[가-힣A-Za-z0-9]+에서\s?근무/g]
    ];
  }

  // 장소 이름만으로는 표시하지 않는다. 같은 문장 안에서 개인의 거주·통학·출퇴근·
  // 반복 방문과 연결된 시설만 생활권 단서로 취급한다.
  function contextualSpans(text) {
    var out = [];
    var places = [
      /(?:[가-힣○]{2,}(?:역|시장|동|아파트|캠퍼스)\s*(?:\d+번\s*출구\s*)?(?:앞|옆|입구|지하)?\s*)?[가-힣○]{2,}(?:마트|카페|미용실|공원|병원|의원|복지관|아동센터|태권도장|교회|필라테스|주차장)(?:\s*○○점)?/g,
      /[가-힣○]{2,}동\s+[가-힣○]{2,}센터\s*옆\s*공원/g,
      /[가-힣○]{2,}(?:필라테스|교회)(?:\s*○○점|\(가명\))?/g
    ];
    var personal = /피해자|고소인|원고|신청인|진술인|진정인|청구인|자녀|아들|딸|저는|제가|제|내|우리/;
    var routine = /매일|매주|평일|주로|자주|반복|출퇴근|등하교|통학|출근|퇴근|하원|방과\s*후|들르|방문|다니|산책|공부|주차|귀가|데려다|일을\s*마치/;
    var relation = /집\s*(?:근처|인근|앞|옆)|자택\s*(?:근처|인근)|거주지\s*(?:근처|인근)|도보\s*\d+분|학교\s*(?:근처|앞|옆|주변)|직장\s*(?:근처|앞|옆|주변)|캠퍼스\s*앞|아파트\s*지하|주소.{0,45}(?:병원|의원)/;
    for (var p = 0; p < places.length; p++) {
      var m;
      while ((m = places[p].exec(text)) !== null) {
        if (/병원$/.test(m[0]) && /.{0,20}근무/.test(text.slice(m.index + m[0].length, m.index + m[0].length + 25))) continue;
        var left = Math.max(text.lastIndexOf('.', m.index - 1), text.lastIndexOf('。', m.index - 1), text.lastIndexOf('\n', m.index - 1)) + 1;
        var right = text.indexOf('.', m.index);
        if (right === -1) right = text.length;
        var context = text.slice(left, right);
        if (!personal.test(context) || !(routine.test(context) || relation.test(context))) continue;
        out.push({ start: m.index, end: m.index + m[0].length, label: '생활권', text: m[0], priority: 20,
          risk_type: 'routine_location', reason: routine.test(context) ? '개인의 반복 이동·방문과 연결됨' : '거주지·학교·직장과의 관계가 드러남' });
      }
    }
    return out;
  }

  function detectSpans(text) {
    if (typeof text !== 'string' || text.length === 0) return [];

    var patterns = buildPatterns();
    var candidates = contextualSpans(text);

    for (var p = 0; p < patterns.length; p++) {
      var label = patterns[p][0];
      var re = patterns[p][1];
      var m;
      while ((m = re.exec(text)) !== null) {
        var start = m.index;
        var end = start + m[0].length;
        if (end > start) {
          candidates.push({
            start: start,
            end: end,
            label: label,
            text: m[0],
            priority: p
          });
        }
        if (m.index === re.lastIndex) re.lastIndex++;
      }
    }

    // 긴 것 우선, 같으면 앞선 것, 같으면 정의 우선순위
    candidates.sort(function (a, b) {
      var la = a.end - a.start;
      var lb = b.end - b.start;
      if (lb !== la) return lb - la;
      if (a.start !== b.start) return a.start - b.start;
      return a.priority - b.priority;
    });

    // 겹침 해소: 그리디 선택
    var selected = [];
    for (var i = 0; i < candidates.length; i++) {
      var c = candidates[i];
      var overlap = false;
      for (var j = 0; j < selected.length; j++) {
        var s = selected[j];
        if (c.start < s.end && s.start < c.end) { overlap = true; break; }
      }
      if (!overlap) selected.push(c);
    }

    selected.sort(function (a, b) { return a.start - b.start; });

    var out = [];
    for (var k = 0; k < selected.length; k++) {
      var sp = selected[k];
      out.push({
        start: sp.start,
        end: sp.end,
        label: sp.label,
        text: sp.text,
        suggestion: suggestFor(sp.label, sp.text)
      });
      if (sp.risk_type) {
        out[out.length - 1].risk_type = sp.risk_type;
        out[out.length - 1].reason = sp.reason;
      }
    }
    return out;
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { detectSpans: detectSpans };
  }
  if (typeof globalThis !== 'undefined') {
    globalThis.detectSpans = detectSpans;
  }
  if (typeof window !== 'undefined') {
    window.detectSpans = detectSpans;
  }
})();
