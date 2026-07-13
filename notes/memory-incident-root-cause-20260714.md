# 最近逆向工作内存事故根因与规避方案（2026-07-14）

## 调查范围

本次先核对 `docs/reverse-engineering-handoff-20260711.md` 第 0.5 节、
`docs/sequel-roadmap.md` 的资源约束、`tools/find_thumb_calls.py`、仓库内 vendored
Capstone Python binding，以及 `play/_scripts/runtime-formation-probe.js`。

没有重新执行全 ROM 扫描。已有两次 OOM 系统日志和当前实现已经足以确认分配机制；
在 4 GiB RAM / 2 GiB swap 环境重做 OOM 只会重复已知事故，不会增加有效证据。

## 已有事故证据

- 2026-07-13 22:37:56：OOM kill `python3`，anon RSS 3,143,600 KiB；
- 2026-07-13 23:19:52：OOM kill `python3`，anon RSS 3,496,848 KiB；
- 两次均伴随 4 GiB RAM 接近耗尽、2 GiB swap 完全耗尽；
- `systemd-journald`、SSH session、proxima watchdog 同时超时；
- 事故后五分钟内核 I/O pressure 的 `full avg300` 仍约 25%；
- 同期存在多个全 ROM `find_thumb_calls.py` 和四个 Chromium runtime probe。

因此“磁盘读写占满”是 swap thrashing 的外观，不是磁盘 I/O error，也不是文件系统写满。
根分区约 95% 使用会缩小恢复余量，但不是触发源。

## 根因链

### 1. 全 ROM 调用实际是一次性分配，不是流式迭代

`tools/find_thumb_calls.py` 当前执行：

```python
data = rom_path.read_bytes()
md.detail = True
md.skipdata = True
for insn in md.disasm(data, 0x08000000):
    ...
```

`read_bytes()` 读取 6 MiB ROM 本身不是主要问题。关键在 vendored
`tools/_vendor/capstone/__init__.py`：`Cs.disasm()` 在开始 yield 前先调用
`cs_disasm(..., count=0)`。Capstone 的接口说明明确指出：`count=0` 会持续解码到输入末尾，
并一次性为全部 `cs_insn` 结果分配数组；内存紧张时应改用 `cs_disasm_iter()`。

所以 Python 代码虽然写成 `for` 迭代器，底层并不是逐条分配/释放。`cs_free()` 只有在整个
生成器结束或退出后才执行。

### 2. `detail=True` 放大每条指令的分配

目标判断只需要分支地址，但工具为所有解码结果启用了 detail。Capstone 会为每条有效指令
提供 `cs_detail` 数据；6 MiB ROM 在 Thumb 模式下可能形成约 157 万至 314 万条指令级
结果，因此单进程 RSS 达到 3 GiB 量级与实现机制一致。

### 3. `skipdata=True` 让数据区也继续走完整 ROM

ROM 中不仅有代码，还有图像、音频、文本和表。`skipdata=True` 会跳过不能解码的字节并继续，
使扫描不会在数据区自然停止。工具也没有 `--start/--end`、chunk size 或候选地址过滤，
因此每次查询都扫描完整 6 MiB。

### 4. 并发将单进程高水位放大成系统级故障

当前工具没有跨进程互斥、资源准入或内存上限。多个调查任务可同时启动相同扫描；同期四个
`runtime-formation-probe` 又各自启动 Chromium。浏览器脚本有 `finally { browser.close() }`，
能处理正常退出，但没有阻止多个独立进程同时启动。因此并发总内存超过 RAM + swap，最终触发
OOM kill，并通过 swap I/O 拖慢系统服务。

## 当前保护状态

当前分支只有文档级操作约束，尚无代码级强制门禁：

- `tools/find_thumb_calls.py` 没有范围、分块、超时、锁或内存预算参数；
- `tools/README.md` 仍给出不带范围的全 ROM 示例；
- `runtime-formation-probe.js` 会在单个进程结束时关闭浏览器，但没有全局单实例锁；
- 最新 `7a02dbe build: lock runtime probe dependencies` 只锁定依赖版本，不是资源锁。

