#!/usr/bin/env node
// 시연 영상 녹화기 (Playwright Chromium). 앱 코드가 아니다 — web/ 는 건드리지 않는다.
//
//   node record_demo.mjs --check [--base URL]          선택자만 확인(녹화 없음, 빠른 나가기는 스텁)
//   node record_demo.mjs [--base URL] [--out DIR]      녹화 → webm → mp4(H.264·yuv420p·30fps·faststart)
//
// 선택 인자
//   --scenario PATH   시나리오(기본: 이 폴더의 scenario.json)
//   --stub-exit       빠른 나가기 이동처(google)를 로컬 스텁으로 바꾼다(리허설용. 실제 녹화에는 쓰지 않는다)
//   --ffmpeg PATH     ffmpeg 실행 파일(기본: $FFMPEG, 없으면 uv 로 imageio-ffmpeg 에서 찾는다)
//   --no-mp4          webm 만 남긴다
//   --headed          창을 띄워서 실행(녹화도 함께)
//   --only a,b        해당 단계만 실행(디버그용, 녹화 길이 검사는 그대로)
//   --pace X          모든 dwellMs 에 X 를 곱한다(예: 1.2 = 20% 더 오래 보여 줌). 전체 길이 조절용
//
// 캡션 띠·강조 고리는 녹화 화면에만 덧씌운 요소다(page.evaluate 로 주입, 앱에는 없다).
// 입력은 scenario.json 의 합성 문장만 쓴다.

