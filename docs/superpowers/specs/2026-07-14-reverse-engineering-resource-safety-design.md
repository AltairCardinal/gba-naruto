# 逆向工程资源安全设计

## 目标

在不依赖人工记忆、也不影响机器上其他项目进程的前提下，消除全 ROM Capstone 扫描的
OOM 根因，并为本项目高内存任务提供单实例、启动准入、运行时监控、超时和精确子进程清理。

本设计只处理本项目主动启动的进程。任何实现都不得按 `python`、`node`、`chromium` 等进程名
批量终止进程，也不得扫描并清理无法证明所有权的 PID。

## 已确认根因

`tools/find_thumb_calls.py` 将完整 6 MiB ROM 传给 `Cs.disasm(..., count=0)`。Capstone
Python binding 在产生第一条 Python 迭代结果之前，先调用 `cs_disasm` 为全部指令结果分配
内存；`detail=True` 和 `skipdata=True` 又分别放大单条结果和扫描覆盖范围。多个此类进程与
多个 Chromium runtime probe 并发后，4 GiB RAM 与 2 GiB swap 被耗尽。

详细证据见 `notes/memory-incident-root-cause-20260714.md`。

## 方案选择

采用“扫描根因修复 + 项目级重任务门禁”的组合方案。

不采用仅增加 swap 的方案，因为它只延迟 OOM 并加重 swap thrashing；不把 cgroup 或
Windows Job Object 作为唯一入口，因为仓库还需要在不具备这些设施的开发环境运行。

## 架构

### 1. Thumb 分支扫描层

新增 `tools/thumb_branch.py` 作为唯一公共 Thumb 直接分支编解码模块，提供：

- `encode_thumb_bl(callsite: int, target: int) -> bytes`；
- `decode_thumb_bl(callsite: int, first: int, second: int) -> int | None`；
- `decode_thumb_b(callsite: int, halfword: int) -> int | None`；
- `iter_thumb_direct_branches(data: bytes, *, rom_base: int, start: int | None = None,
  end: int | None = None) -> Iterator[ThumbBranch]`；
- `find_thumb_branches(data: bytes, target: int, *, rom_base: int,
  start: int | None = None, end: int | None = None) -> list[ThumbBranch]`。

`ThumbBranch` 至少包含 `address`、`target`、`mnemonic` 和用于兼容 CLI 的 `op_str`。
`start`/`end` 使用 GBA 地址、`end` 为 exclusive；范围必须位于输入数据映射内并按 halfword
对齐。BL 需要完整四字节落在范围内；跨越 `end` 的半条指令不得返回。

扫描实现逐 halfword 读取，不创建全 ROM instruction/detail 对象。它可以安全扫描完整 ROM，
也支持调用方缩小范围。数据区仍可能形成编码候选，因此输出是“直接分支候选”，后续用
bounded disasm、运行时命中或已知代码范围复核。

GBA ARM7TDMI 属于 ARMv4T。本层支持 Thumb BL 和 16-bit unconditional B；不承诺 BLX
immediate。旧 Capstone 全数据扫描产生的 BLX 结果不作为兼容契约继续保留。

### 2. 兼容接入

`tools/find_thumb_calls.py` 保留现有 CLI 主体和 `scan_calls(rom_path, target)` 返回结构，内部改为
调用公共扫描层；新增 `--start` 和 `--end`。脚本不再导入 Capstone。

`tools/extract_audio_cue_calls.py` 现有私有 Thumb BL decoder 改为公共模块调用。
`tools/build_save_state_runtime_probe.py` 保留 `encode_thumb_bl` 名称并兼容 re-export，避免一次性
改动大量 probe。numeric/text/tilemap writer probe 后续可逐步改用公共 finder，但本阶段首先
用现有真实 ROM 集合测试证明行为一致，不做无关重构。

`tools/disasm_thumb.py` 保持候选复核职责，并把文件读取改为 seek/read 指定窗口，避免“bounded
disasm 但先 read_bytes 整个文件”的实现偏差。

### 3. 项目级重任务门禁

新增 `tools/project_resource_guard.py`，负责：

- `heavy` 共享非阻塞锁；
- Linux `/proc/meminfo` 与 Windows `GlobalMemoryStatusEx` 的可用内存读取；
- 受控子进程树 RSS 采样；
- 只终止当前 guard 创建的子进程树；
- JSON 运行摘要。

新增 `tools/run_guarded.py` CLI，以 `--` 后的参数作为子命令。高内存静态任务和 Chromium
runtime probe 必须使用同一个 `heavy` 锁，而不是各自独立的锁。第二个重任务发现锁已占用时
立即以退出码 75 失败，不排队形成内存峰值。

默认资源参数：

- 启动前最少可用物理内存：1024 MiB；
- 单个受控进程树最大 RSS：1536 MiB；
- wall timeout：600 秒；
- 无进度 timeout：60 秒；
- RSS 采样间隔：1 秒。

