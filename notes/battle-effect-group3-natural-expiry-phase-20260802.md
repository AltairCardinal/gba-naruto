# Group 3 自然到期提交相位（2026-08-02）

## 结论

忍具 67“引爆牌”的自然链已从 C3 对象创建推进到原生到期演出：battle 14 中唯一
slot 3 对象经正常回合推进到 `remaining_turns=0`，随后从该恢复点零输入运行，原 ROM
在 frame 67 创建 group 3 task，并完整经过 renderer、OAM submit 和 VBlank ack。

本成果将战斗特效精确提交相位覆盖从 5/18 提升为 **6/18**。它仍使用基准 ROM，
所以 production 修改 ROM 的自然最终像素 A/B 保持 **5/18**。

## 可恢复边界

- 输入：`artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-active-c3.ss9`
  (`401256e00877169e98b3e6584488e732f9254b4426806ad2b6b3bdc770259939`)。
- 新恢复点：
  `artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-expiry-ready.ss9`
  (`34eb56d34d876a275546a2b6875804aa5e24c97600a9d299c0c6ba0ae165b501`)。
- 对象仍为 `slot=3/state=1/action=C3`，但剩余回合为 0；输入状态中不存在 group 3
  definition `0x083425D8` / animation `0x083426CC` task。
- 到达方法只使用自然 UI：完成鸣人面向/不防御，再完成佐助、小樱的一格移动、面向与
  不防御选择，随后让敌方阶段推进；没有修改 state 或 RAM。

## 三相运行证据

生产 profile 为
`sequel/content/battle-effect-phase-capture/group-03-natural-tool67-expiry.json`，从上述
恢复点不注入按键，在 600 帧门限内捕获：

| 相位 | ROM 地址 | frame | pending | task |
|---|---|---:|---:|---|
| renderer-post | `0x08063328` | 67 | 0 | slot 126 / `0x03005940` |
| submit-post | `0x08061126` | 67 | 1 | slot 126 / `0x03005940` |
| ack-post | `0x080612AA` | 68 | 0 | slot 126 / `0x03005940` |

三相 task flags 均为 `0x41001281`，目标 task 在两条 active dispatcher 指针中 ordinal
均为 0；ack 后完整 1 KiB shadow/hardware OAM 相等。运行经统一 heavy guard，峰值
tree RSS 为 71.33203125 MiB，`completed/0`、非 degraded，PGID 与 mGBA listener
均无残留。

正式成果为 `artifacts/battle-effect-frame-phase-group3-natural-v1/`。独立 verifier
除重建 PC、task、dispatcher、内存域和 pending 顺序外，还交叉验证：

- 到期前 checkpoint evidence 的 ROM/state/tool 67/C3/E4/group 3 合同；
- savestate 中 C3/0 对象真实存在且输入时没有 group 3 task；
- `notes/battlefield-object-effect-chain-bindings-20260802.json` 通过其独立静态 verifier；
- 自然来源合同不得附带旧式 `accepted_parent`，也不得提前声称到期 handler 已完成。

验证器依赖升级后，既有 groups 1/2/5/11/14 phase artifact 使用批处理工具重新生成
manifest；批处理要求 raw、runtime audit 和 guard 的全文件哈希完全不变，并在新 manifest
验证失败时恢复旧文件。聚合成果现记录 phase 6/18、production自然像素5/18。

## 未完成边界

- 本轮没有构建修改 ROM，因此不增加自然最终像素 A/B 分子；
- 只覆盖 group 3 当前自然到期时的一次全局提交事务，不代表完整动画、非镜像分支、
  palette 尾字生命周期、blend/window、音频或实体 GBA；
- 下一步应把既有 group 3 exclusive relocation 单像素修改与本自然到期入口组合，完成
  baseline/candidate 同输入的最终像素 A/B。
