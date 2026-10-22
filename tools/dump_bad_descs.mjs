#!/usr/bin/env node
// 把「说明看不懂」的字段按**去重后的说明**摊开 —— 同一句说明用在多少字段上。
// 用法：node tools/dump_bad_descs.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..');
const pack = JSON.parse(readFileSync(join(repo, 'rom-editor', 'content', 'pack.json'), 'utf8'));

const ADDR = /0x0[0-9A-Fa-f]{5,7}/;
const OFF = /(字节|记录|字段|槽位|偏移|位域|指针)\s*[+＋]?\s*0x[0-9A-Fa-f]{2,4}/;
const XREF = /(下面|上面|上面那|前面)的?[「『"']?\S{1,8}[」』"']?\s*字段/;

const seen = new Map();
for (const s of pack.structures) {
  for (const f of s.fields || []) {
    const d = String(f.desc || '');
    const bad = ADDR.test(d) || OFF.test(d) || XREF.test(d) || d.length > 160;
    if (!bad) continue;
    if (seen.has(d)) { seen.get(d).n += 1; continue; }
    seen.set(d, { n: 1, t: s.id, k: f.key, l: f.label, d });
  }
}
const arr = [...seen.values()].sort((a, b) => b.n - a.n);
console.log(`distinct descs: ${arr.length}  fields: ${arr.reduce((n, x) => n + x.n, 0)}`);
for (const x of arr) {
  console.log(`\n### [${x.t}.${x.k}] x${x.n}  label=${x.l}`);
  console.log(x.d);
}
