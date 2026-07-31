# Cutscene OBJ bundle 可变长迁移

日期：2026-07-31

## 结论

`0x0853DF70` 与 `0x0853DF90` 的四个固定 Cutscene OBJ ID 已从静态导出推进为
扩展 ROM bundle 迁移。两张表分别保存四组 graphics/palette 和四组
definition/animation 根指针；`0x0853DFB0` 是独立对象，不属于第五项。

源分母包括：

- 4 个 graphics、4 个 palette；
- 4 个 definition table、4 个 animation table；
- 10 个 frame component list、10 个 animation timeline；
- 共 36 条精确源指针引用，未知引用为 0；
- 恰好 4 个自然 loader 调用，传入的资源 ID 集合严格为 `0..3`。

完整保持迁移写入 `cutscene-obj-bundle` 区域
`0xBA0000..0xBB0000`，形成 12 个 allocation、16 个根指针 patch，共 28 项
安全写入。输出 ROM 为 16 MiB，SHA-256：
`00ceb2b2c7715feb176de30a2c190611155e7d753846d2f419acec21bd5c1a5e`。

## 可编辑边界

- ID 固定为 `0..3`，不得把 `0x53DFB0` 扩成第五项；
- frame 与 animation 槽数固定为 `[2,2,2,4]`。loader 将同一计数器同时作为
  frame/animation ID，并以 2 或 4 为硬停止值；
- 每个 ID 的 graphics 可为 `1..256` 个完整 4bpp tile；
- palette 固定为 16 色/32 bytes；
- 每个 frame 支持 1–2 个合法 GBA OBJ component；
- 每个 animation 槽支持非空变长 keyframe 序列，keyframe 可选择该 ID 的任一
  固定 frame，duration 为完整 `u16`；`0` 表示首次在 65,536 次更新后到期；
- component 与 timeline 均由 `FFFF0000` 终止，构建器重新生成终止符和内部指针。

256-tile 上限来自自然 loader，而不是任意预算。graphics 固定解压到
`0x06016000`，即 OBJ tile base `0x300`；OBJ VRAM 终点为 tile `0x400`，
因此安全容量为 `0x400-0x300=256`。257 tile 会在产生 patch 前失败。

## 独立审计

- 实现：`tools/import_cutscene_obj_bundle_relocations.py`
- 审计导出：`tools/export_cutscene_obj_bundle_relocation_audit.py`
- 独立验证：`tools/verify_cutscene_obj_bundle_relocation_audit.py`
- 产物：`artifacts/cutscene-obj-bundle-relocation-v1/`

独立 verifier 不导入迁移器或审计导出器；它从基准 ROM 重建两张表、4 个 BL
调用点、36 条源指针、确定性 LZ77、component/timeline bundle、16 个根指针和
完整 16 MiB 输出。capability fixture 独立验证 256 tile、11 个 component 和
11 个 keyframe，输出 SHA-256：
`f6e1a299f2b8b900abfb923089b6921bee42fd539d5504d6ccbf07f0935f0660`。

正式导出与验证均经统一 heavy lock。导出峰值 RSS 40.125 MiB，验证峰值
23.473 MiB，无超时、swap 或异常退出。

## 未证明边界

本成果不证明第五个 ID、改变固定 frame/animation 槽数、单帧超过两个 component、
调用者层面的场景清理，以及修改后最终屏幕合成像素与时序等价。里程碑只做离线
ROM 重建，没有启动 mGBA，因此不需要新增模拟器快照。
