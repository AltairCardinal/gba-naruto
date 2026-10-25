// 可视化对白编辑器：把一场剧情脚本画成 240×160 的画面，并让人能在对白之间快速跳转、连续播放。
//
// 这一页是**看与改对白的地方**，不是字节码表：
//   * 左边是**舞台** —— 背景、立绘、对白框、正文，按游戏里的比例画；
//   * 右边是**对白列表** —— 这一场的每一条消息（一行 = 一个对白框：
//     上面是名字行，下面是正文），点一下就跳到那一条；
//   * 下面是**播放条** —— 按脚本顺序一条一条推进，可以暂停、可以单步。
//
// 文字**可以就地改，长度不限**：正文内联在字节流里，而脚本里的分支目标是
// 绝对 ROM 地址 —— 等长的直接原地改写；变长 / 变短的话，构建时会把**整个剧本**
// 搬到 ROM 的空闲区，把它内部的绝对地址全部重基，再改根表里指向它的指针。
// 这条约束与写回通路都在 `js/scripttext.js` 与 `js/rom.js` 里，界面上复用同一套。
//
// 依据：
//   * `notes/story-vm-opcodes-20261020.md` §3（操作码语义，权威）
//   * `notes/evidence/story-scene-l3-20261020.md`（mGBA 真机画面）
//   * `notes/evidence/story-message-box-20261022.md`（消息框与台词表）
//   * `notes/evidence/portrait-render-chain-20261022.md`（立绘）
//   * `notes/evidence/story-background-chain-20261022.md`（背景）
//   * `notes/evidence/dialogue-font-render-20261022.md`（对白字形）

import { el, clear, toast, clickableArea } from '../ui.js';
import {
  buildDialogueModel, jumpTo, stepDelayMs, DEFAULT_STEP_MS,
  STAGE_W, STAGE_H, ROOT_LABELS,
} from '../dialogue.js';
import {
  ENTRY_SCENE, SCENE_ID_NOTE, sceneHint, sceneLabel, sceneOptionGroups,
  sceneTag,
} from '../sceneid.js';
import { renderStage } from '../stage.js';
import { textSegmentCell } from './scriptview.js';

const ROOTS = ['before', 'after', 'logic', 'events'];

/**
 * 每一场戏的临时状态（当前在哪一句、播不播、间隔多长）。
 *
 * **不进内容包** —— 换关卡就换一份。
 */
const stateByScene = new Map();

function stateOf(root, scene) {
  const key = `${root}/${scene}`;
  let state = stateByScene.get(key);
  if (!state) {
    state = { index: 0, playing: false, timer: null, delayMs: DEFAULT_STEP_MS };
    stateByScene.set(key, state);
  }
  return state;
}

/**
 * 可视化对白编辑器的主入口。
 *
 * @param {HTMLElement} container
 * @param {object} ctx
 * @param {{root?:string, scene?:number}} params
 */
