// 可视化对白编辑器的无头验收（第十二轮）。
//
// 对应 notes/specs/dialogue-editor-20261022.md 的验收清单：
// 舞台 / 对白列表 / 快速跳转 / 实时播放 / 就地改对白。
//
// 用法：node rom-editor/tools/verify_dialogue_view.mjs
//
// stdout 在 PowerShell 下会被 GBK 弄乱，所以正文写到
// build/dialogue-view-verify.txt。
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { installDom } from './domstub.mjs';
import { decodePng } from './png.mjs';

const documentStub = installDom();

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const packPath = join(repoRoot, 'rom-editor', 'content', 'pack.json');
const romPath = join(repoRoot, 'rom', 'base.gba');

const { ContentPack } = await import('../js/pack.js');
const model = await import('../js/dialogue.js');
const vm = await import('../js/storyvm.js');
const { renderDialogueView } = await import('../js/modules/dialogueview.js');
const { renderScriptView } = await import('../js/modules/scriptview.js');
const { renderStage } = await import('../js/stage.js');
const { parseHash, hashFor } = await import('../js/routing.js');

const lines = [];
let failures = 0;
function check(name, ok, detail = '') {
  if (!ok) failures += 1;
  const line = `  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`;
  lines.push(line);
  console.log(line);
}
function head(text) {
  lines.push(text);
  console.log(text);
}

const packData = JSON.parse(readFileSync(packPath, 'utf8'));
const pack = ContentPack.fromJSON(packData);
const rom = new Uint8Array(readFileSync(romPath));

const jumps = [];
const opened = [];
const changed = [];
const ctx = {
  pack,
  rom,
  baseRom: rom,
  state: { view: { panel: null } },
  onChange() { changed.push(1); },
  openPanel(kind, id, params) { opened.push({ kind, id, params }); },
  goModule() {},
  render() {},
  setStatus() {},
  onJump(target) { jumps.push(target); },
};

head('\n1) 模型：这一场的对白句与真机证据一致');
{
  const m = model.buildDialogueModel(rom, pack, 'before', 54);
  check('场景 54 的 before 剧本有消息', m.lines.length > 0, `${m.lines.length} 条消息`);
  check('场景 54 的剧本指针是 0x08049E76（L2 采样里 VM 入口收到的 r0）',
    m.pointer === 0x08049e76, '0x' + m.pointer.toString(16).toUpperCase());

  // 真机画面（notes/evidence/story-scene-l3.png）上显示的就是**第 4 条消息** ——
  // 这是**屏幕证据**，模型必须与它一字不差。
  //
  // 为什么是第 4 条而不是第 5 条：**一条消息 = 一个对白框**，
  // 名字行（`0x20` 的内联文本）与正文（`0x01`）是**同一个框**里的两行，
  // 所以场景 54 的第 1 条消息（名字行「漩涡鸣人」+ 正文「“呜哇！…”」）
  // 只占**一行**。见 notes/evidence/dialogue-name-row-20261024.md。
  const fourth = m.lines[3];
  check('第 4 条消息的正文与 mGBA 真机画面上那句一字不差',
    fourth && fourth.text.replace(/[↵\s]/g, '') === '“是啊，是我这个班主任所承认的嘛！”',
    fourth ? fourth.text : '没有第 4 条消息');

  check('每一条消息都带名字行或明确没有',
    m.lines.every((l) => l.nameText === null || typeof l.nameText === 'string'));
  check('名字行有两个来源：说话人名表与 0x20 的内联文本',
    m.lines.some((l) => l.nameKind === 'table') && m.lines.some((l) => l.nameKind === 'text'),
    [...new Set(m.lines.map((l) => l.nameKind))].join('、'));
  const named = m.lines.filter((l) => l.speakerName);
  check('有说话人名字的句子不止一种（名字表真的被用上了）',
    new Set(named.map((l) => l.speakerName)).size >= 3,
    [...new Set(named.map((l) => l.speakerName))].join('、'));

  // 立绘是 `0x02 / 0x04` 写进去的（槽 + 头像 id + 表情），
  // `0x11` 清某槽 —— 所以既有「有立绘」的句，也有「没立绘」的句。
  const portraitIds = new Set();
  let withoutPortrait = 0;
  for (const line of m.lines) {
    for (const portrait of line.portraits) {
      if (portrait && portrait.id) portraitIds.add(portrait.id);
    }
    if (!line.portraits.some((p) => p && p.id)) withoutPortrait += 1;
  }
  check('立绘 id 随句子变化（0x02 / 0x04 写进去的）',
    portraitIds.size >= 3, [...portraitIds].join('、'));
  check('有立绘的句与没立绘的句都有（0x11 会清槽）',
    withoutPortrait > 0 && withoutPortrait < m.lines.length,
    `${withoutPortrait} / ${m.lines.length} 句没有立绘`);
}

