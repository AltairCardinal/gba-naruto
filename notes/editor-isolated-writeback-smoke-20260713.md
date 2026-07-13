# Editor DB 隔离正式构建 smoke（2026-07-13）

## 首次失败与根因

在 `git archive HEAD` 临时快照中初始化完整 ROM mirror DB，把 map header 40 的
width 从 36 改为 32，再调用正式 `build_mod.py`。无 DB baseline 构建成功；带 DB
构建最初在 `generate_cutscene_script_patches()` 崩溃：mirror 已按纠正后的
8×8-byte visual-resource pair schema 提供 `primary_ptr/secondary_ptr`，旧 generator
仍读取不存在的 `script_ptr` 并假设 16×u32。

修正 pair generator 后，集成测试继续暴露第二个真实冲突：未编辑的 alternate
chapter mirror 仍发出 base-equal bytes patch，与 manifest 中 scenario 39 的语义
relocation redirect 重叠。chapter mirror 本来就禁止 pointer-only 修改，因此未变化
行现改为 diagnostic `db_chapter_flow_unchanged`，不再用无意义写入覆盖正式 importer。

## 持久集成测试

`tests/test_editor_build_integration.py` 每次在临时目录中：

1. 运行无 DB 的正式 baseline build；
2. 用 `init_rom_tables/populate_rom_tables` 建立完整 mirror DB；
3. 只编辑 `rom_map_headers[_idx=40].width` 为 32；
4. 再运行同一个 `build_mod.build()`；
5. 比较 reserved audit region 之前的全部字节。

当前断言只允许 file `0x53DE10` 从 `0x24` 变为 `0x20`，ROM 尺寸保持不变；临时
ROOT、DB 和 build 输出在测试结束后全部删除，真实 `sequel/editor.db` 与全局 build
产物不会被污染。这补上了过去 automated test 在 DB 不存在时跳过的正式集成点。

边界：该测试证明 DB mirror→正式 generator→安全门禁→ROM 的隔离字节闭环，不等于
浏览器 UI、下载 API、OCR 或剧情长程回归。
