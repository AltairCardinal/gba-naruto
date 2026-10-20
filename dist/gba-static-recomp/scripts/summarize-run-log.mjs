#!/usr/bin/env node
// summarize-run-log.mjs — 把 GBARecomp 运行日志解析成指标表
//
// 用法：
//   node summarize-run-log.mjs <run.log> [--json]
//
// 输出：关键指标 + 健康判定。日志里找不到 bounded_run 时退 2。
//
// 纯 Node.js 内置模块，无第三方依赖。
//
// 解析要点：日志里多行共用同名 key（sha1 / size 出现在 bios_loaded、rom_loaded、
// save_config 里），所以**必须按行前缀分域解析**，不能用全局 key=value 扫描
// ——全局扫描会把 bios 的 size 套到 save 上。

import { readFileSync, existsSync } from 'node:fs';
import { basename } from 'node:path';

const args = process.argv.slice(2);
const file = args.find((a) => !a.startsWith('--'));
const asJson = args.includes('--json');

if (!file || !existsSync(file)) {
  console.error('usage: node summarize-run-log.mjs <run.log> [--json]');
  process.exit(2);
}

const lines = readFileSync(file, 'utf8').split(/\r?\n/);

/** 取以 prefix 开头的那一行，解析它剩余部分的 key=value */
function kvAfter(prefix) {
  const line = lines.find((l) => l.startsWith(prefix));
  if (line === undefined) return {};
  return parseKv(line.slice(prefix.length));
}

/**
 * 取以 prefix 开头的那一行，解析**整行**的 key=value。
 * 用于 "pal_nonzero=512/1024 vram_nonzero=..." 这类前缀本身也是 key 的行——
 * 用 kvAfter 会把前缀那个 key 吃掉。
 */
function kvLine(prefix) {
  const line = lines.find((l) => l.startsWith(prefix));
  if (line === undefined) return {};
  return parseKv(line);
}

function parseKv(text) {
  const o = {};
  for (const part of text.trim().split(/\s+/)) {
    if (!part) continue;
    const i = part.indexOf('=');
    if (i <= 0) continue;
    o[part.slice(0, i)] = part.slice(i + 1).replace(/^"|"$/g, '');
  }
  return o;
}

/** 取以 prefix 开头的那一行的剩余全文（不解析 kv） */
function restAfter(prefix) {
  const line = lines.find((l) => l.startsWith(prefix));
  return line === undefined ? '' : line.slice(prefix.length).trim();
}

const bio   = kvAfter('bios_loaded ');
const rom   = kvAfter('rom_loaded ');
const save  = kvAfter('save_config ');
const run   = kvAfter('bounded_run ');
const fin   = kvLine('final_pc=');
const nnz   = kvLine('pal_nonzero=');
const cov   = kvLine('self_heal_coverage=');
const bioBackend = restAfter('bios_backend=');

const bridged = lines
  .map((l) => l.match(/^\s*bridged\s+(0x[0-9A-Fa-f]+)\s+\((arm|thumb)\)\s+x(\d+)/))
  .filter(Boolean)
  .map((m) => ({ addr: m[1], mode: m[2], hits: Number(m[3]) }));

const num = (v) => (v === undefined || v === '' ? null : Number(v));
const pct = (v, total) => (total > 0 ? ((v / total) * 100).toFixed(1) : '0.0');

const palUsed   = num(nnz.pal_nonzero?.split('/')[0]);
const vramUsed  = num(nnz.vram_nonzero?.split('/')[0]);
const vramTotal = num(nnz.vram_nonzero?.split('/')[1]);
const oamUsed   = num(nnz.oam_nonzero?.split('/')[0]);

const has = (v) => v !== undefined && v !== null && !Number.isNaN(v);

const checks = [];
const add = (ok, label, detail) => checks.push({ ok, label, detail });