head('\n2) 模型：四张根表都能走');
{
  for (const [root, scene] of [['before', 54], ['after', 3], ['logic', 40], ['events', 40]]) {
    const m = model.buildDialogueModel(rom, pack, root, scene);
    check(`${root} / 第 ${scene} 场能扫出指令`, m.instructions.length > 0,
      `${m.instructions.length} 条指令 / ${m.lines.length} 条消息`);
  }
  const empty = model.buildDialogueModel(null, pack, 'before', 54);
  check('没有 ROM 时给了一句说明而不是崩掉',
    !!empty.empty && empty.lines.length === 0, empty.empty || '');
  const noScript = model.buildDialogueModel(rom, pack, 'before', 999);
  check('没有剧本的那一场给了一句说明',
    !!noScript.empty, noScript.empty || '');
}

head('\n3) 跳转与播放间隔');
{
  check('jumpTo 夹到边界（负数 → 0，超界 → 最后一句）',
    model.jumpTo([0, 1, 2], -5) === 0 && model.jumpTo([0, 1, 2], 99) === 2,
    `${model.jumpTo([0, 1, 2], -5)} / ${model.jumpTo([0, 1, 2], 99)}`);
  check('空列表时 jumpTo 返回 -1', model.jumpTo([], 3) === -1);

  const m = model.buildDialogueModel(rom, pack, 'before', 54);
  const withWait = m.lines.find((l) => l.waitFrames !== null);
  check('有 0x0F 等待的行能按帧换算成毫秒',
    !withWait || model.stepDelayMs(withWait) >= 300,
    withWait ? `${withWait.waitFrames} 帧 → ${model.stepDelayMs(withWait)} 毫秒` : '这一场没有 0x0F');
  check('没有等待的行用默认间隔',
    model.stepDelayMs({ waitFrames: null }, 1234) === 1234);
}

head('\n4) 视图：舞台 / 列表 / 播放条都在');
{
  const host = new (globalThis.document.createElement('div').constructor)('div');
  renderDialogueView(host, ctx, { root: 'before', scene: 54 });
  const text = host.textContent;
  const nodes = host.descendants();

  check('页面渲染出来了（不抛异常、节点非空）', nodes.length > 0, `${nodes.length} 个节点`);
  check('有一个 240×160 的画布',
    nodes.some((n) => n.tagName === 'CANVAS' && n.attributes.width === '240' && n.attributes.height === '160'));
  check('有对白框与名牌的容器',
    nodes.some((n) => String(n.className).includes('dlg-box'))
    && nodes.some((n) => String(n.className).includes('dlg-name')));
  check('有播放 / 上一条 / 下一条三个控制',
    text.includes('播放') && text.includes('上一条') && text.includes('下一条'));
  check('有进度指示', text.includes('/ ') && text.includes('条消息'), '');

  const rows = nodes.filter((n) => n.dataset && n.dataset.dlgLine !== undefined);
  const m = model.buildDialogueModel(rom, pack, 'before', 54);
  check('列表行数 = 这一场的消息条数',
    rows.length === m.lines.length, `${rows.length} / ${m.lines.length}`);
  check('每行都带序号与说话人',
    rows.every((r) => r.textContent.includes('#')) && rows.some((r) => r.textContent.includes('鸣人')));
  check('每行都有可编辑的正文输入框',
    rows.every((r) => r.descendants().some((n) => n.tagName === 'INPUT'
      && String(n.className).includes('text-input-inline'))));
  check('页面上没有字面 **', !text.includes('**'), '');
}

