// 기존 HEAD와 현재 브라우저 규칙을 같은 합성 서류 30회씩 비교한다.
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { runInNewContext } from 'node:vm';
import { performance } from 'node:perf_hooks';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const require = createRequire(import.meta.url);
const current = require(resolve(root, 'web/static/detect.js')).detectSpans;
const oldSource = execFileSync('git', ['show', 'HEAD:web/static/detect.js'], { cwd: root, encoding: 'utf8' });
const sandbox = { module: { exports: {} } };
runInNewContext(oldSource, sandbox);
const baseline = sandbox.module.exports.detectSpans;
const docs = JSON.parse(readFileSync(resolve(root, 'data/eval/docs.json'), 'utf8'));

function measure(fn) {
  const samples = [];
  for (let rep = 0; rep < 30; rep++) {
    for (const doc of docs) {
      const start = performance.now();
      fn(doc.text);
      samples.push(performance.now() - start);
    }
  }
  samples.sort((a, b) => a - b);
  return { p50_ms: +samples[Math.floor(samples.length * .5)].toFixed(4),
    p95_ms: +samples[Math.floor((samples.length - 1) * .95)].toFixed(4) };
}

process.stdout.write(JSON.stringify({ environment: 'same Node process, CPU only, 30 repeats per synthetic document',
  baseline: measure(baseline), current: measure(current) }) + '\n');
