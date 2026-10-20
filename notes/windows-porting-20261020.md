# Windows 迁移：逆向工具链的平台缺口（2026-10-20）

**背景**：宿主 Mac 退役，新机为 Windows。本文件记录 `codex/reverse-engineering` 分支
（逆向树）在新机上落地时，**工具链本身**遇到的平台缺口、已应用的修法与验真结果。
机器级全景（分支拓扑、工作树布局、两条工作线的落地）见主树 master 线的
`notes/windows-migration-20261020.md`。

**关联**：`notes/handover-20261020-reverse-tree.md`（§5 平台迁移须知、§7 新机第一组命令）、
`docs/rom-verifier-checkout-setup.md`（新检出的合同恢复流程）、
`tools/data/data-table-b-partial-bank-contract-v2.json`（D0 契约 v2 的钉死清单）。

---

## 0. 一句话状态

**新机环境已可用，且与交接文档的基线一致**：
交接文档 §2.1 钉死的三个 SHA-256（账本 / 审计器 / spec）本机复算吻合；
§7 的四组测试里三组与文档预期完全一致，第四组精确复现文档写的 23 项已知红。
**唯一未对齐的是 D0 一组**：卡在 Windows 缺 POSIX 文件系统原语，
而**卡点文件被 D0 契约 sha 钉死，不能直接改** ⇒ 需要一次决策。

---

## 1. 缺口清单

### 1.1 `core.autocrlf=true` 击穿全部 sha 钉死（最高危，已修）

macOS 上以 LF 提交的文件在 Windows 检出时被转成 CRLF，**工作区字节 ≠ blob 字节**。
本仓库把文件内容的 SHA-256 当证据身份（`evidence_sha256` /
`promotion_manifest_sha256` / `independent_verifier_sha256` / 账本摘要），
换行符一变，全部钉死同时失效，**而 `git status` 不会报脏**（索引 stat 缓存命中 ⇒ 误判干净）。

实测（修前）：

| 文件 | 工作区 sha256 | blob sha256 | 文档钉死值 |
| --- | --- | --- | --- |
| `sequel/rom-byte-coverage.json` | `f80bf327…`（CR=795651） | `d34672a8…`（CR=0） | `d34672a8…` |
| `sequel/reverse-engineering-proof.json` | `f06e9ef5…`（CR=5355） | `754042fe…`（CR=0） | `754042fe…` |

**修法**：仓库级 `.git/config` 设 `core.autocrlf=false` + `core.eol=lf`，
再 `git read-tree HEAD` 清 stat 缓存 + `git checkout-index -a -f` 强制重写。
**注意**：`git reset --hard` / `git checkout-index -f` / `git checkout HEAD -- <file>`
单用都**不会**重写（stat 缓存让 git 判定「已最新」），必须先 `read-tree`。

### 1.2 vendored capstone 只有 macOS dylib（已修）

`tools/_vendor/capstone/` 是 pip 轮子内容，只带 `lib/libcapstone.dylib`；
加载器在 win32 上找 `capstone.dll` ⇒ 审计器 import 链整条断掉。
该包内文件**被 contract 钉死**，不能改 ⇒ 走加载器自带的 `LIBCAPSTONE_PATH`：

```powershell
[Environment]::SetEnvironmentVariable('LIBCAPSTONE_PATH',
  'D:\Shell\Github\gba-naruto\build\python-deps\capstone\capstone\lib', 'User')
```

（`capstone.dll` 7,572,480 B，capstone 5.0.7，与 vendored `dist-info` 同版本。）

### 1.3 Windows 没有 `python3` 可执行名（已修）

多个 verifier/exporter 用 `subprocess.run(["python3", …])` 调子进程。
本机只有 `python.exe` ⇒ 子进程直接 `FileNotFoundError` 死掉，
**掩盖了真正的失败原因**（第 4 组一度报「红 24 项」，实为 24 项全死于找不到 `python3`）。

修法：`build/bin/python3.exe`（3.14.4 `python.exe` 的副本；CPython 3.11+ 经注册表
定位 base_prefix，副本可独立运行）+ 用户级 PATH 追加 `build\bin`。
修完第 4 组立即回到文档写的 **23 项**，根因也回到文档描述的「以整账本 SHA 做身份」。

### 1.4 新检出的合同恢复工具是 POSIX-only（已修）

`docs/rom-verifier-checkout-setup.md` 要求新检出先跑
`python3 tools/prepare_rom_verifier_contracts.py --restore`，
但该工具用 `os.O_DIRECTORY` / `dir_fd=` 锚定路径，Windows 上直接
`AttributeError: module 'os' has no attribute 'O_DIRECTORY'`。
它恢复的三份合同**从未进过 git**（`git log --all` 查无此路径），
只存在于退役 Mac 的工作区 ⇒ 缺失时审计器无法 import。

