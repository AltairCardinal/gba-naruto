## ADDED Requirements

### Requirement: 原生 mGBA 运行必须可追溯
系统 SHALL 记录所用 Windows mGBA 可执行文件版本、发布来源、文件哈希、ROM 和 savestate，并以结构化 JSON 输出寄存器、停止点和读取区域。

#### Scenario: 快照只读检查
- **WHEN** 使用原生 mGBA 加载项目 ROM 与 `.ss9` 并请求若干内存区域
- **THEN** 输出 SHALL 包含 mGBA 命令、停止原因、寄存器和每个地址区域的精确十六进制内容

### Requirement: 大区间内存读取必须有界分块
GDB 客户端 MUST 将逻辑内存读取拆为不超过 256 字节的请求，并保持顺序拼接。

#### Scenario: 读取超过 mGBA 包限制的区域
- **WHEN** 调用方请求 600 字节或完整 EWRAM
- **THEN** 客户端 SHALL 发送多个最大 256 字节的连续请求并返回等长拼接结果

#### Scenario: 任一分块失败
- **WHEN** mGBA 对某个分块返回 `E..` 错误
- **THEN** 整个逻辑读取 MUST 失败并在输出 JSON 中保留错误类型与消息

### Requirement: 运行必须受项目资源守卫约束
每个 mGBA 或浏览器 probe SHALL 在项目资源守卫下运行，并只清理守卫拥有的进程树。

#### Scenario: 正常完成
- **WHEN** probe 在 wall、idle 和 RSS 门槛内结束
- **THEN** 守卫摘要 SHALL 记录 backend、子 PID、峰值 tree RSS、命令和完成原因

#### Scenario: 超时或超内存
- **WHEN** probe 超过规定 wall/idle/RSS 门槛
- **THEN** 守卫 MUST 只终止本次 Windows Job Object 或 POSIX process group，并保留原始失败诊断

### Requirement: 输入不得影响其他桌面应用
系统 MUST 避免全局键盘注入、焦点抢占和按进程名批量终止。

#### Scenario: 原生窗口不能可靠接收定向输入
- **WHEN** 最小化 mGBA 的 `PostMessage` 未触发 KEYINPUT
- **THEN** 系统 SHALL 使用浏览器模拟器实例内按钮 API 或其他同等隔离路径，而不是 `SendInput`

### Requirement: probe 功能变化必须经过 TDD 与独立复核
新增或修改 probe 行为 SHALL 先有因正确原因失败的测试，再实现最小修复，并完成相关单元、集成与代码审查。

#### Scenario: 新增 GDB 分块读取
- **WHEN** 引入自动分块能力
- **THEN** 测试 SHALL 先证明旧实现只发送单个过大请求，再验证分块地址、大小和拼接结果
