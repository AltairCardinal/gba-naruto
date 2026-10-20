// 剧情与对白
import { el, formatOffset } from '../ui.js';
import { renderDomainIndex, renderPanel, summaryTable } from './common.js';

export function renderStory(container, ctx) {
  if (ctx.state.view.panel) {
    const { kind, id } = ctx.state.view.panel;
    return renderPanel(container, ctx, kind, id);
  }

  const pack = ctx.pack;
  const slots = pack.textTable('dialogue_slots');
  const index = pack.textTable('rom_text_index');
  const nonEmpty = slots ? slots.records.filter((r) => r.text).length : 0;

  const extra = el('div', {}, [
    el('div', { class: 'card-grid' }, [
      stat('对白槽位', slots ? slots.count : 0, `其中 ${nonEmpty} 条有内容`),
      stat('全 ROM 文本', index ? index.count : '按需载入',
        index ? '用 ROM 自带字库扫出' : '进入该表时自动下载索引'),
      stat('字形段', pack.structure('font_segments')?.entry_count || 0, '决定能画出哪些字'),
      stat('剧情底图', pack.structure('background_table')?.entry_count || 0, '底图 id'),
    ]),
  ]);

  renderDomainIndex(container, ctx, {
    title: '剧情与对白',
    subtitle: [
      el('span', { text: '对白槽位表 ROM 0x461CE8' }),
      el('span', { text: '字形码 ' + pack.font.codeToChar.size }),
    ],
    intro:
      '对白文本在 ROM 里是**字形码**流（每个汉字 2 字节，lead 0x80–0x9F），不是 Shift-JIS。' +
      '指针表驱动的文本（对白槽位表、任务表、名字表）可以改变长度——构建时会重定位到空闲区并改写指针；' +
      '被代码用绝对地址引用的文本只能等长改写。' +
      '对白指针表 0x461CE8 共 1524 个槽位 = 305 组 ×（4 条 + 1 个 NULL 分隔），' +
      '每组 4 条是「一道题 + 三个选项」；第 g 组的 4 条落在槽 5g..5g+3。',
    extra,
    texts: ['dialogue_slots', 'speaker_names', 'rom_text_index'],
    structures: [
      'story_before_root', 'story_after_root',
      'story_logic_root', 'story_events_root',
      'font_segments', 'background_table',
    ],
  });
}

function stat(label, value, hint) {
  return el('div', { class: 'stat' }, [
    el('div', { class: 'stat-label', text: label }),
    el('div', { class: 'stat-value', text: String(value) }),
    hint ? el('div', { class: 'stat-hint', text: hint }) : null,
  ]);
}