head('\n5) 快速跳转：点列表那一行，舞台就换到那一条');
{
  const host = new (globalThis.document.createElement('div').constructor)('div');
  renderDialogueView(host, ctx, { root: 'before', scene: 54 });
  const rows = host.descendants().filter((n) => n.dataset && n.dataset.dlgLine !== undefined);
  const target = rows[9];
  const head = target.descendants().find((n) => String(n.className).includes('dlg-row-head'));
  check('列表行有可点的行头', !!head);
  if (head) {
    head.listeners.click[0]({ target: head });
    const text = host.textContent;
    check('点第 10 行之后，舞台上的正文换成了那一条',
      text.includes('第 10 /'), text.match(/第 \d+ \/ \d+ 条消息/) ? text.match(/第 \d+ \/ \d+ 条消息/)[0] : '');
    check('当前那一条在列表里被标出来了',
      host.descendants().some((n) => n.classList && n.classList.contains('current')
        && n.classList.contains('dlg-row')));
  }
}

head('\n6) 实时播放：按脚本顺序一条一条推进');
{
  const host = new (globalThis.document.createElement('div').constructor)('div');
  renderDialogueView(host, ctx, { root: 'before', scene: 54 });
  const buttons = host.descendants().filter((n) => n.tagName === 'BUTTON');
  const play = buttons.find((b) => b.textContent === '播放');
  const next = buttons.find((b) => b.textContent === '下一条');
  const prev = buttons.find((b) => b.textContent === '上一条');
  check('有播放 / 下一条 / 上一条三个按钮', !!play && !!next && !!prev);

  // 播放位置是**故意跨重绘保留**的（换关卡再回来还停在这一条），
  // 所以断言要用相对位移，不能钉死绝对句号。
  const currentIndex = () => Number((host.textContent.match(/第 (\d+) \/ \d+ 条消息/) || [])[1] || 0);

  if (next && prev) {
    const before = currentIndex();
    next.listeners.click[0]({ target: next });
    const afterNext = currentIndex();
    check('点「下一条」前进一条', afterNext === before + 1, `${before} → ${afterNext}`);
    prev.listeners.click[0]({ target: prev });
    const afterPrev = currentIndex();
    check('点「上一条」退回去', afterPrev === before, `${afterNext} → ${afterPrev}`);
  }

  if (play) {
    // 把间隔改成最小值再播 —— 播放用的是状态里的 delayMs。
    const delayInput = host.descendants().find((n) => n.tagName === 'INPUT'
      && String(n.className).includes('num-input'));
    check('有播放间隔输入框', !!delayInput);
    if (delayInput) {
      delayInput.value = '100';
      delayInput.listeners.change[0]({ target: delayInput });
      const before = currentIndex();
      play.listeners.click[0]({ target: play });
      await new Promise((resolve) => setTimeout(resolve, 260));
      const after = currentIndex();
      check('播放会自动推进到下一条', after > before, `${before} → ${after}`);
      const pause = host.descendants().find((n) => n.tagName === 'BUTTON' && n.textContent === '暂停');
      check('播放中按钮变成「暂停」', !!pause);
      if (pause) {
        pause.listeners.click[0]({ target: pause });
        const at = currentIndex();
        await new Promise((resolve) => setTimeout(resolve, 260));
        const still = currentIndex();
        check('点「暂停」之后不再推进', at === still, `暂停在第 ${at} 条`);
      }
    }
  }
}