import { chromium } from 'playwright-core';
import { readFileSync, mkdirSync, writeFileSync, renameSync, existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_OUT = '/tmp/claude-1000/-home-ashofrondol/7682b48e-686a-4a42-9902-a98bf6b1332d/scratchpad/demo';

// ---------------------------------------------------------------- args
function parseArgs(argv) {
  const a = { base: 'http://127.0.0.1:18080', scenario: join(HERE, 'scenario.json'), out: process.env.DEMO_OUT || DEFAULT_OUT,
    check: false, stubExit: false, mp4: true, headed: false, ffmpeg: process.env.FFMPEG || '', only: null, pace: 1 };
  for (let i = 2; i < argv.length; i++) {
    const k = argv[i];
    const v = () => argv[++i];
    if (k === '--base') a.base = v().replace(/\/+$/, '');
    else if (k === '--scenario') a.scenario = resolve(v());
    else if (k === '--out') a.out = resolve(v());
    else if (k === '--check') a.check = true;
    else if (k === '--stub-exit') a.stubExit = true;
    else if (k === '--no-mp4') a.mp4 = false;
    else if (k === '--headed') a.headed = true;
    else if (k === '--ffmpeg') a.ffmpeg = v();
    else if (k === '--only') a.only = v().split(',');
    else if (k === '--pace') a.pace = parseFloat(v());
    else if (k === '-h' || k === '--help') { console.log(readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\n').slice(1, 18).join('\n')); process.exit(0); }
    else { console.error('unknown arg: ' + k); process.exit(64); }
  }
  if (a.check) a.stubExit = true;
  return a;
}

const args = parseArgs(process.argv);
const sc = JSON.parse(readFileSync(args.scenario, 'utf8'));
const IN = sc.inputs;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...m) => console.error('[demo]', ...m);

// ---------------------------------------------------------------- selectors
class Missing extends Error {
  constructor(key) { super('selector not found: ' + key); this.key = key; }
}
const selReport = {};   // key -> { found, via, step }
let currentStep = '';

function toMatcher(s) {
  if (typeof s === 'string' && s.length > 2 && s.startsWith('/') && s.lastIndexOf('/') > 0) {
    const j = s.lastIndexOf('/');
    return new RegExp(s.slice(1, j), s.slice(j + 1));
  }
  return s;
}
function candLocator(scope, c) {
  if (typeof c === 'string') return scope.locator(c);
  if (c.role) return scope.getByRole(c.role, c.name ? { name: toMatcher(c.name) } : {});
  if (c.label) return scope.getByLabel(toMatcher(c.label));
  if (c.placeholder) return scope.getByPlaceholder(toMatcher(c.placeholder));
  if (c.text) return scope.getByText(toMatcher(c.text));
  throw new Error('bad candidate ' + JSON.stringify(c));
}

// key 의 후보를 차례로 시도해 처음 보이는(또는 존재하는) 요소를 돌려준다. timeout 동안 다시 시도한다.
async function find(scope, key, { timeout = 5000, visible = true, optional = false } = {}) {
  const cands = sc.selectors[key];
  if (!cands) throw new Error('no selector key in scenario: ' + key);
  const deadline = Date.now() + timeout;
  for (;;) {
    for (let i = 0; i < cands.length; i++) {
      const loc = candLocator(scope, cands[i]);
      let n = 0;
      try { n = await loc.count(); } catch { n = 0; }
      if (!n) continue;
      for (let j = 0; j < Math.min(n, 30); j++) {
        const el = loc.nth(j);
        if (!visible || (await el.isVisible().catch(() => false))) {
          if (!selReport[key] || !selReport[key].found) selReport[key] = { found: true, via: i, step: currentStep };
          return el;
        }
      }
    }
    if (Date.now() > deadline) break;
    await sleep(150);
  }
  if (!selReport[key]) selReport[key] = { found: false, step: currentStep };
  if (optional) return null;
  throw new Missing(key);
}

// key 의 후보 중 처음 존재하는 것의 전체 목록 locator(여러 개를 훑을 때).
async function findAll(scope, key, timeout = 3000, optional = false) {
  const cands = sc.selectors[key];
  const deadline = Date.now() + timeout;
  for (;;) {
    for (let i = 0; i < cands.length; i++) {
      const loc = candLocator(scope, cands[i]);
      if ((await loc.count().catch(() => 0)) > 0) {
        if (!selReport[key] || !selReport[key].found) selReport[key] = { found: true, via: i, step: currentStep };
        return loc;
      }
    }
    if (Date.now() >= deadline) break;
    await sleep(150);
  }
  if (!selReport[key]) selReport[key] = { found: false, step: currentStep };
  if (optional) return null;
  throw new Missing(key);
}

// ---------------------------------------------------------------- overlay (녹화용 덧씌움)
async function overlay(page) {
  await page.evaluate(() => {
    if (document.getElementById('__demo_cap')) return;
    const cap = document.createElement('div');
    cap.id = '__demo_cap';
    cap.setAttribute('aria-hidden', 'true');
    cap.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:2147483646;pointer-events:none;' +
      'background:rgba(17,24,39,.92);color:#fff;padding:18px 40px 20px;display:flex;align-items:center;gap:22px;' +
      'font:600 30px/1.35 "Pretendard","NanumGothic","Noto Sans KR","Malgun Gothic",sans-serif;letter-spacing:-.01em;' +
      'box-shadow:0 -4px 18px rgba(0,0,0,.25);transition:opacity .25s';
    const num = document.createElement('span');
    num.id = '__demo_num';
    num.style.cssText = 'flex:none;background:#f59e0b;color:#111;border-radius:999px;padding:4px 16px;font-size:24px;font-weight:800';
    const txt = document.createElement('span');
    txt.id = '__demo_txt';
    cap.append(num, txt);
    document.documentElement.appendChild(cap);
    const ring = document.createElement('div');
    ring.id = '__demo_ring';
    ring.setAttribute('aria-hidden', 'true');
    ring.style.cssText = 'position:fixed;z-index:2147483645;pointer-events:none;border:5px solid #f59e0b;border-radius:12px;' +
      'box-shadow:0 0 0 6px rgba(245,158,11,.30);opacity:0;transition:opacity .2s,left .25s,top .25s,width .25s,height .25s';
    document.documentElement.appendChild(ring);
  });
}
let capState = { text: '', n: '' };
async function caption(page, text, n) {
  capState = { text, n };
  await overlay(page).catch(() => {});
  await page.evaluate(([t, n]) => {
    const tx = document.getElementById('__demo_txt');
    const nm = document.getElementById('__demo_num');
    if (tx) tx.textContent = t;
    if (nm) nm.textContent = n;
  }, [text, n]).catch(() => {});
}
async function ring(page, loc, ms = 900) {
  const b = await loc.boundingBox().catch(() => null);
  if (!b) return;
  await page.evaluate(([x, y, w, h]) => {
    const r = document.getElementById('__demo_ring');
    if (!r) return;
    r.style.left = (x - 8) + 'px'; r.style.top = (y - 8) + 'px';
    r.style.width = (w + 16) + 'px'; r.style.height = (h + 16) + 'px';
    r.style.opacity = '1';
  }, [b.x, b.y, b.width, b.height]).catch(() => {});
  await sleep(ms);
  await page.evaluate(() => { const r = document.getElementById('__demo_ring'); if (r) r.style.opacity = '0'; }).catch(() => {});
}
// 부드럽게 스크롤하고, 요소 위치가 멈출 때까지(최대 3초) 기다린다. 긴 결과 화면에서 고정 sleep 은 모자란다.
async function show(loc, block = 'center') {
  await loc.evaluate((el, block) => el.scrollIntoView({ behavior: 'smooth', block }), block).catch(() => {});
  let last = null;
  const end = Date.now() + 3000;
  await sleep(200);
  while (Date.now() < end) {
    const b = await loc.boundingBox().catch(() => null);
    const y = b ? Math.round(b.y) : null;
    if (y !== null && y === last) break;
    last = y;
    await sleep(120);
  }
  await sleep(200);
}
async function click(page, loc, ringMs = 450) {
  await show(loc);
  await ring(page, loc, ringMs);
  await loc.click();
}
async function check(page, loc) {
  await show(loc);
  await ring(page, loc, 450);
  if (!(await loc.isChecked().catch(() => false))) await loc.check({ force: true });
}
async function typeInto(loc, text) {
  await loc.click();
  await loc.fill('');
  const d = (sc.typing && sc.typing.delayMs) || 0;
  if (d > 0) await loc.pressSequentially(text, { delay: d });
  else await loc.fill(text);
}
// 응답을 기다리며 클릭한다(고정 sleep 대신).
async function clickAndWait(page, loc, apiPath, timeout) {
  const resp = page.waitForResponse((r) => r.url().includes(apiPath) && r.request().method() === 'POST', { timeout });
  await click(page, loc);
  const r = await resp;
  if (!r.ok()) throw new Error(apiPath + ' http ' + r.status());
  return r;
}
async function waitText(loc, re, timeout) {
  const end = Date.now() + timeout;
  for (;;) {
    const t = (await loc.textContent().catch(() => '')) || '';
    if (re.test(t)) return t;
    if (Date.now() > end) throw new Error('timeout waiting text ' + re);
    await sleep(120);
  }
}

// ---------------------------------------------------------------- steps
function stepDefs(page, ctxState) {
  return {
    async intro(T) {
      await find(page, 'safetyNotice', { optional: true, timeout: 2500 });
      const em = await find(page, 'emergency', { timeout: 3000 });
      await ring(page, em, 1600);
      const qe = await find(page, 'quickExit');
      await ring(page, qe, 1800);
      await sleep(T.dwell);
      const close = await find(page, 'safetyClose', { optional: true, timeout: 1000 });
      if (close) { await click(page, close); await sleep(400); }
    },
    async intake(T) {
      const tab = await find(page, 'tabDiagnose', { optional: true, timeout: 1000 });
      if (tab && (await tab.getAttribute('aria-selected')) !== 'true') await click(page, tab);
      const ta = await find(page, 'intakeText', { timeout: 6000 });   // /api/features 가 llm=true 여야 보인다
      await show(ta);
      await typeInto(ta, IN.intake);
      const btn = await find(page, 'intakeBtn');
      await clickAndWait(page, btn, '/api/intake', T.budget);
      await find(page, 'autoNotice', { timeout: 4000 });
      await sleep(T.dwell);
    },
    async confirm(T) {
      const n = await find(page, 'autoNotice');
      await show(n, 'start');
      await sleep(1800);
      // 상황 항목이 그룹별로 접혀 있으면(details) 그 그룹을 먼저 편다.
      await page.evaluate((id) => {
        const l = document.querySelector("label[data-flag='" + id + "']");
        const d = l && l.closest('details');
        if (d) d.open = true;
      }, IN.manualFlagId).catch(() => {});
      const mf = await find(page, 'manualFlag', { timeout: 3000 });
      await check(page, mf);
      await sleep(600);
      const cf = await find(page, 'autoConfirm');
      await check(page, cf);
      await sleep(T.dwell);
    },
    async diagnose(T) {
      const sub = await find(page, 'diagnoseSubmit');
      await clickAndWait(page, sub, '/api/diagnose', T.budget);
      const head = await find(page, 'resultsHead', { timeout: 5000 });
      await show(head, 'start');
      await sleep(1600);
      const now = await find(page, 'nowFirst', { optional: true, timeout: 1500 });
      if (now) { await ring(page, now, 1400); }
      const ack = await find(page, 'notifyAck', { timeout: 3000 });
      const card = ack.locator('xpath=ancestor::article[1]');
      await show(card, 'start');
      await sleep(1600);
      await check(page, ack);
      await sleep(T.dwell);
    },
    async ask(T) {
      const arts = await findAll(page, 'cards', 5000);
      let target = null;
      const titleRe = toMatcher(IN.askCardTitle);
      for (let i = 0; i < Math.min(await arts.count(), 60); i++) {
        const a = arts.nth(i);
        const t = await (await findAll(a, 'cardTitle', 0, true))?.first().textContent().catch(() => null);
        if (t && (titleRe instanceof RegExp ? titleRe.test(t) : t.includes(titleRe))) { target = a; break; }
      }
      if (!target) log('ask: no card matched ' + IN.askCardTitle + ' — using first card with ask toggle');
      else log('ask: card = ' + ((await target.locator('h3, .card-title').first().textContent().catch(() => '')) || '').trim());
      if (target) {
        // 접힌 '더 보기' 안에 있으면 펼친다(사용자가 누르는 것과 같은 동작: summary 클릭).
        const inClosed = await target.evaluate((el) => { const d = el.closest('details'); return !!(d && !d.open); });
        if (inClosed) {
          const sum = await find(page, 'moreBlock', { visible: true, timeout: 1500 });
          await click(page, sum);
          await sleep(500);
        }
      }
      const scope = target || page;
      const tog = await find(scope, 'askToggle', { timeout: 3000 });
      const card = target || tog.locator('xpath=ancestor::article[1]');
      await show(card, 'start');
      await sleep(900);
      await click(page, tog);
      const inp = await find(card, 'askInput', { timeout: 2000 });
      await typeInto(inp, IN.askQuestion);
      const sb = await find(card, 'askSubmit');
      await clickAndWait(page, sb, '/api/answer', T.budget);
      const out = await find(card, 'askOut', { visible: false });
      const done = await find(out, 'answerDone', { timeout: 4000 });
      await show(done, 'center');
      await sleep(T.dwell);
    },
    async doccheck(T) {
      const tab = await find(page, 'tabDocs');
      await click(page, tab);
      const ta = await find(page, 'docText', { timeout: 3000 });
      await show(ta, 'start');
      await ta.fill(IN.doc);   // '붙여 넣기'
      await sleep(900);
      const t1 = await find(page, 'docTier1');
      await click(page, t1);
      const st = await find(page, 'docStatus', { visible: false });
      await waitText(st, /기본 점검|단서/, 3000);
      const hl = await find(page, 'docHighlight', { visible: false });
      await sleep(1600);
      const t2 = await find(page, 'docTier2');
      await clickAndWait(page, t2, '/api/doccheck', T.budget);
      await waitText(st, /정밀 점검/, 4000);
      await show(hl, 'start');
      await sleep(T.dwell);
    },
    async rewrite(T) {
      const b = await find(page, 'docRewrite', { timeout: 2000 });
      await clickAndWait(page, b, '/api/rewrite', T.budget);
      const res = await find(page, 'rewriteResult', { timeout: 4000 });
      await show(res, 'start');
      await sleep(T.dwell);
    },
    async locate(T) {
      const tab = await find(page, 'tabSearch');
      await click(page, tab);
      const inp = await find(page, 'searchInput', { timeout: 2000 });
      await show(inp);
      if (IN.maskLocateInput) await inp.evaluate((el) => { el.style.filter = 'blur(9px)'; el.dataset.demoMasked = '1'; });
      await typeInto(inp, IN.locateQuestion);
      const btn = await find(page, 'searchBtn');
      await clickAndWait(page, btn, '/api/search', T.budget);
      const box = await find(page, 'refusalBox', { timeout: 4000 });
      await show(box, 'center');
      await ring(page, box, 1400);
      await sleep(T.dwell);
    },
    async exit(T) {
      const qe = await find(page, 'quickExit');
      await ring(page, qe, 700);
      await page.keyboard.press('Escape');
      await sleep(250);
      await page.keyboard.press('Escape');
      await page.waitForURL(/google\.[a-z.]+\/search/, { timeout: T.budget, waitUntil: 'domcontentloaded' });
      ctxState.exitUrl = page.url();
      await sleep(300);
      await caption(page, capState.text, capState.n);
      await sleep(T.dwell);
    },
  };
}

// ---------------------------------------------------------------- ffmpeg
function findFfmpeg() {
  if (args.ffmpeg && existsSync(args.ffmpeg)) return args.ffmpeg;
  const r = spawnSync('uv', ['run', '--no-project', '--with', 'imageio-ffmpeg', 'python', '-c',
    'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'], { encoding: 'utf8' });
  const p = (r.stdout || '').trim().split('\n').pop();
  if (r.status === 0 && p && existsSync(p)) return p;
  throw new Error('ffmpeg not found: pass --ffmpeg or set FFMPEG (uv stderr: ' + (r.stderr || '').slice(-300) + ')');
}
function probe(ff, file) {
  const r = spawnSync(ff, ['-hide_banner', '-i', file], { encoding: 'utf8' });
  const e = r.stderr || '';
  const d = /Duration: (\d+):(\d+):([\d.]+)/.exec(e);
  const v = /Video: (\w+).*?, (\w+)(?:\([^)]*\))?, (\d{3,5})x(\d{3,5}).*?, ([\d.]+) fps/.exec(e);
  return {
    durationSec: d ? (+d[1]) * 3600 + (+d[2]) * 60 + parseFloat(d[3]) : null,
    codec: v ? v[1] : null, pixFmt: v ? v[2] : null,
    width: v ? +v[3] : null, height: v ? +v[4] : null, fps: v ? parseFloat(v[5]) : null,
    faststart: null,
  };
}
function toMp4(ff, webm, mp4, trimStartSec, maxSec) {
  const V = sc.video;
  const vf = `fps=${V.fps},scale=${V.width}:${V.height}:flags=lanczos:force_original_aspect_ratio=decrease,` +
    `pad=${V.width}:${V.height}:(ow-iw)/2:(oh-ih)/2:color=white,format=yuv420p`;
  const r = spawnSync(ff, ['-hide_banner', '-loglevel', 'error', '-y', '-ss', trimStartSec.toFixed(2), '-i', webm,
    '-t', String(maxSec), '-vf', vf, '-r', String(V.fps), '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
    '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', mp4], { encoding: 'utf8' });
  if (r.status !== 0) throw new Error('ffmpeg failed: ' + (r.stderr || '').slice(-800));
  // faststart 확인: moov 박스가 mdat 보다 앞에 있어야 한다.
  const head = readFileSync(mp4).subarray(0, 1 << 20).toString('latin1');
  const moov = head.indexOf('moov'); const mdat = head.indexOf('mdat');
  return moov !== -1 && (mdat === -1 || moov < mdat);
}

// ---------------------------------------------------------------- main
async function main() {
  mkdirSync(args.out, { recursive: true });
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..*/, '').replace('T', '-');
  const B = sc.browser || {};
  const env = { ...process.env };
  const launch = { headless: !args.headed, env, args: ['--hide-scrollbars', '--force-color-profile=srgb'] };
  const browser = await chromium.launch(launch);
  const ctxOpt = {
    viewport: B.viewport || { width: 1920, height: 1080 },
    deviceScaleFactor: B.deviceScaleFactor || 1,
    locale: B.locale || 'ko-KR', timezoneId: 'Asia/Seoul',
    bypassCSP: true,   // 캡션 띠(인라인 style)를 덧씌우기 위해서만. 앱 동작은 바뀌지 않는다.
  };
  if (!args.check) ctxOpt.recordVideo = { dir: args.out, size: { width: sc.video.width, height: sc.video.height } };
  const context = await browser.newContext(ctxOpt);
  if (args.stubExit) {
    await context.route(/https:\/\/www\.google\.[a-z.]+\/.*/, (route) => route.fulfill({
      status: 200, contentType: 'text/html; charset=utf-8',
      body: '<!doctype html><meta charset="utf-8"><title>날씨 - 검색</title><body style="font:20px sans-serif;padding:40px">' +
        '<p style="color:#888">(리허설 스텁 — 실제 녹화에서는 구글 날씨 검색 화면)</p><h1>날씨</h1></body>',
    }));
  }
  const t0 = Date.now();
  const page = await context.newPage();
  const ctxState = {};
  const steps = sc.steps.filter((s) => !args.only || args.only.includes(s.id));
  const defs = stepDefs(page, ctxState);
  const timings = [];
  const errors = [];
  let tLoaded = t0;
  let failed = false;

  try {
    const resp = await page.goto(args.base + '/', { waitUntil: 'networkidle', timeout: 30000 });
    if (!resp || !resp.ok()) throw new Error('page load failed: ' + (resp ? resp.status() : 'no response'));
    if (B.zoom && B.zoom !== 1) await page.evaluate((z) => { document.body.style.zoom = String(z); }, B.zoom);
    await page.evaluate(() => document.fonts && document.fonts.ready);
    const feat = await page.evaluate(async () => (await fetch('/api/features')).json()).catch(() => ({}));
    if (!feat.llm) log('WARNING /api/features llm=false — 말로 설명하기·무슨 뜻·바꾸기 칸이 숨는다');
    await overlay(page);
    tLoaded = Date.now();
    const cap = (sc.video.totalCapSec || 118) * 1000;
    for (let i = 0; i < steps.length; i++) {
      const s = steps[i];
      currentStep = s.id;
      const budgetMs = (args.check ? 3 : 1) * s.maxSec * 1000;
      await caption(page, s.caption, `${i + 1}/${steps.length}`);
      const ts = Date.now();
      let timer;
      try {
        await Promise.race([
          defs[s.id]({ dwell: args.check ? 0 : Math.round((s.dwellMs || 0) * args.pace), budget: budgetMs }),
          new Promise((_, rej) => { timer = setTimeout(() => rej(new Error(`step ${s.id} exceeded ${budgetMs / 1000}s`)), budgetMs); }),
        ]);
      } catch (e) {
        errors.push({ step: s.id, error: String(e.message || e) });
        log(`step ${s.id} FAILED: ${e.message || e}`);
        if (!args.check) { failed = true; break; }
      } finally { clearTimeout(timer); }
      const dt = (Date.now() - ts) / 1000;
      timings.push({ step: s.id, sec: +dt.toFixed(2), maxSec: s.maxSec });
      log(`step ${s.id} ${dt.toFixed(1)}s`);
      if (!args.check && Date.now() - tLoaded > cap) { failed = true; errors.push({ step: s.id, error: `total over cap ${cap / 1000}s` }); break; }
    }
  } catch (e) {
    failed = true;
    errors.push({ step: currentStep || 'load', error: String(e.message || e) });
  }

  const totalSec = (Date.now() - tLoaded) / 1000;
  const video = page.video();
  await context.close();
  await browser.close();

  const report = { base: args.base, mode: args.check ? 'check' : 'record', stubExit: args.stubExit, totalSec: +totalSec.toFixed(2),
    capSec: sc.video.totalCapSec, timings, errors, exitUrl: ctxState.exitUrl || null };

  // 선택자 보고: 쓰지 않은(도달 못 한) 키도 표시
  const sel = {};
  for (const k of Object.keys(sc.selectors)) sel[k] = selReport[k] || { found: null, note: 'not reached' };
  report.selectors = sel;
  const missing = Object.entries(sel).filter(([, v]) => v.found === false).map(([k, v]) => `${k} (step ${v.step})`);
  report.missing = missing;

  if (!args.check && video) {
    const webm = await video.path();
    const base = join(args.out, `sumeunjip-demo-${stamp}`);
    renameSync(webm, base + '.webm');
    report.webm = base + '.webm';
    if (args.mp4 && !failed) {
      const ff = findFfmpeg();
      const trim = Math.max(0, (tLoaded - t0) / 1000 - 0.1);
      const fast = toMp4(ff, base + '.webm', base + '.mp4', trim, 120);
      const p = probe(ff, base + '.mp4');
      p.faststart = fast;
      report.mp4 = base + '.mp4';
      report.probe = p;
      const okP = p.codec === 'h264' && p.pixFmt === 'yuv420p' && p.width === sc.video.width && p.height === sc.video.height &&
        Math.round(p.fps) === sc.video.fps && p.durationSec !== null && p.durationSec <= 120 && fast;
      if (!okP) { failed = true; errors.push({ step: 'convert', error: 'mp4 probe mismatch ' + JSON.stringify(p) }); }
    }
  }
  report.ok = !failed && (args.check ? missing.length === 0 && errors.length === 0 : true);
  const rp = join(args.out, `report-${args.check ? 'check' : 'record'}-${stamp}.json`);
  writeFileSync(rp, JSON.stringify(report, null, 2));
  report.reportPath = rp;
  const brief = { ...report };
  brief.selectors = Object.fromEntries(Object.entries(sel).map(([k, v]) => [k, v.found === true ? `ok#${v.via}` : v.found === false ? 'MISSING' : 'not reached']));
  console.log(JSON.stringify(brief, null, 1));
  process.exit(report.ok ? 0 : (args.check ? 1 : 2));
}

main().catch((e) => { console.error(e); process.exit(3); });
