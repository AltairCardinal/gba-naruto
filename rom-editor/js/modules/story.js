// 剧情与对白
import { el, formatOffset } from '../ui.js';
import { renderDomainIndex, renderPanel, summaryTable, entryCard } from './common.js';
import { renderScriptView } from './scriptview.js';
import { renderDialogueView } from './dialogueview.js';
import { renderScene, renderFont } from './scene.js';

export function renderStory(container, ctx) {
  if (ctx.state.view.panel) {
    const { kind, id, params } = ctx.state.view.panel;
    if (kind === 'script') return renderScriptView(container, ctx);
    if (kind === 'dialogue') return renderDialogueView(container, ctx, params);
    if (kind === 'scene') return renderScene(container, ctx, params);
    if (kind === 'font') return renderFont(container, ctx, params);
    return renderPanel(container, ctx, kind, id, params);
  }

  const pack = ctx.pack;
  const slots = pack.textTable('quiz_questions');
  const index = pack.textTable('rom_text_index');
  const nonEmpty = slots ? slots.records.filter((r) => r.text).length : 0;
  const scripts = (pack.scripts || []).length;

  const extra = el('div', {}, [
    el('div', { class: 'card-grid' }, [
      stat('忍者问题', slots ? '305 道' : '—',
        slots ? `${slots.count} 个槽位 · ${nonEmpty} 条有内容` : '内容包里没有这张表'),
      stat('全 ROM 文本', index ? index.count : '按需载入',
        index ? '用 ROM 自带字库扫出' : '进入该表时自动下载索引'),
      stat('字形段', pack.structure('font_segments')?.entry_count || 0, '决定能画出哪些字'),
      stat('剧情底图', pack.structure('background_table')?.entry_count || 0, '底图 id'),
    ]),
  ]);

  const primary = entryCard(ctx, {
    title: '看对白画面 · 改对白',
    headline: '可视化对白编辑器',
    desc: '把一场剧情脚本画成游戏里的画面：背景、立绘、对白框、正文。' +
      '左边是画面，右边是这一场的每一句对白 —— 点一下就跳到那一句，' +
      '也可以连续播放；正文能就地改，长度不限（变长的话构建时会把整个剧本搬到空闲区）。' +
      '打开时落在**场景 54（主线入口）** —— 那才是游戏开局的那一场：' +
      '开机 → 标题 → START 之后走的就是它。',
    panel: { kind: 'dialogue', id: '对白' },
    actionLabel: '打开对白编辑器',
  });

  const secondary = entryCard(ctx, {
    title: '按忍者问题改',
    headline: '305 道忍者问题（1 道题 + 3 个选项）',
    desc: '忍者问题指针表 0x461CE8：游戏里的**问答小游戏**（不是剧情对白），' +
      '305 组，每组 4 条 + 1 个空指针分隔。' +
      '这一组是可重定位的，改长会重定位并改写指针。',
    panel: { kind: 'text', id: 'quiz_questions' },
    actionLabel: '去改忍者问题',
  });

  const tertiary = entryCard(ctx, {
    title: '看某个场景的剧情脚本',
    headline: `${scripts} 个剧本`,
    desc: '剧情 VM 的字节码反汇编：指令、文本、分支目标。' +
      '文本能就地改（长度不限，变长会搬动剧本）；' +
      '定宽操作数（下一场景 / 地图 / 子配置 / 队员）可以原地改；指令本身不能改。',
    panel: { kind: 'script', id: 'script' },
    actionLabel: '看剧本',
  });

  renderDomainIndex(container, ctx, {
    primary,
    secondary,
    tertiary,
    module: 'story',
    title: '剧情与对白',
    subtitle: [
      el('span', { text: '忍者问题指针表 ROM 0x461CE8' }),
      el('span', { text: '字形码 ' + pack.font.codeToChar.size }),
    ],
    intro:
      '这些文本在 ROM 里是字形码流（每个汉字 2 字节，lead 0x80–0x9F），不是 Shift-JIS。' +
      '指针表驱动的文本（忍者问题表、任务表、战斗目标表）可以改变长度——构建时会重定位到空闲区并改写指针；' +
      '说话人名表是定长内联槽，但可以转换成指针表 + 变长串池；' +
      '说话人全名表与地点名表也是定长内联槽，结构上只能等长改写。' +
      '忍者问题指针表 0x461CE8 共 1524 个槽位 = 305 组 ×（4 条 + 1 个 NULL 分隔），' +
      '每组 4 条是「一道题 + 三个选项」；第 g 组的 4 条落在槽 5g..5g+3。' +
      '**真正的剧情对白在上面第一张卡片里**（可视化对白编辑器）——它读的是剧情脚本，' +
      '不是这张问答表。' +
      '剧情脚本按**场景号**索引（槽号 = 场景号）：1..46 是关卡场景，' +
      '47..55 是关卡之外的特殊场景，**游戏开局是场景 54（主线入口）**。',
    extra,
    // 本域的文本表 —— 这是**策展顺序**，不是可达性清单：
    // `common.js::domainTableRows()` 会把内容包里 `module === 'story'` 的表
    // **自动追加**到本列表末尾，所以两张新表本来就够得着；写进这里是为了让作者
    // 在**一屏之内**看到「说话人简称 / 说话人全名 / 地点名」这三张同属剧情侧的名字表，
    // 而不是散在自动追加的尾巴里。
    //
    // 归属的依据（不是拍脑袋）：
    //  · `speaker_full_names`（说话人全名表，19 B × 64）与 `speaker_names`
    //    （说话人名表 = 简称，12 B × 64）是**同一批说话人的两种形态** ——
    //    简称表本来就在这一域，全名表是它的邻居；
    //  · `location_names`（地点名表，18 B × 55）唯一的原生读者 `fn 0x0808CD40`
    //    是被**剧情状态机** `fn 0x0808F190` 调用的（`0x0808F40C`；同一个函数
    //    还 `bl 0x0808F4D4` 派发场景）⇒ 它是**剧情侧**的数据，不是战斗/地图侧的；
    //  · 内容包自己也这么标：两张表的 `module` 都是 `story`。
    texts: [
      'quiz_questions',
      'speaker_names',
      'speaker_full_names',
      'location_names',
      'rom_text_index',
    ],
    structures: [
      'story_before_root', 'story_after_root',
      'story_logic_root', 'story_events_root',
      'font_segments', 'font_width_table', 'background_table',
    ],
    // 四张剧情脚本根表是同一个场景的四个剧本入口，字形段表与字宽表是同一批字形的两面 ——
    // 分成六行摆着会让作者以为要分别进六张表，那是细碎，不是清楚。
    groups: [{
      label: '场景（四张剧情脚本根表）',
      tables: ['story_before_root', 'story_after_root', 'story_logic_root', 'story_events_root'],
      method: '按场景改',
      strategy: '定宽写回',
      action: '打开场景',
      onPick: (c) => c.openPanel('scene', '场景', {}),
    }, {
      label: '字库（字形段表 + 字宽表）',
      tables: ['font_segments', 'font_width_table'],
      method: '按字形改',
      strategy: '定宽写回',
      action: '打开字库',
      onPick: (c) => c.openPanel('font', '字库', {}),
    }],
  });
}

function stat(label, value, hint) {
  return el('div', { class: 'stat' }, [
    el('div', { class: 'stat-label', text: label }),
    el('div', { class: 'stat-value', text: String(value) }),
    hint ? el('div', { class: 'stat-hint', text: hint }) : null,
  ]);
}
