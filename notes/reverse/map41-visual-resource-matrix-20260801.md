# Map 41 图块／调色板／metatile 自然像素 A/B

日期：2026-08-01

## 结论

同一个已验 loader 前快照
`artifacts/runtime-checkpoints/scenario-41-start-row.ss9` 分别独立启动四次，
每次只输入 `A`（frame 5 按下、frame 13 松开、frame 80 捕获）：

- preservation baseline；
- `tile_graphics` 单字节候选；
- `bg_palette` 单字节候选；
- `metatile_definitions` 单字节候选。

四份 16 MiB ROM 都迁移 map 41 的三类资源，并使用完全相同的六项补丁拓扑：

| 资源 | 新地址 | map 41 header | 解压编辑 |
|---|---:|---:|---|
| BG palette | `0x08980000` | `0x53DE38` | `+0x4A: 0D→0C` |
| tile graphics | `0x089800A4` | `0x53DE34` | `+0x2A20: 34→35` |
| metatile definitions | `0x089827D8` | `0x53DE44` | `+0x230: 19→1A` |

其他地图共享的 header 指针逐字节保持基准 ROM；候选之间没有分配地址、压缩长度或
指针拓扑差异。四次运行均自然到达 battle 41、map dimensions `36×44`，显示状态
固定为 `DISPCNT=0x1940`、`BG0CNT=0x0007`、scroll `(24,104)`。

## 三条运行时因果链

### Tile graphics

- 解压编辑是 tile 337 的首字节低 nibble，palette index `4→5`；
- 完整 EWRAM/PRAM/IO/OAM 均无差异；
- 完整 96 KiB VRAM 只差 `0x06006A20: 34→35`；
- 最终画面只差 `(160,32)` 一个像素：
  `(231,189,107)→(255,222,148)`。

frame 80 时12 KiB graphics区有1,080字节被两边相同的后续运行时 writer 覆盖。
独立 verifier 因此只签发目标 ROM byte 到 `0x06006A20` 再到最终像素的因果链，
同时要求四边的共同覆盖 offset／前后字节签名完全一致；不把本帧冒充为整份12 KiB
loader exact。

### BG palette

- 编辑的是 bank 2 / index 5，BGR555 `0x0E0D→0x0E0C`；
- 完整 EWRAM/VRAM/IO/OAM 均无差异；
- 完整 PRAM 只差 `0x0500004A: 0D→0C`；
- 最终画面精确差119像素，bbox `[0,104,238,116]`，每项都是
  `(107,132,24)→(99,132,24)`。

verifier 检查 PRAM 的透明 color 0 被归零，其余382字节与各自迁移 ROM 解压内容
一致，并从 BG0 screenblock、charbase、flip、palette 和 scroll 重建精确像素集合。

### Metatile definitions

- 编辑 metatile `0x46` 的 entry 0，tile `0x119→0x11A`、bank 3 不变；
- 完整 EWRAM 只差 `0x0201E05C: 19→1A`；
- 完整 VRAM 只差 screenblock entry `0x06000418: 3119→311A` 的低字节；
- 完整 PRAM/IO/OAM 均无差异；
- 最终画面精确差56像素，bbox `[72,24,79,31]`。

整份1,376字节 metatile EWRAM buffer 与各自 ROM 解压内容逐字节一致；primary
layout 的792字节 EWRAM buffer 也在四边都与 ROM 一致。

## 证据与资源安全

正式成果为 `artifacts/map41-visual-resource-matrix-v1/`。独立 verifier：

- 不导入构建器或 exporter；
- 从6 MiB基准 ROM 和每边六项 ledger 重建四份16 MiB ROM；
- 重扫三类资源全部物理源和对齐指针使用者；
- 检查候选单因素解压差异、保留 alias、五个完整内存域及精确前后字节；
- 重新渲染 BG0，并逐项核对坐标和前后 RGB；
- 要求外部 PNG 与对应 `.ss9` 内嵌画面规范化 RGB 完全一致；
- 检查四个独立 run ID／PGID、固定输入、guard、输出哈希及无进程／监听残留；
- 拒绝重签后的 runtime、alias、patch topology、PNG、guard、像素 oracle 和
  implementation hash 篡改。

四次运行均由统一 heavy lock 守卫，`completed/0`、非 degraded，峰值 RSS 为
`55.9609375–56.0625 MiB`。正式 artifact 约716 KiB；四份临时 ROM 只进入受管
实验归档，不进入 Git。

## 复现

```bash
TASK=map41-visual-resource-matrix
RUN_ID=<unique-run-id>
python3 tools/experiment_workspace.py init --task "$TASK" --run-id "$RUN_ID"
RUN_DIR="build/experiments/active/$TASK/$RUN_ID"

python3 tools/build_map41_visual_resource_matrix.py --output "$RUN_DIR/build"

# 对 baseline、tile_graphics、bg_palette、metatile_definitions 各自调用：
# tools/run_macos_mgba_single_input.py，输入 A 5/13、capture 80。

python3 tools/export_map41_visual_resource_matrix_evidence.py \
  --root . --run-dir "$RUN_DIR" --output "$RUN_DIR/final"
python3 tools/verify_map41_visual_resource_matrix_evidence.py \
  --root . --artifact "$RUN_DIR/final"
python3 tools/experiment_workspace.py promote \
  --task "$TASK" --run-id "$RUN_ID" \
  --artifact-name map41-visual-resource-matrix-v1
python3 tools/experiment_workspace.py archive --task "$TASK" --run-id "$RUN_ID"
```

## 边界

本成果把 map 41 的 tile graphics、BG palette、metatile definitions 三类资源从
修改 ROM 闭合到自然 loader、运行时内存和最终像素，并与既有 primary layout
证据合并覆盖同一地图的四个主要视觉资源类型。它不签发其他46张地图、alternate
layout、碰撞玩法、完整 camera/overlay 时序、被后续 writer 覆盖前的精确 tile
loader 边界，或实体 GBA/flashcart 输出。Goal 保持 active。
