# 战斗特效 group 14 自然最终像素 A/B（2026-08-01）

## 结论

scenario 47 战斗中，佐助自然选择主动动作 16“火遁·豪火球术”，静态绑定为
encoded action 16、sequence 16、resource group 14。确认前 checkpoint 只需再输入
一次 A 即可执行完整演出。两份 production-relocation ROM 的最终证据只有一个 VRAM
字节和一个屏幕像素不同，独立 verifier 返回 `errors=[]`。

## 可恢复输入边界

- 父状态：`scenario-47-battle-13-turn5-retreat.ss9`，SHA-256
  `529b3e0f64d5b9a161994765efa25f341f9d8d5b772d45f5f3cc8df9fadd6e55`。
- 正确路线包含9个有连续输入/输出哈希的分段，完整记录在
  `scenario-47-fire-action16-confirmation-evidence.json`；方向误判等试探没有进入成果。
- 最终确认 checkpoint：`scenario-47-fire-action16-confirmation.ss9`，SHA-256
  `50330328232cb626fa6888bce0cc67f5bb6386317d76cf9dfdb1945a8ed6d1dd`。
- checkpoint 已单独零输入重放240帧；守卫`completed/0`、非degraded，峰值
  51.86328125 MiB，PGID和mGBA listener均清洁。

## ROM、内存与像素隔离

基线和候选均把group 14 graphics迁移到`0x08B40000`，并把pair-table graphics
pointer `0x0859918C`重定向到该地址；两边安全LZ77均为2,138 bytes，patch topology
完全相同。候选仅修改源graphics offset `0x3A`的高nibble：byte `0x33→0x23`、
palette index `3→2`。

最终frame 516：

- 完整5,120-byte graphics位于`0x06012400`，分别与各自ROM解压源逐字节一致；
- frame 0/component 0由OAM entry 1显示，属性为
  `0x0030/0x80A0/0x5920`，OBJ tile base 288，palette bank 5；
- EWRAM、IWRAM、IO、PRAM和OAM完全相同；
- VRAM只在`0x0601243A`有`0x33→0x23`；
- mGBA PNG只在`(173,54)`有`(255,165,49)→(255,239,107)`；
- 独立Mode-0 renderer与两份mGBA PNG逐RGB完全一致。

正式A/B运行均经共享heavy lock，峰值tree RSS为55.95703125/56.078125 MiB，无
进程或监听残留。

## 工具化与边界

profile-driven builder/exporter/verifier现同时支持`ninja_tool`与`active_action`，且
保留各自独立自然路线scope。主动动作checkpoint使用专属证据schema，固定父状态、
9段连续哈希、最终确认边界、模拟器身份和零输入稳定性。独立verifier仍不导入builder
或exporter，并新增大小写规范化ledger回归，避免含A–F的pointer offset只在新组失败。

本成果使自然最终像素A/B代表组达到3/18；它只签发group 14、sequence 16、frame 0
的一个graphics像素，不外推到其余15组、其他帧、完整affine/blend/时序/音频或实体
GBA。

## 验证

```bash
python3 -m unittest \
  tests.test_build_battle_effect_pixel_ab \
  tests.test_export_battle_effect_pixel_ab_evidence \
  tests.test_verify_battle_effect_pixel_ab_evidence -v

python3 tools/verify_battle_effect_pixel_ab_evidence.py \
  --artifact artifacts/battle-effect-group14-pixel-ab-v1
```