head('\n7) 一条消息 = 一个对白框：名字行（0x20）与正文（0x01）是同一条');
{
  const m = model.buildDialogueModel(rom, pack, 'before', 54);
  const first = m.lines[0];
  const trim = (s) => String(s || '').replace(/[\s　↵]/g, '');
  check('第 1 条消息的名字行是 0x20 自带的内联文本',
    first.nameKind === 'text' && trim(first.nameText) === '漩涡鸣人',
    `${first.nameKind} / ${first.nameText}`);
  check('第 1 条消息的正文是后面那条 0x01',
    trim(first.text) === '“呜哇！果然还是一乐的拉面最好吃呀！！”',
    first.text);
  check('名字行与正文在**同一条消息**里（一条消息只有一个行号）',
    m.lines[0].nameSegments !== null && m.lines[0].segments.length > 0
    && m.lines.filter((l) => trim(l.text) === '漩涡鸣人').length === 0,
    '名字行不再单独占一行');

  // 与**真机画面**逐像素比对（2026-10-24 新抓）：
  // `notes/evidence/scene54-first-message-20261024.png` = 真机上 START + 1 次 A
  // 之后的那一帧 —— 名字行「漩涡鸣人」+ 正文「“呜哇！…”」**在同一个框里**。
  const refPath = join(repoRoot, 'notes', 'evidence', 'scene54-first-message-20261024.png');
  if (!existsSync(refPath)) {
    check('真机第一帧证据在仓库里', false, refPath);
  } else {
    const reference = decodePng(readFileSync(refPath));
    const stage = renderStage(rom, m.lines[0]);
    const zones = {
      '名字行（0x20 的内联名字，x=24 起、名牌色）': (x, y) => y >= 103 && y < 120 && x >= 20 && x < 60,
      '正文行（第 1 条消息的 0x01 正文）': (x, y) => y >= 120 && y < 136 && x >= 20 && x < 184,
    };
    for (const [label, inside] of Object.entries(zones)) {
      let same = 0;
      let diff = 0;
      for (let y = 0; y < 160; y++) {
        for (let x = 0; x < 240; x++) {
          if (!inside(x, y)) continue;
          const at = (y * 240 + x) * 4;
          if (stage.pixels[at] === reference.pixels[at]
            && stage.pixels[at + 1] === reference.pixels[at + 1]
            && stage.pixels[at + 2] === reference.pixels[at + 2]) same += 1;
          else diff += 1;
        }
      }
      check(`${label}：与真机画面逐像素相同`, diff === 0, `相同 ${same} / 不同 ${diff}`);
    }
  }
}

head('\n8) 就地改对白：长度不限（变长会搬动剧本）');
{
  const host = new (globalThis.document.createElement('div').constructor)('div');
  renderDialogueView(host, ctx, { root: 'before', scene: 54 });
  const pageText = host.textContent || '';
  check('页面的说明条写明「长度不限」', pageText.includes('长度不限'), '');
  check('页面的说明条写明会「搬到空闲区」', pageText.includes('空闲区'), '');
  check('页面的说明条不再说「必须等长」', !pageText.includes('必须等长'));
  const rows = host.descendants().filter((n) => n.dataset && n.dataset.dlgLine !== undefined);
  const first = rows[0];
  const m = model.buildDialogueModel(rom, pack, 'before', 54);
  const segment = m.lines[0].segments[0];
  // 第 1 行有**两个**输入框：上面是名字行（`0x20` 的内联文本），
  // 下面是正文（`0x01`）。这里要的是**正文**那个。
  const inputs = first.descendants().filter((n) => n.tagName === 'INPUT'
    && String(n.className).includes('text-input-inline'));
  const input = inputs.find((n) => n.value === segment.text) || inputs[inputs.length - 1];
  check('正文输入框拿到的初值就是那句正文', input && input.value === segment.text,
    input ? input.value.slice(0, 24) : '没有输入框');

  const before = pack.changedCount();
  if (input) {
    // 改长一个字 —— 现在**不再被拒**：构建时会把整个剧本搬到空闲区并重基地址。
    input.value = segment.text + '啊';
    input.listeners.change[0]({ target: input });
    check('改长一个字被接受（会搬动剧本）', pack.changedCount() === before + 1,
      `改动数 ${before} → ${pack.changedCount()}`);
    const toastText = documentStub.body.textContent;
    check('提示里写明了「搬到空闲区」', toastText.includes('搬到空闲区'), toastText.slice(0, 80));
    check('改长后输入框保留新文本', input.value === segment.text + '啊', input.value.slice(0, 24));
    // 舞台上的正文也要跟着变（画布与 DOM 文字都是这一句的当前值）。
    const m2 = model.buildDialogueModel(rom, pack, 'before', 54);
    check('舞台那一句的正文也是新文本',
      m2.lines[0].text === segment.text + '啊', m2.lines[0].text.slice(0, 24));
  }
}

