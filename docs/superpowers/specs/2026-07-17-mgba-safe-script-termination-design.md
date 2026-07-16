# mGBA Qt 脚本安全终止设计

## 背景与根因

macOS Intel 的 mGBA 0.10.5 Qt 脚本在 CPU 线程执行 Lua `os.exit(0)`。一次固定 B 回放在所有
capture 文件写出后以 `SIGABRT` 退出；系统崩溃报告把调用链定位到
`os_exit -> exit -> QtGui/QtCore QObject 析构 -> malloc_zone_error`。这不是 ROM 崩溃，而是 Qt
对象在错误线程析构的非确定竞态。重试或接受 `child-exit/-6` 都会削弱资源守卫语义。

## 选择

由现有父级资源守卫负责终止已完成的 replay，而不是让 Lua 终止宿主进程。保留 mGBA 0.10.5、
Qt `--script` 回移、固定脚本哈希、单输入和 `completed/0` 门禁；不切换模拟器、不接受崩溃产物，
也不按进程名清理。

## 数据流

1. runner 为本次 run 分配 fresh done-marker 路径和 run ID，并把两者传给固定 Lua。
2. Lua 同步保存 state、截图、audit 和 sentinel，最后写入包含 run ID/capture frame 的 marker；
   callback 随后保持无副作用，不再调用 `os.exit`。
3. `run_guarded.py` 的可选 success-marker 监视器发现 fresh regular marker 后，向自己拥有的进程组
   发送终止信号并等待清理；摘要写 `reason=completed`、`exit_code=0`、
   `completion_trigger=success-marker`。未配置 marker 时行为完全不变。
4. runner 在 guard 返回后验证 marker payload、audit/sentinel、state、PNG、所有 provenance 哈希、
   owned PGID/listener 和源 `base.sav`。marker 提前、内容错误、产物缺失、子进程提前退出或残留均失败。

## 范围

只修改当前受支持的 fixed zero-input 与 single-input replay、两个 Python runner、通用 guard 的可选
参数及对应测试/README。600-frame sampler 继续通过 zero-input replay 在 capture 600 的 marker 收尾。
其他历史 Lua 暂不迁移，不扩大当前 runtime 路径。

## TDD 与验收

- RED：guard 尚不接受 success marker；Lua 仍含 `os.exit`；runner 尚未要求/验证 marker。
- GREEN：marker 触发 owned-process-group 清理并返回 `completed/0`；缺失/错误 marker、非零提前退出、
  超时和残留继续 fail closed；旧无 marker guard 测试不变。
- 集成：用新的 fresh 目录重放同一 inner B。必须没有新增 mGBA crash report，guard 为
  `completed/0` 且 trigger 为 marker，audit/sentinel 完整，RSS 低于上限，PGID/listener/source-save
  clean。原 `child-exit/-6` state 永不消费。

## 边界

成功标记不是证据本身，只是通知 guard 可以清理进程；最终成功仍由 runner 对全部产物和 provenance
复核。guard 只终止本次创建的 process group，绝不扫描或结束其他 mGBA 实例。
