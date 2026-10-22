# 音频域右侧面板页签化（音效工作台 / 乐曲描述符）— 2026-10-22

> 规格：`notes/specs/tabbed-side-panels.md`（第九轮 · 页签化）。
> 通用机制：`rom-editor/js/tabs.js` 的 `TabPanel`。
> 参考实现：`rom-editor/js/modules/battle-map.js`（战场地图那 5 个页签）、
> `rom-editor/js/modules/character.js`（一条记录拆成七类的角标口径）。

## 做了什么

只改了两个文件：

- `rom-editor/js/modules/audio-workspace.js`
- `rom-editor/tools/verify_audio_workbench.mjs`

音频域有**两个**右侧面板，本轮都从「一串纵向追加」改成**页签**
（头部仍留在页签外面）：

| 视图 | 原来纵向堆叠的段落 | 现在的页签 | 每一页装什么 |
|---|---|---|---|
| 音效分派表 `#audio/structure/sound_id_table`（key `editor.audio`） | 标题 + 摘要行 / 「被谁引用」块 / 「声音」分组（描述符指针 + 自定义地址 + 播放通道 + 播放配置）/ 底部动作 | 描述符 · 谁指向它 · 播放入口 | 描述符页 = 描述符指针下拉（81 项，带名字与共用数）+ 自定义地址行；谁指向它页 = 指针级反查清单（`被谁引用（N 处）` + 跳过去）；播放入口页 = 播放通道 / 播放配置两个字段 + 推定出来的播放入口 thunk（槽号 / 代码 / 目标 / 静态推定） |
| 乐曲描述符 `#audio/structure/audio_song_*` | 面板头 / 「这一层能改什么」/ 「被谁引用」块 / 「歌曲头」分组 + 「轨道」分组（一张 N 行表）/ 底部动作 / 「音效 #x 指向这个描述符」脚注 | 描述符 · 谁指向它 · 播放入口 | 描述符页 = 歌曲头（轨道数 / 块数 / 优先级 / 混响 / 音色组指针）+ 轨道指针表；谁指向它页 = 反查块 + 「音效 #x 指向这个描述符」脚注；播放入口页 = 用这个描述符的音效在函数指针表里的播放 thunk（推定） |

两个视图的页签 id 一样（`descriptor` / `refs` / `playback`），所以共用同一个
localStorage 键 `editor.tabs.editor.audio` —— 从一个视图切到另一个视图时停在同一类内容上。

## 关键决定与踩过的坑

1. **`clear(host)` 会把页签面板一起清掉**。用规格里推荐的那条：详情面板拆成
   **四个常驻容器** —— `detailHead` / `detailSub` / `tabHost` / `detailActions`；
   `openDetail()` 只 `clear` 头部、摘要与动作三块，**不碰 `tabHost`**。
   `TabPanel` 实例挂在 `this.tabs` 上，`render()` 里 new 一次，
   换音效时只调 `this.tabs.refresh()` —— 页签条不重建，页签选择与记忆都还在。
   （把 `TabPanel` 建在 `render()` 里而不是第一次点行时：这样视图一进来页签条就在，
   跨域门禁 `verify_tabs.mjs` 直接渲染视图也能查到。）
2. **角标按字节判定**（改了又改回去不算改）：
   - 结构表的「这条记录改过没有」= `pack.changedStructureRecords(structure)` 的
     **`rom_offset` 集合**（新增模块级 `changedOffsets(pack, structure)`）；
   - 「这几个字段里有几处改了」= `originalValue(structure, record, field)`
     （直接从 `record.raw` 读原值）与当前值逐字段比（新增模块级
     `fieldsChanged(structure, record, fields)`）——
     这一层是页签粒度必须的：`changedStructureRecords` 只能判到整条记录。
   - 三个页签各自的口径：
     **描述符** = 描述符指针这一处改没改；
     **谁指向它** = 共用这个描述符的音效里（**除本条外**）改过几条；
     **播放入口** = 播放通道 / 播放配置改了几处，外加函数指针表里那一槽本身。
3. **角标自动跟上**：给 `new TabPanel([...], { key: 'editor.audio', pack })` 传了
   `pack` —— `pack.setValue()` 会 `notifyChanged()`，页签据此重算角标，
   **不需要**在每个输入框的 onchange 里手动 `tabs.refresh()`。
   唯一还需要 `refresh()` 的地方是「换了一条记录」：此时内容要按新记录重画。
4. **懒渲染会改既有断言的位置**。页签内容按需渲染 ⇒ 切走的那一页**不在 DOM 里**。
   既有断言「详情里有『被谁引用』块」改成「先切到『谁指向它』那一页，再看 DOM」，
   断的还是同一件事，断言条数与口径没有放松。
