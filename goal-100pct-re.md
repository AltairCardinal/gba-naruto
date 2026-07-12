# Goal: 100% 完成 naruto-sequel-dev.gba ROM 逆向工程

> **接管决议（2026-07-12）**：保留“100% 完成逆向工程”作为总目标；废弃本文下方
> 2026-06-26 的执行清单、数量型完成标准和旧 `goal_complete` 示例。当前执行依据依次为
> `artifacts/runtime-checkpoints/README.md`、
> `notes/current-re-progress-20260711.md`、`docs/sequel-roadmap.md` 和
> `notes/dynamic-verification-audit.md`。备用章节表 `0x60D54` 已于 2026-07-12 通过
> selector + 通用 dispatch 追踪闭合，`story-b` 已升为 `runtime_verified`。当前首要
> 门槛转为 maps 的剩余 resource-pointer 运行时语义；总目标仍未完成，Draft PR #1
> 保持 Draft，不合并。
>
> **状态更新（2026-07-11）**：本文下方的 2026-06-26 基线和“32 个生成器即可完成”
> 标准已经过期。当前权威交接、完成门槛和下一步请见
> `docs/reverse-engineering-handoff-20260711.md`；逐项证据见
> `notes/dynamic-verification-audit.md`。在别名冲突、真实消费链和安全回写未闭合前，
> 不得按旧清单宣称 100%。

## 当前状态（基线，2026-06-26 final-completion-report）

> 以下内容仅保留为历史上下文，不再用于排期或验收。

- **32 个结构**已有 `sequel/content/<name>/bank.json`
- **14/32** 有 `generate_*_patches()` 函数（缺 18 个）
- **`automated_test.py` 17/17 PASS**
- **最后一次 commit**: `90d58c9 Complete Phase 3`
- ROM: `/root/gba-naruto/build/naruto-sequel-dev.gba`（SHA-1: `26f60795fa5e63b4f0264b84e453beffd56b9f7d`）
- 测试运行: `python3 tests/automated_test.py`

**关键缺口**：18 个结构是占位状态（offset = "—"、verification = "static"），不算完成。

## 完成定义（必须全部满足才能 goal_complete）

对 **全部 32 个** 结构，每个都必须满足：

1. ✅ `bank.json` 有 **真实 offset**（不是 "—"）+ **真实 format** + **真实 entries 数**
2. ✅ **verification** 至少 `static_verified`，关键结构升级到 `code_verified` 或 `dynamic_verified`
3. ✅ `tools/build_db_patches.py` 有对应的 `generate_<name>_patches()` 函数
4. ✅ `tools/build_mod.py` 集成该函数
5. ✅ `automated_test.py` 仍 17/17 PASS（不能 regression）

**整体**：

6. ✅ 全部 32 个 patch 函数在 `python3 tools/build_mod.py` 跑通无 error
7. ✅ 每个结构的**字段语义**有 README/doc（不只是 byte layout）
8. ✅ 所有改动 commit 到 git
9. ✅ `docs/final-completion-report.md` 更新到反映 100% 状态
10. ✅ `tests/automated_test.py` 仍 17/17 PASS

## 18 个缺 generate_*_patches 的结构（必须补完）

```
battle-encounters       data-table-a        data-table-b
encounter-zones         fonts               function-pointers
map-events              map-sprites         palette-related entries
positions               resource-pointers   save-state
sappy-engine            story               story-b/c/d/e
text                    tile-assets         units-related extras
```

（具体清单以 `final-completion-report.md` 表为准，可能有差异。）

## 方法（参考 phase 1-3 的成功路径）

1. **静态分析**：用 Ghidra/IDA/objdump 看 ROM 的 ARM/Thumb 代码 + literal pool
   - 找指针表（u32 数组对齐到 4 字节）
   - 找数据表（按 entry_size × count 模式扫描）
   - 用 `xxd` / Python `struct` 提取 + 验证
2. **动态分析**：用 mGBA + Lua scripting trace runtime 行为
   - mGBA WASM 部署在 `https://sh.kibox.com.cn/gba-naruto/play/`
   - puppeteer 自动化：截屏 + 按键 + 验证画面变化
3. **交叉验证**：
   - bank.json → generate_*_patches → build_mod → apply patch → 启动 ROM → 视觉/逻辑验证
   - 不能只停在 "找到了" —— 必须 "应用 + 验证"

## 工作约束

- **不重定义目标**：不要把 "100%" 拆成 "phase 4 only"。要做完整套。
- **持续推进**：遇困难反思 → 改方法 → 再试；不要中途换目标。
- **保持测试绿**：每加一个 `generate_*_patches` 必须验证 `automated_test.py` 17/17。
- **commit 频繁**：每补完一个结构就 commit（commit message 要明确结构名）。
- **用现有工具**：不要重新发明 `tests/automated_test.py` / `build_mod.py` / `build_db_patches.py` —— 扩展它们。
- **别破坏部署**：mGBA WASM 在 `https://sh.kibox.com.cn/gba-naruto/play/` 是 public 的，别在测试时破坏它。

## 关键文件 / 上下文

- `/root/gba-naruto/docs/final-completion-report.md` — Phase 1-3 完成报告（含全部 32 结构表）
- `/root/gba-naruto/docs/phase3-final-status.md` — Phase 3 动态分析
- `/root/gba-naruto/sequel/content/` — 32 个 bank.json
- `/root/gba-naruto/tools/build_db_patches.py` — 14 个 generate_*_patches（参考模板）
- `/root/gba-naruto/tools/build_mod.py` — patch 集成器
- `/root/gba-naruto/tests/automated_test.py` — 17 个 sanity check
- `/root/gba-naruto/.ralph/*.md` — 历史 phase 进度 + 方法论

## 不要做的

- ❌ 不要停在 analysis / 写文档但没补 bank.json 缺口
- ❌ 不要写 TODO list 然后 goal_complete（必须真做）
- ❌ 不要拆 sub-goal（"先做 phase 4" — 这是逃避 100%）
- ❌ 不要 regression 已有 14 个 generate_*_patches
- ❌ 不要盲跑无限 token —— 用 `--tokens 500k` 预算但要规划（每个 structure ~15k token）

## 完成调用

```python
goal_complete(
  note="100% 逆向完成: 32/32 structures 有真实 offset/format/entries + verification + generate_*_patches。tests 17/17 PASS。commit + docs 更新。"
)
```

**调用前必须逐项审计**：每个 structure 5 项 + 整体 5 项都满足才能调。

## Token & 中断处理

- 启动时已用 `--tokens 500k`
- mimo 5h 限额到了时：人工会 `kill -STOP <pi-pid>`，限额过后 `kill -CONT`
- 详见 `.learnings/mimo-quota-handling.md`
- 你不需要操心限额——专心推进目标，限额时希妲会处理