export function renderDialogueView(container, ctx, params) {
  clear(container);
  const pack = ctx.pack;
  const rom = ctx.rom || ctx.baseRom;
  const root = ROOTS.includes(params && params.root) ? params.root : 'before';
  // 没指定场景时落在**主线入口**（场景 54）—— 那才是玩家在游戏里最先看到的一场。
  // 场景号不是「第几场」，所以「第一场」不等于场景 1（场景 1 是第 1 关的战前剧情）。
  const scene = Number(params && params.scene) || ENTRY_SCENE;
  const state = stateOf(root, scene);

  const model = buildDialogueModel(rom, pack, root, scene);

  // --- 顶栏：换剧本 / 换场景 ----------------------------------------------
  const rootSelect = el('select', {
    class: 'search',
    onchange: (e) => ctx.openPanel('dialogue', '对白', {
      root: e.target.value, scene,
    }),
  });
  for (const id of ROOTS) {
    rootSelect.appendChild(el('option', {
      value: id, text: ROOT_LABELS[id], selected: id === root,
    }));
  }
  const structure = pack.structure(
    root === 'before' ? 'story_before_root'
      : root === 'after' ? 'story_after_root'
        : root === 'logic' ? 'story_logic_root' : 'story_events_root');
  const sceneSelect = el('select', {
    class: 'search',
    onchange: (e) => ctx.openPanel('dialogue', '对白', {
      root, scene: Number(e.target.value),
    }),
  });
  // 下拉按「作者找得到」的顺序分组：主线入口在最前，然后是关卡场景，
  // 最后是其余特殊场景 —— 组内仍按场景号升序（场景号是键，顺序不能乱）。
  for (const group of sceneOptionGroups(structure, scene)) {
    const groupNode = el('optgroup', { label: group.label });
    for (const s of group.scenes) {
      groupNode.appendChild(el('option', {
        value: String(s), text: sceneLabel(s), selected: s === scene,
      }));
    }
    sceneSelect.appendChild(groupNode);
  }

  container.appendChild(el('div', { class: 'panel-head' }, [
    el('div', {}, [
      el('h2', { text: `对白 · ${sceneLabel(scene)}` }),
      el('div', { class: 'panel-sub' }, [
        el('span', { text: `${ROOT_LABELS[root]}剧本` }),
        el('span', { text: model.pointer ? `ROM 0x${model.pointer.toString(16).toUpperCase()}` : '无剧本' }),
        el('span', { text: `${model.counts.lines} 条消息` }),
      ]),
    ]),
    el('div', { class: 'panel-tools' }, [
      rootSelect, sceneSelect,
      el('button', {
        class: 'btn btn-tiny',
        text: '看字节码',
        title: '打开剧本查看器（指令表、分支目标）',
        onclick: () => ctx.onJump({
          module: 'story', kind: 'script', id: 'script',
          params: { root, scene },
          label: `${ROOT_LABELS[root]} · ${sceneLabel(scene)}`,
        }),
      }),
    ]),
  ]));

  container.appendChild(el('div', { class: 'rule-note' }, [
    el('span', { class: 'rule-title', text: '说明' }),
    el('span', {
      text: '左边是这一场戏的画面：背景、立绘、对白框、正文，按游戏里的比例画。' +
        '右边是这一场的每一条消息，点一下就跳到那一条。' +
        '**一条消息 = 一个对白框**：上面一行是**名字行**，下面是正文。' +
        '名字行有两个来源 —— 说话人名表里的名字（脚本里的 0x08），' +
        '或者 0x20 指令自带的内联文本（那种名字行就在这条消息里，标着「名字行」，也能改）。' +
        '正文**可以就地改，长度不限** —— 正文内联在脚本字节流里，' +
        '而脚本里的分支目标是绝对地址，所以等长的直接原地改写；' +
        '**变长 / 变短**的话，构建时会把**整个剧本**搬到 ROM 的空闲区，' +
        '把它内部的绝对地址全部重基，再改根表里指向它的指针。' +
        '每个输入框旁边写着「现在多少字节 / 原来多少字节」，' +
        '以及这一改会不会搬动剧本。',
    }),
  ]));

  // 这一场**是什么** + 场景号到底怎么读 —— 这一段是本轮补的：
  // 以前场景下拉写「第 N 场」，把场景号说成了顺序，于是**游戏开局
  // （场景 54）看起来像最后一场**，占位场景 55 还排在它前面。
  const hint = sceneHint(scene);
  container.appendChild(el('p', { class: 'section-note', text: [
    hint ? `这一场：${sceneTag(scene)}。${hint}` : '',
    SCENE_ID_NOTE,
  ].filter(Boolean).join(' ') }));

  if (!model.hasScript) {
    container.appendChild(el('div', { class: 'empty' }, [
      el('div', { text: model.empty || '这一场没有可显示的对白。' }),
    ]));
    return;
  }

  // --- 版面：左舞台 / 右列表 ----------------------------------------------
  const stage = stagePanel(ctx, model, state);
  const list = listPanel(ctx, model, state, stage);
  container.appendChild(el('div', { class: 'dlg-layout' }, [stage.node, list.node]));
}

