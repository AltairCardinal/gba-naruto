// 音频：m4a 歌曲描述符与 sound-ID 表
//
// 这不是用户要求的六个域之一，但这些表在 ROM 里已被证实，
// 编辑器把它们一并呈现，「所有内容可改」才不落空。
import { el } from '../ui.js';
import { renderDomainIndex, renderPanel, summaryTable, entryCard } from './common.js';

export function renderAudio(container, ctx) {
  const panel = ctx.state.view.panel;
  if (panel) {
    const { kind, id } = panel;
    return renderPanel(container, ctx, kind, id);
  }

  const pack = ctx.pack;
  const soundIds = pack.structure('sound_id_table');

  const rows = { head: ['sound id', '描述符指针', '播放通道', '播放配置'], body: [] };
  if (soundIds) {
    for (const record of soundIds.records) {
      if (!record.values.descriptor_ptr) continue;
      rows.body.push([
        record.id,
        '0x' + (record.values.descriptor_ptr >>> 0).toString(16).toUpperCase(),
        record.values.player_index,
        record.values.player_config,
      ]);
    }
  }

  const extra = el('div', { class: 'section' }, [
    el('h3', { text: '声音 ID 表' }),
    el('p', { class: 'section-note' }, [
      '每个 sound id 指向一个 m4a 歌曲描述符（SongHeader），并给出播放通道与配置。',
      '音频**样本本体**不在这些表里，要改音乐得另走 m4a 导入流程。',
    ]),
    summaryTable(rows),
  ]);

  const primary = entryCard(ctx, {
    title: '按音效改',
    headline: '159 条 sound-ID',
    desc: 'sound-ID 表是音频的入口；五首 m4a 乐曲描述符在同一域。' +
      '音频采样本体是压缩载荷，不在编辑器里改。',
    panel: { kind: 'structure', id: 'sound_id_table' },
    actionLabel: '去改音效',
  });

  renderDomainIndex(container, ctx, {
    primary,
    module: 'audio',
    title: '音频',
    subtitle: [
      el('span', { text: 'sound-ID 表 ROM 0x465B70（159 条）' }),
      el('span', { text: 'm4a SongHeader 0x536368 等 5 首' }),
    ],
    intro:
      'ROM 里的音乐是 m4a 格式。编辑器呈现的是**描述符层**（歌曲头与轨道指针）' +
      '和 sound-ID 分派表；采样数据本身不在这些表里。',
    extra,
    structures: ['sound_id_table', 'function_pointer_table'],
    texts: [],
  });
}