head('\n9) 深链接');
{
  const parsed = parseHash('#story/dialogue/before/54');
  check('#story/dialogue/before/54 能解析成对白视图',
    parsed.module === 'story' && parsed.panel && parsed.panel.kind === 'dialogue'
    && parsed.panel.params.root === 'before' && parsed.panel.params.scene === 54,
    JSON.stringify(parsed.panel && parsed.panel.params));
  const hash = hashFor({ module: 'story', panel: { kind: 'dialogue', id: '对白', params: { root: 'after', scene: 3 } } });
  check('能反向生成深链接', hash === '#story/dialogue/after/3', hash);
}

head('\n10) 与 mGBA 真机画面逐像素比对（这是最强的一条）');
{
  // 真机画面：mGBA 自己渲染器导出的 240×160（notes/evidence/story-scene-l3.png），
  // 对应场景 54 的**第 4 条消息**、按 A 键推进到的那一帧。
  //
  // （为什么是第 4 条：一条消息 = 一个对白框 = 名字行 + 正文；
  //   场景 54 的第 1 条消息把 `0x20` 的名字行与第 1 条 `0x01` 正文合在一起了。）
  const refPath = join(repoRoot, 'notes', 'evidence', 'story-scene-l3.png');
  if (!existsSync(refPath)) {
    check('真机画面证据在仓库里', false, refPath);
  } else {
    const reference = decodePng(readFileSync(refPath));
    const stageModel = model.buildDialogueModel(rom, pack, 'before', 54);
    const line = stageModel.lines[3];
    const stage = renderStage(rom, line);
    check('舞台是 240×160', stage.width === 240 && stage.height === 160);

    // 分区比：每一区单独算「与真机相同 / 不同」。
    const zones = {
      '背景（没有立绘也没有框的那段）': (x, y) => y >= 8 && y < 88 && x >= 96 && x < 144,
      '立绘（消息框立绘所在的 80×80）': (x, y) => y >= 8 && y < 88 && x >= 144 && x < 224,
      '名牌（框内的紫色名字）': (x, y) => y >= 104 && y < 120 && x >= 24 && x < 48,
      '正文（对白字所在的 24×16）': (x, y) => y >= 120 && y < 136 && x >= 24 && x < 168,
    };
    for (const [label, inside] of Object.entries(zones)) {
      let same = 0;
      let diff = 0;
      for (let y = 0; y < 160; y++) {
        for (let x = 0; x < 240; x++) {
          if (!inside(x, y)) continue;
          const at = (y * 240 + x) * 4;
          const a = stage.pixels;
          const b = reference.pixels;
          if (a[at] === b[at] && a[at + 1] === b[at + 1] && a[at + 2] === b[at + 2]) same += 1;
          else diff += 1;
        }
      }
      check(`${label}：与真机画面逐像素相同`, diff === 0, `相同 ${same} / 不同 ${diff}`);
    }

    // 整幅画面：允许有差别，但要能说清差在哪（左边那个过场人物 + 框的边框花纹）。
    let same = 0;
    let diff = 0;
    for (let y = 0; y < 160; y++) {
      for (let x = 0; x < 240; x++) {
        const at = (y * 240 + x) * 4;
        const a = stage.pixels;
        const b = reference.pixels;
        if (a[at] === b[at] && a[at + 1] === b[at + 1] && a[at + 2] === b[at + 2]) same += 1;
        else diff += 1;
      }
    }
    check('整幅画面与真机画面的一致率在 80% 以上（差的是过场人物与框的花纹）',
      same / (same + diff) > 0.8, `${(100 * same / (same + diff)).toFixed(2)}%`);
  }
}

