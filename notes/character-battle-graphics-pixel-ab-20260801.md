# 角色战斗图形自然最终像素 A/B（2026-08-01）

## 结论

角色战斗资源 0（鸣人、visual slot 0）的迁移图形已完成首条“修改 ROM → 自然战斗
入口 → OBJ VRAM → 最终像素”闭环。目标是 source frame 3、component 0、tile offset
96 的局部像素 `(13,17)`：4bpp graphics byte `+0xD26` 从 `0x12` 改为 `0x42`，
即高 nibble 的 palette index `1→4`。

baseline 与 candidate 都使用生产 `resolve_character_battle_bundle_patches` 路径，把
resource 0 的完整 bundle 迁移到 `0x08600000`：

| 区段 | 新地址 |
|---|---:|
| palette | `0x08600000` |
| graphics | `0x08600020` |
| component region | `0x08604820` |
| frame pointer table | `0x08604A00` |
| timeline region | `0x08604A50` |
| animation pointer table | `0x08604B30` |

两边 bundle 均为 `0x4B60` bytes，descriptor row 0 统一重定向；两份 16 MiB ROM 的
补丁拓扑完全相同，整份 ROM 只差 file offset `0x600D46` 一个 byte。

## 自然运行与像素因果链

两边分别从 accepted loader 前快照
`artifacts/runtime-checkpoints/scenario-41-start-row.ss9` 启动，只输入一次 `A`
（frame 5 按下、frame 13 松开），在 frame 80 独立捕获。两边均到达 battle 41、
map `36×44`，没有自动输入或恢复输入。

运行结果：

- 完整 EWRAM、IO、PRAM、OAM 均逐字节相同；
- 完整 96 KiB VRAM 只差 offset `0x10126`，即
  `0x06010126: 0x12→0x42`；
- OAM entry 0 两边均为 `088068c00008e300`，对应屏幕 `(104,8)`、32×64、
  tile 0、palette bank 0、priority 2；
- `DISPCNT=0x1940`，OBJ 启用且使用 1D mapping；局部 `(13,17)` 独立换算为
  OBJ VRAM `0x06010126` 和屏幕 `(117,25)`；
- BG3 在该点 palette index 为 0（透明），BG0 priority 3 位于 OBJ priority 2
  之后，因此目标 OBJ 像素可见；window 未启用，OBJ 也不是 blend/mosaic 模式；
- 最终两张 240×160 截图恰好只差 `(117,25)` 一个像素，
  `(33,33,33)→(255,0,0)`；每张外部 PNG 与对应 `.ss9` 内嵌画面 RGB 指纹一致。

颜色 oracle 最初使用 `value*255//31`，独立 verifier 正确拒绝了原始成果，因为
mGBA 的 5→8 bit 扩展采用位复制 `(value<<3)|(value>>2)`，灰色通道应为 33 而非
32。修正后重新从空 `final/` 导出并通过；失败导出保留在受管实验归档中，没有覆盖
正式证据。

## 证据安全

正式成果位于 `artifacts/character-battle-graphics-pixel-ab-v1/`。独立 verifier：

- 不导入构建器、exporter 或生产 bundle importer；
- 从基准 ROM、两个最小 bundle 和 descriptor 独立重建两份 16 MiB ROM；
- 重建 palette、graphics、component、frame/timeline/animation pointer 区段；
- 固定五个完整运行时内存域的 SHA-256，并重算唯一 VRAM 差异；
- 从 IO/OAM/VRAM/PRAM 独立重算 OBJ 地址、palette index、背景遮挡和最终 RGB；
- 固定原始 `.ss9`、PNG、audit、sentinel、guard、bundle 及 build manifest 身份；
- 绑定两个独立 run ID、输入成功状态、mGBA 与 Lua 哈希、进程组守卫和 RSS；
- 拒绝重签后的 bundle、pixel contract、savestate display、audit、guard、build
  contract 和 scope 扩大篡改。

两次 mGBA 守卫运行均为 `completed/0`、非 degraded、POSIX process group；峰值
owned-tree RSS 分别为 `109.78125 MiB` 与 `109.01171875 MiB`。临时 16 MiB ROM
未进入 Git，实验已压缩归档。

## 复现

```bash
TASK=character-battle-graphics-pixel-ab
RUN_ID=<unique-run-id>
python3 tools/experiment_workspace.py --root . init \
  --task "$TASK" --run-id "$RUN_ID"
RUN_DIR="build/experiments/active/$TASK/$RUN_ID"

python3 tools/build_character_battle_graphics_pixel_ab.py \
  --root . --output "$RUN_DIR/build"

# baseline/candidate 分别经 tools/run_guarded.py 调用
# tools/run_macos_mgba_single_input.py；输入 A 5/13、capture 80，
# 运行产物写入 "$RUN_DIR/runtime/<variant>"。

python3 tools/export_character_battle_graphics_pixel_ab_evidence.py \
  --root . --run-dir "$RUN_DIR" --output "$RUN_DIR/final"
python3 tools/verify_character_battle_graphics_pixel_ab_evidence.py \
  --root . --artifact "$RUN_DIR/final"
python3 tools/experiment_workspace.py --root . promote \
  --task "$TASK" --run-id "$RUN_ID" \
  --artifact-name character-battle-graphics-pixel-ab-v1
python3 tools/experiment_workspace.py --root . archive \
  --task "$TASK" --run-id "$RUN_ID"
```

## 边界

本成果只签发 resource 0、character 1、visual slot 0、frame 3、component 0 的一个
代表性自然像素链，以及同一完整迁移 bundle 的运行时可消费性。它不证明其余 249 个
物理资源、342 个逻辑槽、所有 animation/frame/component、camera、affine、blend、
palette transform、完整动作时序或实体 GBA/flashcart 输出。Goal 保持 active。
