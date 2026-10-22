# mGBA macOS 崩溃报告成因分析与防护规范

## 1. 现象与成因调查

在 macOS (Qt 构建) 环境下驱动 mGBA 自动化执行时，系统 `~/Library/Logs/DiagnosticReports/` 下可能出现 `mGBA-*.ips` 崩溃报告。

通过解析崩溃报告核心线程堆栈：
- **崩溃线程**：Thread 0（Qt GUI 渲染主线程，`QStatusBar::paintEvent` -> `QRasterPaintEngine::fillRect` -> `QMutex::lock()`）
- **异常类型**：`EXC_BAD_ACCESS (SIGSEGV)` / `KERN_INVALID_ADDRESS at 0x0000000000000008`
- **根本原因**：
  在临时测试脚本中，Lua 回调直接调用了 `os.exit(0)`。C 运行时的 `exit(0)` 会立即开始清理全局变量和静态析构函数，而此时 Qt 的 GUI/绘制事件循环正在另一线程并发执行，访问了被析构的锁/指针，导致段错误并被 macOS CrashReporter 捕获。
  这一结论与仓库内 [`tools/mgba_runtime_safety.py`](file:///Users/altair/github/naruto/tools/mgba_runtime_safety.py#L25-L35) 中将 `os.exit` 显式列入 `_DANGEROUS_LUA` 的防护设计完全一致。

## 2. 结论与防护规范

**结论**：模拟器与 ROM 本身没有任何逻辑错误或内存损坏，后续自动化复刻与录屏可以完全顺利进行。

**执行规范**：
1. **严禁在 Lua 脚本中调用 `os.exit()`**。
2. **标准完成通知**：Lua 脚本在完成既定帧数或按键序列录制后，将进度与校验结果写入 `done_marker`（JSON 文件），并将回调置为 idle。
3. **宿主平稳退出**：Python 调度进程轮询 `done_marker`，检测到完成标记后向 mGBA 进程发送 `SIGTERM`，Qt 线程安全退出，退出码为 `-15`，不产生任何系统崩溃日志。
