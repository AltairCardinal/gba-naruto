// 探针：为「战斗剧情触发列表」的真浏览器目视检查准备一份**小**载荷。
//
// 为什么需要它：桌面端的 FilePanel 浏览器**单个文档只能下载约 1 MB**
// （见 rom-editor/content/base-rom/rom-loader.html 的注释：实测约 1 MB/文档）。
// 原版 ROM 是 6 MB，压缩后 2.7 MB —— 浏览器里直接取会卡死，
// 所以「载入内置 ROM」在这台机器上一直失败（这是环境限制，不是本轮引入的）。
//
// 触发列表其实**只需要某一场关卡那两个剧本的字节**（几百字节到几十 KB）。
// 这个探针就把那些字节抽出来，写成一个小 JSON；
// 浏览器端的 qa-trigger-view.html 取回它、拼出一份**稀疏 ROM**，
// 就能用仓库里真正的模块渲染出真正的触发列表。
//
// 自校验（重要）：拼出来的稀疏 ROM 必须与完整 ROM 产出**同一份**触发模型
// —— 块数、每块的条件、跳转目标、事件 id 全部逐项相等。
// 不相等就直接报错退出，不产出载荷。
//
// 用法：
//   node tools/probe_battle_story_qa.mjs            # 第 40 场
//   node tools/probe_battle_story_qa.mjs 7          # 第 7 场
import { readFileSync, writeFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..');
const pack = JSON.parse(gunzipSync(
  readFileSync(join(repo, 'rom-editor', 'content', 'pack.min.json.gz'))).toString('utf8'));
const rom = new Uint8Array(readFileSync(join(repo, 'rom', 'base.gba')));

const { scanScript, ROM_BASE } = await import('../rom-editor/js/storyvm.js');
const bt = await import('../rom-editor/js/battletriggers.js');

const scene = Number(process.argv[2] || 40);
const packAsModel = { structure: (id) => pack.structures.find((s) => s.id === id) };

function rootPointer(structureId) {
  const struct = packAsModel.structure(structureId);
  const record = struct && struct.records ? struct.records[scene] : null;
  const ptr = record && record.values ? record.values.ptr : 0;
  return ptr ? ptr >>> 0 : 0;
}

const logicPtr = rootPointer('story_logic_root');
const eventsPtr = rootPointer('story_events_root');
if (!logicPtr || !eventsPtr) {
  console.error(`第 ${scene} 场没有战场事件剧本（logic=${logicPtr} events=${eventsPtr}）`);
  process.exit(1);
}

/** 一段剧本的**可达**字节范围（scanScript 会跟跳转目标，所以范围可能比剧本首址大）。 */
function reachableRange(ptr) {
  const instructions = scanScript(rom, ptr - ROM_BASE);
  if (!instructions.length) return null;
  let start = Infinity;
  let end = 0;
  for (const instruction of instructions) {
    start = Math.min(start, instruction.offset);
    end = Math.max(end, instruction.offset + instruction.length);
  }
  return { start, end, count: instructions.length };
}

const logicRange = reachableRange(logicPtr);
const eventsRange = reachableRange(eventsPtr);
if (!logicRange || !eventsRange) {
  console.error(`第 ${scene} 场的剧本扫不出指令`);
  process.exit(1);
}

// 两个剧本的范围可能互相重叠（场景 32..38 是同一段字节），合并一下。
const ranges = [];
for (const range of [logicRange, eventsRange]) {
  const last = ranges[ranges.length - 1];
  if (last && range.start <= last.start + last.end) {
    last.start = Math.min(last.start, range.start);
    last.end = Math.max(last.end, range.end);
  } else {
    ranges.push({ start: range.start, end: range.end });
  }
}
ranges.sort((a, b) => a.start - b.start);

// --- 稀疏 ROM 与完整 ROM 的模型必须逐项相等 --------------------------------
const sparse = new Uint8Array(rom.length);
for (const range of ranges) sparse.set(rom.subarray(range.start, range.end), range.start);

function fingerprint(model) {
  return model.blocks.map((block) => [
    block.value,
    block.linked,
    block.conditions.map((c) => [
      c.op, c.offset, c.values.comparator ?? null, c.values.round_count ?? null,
      c.values.expect ?? null, c.values.role_id ?? null, c.values.battle_flag ?? null,
      c.values.sub_config ?? null, c.target.kind, c.target.address,
    ]),
    block.summary,
    block.lineCount,
  ]);
}

const fullModel = bt.buildTriggerModel(rom, packAsModel, scene);
const sparseModel = bt.buildTriggerModel(sparse, packAsModel, scene);
const a = JSON.stringify(fingerprint(fullModel));
const b = JSON.stringify(fingerprint(sparseModel));
if (a !== b) {
  console.error('稀疏 ROM 与完整 ROM 的触发模型不一致 —— 不产出载荷。');
  console.error(`  完整：${a.slice(0, 400)}`);
  console.error(`  稀疏：${b.slice(0, 400)}`);
  process.exit(1);
}

// --- 写载荷 ---------------------------------------------------------------
const parts = [];
for (const range of ranges) parts.push(Buffer.from(rom.subarray(range.start, range.end)));
const data = Buffer.concat(parts).toString('base64');

const payload = {
  scene,
  rom_size: rom.length,
  rom_base: ROM_BASE,
  ranges: ranges.map((range) => [range.start, range.end - range.start]),
  data,
  blocks: fullModel.blocks.length,
  chain: fullModel.counts.chainLength,
  unconditional: fullModel.counts.unconditional,
  conditions: fullModel.counts.conditions,
};

const out = join(repo, 'build', `battle-story-qa-scene-${scene}.json`);
writeFileSync(out, JSON.stringify(payload));
console.log(`第 ${scene} 场：${ranges.length} 段字节 / ${parts.reduce((n, p) => n + p.length, 0)} 字节`);
console.log(`  触发块 ${payload.blocks} 个 · 事件链 ${payload.chain} 段 · 无条件 ${payload.unconditional} 个 · 条件 ${payload.conditions} 条`);
console.log(`  稀疏 ROM 与完整 ROM 的模型逐项相等 ✓`);
console.log(`  载荷：${out}（${data.length} 个 base64 字符）`);