修法：新增 `tools/prepare_rom_verifier_contracts_win.py`（同契约、同报告 schema、
**不修改原工具**）。恢复后与钉死值逐字节一致：

| 合同 | size | sha256 |
| --- | --- | --- |
| cgbsound | 11410 | `12171aa29cd29d14f26dc491e4b0a5bb8ddd3fe6d6daac9f73e732786194561a` |
| cgb-helper | 8694 | `e1f4d0b840d52b19ee996ee7c0ba18c41511f0c96b37f498f77954a24c9105b7` |
| mp2k-dispatcher | 7761 | `936f4fd2200a4ac6cbdc5641880f46585ed5722493cd6a4912632042058e154d` |

### 1.5 D0 验证器链仍是 POSIX-only，且关键文件被钉死（**未解，待决策**）

`tests.test_data_table_b_partial_bank` 本机红 **24 项**，根因统一为
`AttributeError: module 'os' has no attribute 'O_DIRECTORY'`，发生在：

- `tools/verify_data_table_b_partial_bank.py`
- `tools/rom_small_cfg_callback_gaps_independent_verifier.py` ← **被 D0 契约 v2 钉死**
  （`tools/data/data-table-b-partial-bank-contract-v2.json:25`，`c6244e7f…`）
- `tools/verify_data_table_b_message0_pointer_ab.py` ← **被 D0 契约 v2 钉死**
  （同文件 `:28`，`a834781e…`）

**不能直接改**：交接文档 §4.2 明写「期间不要动被 pin 的文件」，
且 D0 离线重放的设计前提就是「冻结 provenance」。
仓库级范围：`tools/` 下共 **47 个文件**使用 `os.O_DIRECTORY` / `dir_fd=`。

**三条候选路径（需决策，未实施）**：

1. **兼容层**：解释器启动时给 `os` 补 `O_DIRECTORY`/`O_NOFOLLOW` 与支持 `dir_fd` 的
   `os.open` 包装；难点是 formal 的子进程用 `python -I -S`，
   `sitecustomize` 在 `-S` 下根本不加载 ⇒ 兼容层要能被子进程继承。
2. **Windows 孪生工具**：为这 3 个模块各写 Windows 版；
   但 D0 契约钉的是**路径与 sha**，孪生文件不满足契约 ⇒ 契约要改 ⇒ 破坏 D0 离线重放身份。
3. **重活回 POSIX 宿主**：账本重建 / formal / D0 采集继续放 macOS/Linux，
   Windows 只承担编辑器与轻量校验。

---

## 2. 验真矩阵（对照交接文档 §7）

环境：Windows 11 / Python **3.14.4**（文档要求 ≥3.10 ✔）/
`rom/base.gba` 6,291,456 B sha `1198ece7…` ✔ /
归档 checkpoint `artifacts/runtime-checkpoints/scenario-50-action7-shadow-clone-confirmation.ss9`（98,443 B）✔。

| 组 | 文档预期 | 本机实测 | 结论 |
| --- | --- | --- | --- |
| 1 `test_audit_reverse_engineering_coverage_count_liveness` | 12 绿 | **12 绿** | ✔ |
| 2 `test_data_table_b_partial_bank` | 14 绿 | **红 24 项**（`O_DIRECTORY`） | ✘ §1.5 |
| 3 `test_build_battle_message_runtime_probe_slots` | 8 绿 | **8 绿** | ✔ |
| 4 四个导出器模块 | 红 23 项 | **33 项中红 23**（3 failures + 20 errors） | ✔ 精确一致 |

第 4 组根因与文档一致：`source artifact identity mismatch` / `coverage identity changed`
⇒ 即交接文档 §4.2 要修的「以整账本 SHA 做身份」。
**注意**：第 2 组在 macOS 上是 14/14 绿，本机红 24 项**不是**文档里的已知回归，
而是平台缺口；两者不要混淆。

---

## 3. 仍然卡住 D0 续作的另一件事

交接文档 §4.3 的 ② D0 续作（79 个消息状态采集）需要 **Windows 版 mGBA**：
旧构建是 macOS dylib，本机不存在；必须按同一源码 commit `d8bad14b` 重建 Qt 版，
且重建后二进制 sha 会变 ⇒ `tools/macos_mgba_toolchain_profile.py` 的
`CURRENT_TOOLCHAIN_PROFILE_SHA256` / `CURRENT_MGBA_SOURCE_COMMIT` 必须重新声明，
**不得沿用 macOS 的二进制 sha**。

---

## 4. 本次留下的产物

- `tools/prepare_rom_verifier_contracts_win.py`：Windows 版合同恢复工具（新增文件）。
- `notes/windows-porting-20261020.md`：本文件。
- `AGENTS.md` 任务模式登记表新增一行「跨平台迁移后的新检出初始化与字节级身份复验」。
