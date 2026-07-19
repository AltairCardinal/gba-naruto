# mGBA 运行时安全整改设计

## 目标

阻止 Lua 回调通过 `os.exit()` 等方式结束 mGBA 进程；任何新 mGBA 崩溃都必须使后续模拟熔断，且成功标记不能掩盖崩溃。

## 设计

- 复用 `tools/run_guarded.py` 作为所有高开销进程的统一入口；在同一把 heavy lock 内依次执行 Lua/熔断预检、mGBA 启动与崩溃报告收尾，后一个 mGBA 请求不能越过尚未完成的收尾。
- 允许固定脚本所需的直接 `os.getenv(...)` 与 `io.open(...)`；拒绝其余 `os`、`io`、`ffi`、`posix` 全局访问以及动态全局加载入口，因而同时覆盖直接调用、方括号访问和二级别名。检查传入的实际文件，因此也覆盖 `build/` 下临时脚本。
- 启动前读取 `build/resource-guard/mgba-crash-latch.json`。熔断存在时拒绝新 mGBA；它只能由显式审计命令在确认没有未处理崩溃后清除。
- 持久化已确认的 crash-report 基线。运行前后比较 `~/Library/Logs/DiagnosticReports/mGBA-*.ips`；本轮或上一轮收尾后迟到的新报告都会写入熔断并把结果改判为失败，即使成功 marker 已先产生。
- 构建验收的 sentinel 直接把 mGBA 作为 `run_guarded.py` 子进程，禁止通过 Python 包装器二次启动而绕过策略。
- 现有 marker 的 run ID、输出文件与哈希、PGID 清理验证继续保留；场景推进暂时只使用固定零输入/单输入 runner 串联快照。

## 边界与失败处理

- 非 mGBA 命令不受 Lua 检查和 mGBA 熔断影响。
- 崩溃目录不存在时不伪造崩溃；目录扫描、基线、熔断或摘要写入失败时，本轮返回 125，不得报告成功。
- 不自动删除 crash report，也不关闭 macOS 崩溃提示。
- 熔断清除必须留下审计记录；本次先实现检查、写入和显式清除接口，不做自动恢复。

## 验证

- 单元测试覆盖危险脚本（含直接、方括号和别名访问）拒绝、安全脚本允许、已有熔断拒绝、迟到报告、新 crash report 覆盖 marker 成功、扫描/写入失败和显式清除。
- 集成测试覆盖 `run_guarded.py` 的 mGBA 路由与非 mGBA 回归。
- 使用固定 runner 做一次真实快照回放，确认无新 `.ips`、无进程残留且输出证据完整。