阈值可以通过显式 CLI 参数收紧或为不同机器调整，但调用方不能关闭共享锁，也不能把其他
进程纳入清理范围。无法可靠读取内存时应拒绝启动，除非调用方显式选择可审计的降级开关；
降级状态必须写入摘要。

### 4. 进程所有权与平台隔离

POSIX 子进程使用独立 session/process group；超时或超限只向该 group 发送终止信号，宽限期后
再强制结束该 group。

Windows 子进程放入当前 guard 创建的 Job Object，并启用 `KILL_ON_JOB_CLOSE`；RSS 超限或
timeout 时终止该 Job。若 Job Object 初始化失败，guard 应在启动子进程前报错，不能退化为
按进程名称调用 `taskkill /IM`。

锁使用持有打开文件句柄的 OS lock：POSIX `fcntl.flock(LOCK_NB)`，Windows
`msvcrt.locking(LK_NBLCK)`。进程正常或异常退出后由 OS 释放锁，避免陈旧 PID 文件。

### 5. 运行日志与定时检查

每次 guarded run 输出一份 JSON 摘要到调用方指定路径，至少包含：

- guard PID 与 child PID；
- 命令、工作目录、开始/结束时间；
- 初始可用内存、进程树 peak RSS；
- lock 名称与平台隔离后端；
- 退出码以及 `completed`、`lock-busy`、`admission-rejected`、`wall-timeout`、
  `idle-timeout`、`memory-limit` 或 `launch-error` 原因。

逆向工程期间，主工作流在每项 runtime probe 前后执行项目范围进程检查和系统可用内存检查。
发现异常时只处理本次 guard 摘要中记录的 PID/Job/process group，不操作其他项目进程。

Chromium probe 需要输出阶段进度，使 60 秒 idle timeout 有可靠语义。进度点至少覆盖浏览器
启动、页面加载、ROM core 就绪、checkpoint 加载、导航阶段切换和结果落盘。

## 错误处理

- 参数地址未对齐、越界或 `start > end`：在扫描前返回明确错误；
- `heavy` 锁已占用：不启动子进程，退出 75；
- 可用内存低于门槛：不启动子进程，写 admission-rejected 摘要；
- timeout/RSS 超限：先终止自己创建的进程树，等待宽限期后只强制结束同一进程树；
- 子进程非零退出：保留其退出码和输出，不将其误写成资源事故；
- 监控后端不可用：默认拒绝；显式降级时在日志中标明 protection degraded；
- 任何路径都必须释放锁并完成摘要的原子落盘。

## TDD 与集成验证

### Thumb 扫描

- BL 前向、负位移、最小/最大合法范围；
- 奇数地址、越界目标、错误 halfword 和尾部不足四字节；
- unconditional B 正负位移，不把条件 B 识别为直接 B；
- `start`/`end` 边界、非默认 `rom_base`、跨 end BL 排除；
- CLI 文本与输出文件兼容；
- 在 Capstone 不可导入的环境仍能扫描大型 synthetic bytes；
- 真实 ROM 音频调用和三个 writer call-site 集合测试继续通过；
- bounded disasm 只读取请求窗口。

### 资源门禁

- 一个进程持有 `heavy` 锁时，第二个实例退出 75；
- 正常和异常退出后锁均可重新获得；
- scan 与 Chromium probe 争用同一把锁；
- 注入内存快照验证启动准入；
- child + grandchild 在 timeout 或超限时被终止；
- 同时运行的无关同名 Python 哨兵保持存活；
- 运行摘要记录 peak RSS、后端和退出原因；
- 静态检查不得出现 `pkill`、`killall` 或按映像名 `taskkill`；
- 所有自动测试只使用短时 sleep/小额分配假进程，不启动浏览器或全 ROM Capstone。

### 验证命令

实施计划必须至少运行：

```text
python -m unittest tests.test_thumb_branch tests.test_find_thumb_calls
python -m unittest tests.test_project_resource_guard
python -m unittest tests.test_extract_audio_cue_calls
python -m unittest tests.test_build_text_writer_trace_probe tests.test_build_numeric_writer_trace_probe tests.test_build_tilemap_writer_trace_probe
node play/_scripts/runtime-formation-probe.test.js
python -m unittest discover -s tests -p "test_*.py"
```

## 推进边界

本规格完成并验证后，才能启动下一项高内存 runtime 工作。逆向 P0 下一项是透明观察
`0x08073946 -> 0x0806F718`，从 scenario 41 可行动 checkpoint 证明玩家控制边界；随后严格按
MOVEDONE、胜负谓词、结果写入、natural postbattle、升级和 levels 自然消费顺序推进。

资源安全实现不会改变任何 bank 的 verification 状态，因此本阶段不更新
`docs/sequel-roadmap.md` 的 13 runtime / 10 code / 9 disproved 分布。