add(Boolean(bio.sha1), 'BIOS 哈希校验', bio.sha1 ? `sha1=${bio.sha1.slice(0, 16)}…` : '日志里没有 bios_loaded');
add(Boolean(rom.sha1), 'ROM 哈希校验', rom.sha1 ? `sha1=${rom.sha1.slice(0, 16)}… title=${rom.title ?? '?'}` : '日志里没有 rom_loaded');
add(/^LLE/.test(bioBackend), 'BIOS 走 LLE（重编译）而非 HLE 兜底', bioBackend || '未知');
add((palUsed ?? 0) > 0, '调色板已写入（pal_nonzero>0）', `${palUsed ?? 0}/1024`);
add((vramUsed ?? 0) > 0, 'VRAM 已写入（vram_nonzero>0）', `${vramUsed ?? 0}/${vramTotal ?? '?'} (${pct(vramUsed ?? 0, vramTotal ?? 0)}%)`);
add((oamUsed ?? 0) > 0, 'OAM 有精灵（oam_nonzero>0）', `${oamUsed ?? 0}/1024`);
add(has(num(fin.unmapped)) && (num(fin.unmapped) ?? 0) <= 1, '未映射访问 ≤1', `unmapped=${fin.unmapped ?? '?'}`);
add(has(num(cov.dispatch_misses)) && (num(cov.dispatch_misses) ?? 0) === 0,
    'dispatch miss = 0（100% 静态覆盖）',
    `misses=${cov.dispatch_misses ?? '?'} interpreted=${cov.interpreted_insns ?? '?'}`);
add(Boolean(save.type) && save.type !== 'unknown', '存档芯片已确定', save.type ? `${save.type} size=${save.size ?? '?'}` : 'unknown');

const result = {
  log: basename(file),
  rom: { sha1: rom.sha1, title: rom.title, code: rom.code, entry: rom.entry, size: rom.size },
  bios: { sha1: bio.sha1, backend: bioBackend },
  save: { type: save.type, size: save.size, source: save.source },
  run: {
    frames: run.end_frame ? Number(run.end_frame) - Number(run.start_frame ?? 0) : null,
    guest_fps: num(run.guest_fps),
    presented: num(fin.frames_presented),
    final_pc: fin.final_pc,
    steps: num(fin.steps),
    cycles: num(fin.cycles),
    unmapped: num(fin.unmapped),
  },
  render: { pal: palUsed, vram: vramUsed, oam: oamUsed },
  coverage: {
    status: cov.self_heal_coverage,
    dispatch_misses: num(cov.dispatch_misses),
    interpreted_insns: num(cov.interpreted_insns),
    healed_native: num(cov.healed_native),
    failed: num(cov.failed),
  },
  bridged,
  checks,
  verdict: checks.every((c) => c.ok) ? 'PASS'
         : checks.some((c) => c.label.startsWith('dispatch miss')) ? 'PARTIAL'
         : 'FAIL',
};

if (asJson) {
  console.log(JSON.stringify(result, null, 2));
} else {
  const pad = (s, n) => String(s).padEnd(n);
  console.log(`== ${result.log} ==`);
  console.log(`verdict      : ${result.verdict}`);
  console.log(`rom          : ${result.rom.title ?? '?'} ${result.rom.code ?? ''} entry=${result.rom.entry ?? '?'}`);
  console.log(`bios backend : ${result.bios.backend ?? '?'}`);
  console.log(`save         : ${result.save.type ?? '?'} size=${result.save.size ?? '?'}`);
  console.log(`run          : ${result.run.frames ?? '?'} frames, guest_fps=${result.run.guest_fps ?? '?'}, final_pc=${result.run.final_pc ?? '?'}`);
  console.log(`render       : pal=${result.render.pal ?? 0}/1024 vram=${result.render.vram ?? 0}/${vramTotal ?? '?'} oam=${result.render.oam ?? 0}/1024`);
  console.log(`coverage     : ${result.coverage.status ?? '?'} misses=${result.coverage.dispatch_misses ?? '?'} interpreted=${result.coverage.interpreted_insns ?? '?'} healed=${result.coverage.healed_native ?? '?'}`);
  if (bridged.length) {
    console.log('bridged PCs  :');
    for (const b of bridged) {
      const kind = /^0x0[23]/.test(b.addr) ? 'RAM-copy -> 需 [[code_copy]]'
                 : /^0x00/.test(b.addr) ? 'BIOS -> 属 bios 配置'
                 : 'ROM -> 补 [[extra_func]]';
      console.log(`  ${pad(b.addr, 12)} ${pad(b.mode, 6)} x${String(b.hits).padEnd(8)} ${kind}`);
    }
  }
  console.log('checks       :');
  for (const c of checks) console.log(`  [${c.ok ? 'ok  ' : 'WARN'}] ${pad(c.label, 42)} ${c.detail ?? ''}`);
}

if (!run.end_frame) process.exit(2);
process.exit(result.verdict === 'FAIL' ? 1 : 0);
