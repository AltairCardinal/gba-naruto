# Cutscene 视觉资源表玩家可见闭环（2026-08-09）

## 结论

历史 `cutscene-scripts@0x53DF70` 不是剧情脚本表，而是两张相邻的四记录视觉资源表。`artifacts/cutscene-obj-id1-primary-ptr-ab-v1/` 直接隔离修改源表字段并完成自然运行时最终像素 A/B，可将该 bank 从 `code_verified` 升为 `runtime_verified`。

## 静态身份与消费链

- `0x0853DF70`：ID 0..3 的 LZ77 graphics/palette pair。
- `0x0853DF90`：同一组 ID 的 sprite definition/animation pair。
- `0x08072F0C` 以 `id * 8` 读取第一表，并经 `0x0809C0E8` 解压到 `0x06016000` 与 `0x05000380`。
- `0x08072EDC` 又把第二表交给 `0x080625A4`；其 `0x08062668` 路径同样以 `id * 8` 安装 definition/animation。
- 四个直接 caller 只传入 ID 0..3；`0x53DFB0` 是后续独立对象，不能扩成第五条记录。

## 直接字段自然运行时证据

- 输入快照：`artifacts/runtime-checkpoints/scenario-41-combat-popup.ss9`，SHA-256 `01f478cfafa2796cbe1652007c16e54480d2a289d1e6f54068ace8adc970300a`。
- 输入：frame 5 按 A、frame 13 松开；frame 512 捕获。快照输入前 `0x06016000` 尚不存在目标资源。
- baseline/candidate 先使用完全相同的 production relocation；A/B 之间只把 ROM `0x53DF78..79` 的 ID 1 `primary_ptr` 从 `0x08BA04C0` 改为同为 4096-byte graphics 的 ID 2 donor `0x08BA09CC`，其余 16 MiB ROM 字节完全相同。
- 两案分别从各自表指针选中的 LZ77 流解压，4096-byte graphics 与运行时 `0x06016000..0x06016FFF` 完全相等。
- 六个完整内存域中仅 VRAM 有 2,263 字节不同；EWRAM、IWRAM、IO、PRAM、OAM 全部相同，OAM entry 1 与 palette 也保持相同。
- mGBA PNG 与 savestate 的 Mode 0 离线重放逐 RGB 相等；最终在 `(42,49)..(197,110)` 改变 4,032 个像素。
- 两次 guard 均 `completed/0`、非 degraded，峰值 owned-tree RSS 为 59.66/59.76 MiB。

## 本轮修复与验证

先行复核发现既有 `artifacts/cutscene-obj-id1-pixel-ab-v1/` 只改变 relocation 后的 graphics 内容，虽证明自然 loader 与最终像素，却不满足本项目“bank 字段直接 A/B”的严格口径；因此没有据此提前升级。另修复了该旧 artifact 因共享 Mode 0 渲染器升级产生的 implementation hash 漂移，并让静态导出器兼容 `runtime_verified` 状态。最终升级只引用新的直接 pointer A/B artifact。

## 证据边界

已证明 ID 1 `primary_ptr` 通过真实原生表、production relocation、自然胜利 loader、VRAM、OAM 合成到最终像素的因果链。没有证明资源 0/2/3 的逐项运行时行为、第二表的 definition/animation 字段 A/B、物理 GBA 或任何剧情脚本语义。