因此只要后续执行者忽略交接文档，同类事故仍可复现。

## 立即可用的无代码改动规避方案

按优先级执行：

1. 不再用 `find_thumb_calls.py` 做默认全 ROM 查询。先直接搜索 Thumb BL/BLX 编码或目标
   literal，再对候选附近运行 `tools/disasm_thumb.py` bounded disasm。
2. 任何必须运行的旧扫描只允许一个进程；不得与 Chromium runtime probe 并发。
3. 所有长命令设置外部 timeout；60 秒没有有效进度输出就终止并换成候选搜索/局部反汇编。
4. 在 4 GiB 主机上，每批任务前后检查 `free -h`、swap、`/proc/pressure/io` 和相关进程；
   swap 已显著增长时不启动下一项高内存任务。
5. Linux 上优先用 cgroup/systemd scope 提供最终保险，例如给扫描进程设置 MemoryMax，并令
   OOM 只终止该 scope，而不是拖垮 SSH、journald 和 watchdog。

## 应实施的代码级方案

若后续授权修复，建议按以下顺序做 TDD：

1. **默认改为编码扫描**：对 Thumb `BL`/`BLX` 的两个 halfword 直接解码目标地址；这类查询
   不需要对整份 ROM 建立 Capstone instruction/detail 对象。
2. **强制范围接口**：增加 `--start/--end`，默认拒绝无界扫描；只允许显式危险开关请求全 ROM。
3. **分块/流式反汇编**：通用分支场景使用 `cs_disasm_iter()`，或按小窗口分块并保留最多
   4 字节重叠；初筛禁用 detail，只对候选位置做局部 detail 反汇编。
4. **跨进程互斥**：静态全 ROM 扫描和 Chromium runtime probe 分别使用项目级 lock file；
   资源不足或已有实例时 fail fast，不排队堆积多个重进程。
5. **资源门禁与可观察性**：启动前检查可用内存，记录 PID、范围、RSS 峰值和进度；设置硬 timeout
   和内存上限。即使调用者绕过约定，也应由工具拒绝危险组合。
6. **文档与测试同步**：替换 `tools/README.md` 的无界示例，并添加能在退化为
   `md.disasm(full_rom, count=0)` 时失败的测试；另测试并发锁和范围边界。

## 可复用的现有模式

- `notes/battle-start-control-flow-20260713.md` 已证明“literal 搜索 → Thumb PC-relative
  `ldr` 反查 → 局部 `disasm_thumb.py`”比全 ROM Capstone 扫描更适合当前问题；
- `tests/test_build_numeric_writer_trace_probe.py` 和
  `tests/test_build_tilemap_writer_trace_probe.py` 已有按 halfword 遍历、直接识别 Thumb BL
  编码的模式，可抽取为公共扫描能力；
- `tools/disasm_thumb.py` 已支持地址窗口，适合作为候选复核层，不应承担无界发现层。

## 重要文件与边界

- `tools/find_thumb_calls.py:23-39`：事故的直接扫描路径；
- `tools/_vendor/capstone/__init__.py:1158-1185`：`disasm()` 先调用一次 `cs_disasm`；
- `tools/_vendor/capstone/include/capstone/capstone.h:605-705`：`count=0` 和
  `cs_disasm_iter()` 的官方接口说明；
- `play/_scripts/runtime-formation-probe.js:469-474`：每个 probe 启动一个 Chromium；
- `play/_scripts/runtime-formation-probe.js:738-740`：正常路径的浏览器关闭保障；
- ROM 扫描边界：file `0x000000..0x5FFFFF`，GBA `0x08000000..0x085FFFFF`。

## 结论

本次内存异常不是一般意义的 Python 泄漏，而是 **无界 `cs_disasm(count=0)` 的一次性结果分配，
被 detail/skipdata 放大，再被多进程扫描和多 Chromium 并发叠加**。最有效的避免方式不是单纯
增加 swap，而是取消默认全 ROM Capstone 路径，改用编码/literal 候选搜索和 bounded disasm，
并以互斥锁、内存上限和 timeout 把文档约束变成工具强制约束。