/**
 * 左边的舞台：画面 + 播放条 + 「这一句在脚本里的什么状态」。
 *
 * 舞台画在一个 240×160 的坐标系里，再用 CSS 放大 —— 放大的是**整幅画面**，
 * 所以背景的像素、字的行距、框的位置都按游戏的比例。
 */
function stagePanel(ctx, model, state) {
  const canvas = el('canvas', { class: 'dlg-canvas', width: STAGE_W, height: STAGE_H });
  const nameNode = el('div', { class: 'dlg-name' });
  const textNode = el('div', { class: 'dlg-text' });
  const boxNode = el('div', { class: 'dlg-box' }, [nameNode, textNode]);
  const screen = el('div', { class: 'dlg-screen' }, [canvas, boxNode]);
  const stage = el('div', { class: 'dlg-stage' }, [screen]);

  const position = el('div', { class: 'dlg-position' });
  const progress = el('div', { class: 'dlg-progress' });

  // --- 播放条 ------------------------------------------------------------
  const playButton = el('button', { class: 'btn btn-tiny', text: '播放' });
  const prevButton = el('button', { class: 'btn btn-tiny', text: '上一条' });
  const nextButton = el('button', { class: 'btn btn-tiny', text: '下一条' });
  const delayLabel = el('span', { class: 'dlg-delay-label', text: `每条 ${state.delayMs} 毫秒` });
  const delayInput = el('input', {
    class: 'num-input', type: 'text', style: { width: '64px' },
    value: String(state.delayMs),
    title: '播放时每条消息停留多久（毫秒）。这不是 ROM 里的值 —— ' +
      '对白在游戏里是等玩家按键才翻页的，停留多久由作者定。',
    onchange: (e) => {
      const value = Number(e.target.value);
      if (!Number.isFinite(value) || value < 100 || value > 20000) {
        toast('请输入 100–20000 毫秒', 'error');
        e.target.value = String(state.delayMs);
        return;
      }
      state.delayMs = Math.round(value);
      delayLabel.textContent = `每条 ${state.delayMs} 毫秒`;
    },
  });

  const controls = el('div', { class: 'dlg-controls' }, [
    playButton, prevButton, nextButton,
    el('span', { class: 'dlg-sep' }),
    delayLabel, delayInput,
    el('span', { class: 'dlg-sep' }),
    progress,
  ]);

  const node = el('div', { class: 'dlg-left' }, [
    el('div', { class: 'dlg-stage-wrap' }, [stage]),
    controls,
    position,
  ]);

  // --- 画当前这一句 ------------------------------------------------------
  function paint() {
    const line = model.lines[state.index] || null;
    paintStage(ctx, canvas, boxNode, nameNode, textNode, model, line);
    progress.textContent = model.lines.length
      ? `第 ${state.index + 1} / ${model.lines.length} 条消息`
      : '没有消息';
    clear(position);
    position.appendChild(el('span', {
      class: 'dlg-state',
      text: line ? describeState(line) : '—',
    }));
    if (line) {
      position.appendChild(el('span', {
        class: 'dlg-state',
        text: `正文在 ROM 0x${(line.offset + 0x08000000).toString(16).toUpperCase()}`,
      }));
    }
  }

  // --- 播放 --------------------------------------------------------------
  function stop() {
    state.playing = false;
    if (state.timer) { clearTimeout(state.timer); state.timer = null; }
    playButton.textContent = '播放';
  }

  function schedule() {
    if (!state.playing) return;
    if (state.timer) clearTimeout(state.timer);
    const delay = stepDelayMs(model.lines[state.index], state.delayMs);
    state.timer = setTimeout(() => {
      if (!state.playing) return;
      if (state.index >= model.lines.length - 1) { stop(); paint(); return; }
      state.index += 1;
      paint();
      onIndexChanged(state.index);
      schedule();
    }, delay);
  }

  playButton.addEventListener('click', () => {
    if (state.playing) { stop(); paint(); return; }
    if (!model.lines.length) return;
    state.playing = true;
    playButton.textContent = '暂停';
    schedule();
  });
  prevButton.addEventListener('click', () => {
    stop();
    state.index = jumpTo(model.lines, state.index - 1);
    paint();
    onIndexChanged(state.index);
  });
  nextButton.addEventListener('click', () => {
    stop();
    state.index = jumpTo(model.lines, state.index + 1);
    paint();
    onIndexChanged(state.index);
  });

  /** 舞台换句时，列表也跟着滚到那一句（列表自己订了回调）。 */
  function onIndexChanged(index) {
    if (state.onIndexChanged) state.onIndexChanged(index);
  }

  paint();
  return { node, paint, onIndexChanged };
}

