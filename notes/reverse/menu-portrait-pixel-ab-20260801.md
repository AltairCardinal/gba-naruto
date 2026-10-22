# 菜单／剧情立绘生产迁移自然像素 A/B（2026-08-01）

## 结论

`artifacts/menu-portrait-pixel-ab-v1/` 将菜单／剧情立绘从“静态导出、可变长迁移和
旧受控 pair 替换”推进到修改 ROM 后的自然 `ShowPortrait` 最终像素链。

目标是 portrait row 1 / variant 0（鸣人）、catalog resource 0。resource 0 共有
36 个逻辑别名；本轮通过 production `menu_portrait_relocation` 只拆分并重定向
pair `0x5A4E14`，没有连带修改另外 35 个别名。baseline 与 candidate 均把 graphics
迁移到 `0x08A80000`、palette 迁移到 `0x08A80CEC`，两个 descriptor pointer 完全
相同。

candidate 只把 80×80 authored canvas 的 `(40,40)` 从 palette index `52` 改为
`14`。六组件 1D OBJ 逆变换后，解压 graphics 只有 stream byte `5184` 从
`52→14`；palette 128 bytes 不变。两份 VRAM 安全压缩流均为 3306 bytes，分配与
指针拓扑完全相同。

## 自然预加载与输入

输入是已接纳的 base-ROM checkpoint：

- `artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-9.ss9`；
- SHA-256 `5635916176865f63b12154ea1c68e202393baaf6e1427473fb6be8a84b18eba8`；
- script cursor `0x08031F42`；
- 当前 `RenderText` 后的下一条 portrait 命令位于 `0x08031F6E`：
  `02 00 01 00 = ShowPortrait(slot 0, row 1, variant 0)`。

输入前目标 6400-byte graphics 不在动态 OBJ VRAM。baseline/candidate 分别独立运行，
均只在 frame 5 按 A、frame 13 松开，frame 80 捕获。没有脚本游标补丁、selector
强制、自动输入或恢复输入。

## 运行结果

- 两边完整 IO、PRAM、OAM 相同；
- EWRAM 只有 `0x02003CC0: 52→14`；
- OBJ VRAM 只有 `0x06011440: 52→14`；
- 两边 `0x06010000..0x060118FF` 均逐字节等于各自 6400-byte authored graphics；
- `0x05000200..0x0500027F` 均等于 catalog palette；
- OAM entries 1..6 完全相同，六组件共同覆盖 80×80 立绘；
- mGBA 最终 PNG 只有屏幕 `(56,48)` 一个像素不同：
  `(239,189,165)→(99,74,57)`；
- 仓库 Mode-0 compositor 从各自 ss9 重建后与各自 mGBA PNG 逐 RGB 完全一致。

完整 IWRAM、IO、PRAM、OAM 均零差异。EWRAM decompression work 区前部在 frame 80
已被后续工作复用，因此只签发目标 byte 和最终 OBJ VRAM 的全流一致性，不误报整段
EWRAM scratch 仍等于初始解压流。

## 证据、安全和复现

原始两次运行只保留 ss9、PNG、audit、sentinel、guard、authoring PNG/spec 和 build
manifest；两份 16 MiB ROM 与 staged ROM 留在临时实验目录，不进入 Git。两次运行
均经共享 heavy lock、2 GiB 启动门槛、512 MiB owned-tree RSS ceiling 和进程／监听
残留检查，`completed/0`、非 degraded，峰值分别为 55.96484375 和 56.1328125 MiB。
raw audit/spec 中的绝对实验目录和 staged ROM 路径只作为当次运行 provenance 保留；
临时目录清理后不可直接按这些历史路径复跑，独立 verifier 也不依赖它们存在。

```bash
python3 tools/export_menu_portrait_pixel_ab_evidence.py \
  --root . \
  --raw-root artifacts/menu-portrait-pixel-ab-v1/raw \
  --output artifacts/menu-portrait-pixel-ab-v1

python3 tools/verify_menu_portrait_pixel_ab_evidence.py \
  --root . \
  --artifact artifacts/menu-portrait-pixel-ab-v1
```

独立 verifier 不导入 builder、exporter 或 production importer。它自行完成六组件
canvas→OBJ stream 逆变换、BGR555 palette、LZ77、16 MiB ROM 重建、pair pointer
重定向、自然脚本边界、五个硬件／内存域、EWRAM/IWRAM 差分、OAM、最终像素、
renderer、audit/guard、文件全集与实现哈希检查。负测覆盖重签后的像素语义和原始
savestate 篡改。

## 被排除的 regular BG 候选

同轮曾尝试从 `scenario-41-start-row.ss9` 验证 regular BG entry 1 palette。生产迁移
本身正确，但 baseline/candidate 的 frame-80 全内存和截图完全相同。回查证明该
checkpoint 在输入前就已含 entry 1 palette（运行时仅覆盖透明色），所以它只是地图
runtime 的 pre-load，不是 regular BG 的 pre-load。该路线已清理，后续不得重复用它
声称 regular BG loader 证据。

## 边界

本成果只签发 row 1 / variant 0 在一次自然 `ShowPortrait` 首加载中的单像素
production relocation 链。它不外推至其余 310 个逻辑立绘、另外 73 个资源 pair、
`UpdatePortrait`、dim/fill 等转场、所有场景时序或实体 GBA 输出，Goal 保持 active。
