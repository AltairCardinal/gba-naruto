# Probe 逐行读取器的线程创建修复

## 问题与证据边界

2026-10-24 的 Windows 事件记录将一段高频线程活动定位到
`tools/s49_battle_balance/w1_record.py`，进程启动链为
MiniMax Code → PowerShell → Python。该脚本使用
`tools/s49_victory_capture/probe.py`。

原 `_read_line()` 每读取一行，就新建一个 Queue 和读取线程，执行
`start()`、`join(timeout)`。`run()` 对命令输出循环调用它，因此线程创建数
随输出行数增长。记录保留下来的约 4.05 秒窗口内，该 Python 创建了
31,967 个线程。循环事件文件已覆盖开头，不能将这段窗口当成完整的
30 秒分配/释放账本。

同机后台任务持续运行时，以内存文本隔离执行两轮等时对照：每轮读取
1000 行、持续约 0.35 秒。直接读取的全局 `VadS` 净增分别为 609024、
609888 字节；逐行创建线程路径分别为 699264、706272 字节。两组均值差
93312 字节，接近每线程一个 96 字节对象。这支持高频线程创建是当前
VAD 增长的触发因素，但全局计数仍含后台活动，不证明对象永久不回收，
也不证明历史十多 GB 全部来自此工具链。

## 修复后的行为与维护约束

- 每个 Probe 子进程只启动两个长期读取线程：stdout、stderr 各一个。
  stdout 按原顺序进入 FIFO 队列，`_read_line()` 不再创建线程。
- stdout 队列最多预读 1024 行；满队列时施加背压，不丢弃正常输出。
  这是行数限制，不是字节限制；单行大小、`run()` 返回列表及原有 stderr
  历史列表的总大小不在本次修复范围。
- 队列等待保留逐行超时。超时不再留下另一个竞争同一管道的读取线程。
  调用方通常应在 ProbeError 后退出 Probe 上下文；若选择继续读取，必须
  先消费上一条命令的完整结束标记，不能直接发送新命令假定协议已复位。
- stdout EOF 可重复读取为 None；stdout 读取或 UTF-8 解码失败通过
  ProbeError 显式报告。stderr 失败记录进 `stderr` 并尝试入队报告；
  两条流之间不保证时序，若 stdout EOF 已被消费，迟到的 stderr 错误
  仍保留在日志中，但不保证从 `_read_line()` 再次抛出。
- 读取线程持有本次进程的具体管道。只由读取线程关闭自己的读取端，
  避免主线程关闭正在 readline 的 TextIOWrapper 而阻塞。
- `close()` 先设置关闭事件，解除满队列等待，然后沿用原有 quit、
  等待/超时终止逻辑，并分别等待读取线程最多一秒。启动中途失败也清理。
  若旧读取线程仍未退出，拒绝在同一 Probe 实例上重新启动，以免线程
  积累或跨进程串流。不要为绕过此保护反复新建实例。
- `run()` 仍是单消费者接口，不支持多个线程同时发送命令。
- 已运行的 Python 进程不会自动热更新；本次没有停止任何既有业务进程。
  后续新启动并导入该模块的工具使用修复版本。

## 假设台账与验证

| 假设 / 验收项 | 判定方法 | 结果 | 状态 |
| --- | --- | --- | --- |
| 每行新建线程造成线程数随输出规模增长 | 静态调用链和 Windows 线程创建事件 | 逐行建线程，约 4.05 秒创建 31967 个 | 已确认 |
| 修复后输出规模不会放大线程创建数 | 真实 Windows 子进程连续输出 10000 行，统计 Thread.start | 输出完整且顺序正确，仅创建两个读取线程 | 已确认 |
| 边界与生命周期保持可用 | EOF、超时后排空旧标记、满队列关闭、重启、启动失败、解码失败测试 | 9 项通过，无 ResourceWarning | 已确认 |
| 修复已经解决历史全部非分页池问题 | 尚需后续实际负载观测 | 没有此证据，不作此结论 | 未验 |

针对性测试（仓库根目录；设置 PYTHONUTF8=1、PYTHONIOENCODING=utf-8、
PYTHONDONTWRITEBYTECODE=1）：

```text
python -X utf8 -W error::ResourceWarning -m unittest discover -s tests -p test_s49_probe_stream.py -v
```

独立只读审查一轮通过，无阻塞问题；复用了上述测试结果，未重复执行。
未运行仓库全量测试、未重建并行任务产物。

实际无头探针补验通过：使用现成的
`build/mgba-probe-w1/mgba-probe.exe` 和
`D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba`，执行
`echo reader-smoke`、`frames 2 0x00000000`，分别得到准确回显与
`OK frames 2 0x00000000 bp=0 done=2`。固定两个读取线程均在关闭后退出，
无 ResourceWarning；验证前后 exe 与 ROM 的 SHA-256 均相同。
这覆盖真实探针的生产命令/管道链路，不包含长时间画面或 ROM 录制验收。
