# Task 4.6 Step 1 实施报告

## 状态

`DONE`

本报告仅覆盖 Step 1：严格 mGBA 0.10.5 Qt `--script` 两文件回移、受控构建、
CLI 能力检查和 base ROM Lua sentinel。未执行、未勾选 Step 2/3，也未修改
OpenSpec tasks、Comet progress、plan、ROM 或 runtime artifacts。

## RED / GREEN

第一轮最小 RED：

```text
python3 -m unittest \
  tests.test_build_macos_mgba.BuildMacosMgbaBootstrapTests.test_builder_module_exists -v
FAIL: Task 4.6 Step 1 builder is missing
```

最小 GREEN 创建 builder 模块骨架后，同命令 `1/1 PASS`。

第二轮行为 RED：

```text
python3 -m unittest tests.test_build_macos_mgba -v
10 tests, 10 errors
```

错误均来自预期接口/资产尚未实现，覆盖错误 commit/tag、dirty source、patch
apply-check、patch 精确双路径、guard/CMake 指纹、未回移 help、summary、Lua
sentinel 和 binary manifest。最小实现后 `10/10 PASS`。

真实 `git apply --check` 首次暴露 patch 转录损坏。加载 systematic-debugging 后，
根因定位为首个 unified-diff hunk 漏掉一行上下文，导致 hunk 行数与正文不一致。
新增语法 RED：

```text
python3 -m unittest \
  tests.test_build_macos_mgba.BuildMacosMgbaTests.test_versioned_patch_is_valid_unified_diff -v
FAIL: error: corrupt patch at line 26
```

通过 guarded 官方仓库克隆从 `7cacae1` 重新生成原始两文件 format-patch 后，
该测试和针对真实 clean 0.10.5 cache 的 `git apply --check` 均通过。

首次真实 sentinel 暴露 `rom/base.sav` 旁路副作用。新增 staging RED 因
`_run_staged_sentinel` 缺失而失败；实现“guard 内复制 ROM 到 build evidence 后再
启动 mGBA”后 targeted test `1/1 PASS`，全套最终为：

```text
python3 -m unittest tests.test_build_macos_mgba -v
Ran 13 tests — OK
python3 -m py_compile tools/build_macos_mgba.py tests/test_build_macos_mgba.py
exit 0
```

测试不访问网络。测试覆盖错误 commit/tag、dirty source、patch 不可应用、原始
patch 恰好两个路径且 unified diff 有效、SHA-256 防篡改、unpatched help 缺
`--script`、固定 CMake/guard/build summary 指纹、manifest 身份、Lua post-load
first-frame marker，以及 ROM staging 不污染输入目录。

## 实际 guarded build / sentinel

共同约束：`build/resource-guard/heavy.lock`、minimum available 4096 MiB、maximum
owned-tree RSS 1536 MiB、non-degraded POSIX process group、Ninja parallel 2。

| Phase | Summary | Peak RSS | Child/PGID | 完成后 PGID |
|---|---|---:|---:|---|
| prepare/local clone + apply | completed/0 | 68.7578125 MiB | 60856 | clean |
| configure | completed/0 | 13.4765625 MiB | 61147 | clean |
| build | completed/0 | 10.90234375 MiB | 62291 | clean |
| help | completed/0 | 0.95703125 MiB | 64862 | clean |
| version | completed/0 | 0.81640625 MiB | 64886 | clean |
| final staged Lua sentinel | completed/0 | 18.12109375 MiB | 67483 | clean |

Configure 指纹：Qt5 `/usr/local/opt/qt@5`、Release、`ENABLE_SCRIPTING=ON`、
`BUILD_QT=ON`、`BUILD_SDL=OFF`、`CMAKE_POLICY_VERSION_MINIMUM=3.5`。

最终 binary：

- 标识：`mGBA 0.10.5 + Qt script backport`
- source commit：`26b7884bc25a5933960f3cdcd98bac1ae14d42e2`
- upstream/backport commit：`7cacae126207de5499857439b9c7919bf8e882c2`
- patch SHA-256：`e76c8fc4f5451bdffe28b7f3595cd441bbb90fb1aa88a926cfbe4f1254d3d2a6`
- binary SHA-256：`af6ab51a2ff63d6067908938aa74181fe2bbad0c441e231f3c4dbc80e7d6fe5d`
- version：`mGBA 0.10.5 (26b7884bc25a5933960f3cdcd98bac1ae14d42e2-dirty)`；
  `-dirty` 只表示独立 clone 中的两文件 backport
- file：`Mach-O 64-bit executable x86_64`
- help：包含 `--script FILE Script file to load on start`
- sentinel：从 `rom/base.gba` 暂存副本启动，第一帧写出
  `{"script_loaded":true,"frame":1,"pc":"140299572"}` 并正常退出

clean cache `/Users/altair/.cache/codex-tools/mgba/0.10.5-src` 最终 status 为空；
独立 workspace diff 恰好是 `ConfigController.cpp` 与 `Window.cpp`。所有 source、
build、manifest 和 sentinel 临时证据均在 `/Users/altair/.cache` 或 ignored `build/`，
不进入提交。`rom/base.sav` 已确认是首次 sentinel 新生成的副产物，随后删除；最终
status 不含该文件。

## 提交

- 实现提交：本报告所在的单一聚焦提交（Git 提交对象无法在自身内容中包含其自身
  SHA-1；实际哈希见最终交付消息）
- 变更文件：
  - `tools/patches/mgba-0.10.5-qt-script-cli.patch`
  - `tools/build_macos_mgba.py`
  - `tests/test_build_macos_mgba.py`
  - `tools/README.md`
  - `notes/macos-intel-runtime-preflight-20260715.md`
  - `.superpowers/sdd/task-4.6-step1-report.md`

## 顾虑

- binary version 的 `-dirty` 是 mGBA 对独立工作副本中未提交 backport 的正常标识；
  消费者必须同时校验 label、source/backport commit、patch SHA-256 和 binary
  SHA-256，不得只按 `0.10.5` 字符串选择 binary。
- Step 1 只证明 Qt CLI 脚本加载和 base-ROM first-frame 执行，不证明 Step 2 的
  frame-80 replay 或 Step 3 的 prebattle candidate acceptance。