head('\n11) 整块可点：点行里的任何地方都能选中，但输入框不抢');
{
  const host = new (globalThis.document.createElement('div').constructor)('div');
  renderDialogueView(host, ctx, { root: 'before', scene: 54 });
  const rows = host.descendants().filter((n) => n.dataset && n.dataset.dlgLine !== undefined);
  const row = rows[4];
  check('对白列表的每一行都标了「整块可点」',
    rows.every((r) => r.classList && r.classList.contains('area-clickable')),
    `${rows.length} 行`);

  // 找一个**不在按钮里**的普通元素 —— 行头那颗按钮里的文字点下去
  // 当然是「点那颗按钮」，不算「点行的空白处」。
  const plain = (() => {
    for (const node of row.descendants()) {
      if (String(node.tagName).toUpperCase() !== 'SPAN') continue;
      if (String(node.className || '').includes('xref-link')) continue;
      let up = node;
      let insideButton = false;
      while (up && up !== row) {
        if (String(up.tagName).toUpperCase() === 'BUTTON') { insideButton = true; break; }
        up = up.parentNode;
      }
      if (!insideButton) return node;
    }
    return null;
  })();
  const input = row.descendants().find((n) => String(n.tagName).toUpperCase() === 'INPUT');
  check('行里有一个普通元素可点（不在按钮里，也不是输入框）', !!plain && !!input);

  // 点行里的普通元素 → 选中这一句。
  row.listeners.click[0]({ target: plain });
  check('点行里的普通元素就选中这一条',
    host.textContent.includes('第 5 /'), (host.textContent.match(/第 \d+ \/ \d+ 条消息/) || [''])[0]);

  // 点正文输入框 → 不抢（那是编辑，不是选中）。
  const before = (host.textContent.match(/第 (\d+) \/ \d+ 条消息/) || [])[1];
  row.listeners.click[0]({ target: input });
  const after = (host.textContent.match(/第 (\d+) \/ \d+ 条消息/) || [])[1];
  check('点正文输入框不会切换当前条（那里是编辑，不是选中）', before === after,
    `第 ${before} 条 → 第 ${after} 条`);
}

