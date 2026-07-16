# macOS mGBA GDB 严格归属设计

## 目的

让既有 `mgba_gdb_probe.py` 在 macOS Intel 上复用 mGBA 0.10.5 的 GDB RSP、`.ss9` 加载、
ROM 指纹、精确断点和只读内存能力，同时保持与 Windows 相同的 fail-closed 进程归属门禁。

## 已确认根因

run `2c8762c77a7ddd153ebe9f3afabf73be` 的空 Lua trace 不是 Thumb 地址或执行窗口问题：Qt
backport 在一次性 `start` callback 后才加载脚本，而且精确 0.10.5 binary 不导出
`setBreakpoint`、`clearBreakpoint`、`currentCycle`。因此不扩大 Lua backport，回到当前 change
已批准的 native GDB 通道。

## 设计

- 保留 RSP packet、`Z0`、stop/PC 校验、256-byte 分块、ROM fingerprint 和有界日志。
- Windows owner 查询不变。
- Darwin 调用 `/usr/sbin/lsof -nP -FpnT -iTCP:<port>`，解析 process、endpoint 与 TCP state。
- listener 必须是目标 host/port 的唯一 LISTEN owner；连接必须是 server-local → client-peer 的
  唯一 ESTABLISHED owner；两者都必须等于刚启动的 mGBA PID。
- `lsof` 缺失、超时、非零且无可解析记录、字段畸形、owner 为空/多义/不匹配都失败。
- 实际运行必须再由 `tools/run_guarded.py` 的 shared heavy lock、owned process group、RSS ceiling
  和 success/failure summary 包裹；探针自身只终止直接 child，不清理其他进程。
- GDB 不发送按键。首次 smoke 只在 observer ROM/state 上断到 `0x08095F12` 并读取少量上下文，
  不消费输出、不声明玩家控制。

## 测试与验收

- 单元测试覆盖 `lsof -FpnT` 多进程/多 FD 解析、LISTEN 与双向 ESTABLISHED 精确筛选、异常输出、
  owner mismatch、Windows 分支不回归。
- Darwin 集成测试创建当前 Python 进程拥有的临时 listener/connection，验证真实 `lsof` 查询能
  返回当前 PID；无 shell 文本解析。
- parent 复跑现有 GDB probe 测试；独立 reviewer 同时给出 Spec 与 Quality verdict。
- runtime smoke 只允许一次；guard、RSS、ROM/state/binary hash、stop PC、owner PID、residue 和
  `rom/base.sav` 门禁任一失败都停止，不 retry。

## 边界

不实现新的 GDB 协议、不修改 mGBA binary、不把 GDB 变成输入通道、不升级玩家控制结论。
Lua breakpoint trace 在 GDB smoke 通过后移除，避免对当前 0.10.5 binary 产生不可审计的空记录。