/** 这一句在脚本里的画面状态（人话）。 */
function describeState(line) {
  const parts = [];
  parts.push(line.backgroundId === null || line.backgroundId === undefined
    ? '背景：这一场没写换底图'
    : `底图 ${line.backgroundId}`);
  const portraits = [];
  if (line.portraitA !== null && line.portraitA !== undefined && line.portraitA !== 0) {
    portraits.push(`头像 ${line.portraitA}`);
  }
  if (line.portraitB !== null && line.portraitB !== undefined && line.portraitB !== 0) {
    portraits.push(`头像 ${line.portraitB}`);
  }
  parts.push(portraits.length ? `立绘：${portraits.join(' + ')}` : '立绘：无');
  parts.push(line.nameText ? `名字行：${line.nameText}` : '名字行：无');
  if (line.waitFrames !== null && line.waitFrames !== undefined) {
    parts.push(`脚本在这里等 ${line.waitFrames} 帧`);
  }
  return parts.join('　·　');
}

/**
 * 把一句话画到舞台上。
 *
 * **整幅画面都是像素**：背景、立绘、对白框、名牌、正文 —— 全部按 ROM 里的
 * 原始数据画，所以看着就是游戏里的样子。
 *
 *   * 背景：剧情底图（240×80，在上半屏；`BG0VOFS=-8` 的下移已经算进去了）
 *   * 立绘：消息框立绘（80×80，槽 0 在 x=16、槽 1 在 x=144）
 *   * 对白框：按真机量出来的几何与配色画的等效框
 *     （框的边框花纹是 BG3 的图块，仓库还没定位到那组图块 ⇒ 花纹对不上）
 *   * 名牌与正文：**用 ROM 里的原字形**画（8×16 2bpp）
 *
 * 依据：notes/evidence/{story-background-chain,portrait-render-chain,
 * dialogue-font-render}-20261022.md —— 每一块都与 mGBA 真机画面逐像素比对过。
 */
function paintStage(ctx, canvas, boxNode, nameNode, textNode, model, line) {
  const rom = ctx.rom || ctx.baseRom;
  const context = canvas2d(canvas);
  if (context) {
    context.clearRect(0, 0, STAGE_W, STAGE_H);
    // 整幅画面由 `js/stage.js` 合成（背景 + 立绘 + 对白框 + 名牌 + 正文），
    // 那边是纯函数，门禁能拿它跟 mGBA 真机画面逐像素比对。
    const stage = renderStage(rom, line);
    const data = context.createImageData(stage.width, stage.height);
    data.data.set(stage.pixels);
    context.putImageData(data, 0, 0);
  }

  // 画布里的字是像素，**读不出来** —— 所以另存一份文字在 DOM 里
  //（屏幕阅读器能读，也方便自动化检查）。
  clear(nameNode);
  clear(textNode);
  boxNode.classList.toggle('empty', !line);
  if (!line) return;
  nameNode.textContent = line.nameText || '';
  nameNode.style.display = line.speakerName ? '' : 'none';
  // 正文里的换行（0x0A）在界面上显示成 ↵；这里换成真正的换行。
  textNode.textContent = line.text.split('↵').join('\n');
}

