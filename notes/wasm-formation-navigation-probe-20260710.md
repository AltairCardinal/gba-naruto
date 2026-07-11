# WASM 章节/战斗导航与编成轮询探针（2026-07-10）

## 本轮尝试

基于 `play/_scripts/t7-puppeteer-e2e.js` 的 START → 新游戏 → 连续 A 导航方法，新增
`runtime-formation-probe.js`。探针将导航拆成显式、可测试的按键计划；每次按键后读取
WRAM 单位数组并与 `sequel/content/positions/bank.json` 的 48×3 个编成候选匹配。

严格按红绿重构执行：先添加纯函数测试，首次运行因
`runtime-formation-probe-lib.js` 不存在而失败；随后实现最小按键计划、快照分类和坐标
多重集匹配，4 项测试通过。匹配出现并列时返回歧义，绝不猜测 group/variant。

## 学到的内容

- 远端 threaded mGBA 的 `window.__mGBA._readGbaByte(address)` 可以只读访问 GBA
  总线，但必须同时等待游戏 core 就绪。仅等待 `window.__mGBA` 存在会得到 `-1`；转成
  `Uint8Array` 后表现为整段 `FF`，容易被误当成有效内存。
- 可用的就绪门禁是：速度按钮已启用，且 `_readGbaByte(0x08000000) !== -1`。
- 远端模块暴露 `_readGbaBytes`，却没有在 `Module` 上暴露 `_malloc`；所以当前部署无法
  从页面代码安全提供目标 buffer。探针在分配器不可用时逐字节调用 `_readGbaByte`。
- core 就绪后的 smoke test 成功读取 `0x020240C0` 起 `0x2BE0` 字节；进入新游戏前该
  范围全零，证明读取路径有效且未把 `-1` 当数据。
- 500ms 的激进按键间隔在 30 START + 100 A 内没有进入可识别战斗编成。该结果不能
  否定导航路线；游戏很可能要求更长的按键/渲染间隔，默认仍沿用 T7 的 3 秒节奏。
- 瞬时 `keyboard.press()` 在 4× 运行时可能错过 mGBA 的输入采样。按 TDD 新增
  `keyHoldMs`（默认 125ms），运行时明确执行 keydown → hold → keyup；相关测试先因
  动作缺少 `holdMs` 正确失败，最小实现后 6/6 通过。
- 真实部署用 125ms hold、500ms 间隔运行 30 START + 250 A（约 3 分钟），最终已越过
  对白，进入鸣人人物信息页（画面提示 B=返回），而不是战斗编成确认页。此时单位数组
  仍全零，说明该 UI 尚未执行战斗单位实例化，不能在该画面期待 positions 命中。
- 后续真实运行确认正确序列为 `KeyX,ArrowDown,ArrowDown,KeyZ`（B 返回、下、下、
  A 确认），并已在 `/tmp/formation-battle-final.png` 观察到战斗转场；此前推测的
  B → 右 → A 已撤销。探针
  现通过 `PROBE_TAIL_KEYS` 接受逗号分隔的尾部序列，并用 `PROBE_TAIL_DELAY_MS`
  设置动作间隔。结构化
  运行结果保存在 `notes/wasm-formation-probe-result-20260710.md`（JSON code block；
  仓库规则会忽略 `notes/*.json`）。
- 转场后单位数组可能延迟初始化，不能把尾部最后一次按键后的单次快照当作失败。
  新增 post-settle 只读轮询：`PROBE_SETTLE_COUNT`（默认 20）控制次数，
  `PROBE_SETTLE_DELAY`（默认 500ms）控制间隔。settle 阶段不发送任何按键，只读取
  `0x020240C0`、尝试 positions 匹配，并保存 settle 截图与结构化结果；耗尽时明确记录
  `settle-exhausted`。

## 重要范围与判定

- WRAM `0x020240C0`：单位数组物理基址。
- stride `0x1D4`；只读取 slot `0..20`。slot 21 已跨入 `0x02026804`
  战斗控制块，不是单位记录。
- 坐标：unit `+0xC4/+0xC5`；初始坐标 `+0xC7/+0xC8`。
- ROM `0x5461C4` 起：用于坐标匹配的 positions 编成矩阵。
- ROM `0x08000000`：仅作为 core 已就绪的只读探针地址。

当前结果：脚本已用 B → 下 → 下 → A → A 进入首战，settle 后
WRAM slot 1 稳定为 `(4,4)`，唯一匹配 positions group 40 / variant 0 /
record 0（ROM `0x588CA8`）。positions 因此升级为 `runtime_verified`。

## 2026-07-11 重放与 battle-control 采集

为后续 maps 验证，探针按 TDD 增加了对 `0x02026804..0x0202680B` 的逐阶段
读取，结果字段为 `battleControl.rawHex` 和 `battleControl.chapterBattleId`
（后者取 `0x02026805`）。单元测试先因缺少解码函数失败，最小实现后 10/10
通过。

使用与成功样本相同的 30 次 START、250 次 A 和
`B, Down, Down, A, A` 尾序列重放时，本次没有进入战斗：boot、new-game、story、
tail 和第 40 次 settle 的单位区均为空，battle-control 始终为
`0000000000000000`，结果为 `not-found / settle-exhausted`。失败结果位于本机
`/tmp/formation-map-result.json`，但关键结构和结论已在此固化。

结论：按固定次数推进剧情的路线存在时序漂移，不能作为 maps 的可重复动态门禁；
在加入画面/内存状态驱动的导航之前，maps 保持 `code`，也不得用此前一次成功的
positions 样本顺带升级 maps。

随后增加了可选 `PROBE_SETTLE_CONFIRM_EVERY`：值大于零时，每隔指定轮询补发一次
A，默认 0 仍保持纯只读 settle。TDD 先证明旧计划没有恢复动作，最小实现后
11/11 通过。配置为每 2 轮确认的独立重放在 tail 阶段便成功实例化 slot 1，因而
恢复动作本次没有实际执行；不能据此宣称已消除所有时序漂移。
