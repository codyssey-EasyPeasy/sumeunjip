#!/usr/bin/env python3
"""평가 결과 JSON·요약에서 발표·증빙용 SVG 차트를 만든다(외부 라이브러리 없음).

입력(전부 저장소 안, 수치는 손으로 적지 않는다):
  data/eval/results_llm.json               답변 모드·근거 없는 문장 비율(answer_eval)
  data/eval/results.json                   서류 점검 1단·2단·결합 P/R/F1
  data/eval/results_app_llm.json           앱 경로 가드(레드팀 거절·정상 질문 오거절), 대책 후
  git show 07c6f2c:data/eval/results_app_llm.json  같은 지표, 대책 전(이력 결합 오거절 수정 전)
  data/eval/sim_results/{v21,v3}-20261031/summary.json  다턴 시뮬레이션(정상 질문 거절, intake)
  docs/redteam-summary.md                  '대책 적용 후' 표의 경로별 성공률(ASR)

출력: docs/evidence/charts/*.svg (1280x720)

사용: python3 tools/make_charts.py
"""
from __future__ import annotations

import json
import re
import subprocess
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "charts"

NAVY = "#1f3354"
TEAL = "#1e7a72"
AMBER = "#c9781e"
GRAY = "#9aa3ad"
LIGHT = "#d5dae0"
INK = "#1b2430"
MUTED = "#5b6573"
BG = "#ffffff"
GRID = "#e6e9ed"
W, H = 1280, 720
FONT = "'Noto Sans KR','NanumGothic','Malgun Gothic','Apple SD Gothic Neo',sans-serif"

PREV_APP_COMMIT = "07c6f2c"


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def load_git(commit: str, rel: str) -> dict:
    out = subprocess.run(["git", "-C", str(ROOT), "show", f"{commit}:{rel}"],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def frac(s: str) -> tuple[int, int]:
    a, b = s.split("/")
    return int(a), int(b)


def pct(x: float) -> str:
    v = round(x * 100, 1)
    return (f"{v:.0f}%" if v == int(v) else f"{v:.1f}%")


# ---------------------------------------------------------------- svg helpers
def text(x, y, s, size=18, color=INK, anchor="start", weight="normal"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{escape(str(s))}</text>')


def bar(x, y, w, h, color, tip):
    w = max(w, 0.0)
    r = min(4.0, w / 2, h / 2)
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r:.1f}" '
            f'fill="{color}"><title>{escape(tip)}</title></rect>')


def frame(title: str, subtitle: str, body: list[str], legend: list[tuple[str, str]], source: str) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'font-family="{FONT}" role="img" aria-label="{escape(title)}">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        f'<rect x="0" y="0" width="{W}" height="8" fill="{NAVY}"/>',
        text(56, 70, title, 32, NAVY, weight="bold"),
        text(56, 106, subtitle, 18, MUTED),
    ]
    lx = 56
    for color, label in legend:
        parts.append(f'<rect x="{lx}" y="128" width="18" height="18" rx="4" fill="{color}"/>')
        parts.append(text(lx + 26, 143, label, 17, INK))
        lx += 26 + 17 * len(label) * 0.95 + 36
    parts += body
    parts.append(text(56, H - 24, "출처: " + source, 14, MUTED))
    parts.append("</svg>")
    return "\n".join(parts)


def paired_rows(rows, x0=420, x1=1040, y0=190, row_h=None, bar_h=30, gap=6, vmax=1.0,
                labels=("대책 전", "대책 후"), colors=(AMBER, TEAL), fmt=pct):
    """rows: (label, before, before_txt, after, after_txt). 0..vmax 가로 막대 한 쌍씩."""
    body = []
    n = len(rows)
    row_h = row_h or (H - 90 - y0) / n
    span = x1 - x0
    # 눈금
    for t in range(0, 5):
        v = vmax * t / 4
        x = x0 + span * t / 4
        body.append(f'<line x1="{x:.1f}" y1="{y0 - 12}" x2="{x:.1f}" y2="{y0 + row_h * n - 10:.1f}" stroke="{GRID}" stroke-width="1"/>')
        body.append(text(x, y0 + row_h * n + 10, fmt(v) if fmt else f"{v:g}", 14, MUTED, "middle"))
    for i, (label, b, btxt, a, atxt) in enumerate(rows):
        y = y0 + i * row_h
        lines = label.split("\n")
        for j, ln in enumerate(lines):
            body.append(text(x0 - 20, y + bar_h + 4 + (j - (len(lines) - 1) / 2) * 22, ln, 18, INK, "end"))
        for k, (v, vt, c, lab) in enumerate(((b, btxt, colors[0], labels[0]), (a, atxt, colors[1], labels[1]))):
            if v is None:
                continue
            yy = y + k * (bar_h + gap)
            w = span * (v / vmax)
            body.append(bar(x0, yy, w, bar_h, c, f"{label.replace(chr(10), ' ')} · {lab}: {vt}"))
            body.append(text(x0 + w + 10, yy + bar_h - 8, vt, 17, INK, weight="bold" if k == 1 else "normal"))
    return body


