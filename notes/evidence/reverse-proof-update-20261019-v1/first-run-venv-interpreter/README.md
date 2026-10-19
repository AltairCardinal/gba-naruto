# 首轮并发 formal 的收据（**已知环境漂移，不可作为语义证据**）

- 目录：`notes/evidence/reverse-proof-update-20261019-v1/first-run-venv-interpreter/`
- 文件：`formal-parallel-report.json` / `formal-parallel-guard.json` / `formal-parallel-run.log`
- 墙钟：**6,214 s**（guard exit 0、degraded=false、peak RSS 861.27 MiB）
- 结果：`complete=false`、`blockers=176`、`verifiers_executed=108`、
  `coverage verified=true`、`unknown_bytes=86089`、`banks_complete=10`

## 为什么这轮有 176 个 blocker（基线是 175）

多出来的第 176 个是：

```
gate rom_byte_coverage: verifier execution did not satisfy its contract:
  gate rom_byte_coverage: verifier failed with exit 1:
  .../python -I -S tools/verify_rom_sprite_loader_tail.py --root . --artifact-dir artifacts/rom-sprite-loader-tail-v1
```

**不是语义失败，是解释器解析漂移。**

该轮 runner 把 `.venv/bin` 放在 `PATH` 最前面，于是 proof spec 里的 `python3`
被解析成 `.venv/bin/python`（3.14.3，但 `--system-site-packages` 建出来的 venv
**自己没有** site-packages 内容）。

`tools/verify_rom_sprite_loader_tail.py::_load_source_verifier()` 有一段刻意的
兼容 workaround：

```python
purelib = sysconfig.get_path("purelib")
if purelib and purelib not in sys.path:
    sys.path.append(purelib)
```

验证器命令一律带 `-I -S`（隔离 + 跳过 site），Pillow 本来不可见，
靠这段手动补 purelib 才能 import `PIL`。

而 `sysconfig.get_path("purelib")` 取决于**正在运行的那个解释器**：

| 解释器 | purelib | 有 Pillow |
| --- | --- | --- |
| `/usr/local/bin/python3` | `/usr/local/lib/python3.14/site-packages` | 是 |
| `.venv/bin/python` | `<repo>/.venv/lib/python3.14/site-packages` | **否** |

于是 workaround 静默失效 → `ModuleNotFoundError: No module named 'PIL'`
→ 该验证器 exit 1 → 多出第 176 个 blocker。

**结论：正式 formal 必须用 `/usr/local/bin/python3`，
且不得把 `.venv/bin` 放在 `PATH` 前面。** 只有在这个与 9-30 基线完全一致的
解释器解析下，墙钟对比（2,383 s 基线）才成立。

第二轮收据在上级目录（`../formal-parallel-*`）。
