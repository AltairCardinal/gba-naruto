# mGBA 崩溃锁取证与解除：崩溃者不是签收二进制（2026-10-20）

## 1. 现象

第 14 轮开头要跑新 ROM 的重制侧 walk，守卫直接拒绝：

```
artifacts/s49-remake-exproom-20261020/guard.json
  "reason": "mgba-safety-rejected",
  "safety_error": "unacknowledged mGBA crash report appeared after the previous run",
  "exit_code": 125,
  "protection_backend": "not-launched"
```

锁文件 `build/resource-guard/mgba-crash-latch.json` 记录了"上一轮之后新出现的崩溃报告"：

```
"reports": [{"path": "~/Library/Logs/DiagnosticReports/mGBA-2026-10-20-133930.ips",
             "mtime_ns": 1792474770775407229, "size": 5679}]
```

**关键事实：被拒绝的那次运行从未启动 mGBA**（`protection_backend: "not-launched"`、
`peak_tree_rss_mib: 0.0`），所以这不是"跑崩了"，而是"上一次留下的崩溃报告没被确认"。

## 2. 取证方法（可复现）

判定"这次崩溃是不是我们的问题"，只需要三样东西，全部来自崩溃报告本身：

1. `termination.indicator` / `termination.details` —— 区分**启动期失败**与**模拟期崩溃**。
2. `termination.reasons` —— dyld 的 dylib 搜索列表，直接暴露崩溃二进制的 rpath。
3. `usedImages[0]` —— 崩溃二进制自己的 bundle 版本号。

```bash
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
/usr/local/bin/python3 - <<'PY'
import json,re
p="/Users/altair/Library/Logs/DiagnosticReports/mGBA-2026-10-20-133930.ips"
txt=open(p,encoding="utf-8",errors="replace").read()
i=txt.find('"termination"'); print(txt[i:i+1400])
PY
```

实得：

```
"termination": {"code":1, "namespace":"DYLD", "indicator":"Library missing",
  "details":["(terminated at launch; ignore backtrace)"],
  "reasons":["Library not loaded: @rpath/libmgba.0.11.dylib", ...
    "tried: '/usr/local/Cellar/ffmpeg/8.1/lib/libmgba.0.11.dylib' (no such file),
     '/private/tmp/mgba-c16-runtime-20260809/build/libmgba.0.11.dylib' (no such file),
     '/usr/local/lib/libmgba.0.11.dylib' (no such file)"]}
"usedImages": [{"CFBundleShortVersionString":"0.11.0", "bundleID":"com.endrift.mgba-qt", ...}]
```

⇒ 这是 **DYLD 启动期 abort**（`terminated at launch; ignore backtrace`），不是模拟中的
非法访问/崩溃。

## 3. 关键判别：崩溃者 ≠ 签收二进制

| | 签收二进制 | 崩溃报告里的二进制 |
|---|---|---|
| 路径 | `build/macos-mgba/build/qt/mGBA.app/Contents/MacOS/mGBA` | `/Users/USER/*/mGBA.app/Contents/MacOS/mGBA` |
| bundle 版本 | **0.10.5** | **0.11.0** |
| 链接 | `@rpath/libmgba.0.10.5.dylib` | `@rpath/libmgba.0.11.dylib` |
| SHA-256 | `d1a9c2311980dead5fee8c8ddeeee6a31e7a094aff335c9302096dd8feb44872`（= `artifacts/macos-mgba-20261019-v1/manifest.json` 的 `binary_sha256`） | — |
| rpath | `build/macos-mgba/build`（存在 1024 KB 的 `libmgba.0.10.5.dylib`） | `/usr/local/Cellar/ffmpeg/8.1/lib`、`/private/tmp/mgba-c16-runtime-20260809/build`、`/usr/local/lib`（前两处都没有 `libmgba.0.11.dylib`） |

本机还留着两个 **8 月/3 月的临时 0.11.0 构建**（都已失效）：

- `/Users/altair/github/mgba-build-c16/qt/mGBA.app`（0.11.0，2026-08-09）
- `/Users/altair/github/mgba-build-qt/qt/mGBA.app`（0.11.0，2026-03-28）

它们的 `libmgba.0.11.dylib` 确实还在 `/Users/altair/github/mgba-build*/` 下，但**不在自己的
rpath 里** ⇒ 这两个 app 永远启动不了，属于历史遗留垃圾，不是可用仿真器。

## 4. 结论

1. 这次崩溃**与本轮 ROM、脚本、按键无关**：崩溃者是外部遗留的 0.11.0 构建，因其 rpath 指向
   已被清空的 `/private/tmp/mgba-c16-runtime-20260809/build` 而在 dyld 阶段 abort。
2. 签收的 0.10.5 + Qt script backport 二进制**自始至终没有被启动过**（守卫在启动前就拒绝了）。
3. 因此这条崩溃报告属于"已解释、无需追责"，可以按审计流程解除锁。

## 5. 解除方式（保留审计轨迹）

```bash
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
/usr/local/bin/python3 - <<'PY'
import sys; sys.path.insert(0, "tools")
from mgba_runtime_safety import clear_crash_latch
clear_crash_latch()
PY
```

`clear_crash_latch()` 做三件事（见 `tools/mgba_runtime_safety.py:334`）：

1. 往 `build/resource-guard/mgba-crash-latch.json.history.jsonl` 追加一条 `action: "clear"`
   事件，含锁的原文与解除时刻的崩溃报告清单；
2. 用当前崩溃目录快照刷新 `mgba-crash-baseline.json`（5 条报告）；
3. 删除锁文件。

实跑结果：`latch exists before: True` → `latch exists after: False`；baseline 报告数 4 → 5。

## 6. 由此固化的工作守则

1. **每一次 mGBA 运行都要把签收二进制钉死**：`capture_s49_advance.py` 等工具的
   `inputs.json` 记录 `mgba` 路径与 `mgba_sha256`，与
   `artifacts/macos-mgba-20261019-v1/manifest.json` 的 `binary_sha256` 一致；
   两者不一致就说明跑的不是签收件。
2. **不要用"清锁"掩盖模拟期崩溃**。本轮之所以能清，是因为崩溃报告明确写着
   `terminated at launch` 且崩溃者版本与签收件不同；若崩溃者是 0.10.5 签收件本身，
   那就属于真实问题，必须先定位再清。
3. **历史遗留的临时构建是取证污染源**：它们不会自己消失，但会被误当成"可用的 mGBA"。
   判别时先比 `usedImages` 的 bundle 版本，再比 rpath 列表。

## 引用

- 守卫策略与清锁实现：`tools/mgba_runtime_safety.py`（`prepare_mgba_launch` / `finish_mgba_launch` /
  `clear_crash_latch`）。
- 签收清单：`artifacts/macos-mgba-20261019-v1/manifest.json`（`binary_sha256` =
  `d1a9c231…44872`，sentinel `script_loaded = true`）。
- 受影响的收据：`artifacts/s49-remake-exproom-20261020/guard.json`（拒绝，exit 125）。
- 解除后的成功收据：`artifacts/s49-remake-expfix-20261020-v1/`（35 步，exit 0）。
