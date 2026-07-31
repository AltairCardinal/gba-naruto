# Map 41 primary layout 自然加载像素 A/B（2026-08-01）

## 目的与编辑

本闭环验证地图编辑器最关键的一条生产链：修改解压后的地图布局、只拆分目标地图
的共享别名、构建扩容 ROM、经自然 UI 重新执行 map loader，并在 EWRAM、VRAM 和
最终 mGBA 画面看到同一个改动。

map 39–45 共享 primary layout 内容 SHA-256
`950f9555a8b12c73b3c3fdabb50209917b849972ff1ee6c3e5b80ead5d472f6f`。构建器仅把
map 41 header pointer `0x53DE3C` 重定向到 `0x08980000`；另外六个 header 保持
原指针。固定编辑交换 coarse cell `(1,6)` 内的两个 metatile：decoded offset
`0xDC` 从 `0x00350022` 改为 `0x00220035`。baseline 与 candidate 都通过正式
`map_resource_relocation` 路径生成 16 MiB ROM，patch ledger 各只有一项分配和
一项 map 41 pointer redirect。

## 自然 loader 边界

两边都从已验收的
`artifacts/runtime-checkpoints/scenario-41-start-row.ss9` 开始。该快照 SHA-256 为
`e5039f21675dde00f3bc78e7dad08bf7cbd4ce8bff2944ea108a92bbf25b9e81`，并且运行时
battle/control、map dimensions 和目标布局 word 全为零，明确位于 map loader 前。
每个 ROM 独立发送完全相同的一次 `A`（down frame 5、up frame 13、capture frame
80），不在两个变体间复用派生快照。两次运行均由固定 single-input runner 进入共享
heavy lock；峰值 owned-tree RSS 分别为 `56.0546875 MiB` 和 `56.14453125 MiB`，
均为 `completed/0`、非 degraded、PGID 与监听端口无残留，也没有产生 crash latch。

## 结果

- 两边都自然到达 battle 41、map runtime `24 2c 09 16`（36×44、9×22）。
- `0x0201BE2C` 的 792-byte primary layout 分别逐字节等于各自 ROM
  `0x08980000` 的 LZ77 解压内容。
- `0x0201BF08` 从 baseline `0x00350022` 变为 candidate `0x00220035`；完整
  256 KiB EWRAM 只有地址 `0x0201BF08/0x0201BF0A` 两个 byte 不同。
- coarse cell 经 metatile 展开后，完整 96 KiB VRAM 只在八个 BG0 entry 的低 byte
  不同：`0x06000308/30A/30C/30E/348/34A/34C/34E`。八个 u16 的变化由 ROM
  layout 和 metatile definitions 独立推导，不依赖运行输出自报。
- IO、PRAM、OAM 全域相同；BG0 为 `BG0CNT=0x0007`、scroll `(24,104)`。
- 因当前垂直 scroll，目标 32×16 cell 只有下半部出现在屏幕顶部。独立 tile、flip、
  palette oracle 逐像素重建 `[8,0]..[39,7]`，两张 mGBA PNG 恰好只在该区域改变
  204 个像素，且 baseline/candidate 的 32×8 可见像素都与 ROM oracle 完全一致。

正式证据位于 `artifacts/map41-primary-layout-pixel-ab-v1/`。独立 verifier 不导入
builder 或 exporter，会从 6 MiB 基准 ROM 和 patch ledger 重建两份 16 MiB ROM，
重新解压资源、检查七地图 alias split、验证 loader 前零状态、single-input/guard
审计、完整 EWRAM/VRAM/IO/PRAM/OAM 差异以及最终像素 oracle；每张外部 PNG 还必须
与对应 `.ss9` 内嵌画面的规范化 RGB 哈希一致。测试另覆盖重签后的运行时布局、
alias split、输入 audit 语义和外部 PNG 篡改。

## 复现

```bash
TASK=map41-primary-layout-pixel-ab
RUN_ID=<unique-run-id>
python3 tools/experiment_workspace.py init --task "$TASK" --run-id "$RUN_ID"
RUN_DIR="build/experiments/active/$TASK/$RUN_ID"

python3 tools/build_map41_primary_layout_pixel_ab.py \
  --output "$RUN_DIR/build"

# baseline/candidate 各自使用 tools/run_macos_mgba_single_input.py，
# 从 scenario-41-start-row.ss9 输入 A（5/13/80），输出分别放入
# "$RUN_DIR/baseline" 与 "$RUN_DIR/candidate"。

python3 tools/export_map41_primary_layout_pixel_ab_evidence.py \
  --root . --run-dir "$RUN_DIR" --output "$RUN_DIR/final"

python3 tools/verify_map41_primary_layout_pixel_ab_evidence.py \
  --root . --artifact "$RUN_DIR/final"

python3 tools/experiment_workspace.py promote \
  --task "$TASK" --run-id "$RUN_ID" \
  --artifact-name map41-primary-layout-pixel-ab-v1
python3 tools/experiment_workspace.py archive \
  --task "$TASK" --run-id "$RUN_ID"
```

## 边界

本成果证明一个代表性 map 41 primary-layout 编辑经过自然 loader、EWRAM、metatile
展开、VRAM 和最终像素的完整因果链，也证明共享资源可只拆分目标地图。它不签发
精确 loader PC 的运行时断点、任意地图/任意资源类型的全量像素 A/B、完整 camera
与动态 overlay 时序、碰撞玩法语义或实体 GBA/flashcart 输出。Goal 因此保持 active。
