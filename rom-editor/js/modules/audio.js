// 音频：m4a 歌曲描述符与 sound-ID 分派表
//
// 音频域有三张入口：
//   * 音效分派表 —— 改「哪个音效播哪首曲子」（描述符指针）
//   * 乐曲描述符 —— 改「这首曲子的轨道指向哪段数据」
//   * 函数指针表 —— 1..11 槽是播放入口（音效号的对应是**静态推定**）
//
// 面板路由：音频自己的表由 audio-workspace.js 渲染（描述符下拉与指针反查
// 需要音频专属的呈现），别的面板仍走通用结构编辑器。

import { el } from '../ui.js';
import { renderDomainIndex, renderPanel, entryCard, summaryTable } from './common.js';
import { renderAudioStructure, isAudioStructure } from './audio-workspace.js';

/**
 * 本域样式（css/audio.css）。
 *
 * index.html 里已经有 css/route.css 与 css/assets.css 的链接；音频这一张
 * 如果还没被链接上，这里补一次 —— 纯前端，没有构建步骤。
 */
function ensureAudioStyles() {
  if (typeof document === 'undefined' || !document.head) return;
  try {
    if (document.querySelector('link[href="css/audio.css"]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'css/audio.css';
    document.head.appendChild(link);
  } catch (err) {
    /* 样式表读不到不影响功能，忽略 */
  }
}

/** 域首页：三张推荐入口卡 + 本域全部表 + 一览（统计）。 */
function renderAudioDomain(container, ctx) {
  const pack = ctx.pack;
  const stats = (pack.derived && pack.derived.sound_stats) || {};
  const kinds = stats.descriptor_kinds || {};
  const channel = stats.channel_histogram || {};

  const cards = el('div', {
    class: 'audio-cards',
    style: {
      gridColumn: '1 / -1',
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))',
      gap: '10px',
    },
  }, [
    entryCard(ctx, {
      title: '改音效分派',
      headline: `${stats.sound_id_count ?? 159} 条 sound id`,
      desc: `${stats.real_descriptor_count ?? 80} 个有内容 + `
        + `${stats.empty_sound_ids ?? 79} 个空哨兵。改描述符指针就是换一个曲子。`,
      panel: { kind: 'structure', id: 'sound_id_table' },
      actionLabel: '去改音效',
    }),
    entryCard(ctx, {
      title: '乐曲描述符',
      headline: `${stats.real_descriptor_count ?? 80} 个真实描述符`,
      desc: `${kinds['乐曲'] ?? 22} 首多轨乐曲 + ${kinds['短音效'] ?? 58} 个单轨短音效，`
        + '外加 1 个没有声音的空哨兵。',
      panel: { kind: 'structure', id: 'audio_song_1' },
      actionLabel: '看描述符 #1',
    }),
    entryCard(ctx, {
      title: '函数指针表',
      headline: '13 槽 · 11 条播放入口',
      desc: '槽 1..11 是「movs r0,#k」的播放 thunk；'
        + 'k 与音效号的对应是静态推定，尚未由运行时证据闭环。',
      panel: { kind: 'structure', id: 'function_pointer_table' },
      actionLabel: '看指针表',
    }),
  ]);

  const channelText = [0, 1, 2, 3]
    .map((c) => `通道 ${c}：${channel[String(c)] ?? 0} 条`)
    .join(' ｜ ');

  const extra = el('div', { class: 'section' }, [
    el('h3', { text: '音频构成' }),
    el('p', { class: 'section-note' }, [
      '每个 sound id 指向一个 m4a 歌曲描述符（SongHeader），并给出播放通道与配置。'
      + '音频采样本体是压缩载荷，不在这些表里，要改采样得另走 m4a 导入流程。',
    ]),
    summaryTable({
      head: ['项目', '值'],
      body: [
        ['音效总数', `${stats.sound_id_count ?? 159} 条 = `
          + `${stats.real_descriptor_count ?? 80} 个有内容 + `
          + `${stats.empty_sound_ids ?? 79} 个空哨兵`],
        ['空哨兵', `${stats.empty_descriptor ?? '0x08466068'}`
          + `（ROM ${stats.empty_descriptor_offset ?? '0x466068'}，0 轨 = 没有声音），`
          + `被 ${stats.empty_sound_ids ?? 79} 个音效共用`],
        ['真实描述符', `${stats.real_descriptor_count ?? 80} 个：`
          + `${kinds['乐曲'] ?? 22} 首乐曲 + ${kinds['短音效'] ?? 58} 个单轨短音效`],
        ['播放通道分布', channelText],
        ['播放配置', stats.config_equals_channel
          ? '159 行里与播放通道逐行相等（改它可能没有效果）'
          : '与播放通道不完全相等'],
        ['函数指针表', '13 槽：槽 0 / 12 是哨兵（FFFFFFFF），'
          + '槽 1..11 是播放入口（音效号对应为静态推定）'],
      ],
    }),
  ]);

  renderDomainIndex(container, ctx, {
    primary: cards,
    module: 'audio',
    title: '音频',
    subtitle: [
      el('span', { text: 'sound-ID 表 ROM 0x465B70（159 条）' }),
      el('span', {
        text: `m4a SongHeader ${stats.real_descriptor_count ?? 80} 个真实描述符 + 1 个空哨兵`,
      }),
      el('span', { text: '函数指针表 ROM 0x53D5F0（13 槽）' }),
    ],
    intro: 'ROM 里的音乐是 m4a 格式。编辑器能改的是描述符层：'
      + '哪个音效播哪首曲子、这首曲子的轨道指向哪段数据。'
      + '采样数据本身是压缩载荷，不在这些表里。',
    extra,
    structures: ['sound_id_table', 'function_pointer_table'],
    texts: [],
  });
}

export function renderAudio(container, ctx) {
  ensureAudioStyles();
  const panel = ctx.state.view.panel;
  if (panel) {
    if (panel.kind === 'structure' && isAudioStructure(panel.id)) {
      return renderAudioStructure(container, ctx, panel.id, panel.params);
    }
    return renderPanel(container, ctx, panel.kind, panel.id, panel.params);
  }
  return renderAudioDomain(container, ctx);
}
