# 战斗特效 group 15 自然单像素 A/B（2026-08-02）

## 结论

原 ROM 的 AI 在 battle 8 自然选择 action 64，并经 side 1、sequence 17 绑定
group 15。由确认前 checkpoint 只输入一次 `A:60:68`，baseline 与 candidate
均在 frame 1549 捕获。candidate 只把 group 15 解压图形 offset `0xA3` 从
`0x23` 改为 `0x24`；两份 16 MiB ROM 保持相同 1,560-byte LZ77 拓扑。

运行结果的 EWRAM、IWRAM、IO、PRAM、OAM 均无差异，VRAM 仅
`0x060124A3:0x23→0x24`。OAM entry 1 为
`0x0030/0x9030/0x5920`，水平翻转把源 component pixel `(14,8)` 映射到屏幕
`(65,56)`；最终 PNG 也只有该像素从 `(82,140,255)` 变为 `(0,82,255)`。
独立 Mode-0 renderer 与两张 mGBA PNG 逐 RGB 字节一致。

正式成果为：

- `artifacts/runtime-checkpoints/battle8-action64-ai-preconfirm.ss9`；
- `sequel/content/battle-effect-pixel-ab/group-15-action64-water-dragon.json`；
- `artifacts/battle-effect-group15-pixel-ab-v1/`。

生产修改 ROM 的自然最终像素 A/B 因而由 `4/18` 提升到 `5/18`。这不扩大既有
frame-phase 的 `5/18` 分母，也不证明 group 15 的全部 9 帧、音频、blend/window、
原剧情可达性或实体 GBA 等价。

## 输入与来源

确认前 checkpoint 是已验收父 artifact
`artifacts/battle-effect-group15-natural-runtime-v1/raw-runtime.tar` 的
`source/input-state.ss9` 的逐字节副本，SHA-256 为
`c775d4b5ea952f95bdac11993979ad62e11a9418456afc99a54d484b202ce1e1`。
独立 verifier 会先完整运行父 artifact verifier，再以流式安全 tar reader 读取该
成员，并要求它与仓库 checkpoint 完全相等；不能仅靠复制哈希字段重签。

运行工具链绑定 `artifacts/rom-expansion-profile-v1/profile.json`：mGBA binary
SHA-256 `c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8`，
source commit `d8bad14b4540f9114246c0281d74985cf81adc68`。新增
`tools/run_macos_mgba_single_input_current.py` 只接受该当前桌面 profile；历史
`tools/run_macos_mgba_single_input.py` 保持 SHA-256
`aa94c3f540d9a18a898de2bf0f41809bf9a1073bc9b2b56ed250f179a124a057`，避免破坏
旧 artifact 的生成来源。

## 单因素选择

候选选择先离线扫描可保持压缩长度的像素，再做真实运行排除：

1. 源像素 `(12,10)` 的候选会改变 LZ77 长度，builder 在运行前拒绝；
2. 源像素 `(12,8)` 虽保持 1,560 bytes，但真实候选产生额外 IWRAM
   `0x03007F9C:0x2E→0x2C`，不满足单因素合同；
3. 最终 `(14,8)` 只改变一个压缩 literal、一个解压字节、一个 VRAM 字节和一个
   最终像素，其他完整内存域均为零差异。

## 资源安全与复验

baseline/candidate 的 guarded run ID 分别为
`101d0bb80b33a03ab2ddee4ba6bf589e`、`7836114c0fe1d3ecc8b0833a3a5d8bb1`；
峰值 tree RSS 为 `69.54296875/69.5390625 MiB`，均以 success-marker、非 degraded
完成，PGID 与 mGBA listener 无残留。

复验命令：

```text
python3 tools/verify_battle_effect_pixel_ab_evidence.py \
  --root . \
  --artifact artifacts/battle-effect-group15-pixel-ab-v1
```
