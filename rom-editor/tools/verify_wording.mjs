// 字段说明「说人话」的无头验收（第十轮）。
//
// 这一轮的第二件事：把全包字段的说明改成人话。
// 说明的**唯一真相在内容包里**（`tools/export_content_pack.py` 导出到
// `rom-editor/content/pack.json`），所以「说人话」这件事最终要由内容包说了算。
//
// 这一条门禁就是防止它退回去的：说明里再出现 ROM 地址、再拿偏移当主语、
// 再指路（交叉引用）、再甩一个裸公式、再说「未解」而不说这东西干嘛 ——
// 门禁立刻红。
//
// 判定正则与 `tools/audit_field_wording.py` **保持一致**：
// 那个审计工具是「还有多少字段没改成人话」的进度尺，
// 这条门禁是同一把尺子的断言版（退出码非 0 = 失败）。
//
// 用法：node rom-editor/tools/verify_wording.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const pack = JSON.parse(readFileSync(join(repoRoot, 'rom-editor', 'content', 'pack.json'), 'utf8'));

let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

// --- 判定规则（与 tools/audit_field_wording.py 同一套）---------------------

// 说明里出现 ROM 地址：那是**证据**，不是解释 —— 地址该待在 notes/ 里。
const ROM_ADDRESS = /0x0[0-9A-Fa-f]{5,7}/;
// 拿内部对象当主语：「字节 +0x04」「记录 [+0x0C]」「字段 +0x02」。
const OFFSET_SUBJECT = /(字节|记录|字段|槽位|偏移|位域|指针)\s*[+＋]?\s*0x[0-9A-Fa-f]{2,4}/;
// 交叉引用：「由下面的『成长目标』字段选中」「见上面的」。
const CROSS_REF = /(下面|上面|上面那|前面)的?[「『"']?\S{1,8}[」』"']?\s*字段/;
// 裸公式：给了公式却没说这个值是什么。
const BARE_FORMULA = /[=＝]\s*[^，。；\n]{0,24}×[^，。；\n]{0,24}/;
// 只说「未解」：说清了没证明，却没说这个值在游戏里是干嘛的。
const ONLY_UNDECIDED = /^[^。]{0,24}(未解|未证|语义未解|尚未证明)[。\s]*$/;
// 说明不该是长篇论文。
const TOO_LONG = 160;
// 编辑器不渲染 markdown，星号会原样露出来。
const STARS = /\*\*/;

/** 一个字段的说明 + 标签。 */
function fields() {
  const out = [];
  for (const structure of pack.structures || []) {
    for (const field of structure.fields || []) {
      out.push({
        where: `${structure.id}.${field.key}`,
        desc: String(field.desc || ''),
        label: String(field.label || ''),
      });
    }
  }
  return out;
}

const all = fields();

/** 报一批命中的字段（多了只列前 8 个，全量在 build/field-wording.md 里）。 */
function report(hits, describe) {
  if (!hits.length) return '一个都没有';
  return `${hits.length} 个：${hits.slice(0, 8).map(describe).join('、')}`
    + (hits.length > 8 ? ' …' : '');
}

console.log(`\n字段总数：${all.length}`);

console.log('\n1) 每个字段都有说明');
{
  const empty = all.filter((f) => !f.desc.trim());
  check('没有「点开也看不懂」的字段', empty.length === 0,
    report(empty, (f) => f.where));
}

console.log('\n2) 说明里没有 ROM 地址');
{
  const hits = all.filter((f) => ROM_ADDRESS.test(f.desc));
  check('说明里没有 0x08xxxxxx 这类证据地址', hits.length === 0,
    report(hits, (f) => f.where));
}

console.log('\n3) 说明不以偏移当主语');
{
  const hits = all.filter((f) => OFFSET_SUBJECT.test(f.desc));
  check('说明里没有「字节 +0xNN」「记录 +0xNN」这种主语', hits.length === 0,
    report(hits, (f) => f.where));
}

console.log('\n4) 说明没有交叉引用');
{
  const hits = all.filter((f) => CROSS_REF.test(f.desc));
  check('说明里没有「由下面的 X 字段选中」这种指路', hits.length === 0,
    report(hits, (f) => f.where));
}

console.log('\n5) 说明不是裸公式');
{
  const hits = all.filter((f) => BARE_FORMULA.test(f.desc)
    && !['等级', '数值', '倍数'].some((w) => f.desc.includes(w)));
  check('给公式时同时说了这是等级 / 数值 / 倍数', hits.length === 0,
    report(hits, (f) => f.where));
}

console.log('\n6) 说明不是只说「未解」');
{
  const hits = all.filter((f) => ONLY_UNDECIDED.test(f.desc.trim()));
  check('没有「整句只有未解 / 未证 / 尚未证明」的说明', hits.length === 0,
    report(hits, (f) => f.where));
}

console.log('\n7) 说明不长于 160 字');
{
  const hits = all.filter((f) => f.desc.length > TOO_LONG);
  check(`说明都不长于 ${TOO_LONG} 字`, hits.length === 0,
    report(hits, (f) => `${f.where}（${f.desc.length} 字）`));
}

console.log('\n8) 页面文本里没有字面 **');
{
  // 说明与标签：编辑器不渲染 markdown，星号会原样露出来。
  //
  // （表与表的 note 不在检查范围内 —— editors.js 渲染它们时用的是
  //   `plainText()`，星号当场就被剥掉了，页面上看不到。）
  const hits = all.filter((f) => STARS.test(f.desc) || STARS.test(f.label));
  check('字段的说明与标签里没有 **', hits.length === 0,
    report(hits, (f) => f.where));
  // 文本记录的标签也是页面上直接显示的字。
  const recordHits = [];
  for (const table of pack.texts || []) {
    for (const record of table.records || []) {
      if (STARS.test(String(record.label || ''))) recordHits.push(`${table.id}#${record.id}`);
    }
  }
  check('文本记录的标签里没有 **', recordHits.length === 0,
    report(recordHits, (f) => f));
}

console.log(`\n${failures === 0 ? '全部通过' : failures + ' 项失败'}`);
process.exit(failures === 0 ? 0 : 1);
