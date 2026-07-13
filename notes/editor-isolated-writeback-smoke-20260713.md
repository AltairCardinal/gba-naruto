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

## Build-ID 外部目录与请求 DB

后续隔离测试又闭合了 API 子进程的路径一致性：

- `tools/build_mod.py` 的三个 DB 读取点统一优先使用 `DB_PATH`，避免 real patches
  读取请求 DB、dialogue override 却混读全局 `sequel/editor.db`；
- `BUILD_OUTPUT_DIR` 改为每次 `load_context()` 动态读取，外部绝对目录不再因
  `relative_to(ROOT)` 崩溃；
- `tools/automated_test.py` 复用 build context 的 ROM/report 路径，实际验证当前
  build-ID 产物，不再让隔离 ROM 构建失败时仍用全局旧报告得到假绿；
- backend build subprocess 支持 `BUILD_CWD` / `PROJECT_ROOT`，使用当前 Python，
  并要求 ROM、build report、automated report 三个产物同时存在才标记 done。

`tests/test_automated_test_output_isolation.py` 在外部临时目录运行完整 automated
checks，断言三个产物、零失败、report SHA 与临时 ROM 一致，同时确认全局 ROM/report
哈希前后不变。`tests/test_editor_build_integration.py` 也已改为通过 `DB_PATH` 注入完整
mirror DB。

并发一致性也已闭合：trigger 使用 SQLite backup API 把活动 DB 事务一致地复制到
build-ID 目录，随后只把该 snapshot 的 `DB_PATH` 传给子进程；用户继续编辑不会改变
已触发 build 的输入。完整 mirror snapshot 同时暴露并修复了三个 silent no-op
generator：battle-encounters/map-events 旧字段查询改为纠正后 read-only diagnostics，
save-state 改用当前 `payload_length` 字段。
