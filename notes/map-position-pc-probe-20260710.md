# Maps / Positions PC 探针（2026-07-10）

## 尝试内容

审查了 `tools/mgba-headless-snapshot.py`、`tools/mgba_trace_chapter_init.lua`
及已有 mGBA 记录，并为 CLI 调试器增加 `probe` 模式：在指定 ROM PC 设置
执行断点，命中后在同一停止上下文读取 ROM/WRAM，输出结构化 JSON。

严格按 TDD 完成：

1. 先加入 `tests/test_mgba_headless_probe.py`，4 个测试因缺少
   `build_probe_commands`、`parse_probe_output`、`mode_probe` 而失败；
2. 加入最小实现后，4/4 通过；
3. 以真实 `/usr/games/mgba` 和 `rom/base.gba` 做集成 smoke test。

## 已学到的结果

- mGBA 0.10.1 的 CLI 断点命令是 `b 0xADDRESS`，成功设置输出
  `Added breakpoint #N`，真实命中输出 `Hit breakpoint N at 0xADDRESS`。
- `status` 也会打印寄存器，因此必须以明确的 `Hit breakpoint` 行作为
  `hit=true` 的门禁；只看到寄存器不能证明代码执行到目标地址。
- 真实 smoke test 在 `0x080000C0` 于 cycle 48 命中，并在同一上下文成功读取：
  - 地图表首行：ROM `0x0853D910`（文件偏移 `0x53D910`），首 32 字节；
  - 单位运行时区域：WRAM `0x02024290`，冷启动时为零。
- smoke test 证明了探针机制，但**没有**证明 map loader 消费了地图行，也没有
  证明 positions 的 ROM 来源。动态结论仍必须要求 `0x08068FF0` 真实命中。

## maps / positions 的最小验证协议

目标断点与读取范围：

- map loader PC：`0x08068FF0`；
- map header table：ROM `0x0853D910`（文件偏移 `0x53D910`），每项 32 字节；
- unit array 物理基址：WRAM `0x020240C0`，stride `0x1D4`；
- WRAM `0x02024294` 是 slot 1，不是独立数组基址；
- positions ROM 编成矩阵：`0x085461C4`，记录 `+2/+3` 为 x/y。

命令见 `tools/README.md`。验收必须同时满足：

1. JSON `hit=true` 且 `hit_pc=0x08068FF0`；
2. 保存当次寄存器（尤其 `r0-r3`、`lr`）及 map row/WRAM 读取；
3. 对不同章节/地图重复运行，证明 map id 与 `base + id*32` 行对应；
4. 在 `0x0806E41E` 或 `0x0806E71E` 真实命中后，对照 `r5`、
   `0x085461C4` 记录与创建后 slot 坐标；不能继续把 `0x53D914`
   （map header 内字段）称为单位位置表。

## 当前限制与下一步

CLI 调试器不能注入按键，现有 `--savestate` 参数也尚未形成可验证的加载路径；
旧的 chapter-init Lua 记录为 `timeout_no_hits`。应复用现有 Lua 按键导航，先让
`0x08068FF0` 可重复命中，或者取得有效的战斗 savestate，再运行本探针。

后续状态更新：网页 WASM 导航已进入首战，单位槽 1 的 `(4,4)` 与 positions 的
group 40 / variant 0 / record 0（ROM `0x588CA8`）唯一匹配，因此 positions 已提升
为 `runtime_verified`；详见 `notes/wasm-formation-probe-result-20260710.md`。
WASM 接口不暴露 PC/LR，maps 仍保持 `code`，本文件所述 PC 探针仍是其动态验证
所需的后续路线。