5. **一个真坑：`ContentPack.fromJSON()` 不复制数据** —— 记录对象是共享的，
   写回会**就地改**传进去的 JSON 对象。验收脚本里第 7 组原本
   `ContentPack.fromJSON(packData)` 写的值会留在 `packData` 里，
   于是第 10 组的「干净内容包」并不干净（音效 #3 的描述符指针被改过，
   连带「谁指向它」的角标误亮 1）。现在脚本开头存一份深拷贝快照
   （`cleanPackData`），需要干净包时用 `freshPack()` 重新深拷贝。
6. **播放入口块与反查块都用 `xref-block`**（同一套边框样式），但它们不是一回事：
   播放入口块另加一个 `audio-play-entry` 标记类，断言里据此区分
   （「切到播放入口后反查块不在 DOM 里」这条要数的是**反查**块，不是播放入口块）。
7. **两个视图都页签化了**：`verify_tabs.mjs`（跨域门禁）查的是
   `renderAudioStructure(host, ctx, 'audio_song_1', {})`，也就是**乐曲描述符**那个视图；
   它在改动前是 5 条 FAIL（音频域那一组）。本轮把两个视图都按同一套页签分类做齐，
   该组现在全过。

## 复核出来的关键事实

- `sound_id_table`：ROM `0x465B70`，159 条 × 8 字节，**只有 3 个字段** ——
  `descriptor_ptr`（u32，offset 0）/ `player_index`（u16，offset 4）/
  `player_config`（u16，offset 6）。原生 159 行里 `player_config` 恒等于 `player_index`。
- `audio_song_1`：ROM `0x536368`，单条 40 字节；字段 = 轨道数 / 块数 / 优先级 / 混响 /
  音色组指针 + `track0_ptr..track7_ptr`（`array: 'tracks'`，导出器补的轨道表）。
- `function_pointer_table`：13 槽；槽 0 与 12 是哨兵（FFFFFFFF），
  槽 1..11 是 `kind: 'play_entry'`、`sound_id` 1..11、`evidence: 'static'`
  （「静态推定」在界面上必须留着，docs/rom-editor.md §音频 明确不许省）。
- 描述符：81 个选项（80 个真实 + 1 个空哨兵 `0x08466068` / ROM `0x466068`，
  被 79 个音效共用）；音效 #1 指向 `0x08536368`（音频曲 1，8 轨）。
- 播放入口槽的 id **等于**槽号，也等于 `sound_id`（槽 1 ↔ 音效 #1）；
  代码里仍按 `slot.sound_id` 匹配，不假设两者相等。

## 验收

```
node rom-editor/tools/verify_syntax.mjs         # exit 0（57 个文件全过）
node rom-editor/tools/verify_views.mjs          # exit 0
node rom-editor/tools/verify_audio_workbench.mjs # exit 0（新增第 9、10、11 组）
node rom-editor/tools/verify_labels.mjs         # exit 0
node rom-editor/tools/verify_tabs.mjs           # exit 0（跨域门禁；改前音频域那组 5 条 FAIL）
```

新增断言（`verify_audio_workbench.mjs`）：

- **第 9 组（页签结构）**：右侧面板有页签条；页签标签依次是
  描述符 / 谁指向它 / 播放入口；DOM 里只有一个内容区（懒渲染）；
  默认停在「描述符」（描述符下拉 + 自定义地址都在）；
  切到「谁指向它」后反查块在 DOM 里、描述符页的下拉不在；
  切到「播放入口」后播放通道与推定的入口在、反查块不在。
- **第 10 组（角标）**：没改过没有角标；改描述符指针后「描述符」页签**自动**亮出角标 1
  （不用手动 refresh）；改回去之后角标消失（按字节判定）。
- **第 11 组（乐曲描述符也页签化）**：页签条与三个标签；默认页有歌曲头与轨道表；
  能切到「谁指向它」并看到反查块；能切到「播放入口」并看到「静态推定」标注。

改动的既有断言只有一条：第 3 组的「详情里有『被谁引用』块」，
改成先切到「谁指向它」那一页再看 DOM（见上文第 4 点）。

## 没做的事 / 留给别人的

- 没有改任何 CSS：新增的 `detail-tabs` 只是普通 `div`（没有对应样式），
  视觉效果由现有的 `.detail-head` / `.detail-sub` / `.detail-actions` /
  `.tab-*` / `.xref-block` 承担。
- 没有改 `tabs.js` / `common.js` / `fields.js` / `pack.js` / `editors.js`；
  写回仍然只有 `pack.setValue` 一条路。
- `docs/sequel-roadmap.md` 本轮第九轮的汇总段由主代理统一写（本文件不碰共享文件）。