head('\n12) 场景号口径：游戏开局是场景 54，不是「第 54 场」');
{
  // 这一组是 2026-10-24 补的 —— 以前场景下拉写「第 N 场」，把**场景号**
  // 说成了「第几场」，于是游戏开局（场景 54）看起来像最后一一场，
  // 占位场景 55 还排在它前面。
  const host = new (globalThis.document.createElement('div').constructor)('div');
  renderDialogueView(host, ctx, { root: 'before', scene: 54 });
  const nodes = host.descendants();
  const options = nodes.filter((n) => n.tagName === 'OPTION');
  const groups = nodes.filter((n) => n.tagName === 'OPTGROUP');
  const text = host.textContent;

  check('场景下拉里有「场景 54 · 主线入口（游戏开局）」这一项',
    options.some((o) => o.textContent === '场景 54 · 主线入口（游戏开局）'),
    options.filter((o) => String(o.textContent).includes('54')).map((o) => o.textContent).join(' / '));
  check('下拉分成组，主线入口排在最前',
    groups.length >= 2 && groups[0].getAttribute('label').includes('主线入口')
    && groups[0].children[0].textContent === '场景 54 · 主线入口（游戏开局）',
    groups.map((g) => g.getAttribute('label')).join(' / '));
  check('下拉里不再有「第 N 场」这种写法',
    !options.some((o) => /第 \d+ 场/.test(String(o.textContent))),
    options.filter((o) => /第 \d+ 场/.test(String(o.textContent))).map((o) => o.textContent).join(' / ') || '没有');
  check('关卡场景仍然带关卡名（场景 1 = 第 1 关）',
    options.some((o) => o.textContent === '场景 1（第 1 关）'),
    options.find((o) => String(o.textContent).includes('场景 1'))?.textContent || '没有');
  check('占位场景说得出自己是什么（55 = 无法进入此处）',
    options.some((o) => o.textContent.includes('场景 55') && o.textContent.includes('占位')),
    options.find((o) => String(o.textContent).includes('场景 55'))?.textContent || '没有');

  check('页面解释了「场景号不是第几场」',
    text.includes('它不是「第几场」'), '');
  check('页面点明游戏开局是场景 54',
    text.includes('游戏开局是场景 54'), '');

  // 不给参数时落在主线入口 —— 那是玩家在游戏里最先看到的一场。
  const defHost = new (globalThis.document.createElement('div').constructor)('div');
  renderDialogueView(defHost, ctx, {});
  check('不给场景号时默认落在主线入口（场景 54）',
    defHost.textContent.includes('场景 54 · 主线入口（游戏开局）'),
    (defHost.textContent.match(/对白 · [^（\n]{0,24}/) || [''])[0]);

  // 剧本查看器同一套口径：不再列 0 号空槽，默认也落在主线入口。
  const scriptHost = new (globalThis.document.createElement('div').constructor)('div');
  renderScriptView(scriptHost, ctx);
  const scriptOptions = scriptHost.descendants().filter((n) => n.tagName === 'OPTION');
  check('剧本查看器不再列 0 号空槽（四张根表的 0 号都没有指针）',
    !scriptOptions.some((o) => String(o.textContent).startsWith('场景 0')),
    scriptOptions.filter((o) => String(o.textContent).includes('场景 0')).map((o) => o.textContent).join(' / ') || '没有');
  check('剧本查看器默认也落在主线入口',
    scriptHost.textContent.includes('场景 54 · 主线入口（游戏开局）'),
    (scriptHost.textContent.match(/战前剧情 · [^（\n]{0,24}/) || [''])[0]);

  // 切到「战场事件逻辑」（那张根表只有 46 个槽）时，当前场景 54 不在表内 ——
  // 下拉必须**补出这一项**，否则它会显示成第一项（场景 1），与页面显示的对不上。
  const logicHost = new (globalThis.document.createElement('div').constructor)('div');
  renderDialogueView(logicHost, ctx, { root: 'logic', scene: 54 });
  const logicOptions = logicHost.descendants().filter((n) => n.tagName === 'OPTION');
  check('切到没有这一槽的根表时，下拉补出当前场景（不会显示成第一项）',
    logicOptions.some((o) => o.getAttribute('value') === '54'
      && o.getAttribute('selected') !== null),
    logicOptions.filter((o) => o.getAttribute('selected') !== null)
      .map((o) => o.getAttribute('value')).join(' / ') || '没有选中项');
}


const summary = failures === 0
  ? `全部通过（${lines.filter((l) => l.includes('[PASS]')).length} 条断言）`
  : `${failures} 项失败`;
lines.push('');
lines.push(summary);
writeFileSync(join(repoRoot, 'build', 'dialogue-view-verify.txt'), lines.join('\n') + '\n', 'utf8');
console.log('');
console.log(summary);
process.exit(failures === 0 ? 0 : 1);