/**
 * 右边的对白列表。
 *
 * 一行 = **一条消息**（= 游戏里的一个对白框）。
 * 每行：序号 + 名字 + 地址 + 名字行输入框（只有 `0x20` 内联名字时才有）+ 正文输入框 + 字节预算。
 * 点序号那一块就跳到那一条（舞台跟着换）。
 */
function listPanel(ctx, model, state, stage) {
  const list = el('div', { class: 'dlg-list' });
  const node = el('div', { class: 'dlg-side' }, [
    el('div', { class: 'dlg-list-head' }, [
      el('span', { text: `这一场 ${model.counts.lines} 条消息` }),
      el('span', { class: 'stat-hint', text: '点序号跳到那一条' }),
    ]),
    list,
  ]);

  for (const line of model.lines) {
    const row = el('div', {
      class: 'dlg-row',
      dataset: { dlgLine: String(line.index) },
      title: '点这一行的任何地方都能跳到这一句（正文输入框和「跳到原始字节」除外）',
    });
    const select = () => {
      state.playing = false;
      state.index = line.index;
      stage.paint();
      stage.onIndexChanged(line.index);
    };
    const head = el('button', {
      class: 'dlg-row-head',
      type: 'button',
      title: '跳到这一句',
      onclick: select,
    }, [
      el('span', { class: 'dlg-row-no', text: `#${line.index + 1}` }),
      el('span', { class: 'dlg-row-speaker', text: line.nameText || '（无名牌）' }),
      el('span', { class: 'dlg-row-addr', text: '0x' + (line.offset + 0x08000000).toString(16).toUpperCase() }),
    ]);
    const body = el('div', { class: 'dlg-row-body' });
    // **名字行**（`0x20` 自带的内联文本）—— 它是这条消息的一部分，
    // 在游戏里画在消息框顶上那一行（名牌位、名牌色），也能就地改。
    for (const segment of line.nameSegments || []) {
      body.appendChild(el('div', { class: 'dlg-row-name' }, [
        el('span', {
          class: 'dlg-row-name-tag',
          title: '这一行的名字来自脚本里的 0x20 指令（它自带一段内联文本）。' +
            '游戏把它画在消息框顶上那一行 —— 与说话人名表里的名字**同一个位置、同一套颜色**。',
          text: '名字行',
        }),
        textSegmentCell(ctx, segment, () => {
          line.nameText = line.nameSegments.map((s) => s.text).join('');
          stage.paint();
        }),
      ]));
    }
    for (const segment of line.segments) {
      body.appendChild(textSegmentCell(ctx, segment, () => {
        // 改完正文：这一句的文本变了，舞台与计数都要跟上。
        line.text = line.segments.map((s) => s.text).join('');
        line.characters = line.text.length;
        stage.paint();
      }));
    }
    row.appendChild(head);
    row.appendChild(body);
    // 整张卡都能点 —— 只有正文输入框和「跳到原始字节」保留自己的动作。
    clickableArea(row, select);
    list.appendChild(row);
  }

  if (!model.lines.length) {
    list.appendChild(el('div', { class: 'empty', text: '这一场没有带文字的指令。' }));
  }

  // 舞台换句时，列表里当前那一句高亮并滚到可见。
  function markCurrent(index) {
    for (const row of list.children) {
      if (!row.dataset) continue;
      const isCurrent = Number(row.dataset.dlgLine) === index;
      row.classList.toggle('current', isCurrent);
      if (isCurrent && row.scrollIntoView) row.scrollIntoView({ block: 'nearest' });
    }
  }
  state.onIndexChanged = markCurrent;
  markCurrent(state.index);

  return { node, markCurrent };
}

/** 画布的 2D 上下文（无头环境里没有，返回 null）。 */
function canvas2d(canvas) {
  if (!canvas || typeof canvas.getContext !== 'function') return null;
  try {
    return canvas.getContext('2d');
  } catch (err) {
    return null;
  }
}
