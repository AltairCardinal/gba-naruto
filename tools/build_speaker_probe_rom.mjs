// 二分定位：哪一处「说话人名表读者」的补丁把游戏弄坏了。
//
// 用法：
//   node tools/build_speaker_probe_rom.mjs --out build/sp.gba --readers 1,2,3
//   python tools/mgba_probe/render_screen.py build/sp.png --live --rom build/sp.gba \
//       --press START --press A --press A --press A --press A
//
// 依据：notes/evidence/speaker-name-code-patches-20261023.md
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..');

const { ContentPack } = await import('../rom-editor/js/pack.js');
const { buildRom } = await import('../rom-editor/js/rom.js');

function arg(name, fallback) {
  const at = process.argv.indexOf(name);
  return at >= 0 ? process.argv[at + 1] : fallback;
}
const outPath = arg('--out', 'build/speaker-probe.gba');
const dataOnly = process.argv.includes('--data-only');
const readers = arg('--readers', '');
const sites = arg('--sites', '');
const targetId = Number(arg('--id', '1'));
const newText = arg('--text', '');

const rom = new Uint8Array(readFileSync(join(repoRoot, 'rom', 'base.gba')));
const pack = ContentPack.fromJSON(
  JSON.parse(readFileSync(join(repoRoot, 'rom-editor', 'content', 'pack.json'), 'utf8')));
pack.patches = [];

// 只保留选中的读者补丁。
// ⚠️ `new Set(null)` 会得到一个**空集合**（不是 null）——
//    所以「不筛选」必须是 `null` 而不是 `new Set(null)`，
//    否则「全部读者」这一档会静默地一个补丁都不打（踩过这个坑）。
const wanted = readers ? new Set(readers.split(',').map((x) => Number(x.trim()))) : null;
const wantedSites = sites ? new Set(sites.split(',').map((x) => Number(x.trim()))) : null;
const conversion = pack.conversions.speaker_names;
const all = conversion.code_patches;
conversion.code_patches = dataOnly ? []
  : all.filter((p) => {
    const readerMatch = /读者 (\d+)/.exec(p.label || '');
    if (wanted && !(readerMatch && wanted.has(Number(readerMatch[1])))) return false;
    if (wantedSites) {
      const offset = Number(p.offset);
      if (!wantedSites.has(offset)) return false;
    }
    return true;
  });

const table = pack.textTable('speaker_names');
const record = table.records.find((r) => r.id === targetId);
pack.setText(table, record, newText || `${record.text}测试`);

const { bytes, report } = buildRom(pack, rom);
if (report.errors.length) {
  console.error('构建失败：');
  for (const e of report.errors) console.error('  ' + e);
  process.exit(1);
}
writeFileSync(join(repoRoot, outPath), Buffer.from(bytes));
console.log(`已写出 ${outPath}（代码补丁 ${conversion.code_patches.length} 处 / `
  + `${dataOnly ? '数据侧' : '读者 ' + (readers || '全部')}）`);