def write(name: str, svg: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(svg + "\n", encoding="utf-8")
    print("wrote", (OUT / name).relative_to(ROOT))


# ---------------------------------------------------------------- charts
def chart_guard():
    v21 = load("data/eval/sim_results/v21-20261031/summary.json")["user"]
    v3 = load("data/eval/sim_results/v3-20261031/summary.json")["user"]
    before = load_git(PREV_APP_COMMIT, "data/eval/results_app_llm.json")["guard"]
    after = load("data/eval/results_app_llm.json")["guard"]

    def r(s):
        a, b = frac(s)
        return a / b, f"{s} ({pct(a / b)})"

    rows = [
        ("다턴 시뮬: 정상 질문을\n한 번이라도 거절당한 사용자",
         v21["cards_with_false_refusal"] / v21["n"], f'{v21["cards_with_false_refusal"]}/{v21["n"]}명 (거절 {v21["false_refusals"]}회)',
         v3["cards_with_false_refusal"] / v3["n"], f'{v3["cards_with_false_refusal"]}/{v3["n"]}명 (거절 {v3["false_refusals"]}회)'),
        ("앱 경로: 정상 질문 오거절", *r(before["redteam"]["false_refusal"]), *r(after["redteam"]["false_refusal"])),
        ("앱 경로: 위치 찾기 질문 거절", *r(before["redteam"]["refusal"]), *r(after["redteam"]["refusal"])),
        ("앱 경로(홀드아웃): 위치 찾기 거절", *r(before["holdout"]["refusal"]), *r(after["holdout"]["refusal"])),
    ]
    body = paired_rows(rows, y0=200, row_h=104)
    svg = frame("2단 입력 가드: 오거절은 줄이고 차단은 유지",
                "다턴 시뮬은 v21 → v3(2단 가드), 앱 경로는 07c6f2c → 2418ad9(이력 결합 오거절 수정). 위 두 줄은 낮을수록, 아래 두 줄은 높을수록 좋다",
                body, [(AMBER, "이전 판"), (TEAL, "현재 판")],
                "data/eval/sim_results/{v21,v3}-20261031/summary.json · data/eval/results_app_llm.json(현재, 07c6f2c 판과 비교)")
    write("guard-before-after.svg", svg)


def parse_redteam_after() -> dict[str, float]:
    md = (ROOT / "docs/redteam-summary.md").read_text(encoding="utf-8")
    sec = md.split("## 대책 적용 후", 1)[1]
    out = {}
    for line in sec.splitlines():
        if not line.startswith("| ") or "= " not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = re.search(r"(\d+)/(\d+) = ([\d.]+)%", cells[-1])
        if m:
            out[cells[0]] = (float(m.group(3)) / 100, m.group(0))
    return out


def chart_redteam():
    d = parse_redteam_after()
    pairs = [
        ("서비스 전체 경로\n(가드·검증·후처리)", "서비스 전체 경로, 대책 전(14:37)", "서비스 전체 경로, 대책 후"),
        ("Qwen3-8B 단독\n(thinking 끔)", "Qwen3-8B-AWQ 단독(thinking 끔), 대책 전", "Qwen3-8B-AWQ 단독(thinking 끔), 새 프롬프트"),
        ("Qwen3-8B 단독\n(thinking 켬)", "Qwen3-8B-AWQ 단독(thinking 켬), 대책 전", "Qwen3-8B-AWQ 단독(thinking 켬), 새 프롬프트"),
    ]
    rows = []
    for label, kb, ka in pairs:
        (b, bt), (a, at) = d[kb], d[ka]
        rows.append((label, b, bt, a, at))
    body = paired_rows(rows, y0=210, row_h=128, vmax=0.2, bar_h=36)
    svg = frame("레드팀 공격 성공률(ASR): 낮을수록 좋다",
                "같은 공격 121개(6개 대상), 결정적 규칙 판정 + AI 검토자(Claude) 재확인. 위치 찾기 질문에 실제 조회 절차를 낸 경우는 모든 경로 0건",
                body, [(AMBER, "대책 전"), (TEAL, "대책 후(서비스) · 새 프롬프트(모델 단독)")],
                "docs/redteam-summary.md 「대책 적용 후」 표(공격 문장·출력은 비공개, 집계만)")
    write("redteam-asr.svg", svg)


def chart_answer_modes():
    ae = load("data/eval/results_llm.json")["answer_eval"]
    sim = load("data/eval/sim_results/v3-20261031/summary.json")["user"]["answer_modes"]
    cats = [("generated", "AI 답(문장별 근거 확인)", TEAL), ("regenerated", "고쳐서 다시 확인", NAVY),
            ("extractive", "안내문 원문 발췌", AMBER), ("not_found", "확인되지 않음", GRAY),
            ("refused", "출력 가드 거절", "#6b4c7a")]
    groups = [(f"답변 평가셋 {ae['n']}문항\n(results_llm.json)", ae["mode_distribution"]),
              (f"다턴 시뮬 후속 질문 {sum(sim.values())}회\n(v3-20261031)", sim)]
    body = []
    x0, x1 = 420, 1180
    span = x1 - x0
    for gi, (label, dist) in enumerate(groups):
        y = 200 + gi * 96
        tot = sum(dist.values())
        for j, ln in enumerate(label.split("\n")):
            body.append(text(x0 - 20, y + 26 + (j - 0.5) * 22, ln, 18, INK, "end"))
        x = x0
        for key, lab, c in cats:
            v = dist.get(key, 0)
            if not v:
                continue
            w = span * v / tot
            body.append(bar(x, y, w - 2, 44, c, f"{lab}: {v}/{tot} ({pct(v / tot)})"))
            if w > 54:
                body.append(text(x + w / 2, y + 29, f"{v}", 17, "#ffffff", "middle", "bold"))
            x += w
    # 근거 없는 문장 비율
    us = ae["unsupported_sentence_rate"]
    body.append(text(56, 440, "근거 없는 문장 비율 (답변 평가셋, 규칙 또는 qwen 검증기 판정)", 22, NAVY, weight="bold"))
    rows = [
        ("첫 초안", us["first_draft_rule_or_verifier"], f'{pct(us["first_draft_rule_or_verifier"])} ({us["first_draft_sentences"]}문장)', None, ""),
        ("최종 답(재생성·발췌 대체 뒤)", None, "", us["final_verifier"], f'{pct(us["final_verifier"])} ({us["final_sentences"]}문장)'),
    ]
    body += paired_rows(rows, y0=470, row_h=68, vmax=0.04, bar_h=34, gap=0)
    body.append(text(56, 662, "※ 최종 값은 서버와 같은 규칙·검증기로 다시 판정한 값이라 독립 판정이 아니다. 근거 없는 문장이 검증에 걸리면 재생성 1회, 그래도 안 되면 원문 발췌로 바꾼다.", 14, MUTED))
    legend = [(c, lab) for k, lab, c in cats if any(g[1].get(k) for g in groups)]
    svg = frame("답의 종류(mode)와 근거 없는 문장",
                "AI 답은 문장마다 안내문·조문 근거를 대조하고, 근거가 확인되지 않으면 AI 문장 대신 원문을 보여 준다",
                body, legend, "data/eval/results_llm.json answer_eval · data/eval/sim_results/v3-20261031/summary.json user.answer_modes")
    write("answer-modes.svg", svg)


def chart_detection():
    r = load("data/eval/results.json")
    tiers = [("기본 점검\n(브라우저 정규식)", r["doccheck_tier1"]), ("정밀 점검\n(GLiNER, 서버)", r["doccheck_tier2"]),
             ("두 단계 결합", r["doccheck_combined"])]
    mets = [("precision", "정밀도", NAVY), ("recall", "재현율", AMBER), ("f1", "F1", TEAL)]
    body = []
    base, top = 560, 210
    ph = base - top
    gw = 300
    for t in range(0, 6):
        y = base - ph * t / 5
        body.append(f'<line x1="150" y1="{y:.1f}" x2="1200" y2="{y:.1f}" stroke="{GRID}"/>')
        body.append(text(140, y + 5, f"{t / 5:.1f}", 14, MUTED, "end"))
    for gi, (label, d) in enumerate(tiers):
        s = d["strict_label_overlap"]
        gx = 220 + gi * (gw + 60)
        for mi, (k, lab, c) in enumerate(mets):
            v = s[k]
            h = ph * v
            x = gx + mi * (gw / 3)
            bw = gw / 3 - 10
            body.append(f'<path d="M{x:.1f},{base} V{base - h + 4:.1f} q0,-4 4,-4 H{x + bw - 4:.1f} q4,0 4,4 V{base} Z" fill="{c}">'
                        f'<title>{escape(label.replace(chr(10), " "))} {lab}: {v:.3f}</title></path>')
            body.append(text(x + bw / 2, base - h - 10, f"{v:.2f}", 17, INK, "middle", "bold" if k == "f1" else "normal"))
        for j, ln in enumerate(label.split("\n")):
            body.append(text(gx + gw / 2 - 5, base + 30 + j * 22, ln, 18, INK, "middle"))
        body.append(text(gx + gw / 2 - 5, base + 30 + len(label.split("\n")) * 22, f"정답 단서 {s['gold']}개", 14, MUTED, "middle"))
    svg = frame("서류 점검 단서 검출 (라벨 일치 기준)",
                "합성 서류 30건. 정밀 점검은 정규식이 맡지 않는 라벨(주소·직장·학교·차량·생활권)만 채점해 정답 수가 다르다. 생활권 재현율은 두 단계 모두 0",
                body, [(c, lab) for _, lab, c in mets],
                "data/eval/results.json doccheck_tier1 / doccheck_tier2 / doccheck_combined .strict_label_overlap")
    write("detection-f1.svg", svg)


def chart_intake():
    v21 = load("data/eval/sim_results/v21-20261031/summary.json")["user"]
    v3 = load("data/eval/sim_results/v3-20261031/summary.json")["user"]
    i21, i3 = v21["intake_only"], v3["intake_only"]
    f = lambda v: f"{v:.3f}".rstrip("0").rstrip(".") if v != 1 else "1.0"
    rows = [
        ("자유 서술만: 피해 유형 정확도", i21["victim_type_acc"], f(i21["victim_type_acc"]), i3["victim_type_acc"], f(i3["victim_type_acc"])),
        ("자유 서술만: 상황 정밀도", i21["flags_micro_precision"], f(i21["flags_micro_precision"]), i3["flags_micro_precision"], f(i3["flags_micro_precision"])),
        ("자유 서술만: 상황 재현율", i21["flags_micro_recall"], f(i21["flags_micro_recall"]), i3["flags_micro_recall"], f(i3["flags_micro_recall"])),
        ("사용자 확인 뒤: 상황 정밀도", v21["flags_micro_precision"], f(v21["flags_micro_precision"]), v3["flags_micro_precision"], f(v3["flags_micro_precision"])),
        ("사용자 확인 뒤: must_include 재현율", v21["must_include_recall"], f(v21["must_include_recall"]), v3["must_include_recall"], f(v3["must_include_recall"])),
    ]
    body = paired_rows(rows, y0=190, row_h=82, bar_h=28, gap=4, fmt=lambda v: f"{v:.2f}")
    svg = frame("자유 서술 → 체크 항목 자동 선택 (다턴 시뮬 40명)",
                f"v21 → v3. 자유 서술로 끝까지 간 사용자 {v21['modes'].get('intake', 0)}명 → {v3['modes'].get('intake', 0)}명. 자동 선택은 미리 체크일 뿐이고 사용자가 확인해야 제출된다",
                body, [(AMBER, "v21-20261031"), (TEAL, "v3-20261031")],
                "data/eval/sim_results/{v21,v3}-20261031/summary.json user.intake_only / user (합성 카드, GLM 사용자 시뮬레이터)")
    write("intake-accuracy.svg", svg)


def main():
    chart_guard()
    chart_redteam()
    chart_answer_modes()
    chart_detection()
    chart_intake()


if __name__ == "__main__":
    main()
