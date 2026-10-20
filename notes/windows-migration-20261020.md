# Windows 迁移落地记录（2026-10-20，新机接入）

**触发**：宿主 Mac 退役后在新 Windows 机器上执行「拉取更新」时，发现远端两条工作线
（`codex/reverse-engineering` / `codex/butano-foundation-research`）已在宿主退役前推送，
而本机检出环境是 macOS → Windows 的第一次迁移。

**关联**：
- 逆向树交接文档 `notes/handover-20261020-reverse-tree.md`（远端 `codex/reverse-engineering` 分支内）
- 分支地图与保留理由 `notes/repo-size-audit-20261019.md` §5
- 执行策略转向 `notes/why-external-editor-shipped-20261020.md`（本文件所在 `master` 线）

---

## 0. 一句话状态

**远端更新已全部落地并可验证**：两条工作线已检出为独立工作树，工作区字节与 git blob
逐字节一致（0 个跟踪文件被改写），交接文档 §2.1 钉死的三个 SHA-256（账本 / 审计器 /
spec）在本机复算全部吻合，交接文档 §7 的四组测试里 **3 组与文档预期完全一致**；
**剩余 1 组（D0）卡在 Windows 平台缺口，且卡点文件被 sha 钉死，不能直接改**。

---

## 1. 拉取结果

| 远端 ref | 状态 | 本机落地 |
| --- | --- | --- |
| `origin/master` | **无新提交**（仍是 `99fd5bc3`） | 本地 `master` = `99fd5bc3` + `e3b66263`（本次提交，策略转向） |
| `origin/codex/reverse-engineering` | `f054f4c1`（较上次 fetch 新增 3 个提交；相对基线 `43d7e159` 领先 **683**） | 本地分支 + 工作树 `D:\Shell\Github\gba-naruto-reverse` |
| `origin/codex/butano-foundation-research` | `b78e3f74`（新增 3 个；领先基线 **525**） | 本地分支 + 工作树 `D:\Shell\Github\gba-naruto-butano` |
| `origin/task/units-character-definitions` | 无变化（`6e129bed`） | 本地已有，无需动作 |
| `origin/gh-pages` | 新增远端分支 | 与本项目工作无关，未落地 |

### 1.1 为什么不把两条 codex 分支合进 master

`notes/repo-size-audit-20261019.md` §5.2 已把分支策略写死：`master` 是**收敛快照**
（GitHub 默认分支与公开门面），`codex/butano-foundation-research` 是 10 月重制线的唯一
真源，`codex/reverse-engineering` 是逆向证据（24 个 artifact 家族 + 143 个提交）的唯一
存放处，**三者刻意不合并**。本次只做「落地 + 验真」，没有做 merge。

### 1.2 本机工作树布局

```
D:\Shell\Github\gba-naruto            -> master（e3b66263）        规划/决策线（第三方编辑器复盘 + 策略转向）
D:\Shell\Github\gba-naruto-butano     -> codex/butano-foundation-research  Butano 重制线
D:\Shell\Github\gba-naruto-reverse    -> codex/reverse-engineering        逆向证据线
```

注：`D:\Github\gba-naruto` 是 `D:\Shell\Github\gba-naruto` 的目录联接（junction），同一份仓库。

---

## 2. Windows 平台缺口（5 项，前 4 项已修，第 5 项待决策）

### 2.1 换行符转换击穿全部 SHA-256 钉死 ★最高危

**现象**：本机 `core.autocrlf=true`（系统级 + 用户级 `~/.gitconfig` 都有），
macOS 上以 LF 提交的 blob 在 Windows 检出时被转成 CRLF，**工作区字节 ≠ blob 字节**。

**证据**（逆向树，工作区文件 vs `git cat-file blob`）：

| 文件 | 工作区 sha256 | blob sha256 | 交接文档钉死值 |
| --- | --- | --- | --- |
| `sequel/rom-byte-coverage.json` | `f80bf327…`（CR=795651） | `d34672a8…`（CR=0） | `d34672a8…` ✔ |
| `tools/audit_rom_byte_coverage.py` | `ea5b8b50…` | `ea5b8b50…` | `ea5b8b50…` ✔ |
| `sequel/reverse-engineering-proof.json` | `f06e9ef5…`（CR=5355） | `754042fe…`（CR=0） | `754042fe…` ✔ |

本仓库的证据链把「文件内容的 SHA-256」当身份（`evidence_sha256` /
`promotion_manifest_sha256` / `independent_verifier_sha256` / 账本摘要），
换行符一变，**所有钉死同时失效**，且 `git status` 不会报脏（stat 缓存命中 ⇒ 误判为干净）。

**修法**（仓库级 `.git/config`，三工作树共用）：

```powershell
git config core.autocrlf false
git config core.eol lf
# 关键：必须让 git 重建索引并强制重写工作区，否则 stat 缓存会让它跳过重写
foreach ($w in @('D:\Shell\Github\gba-naruto','D:\Shell\Github\gba-naruto-butano','D:\Shell\Github\gba-naruto-reverse')) {
  git -C $w read-tree HEAD
  git -C $w checkout-index -a -f
}
```

**踩坑记录**：`git reset --hard` / `git checkout-index -f` / `git checkout HEAD -- <file>`
**都不生效**——索引里的 stat 缓存让 git 判定「文件已是最新」而跳过写入；
只有 `read-tree HEAD` 清掉 stat 缓存后才真正重写。验真后三工作树
`git status` 的「跟踪文件被改写」计数均为 **0**。

### 2.2 vendored capstone 是 macOS 轮子

`tools/_vendor/capstone/` 是 pip 轮子内容，**只带 `lib/libcapstone.dylib`**；
加载器在 win32 上找的是 `capstone.dll` ⇒ `ImportError: fail to load the dynamic library`，
审计器 `tools/audit_rom_byte_coverage.py` 的 import 链因此整条断掉。

**修法（不改任何被钉死的文件）**：加载器第一个尝试就是 `os.getenv('LIBCAPSTONE_PATH')`，
而 `tools/_vendor/capstone/__init__.py` **本身被 contract 钉死**
（`tools/data/rom-display-text-delta-contract-v1.json` 等），所以只能走环境变量：

```powershell
[Environment]::SetEnvironmentVariable('LIBCAPSTONE_PATH',
  'D:\Shell\Github\gba-naruto\build\python-deps\capstone\capstone\lib', 'User')
```

（`capstone.dll` 7,572,480 B，capstone 5.0.7，与 vendored `dist-info` 同版本。）

### 2.3 Windows 没有 `python3` 可执行名

多个 verifier / exporter 用 `subprocess.run(["python3", …])` 调子进程
（`tools/verify_rom_cgbsound_bounded_cfg.py` 等）。Windows 只有 `python.exe`，
子进程直接 `FileNotFoundError` 死掉，**掩盖了真正的失败原因**：
第 4 组测试在本机一度报「红 24 项」，实际是 24 项全部死于找不到 `python3`。

**修法**：`build/bin/python3.exe`（3.14.4 `python.exe` 的副本，CPython 3.11+ 经注册表
定位 base_prefix，副本可独立运行）+ 用户级 PATH 追加 `build\bin`：

```powershell
[Environment]::SetEnvironmentVariable('PATH',
  ([Environment]::GetEnvironmentVariable('PATH','User').TrimEnd(';') + ';D:\Shell\Github\gba-naruto\build\bin'), 'User')
```

修完第 4 组立刻回到交接文档写的「红 23 项」，根因也回到文档描述的
「以整账本 SHA 做身份」。

### 2.4 新检出的合同恢复工具是 POSIX-only

`docs/rom-verifier-checkout-setup.md` 要求新检出先跑
`python3 tools/prepare_rom_verifier_contracts.py --restore`，
但该工具用 `os.O_DIRECTORY` / `dir_fd=` 锚定路径，Windows 上直接
`AttributeError: module 'os' has no attribute 'O_DIRECTORY'`。
它恢复的三份合同（`build/experiments/active/*-contract/codex-r1-20260829/CONTRACT.json`）
**从未进过 git**（`git log --all` 查无此路径），只存在于退役 Mac 的工作区。

**修法**：新增 `tools/prepare_rom_verifier_contracts_win.py`（Windows 版孪生工具，
同契约同报告 schema，**不修改原工具**）。恢复后三份合同与钉死值逐字节一致：

| 合同 | size | sha256 |
| --- | --- | --- |
| cgbsound | 11410 | `12171aa29cd29d14f26dc491e4b0a5bb8ddd3fe6d6daac9f73e732786194561a` |
| cgb-helper | 8694 | `e1f4d0b840d52b19ee996ee7c0ba18c41511f0c96b37f498f77954a24c9105b7` |
| mp2k-dispatcher | 7761 | `936f4fd2200a4ac6cbdc5641880f46585ed5722493cd6a4912632042058e154d` |

### 2.5 仍未解决：D0 验证器链是 POSIX-only，且关键文件被钉死

`tests.test_data_table_b_partial_bank` 本机红 **24 项**，根因统一是
`AttributeError: module 'os' has no attribute 'O_DIRECTORY'`，发生在：

- `tools/verify_data_table_b_partial_bank.py`
- `tools/rom_small_cfg_callback_gaps_independent_verifier.py` ← **被 D0 契约 v2 钉死**
  （`tools/data/data-table-b-partial-bank-contract-v2.json:25`，`c6244e7f…`）
- `tools/verify_data_table_b_message0_pointer_ab.py` ← **被 D0 契约 v2 钉死**
  （同文件 `:28`，`a834781e…`）

**不能直接改**：交接文档 §4.2 明写「期间不要动被 pin 的文件」，
且 D0 离线重放的整个设计就是「冻结 provenance」。
仓库级范围：`tools/` 下共 **47 个文件**使用 `os.O_DIRECTORY` / `dir_fd=` 这类 POSIX 原语。

**可选路径（需用户决策，未实施）**：
1. **兼容层**：在解释器启动时给 `os` 补 `O_DIRECTORY`/`O_NOFOLLOW` 与支持 `dir_fd` 的
   `os.open` 包装（需同时解决 formal 的 `python -I -S` 子进程拿不到 sitecustomize 的问题）；
2. **Windows 孪生工具**：为这 3 个模块各写一个 Windows 版，**但 D0 契约钉的是路径**，
   孪生文件不满足契约，契约本身要改 ⇒ 会破坏 D0 离线重放身份；
3. **重活回 POSIX 宿主**：账本重建 / formal / D0 采集继续放在 macOS/Linux 上跑，
   Windows 只做编辑器与轻量校验。

---

## 3. 验真结果（对照交接文档 §7「新机器上的第一组命令」）

环境：Python **3.14.4**（文档要求 ≥3.10 ✔）、`rom/base.gba` 6,291,456 B /
sha `1198ece7…` ✔、归档 checkpoint
`artifacts/runtime-checkpoints/scenario-50-action7-shadow-clone-confirmation.ss9`（98,443 B）✔。

| 组 | 文档预期 | 本机实测 | 结论 |
| --- | --- | --- | --- |
| 1 `test_audit_reverse_engineering_coverage_count_liveness` | 12 项全绿 | **12 绿** | ✔ 一致 |
| 2 `test_data_table_b_partial_bank` | 14 项全绿 | **红 24 项**（`O_DIRECTORY`） | ✘ §2.5 平台缺口 |
| 3 `test_build_battle_message_runtime_probe_slots` | 8 项全绿 | **8 绿** | ✔ 一致 |
| 4 四个导出器模块 | 红 23 项（已知回归） | **33 项中红 23**（3 failures + 20 errors） | ✔ 精确一致 |

第 4 组根因与文档一致：`source artifact identity mismatch` /
`coverage identity changed` ⇒ 交接文档 §4.2 要修的那条「以整账本 SHA 做身份」。

**注意**：第 2 组在 macOS 上是 14/14 绿，本机红 24 项**不是**文档里的已知回归，
而是 Windows 平台缺口（§2.5）；两者不要混淆。

---

## 4. 仍未闭合的工作（交接文档 §4，按原顺序）

1. **§4.1 整模块补跑绿**：宿主退役时 4 个分片各跑到 1/7/7/6 个用例（0 失败），
   新机应重跑，预计 1.5–2 h。
2. **§4.2 ④ purelib + ③ psg 链时身份 + 4 个红导出器**：一次改完，只跑一次账本重建 + 一次 formal。
   落地顺序（否则导出器拒绝覆盖）：先移走旧 artifact 目录 → 改脚本 → 重新落地 5 个 artifact
   → 更新 audit pin → 受管重建账本 → 同步 spec → 一次 formal。
3. **§4.3 ② D0 续作（79 个消息状态采集）**：需要 **Windows 版 mGBA（Qt，源码 commit d8bad14b）**，
   本机不存在（旧构建是 macOS dylib）。重建后二进制 sha 会变，
   `tools/macos_mgba_toolchain_profile.py` 的 `CURRENT_TOOLCHAIN_PROFILE_SHA256` /
   `CURRENT_MGBA_SOURCE_COMMIT` 需同步。**这是当前 D0 续作的硬前置。**
4. 三道用户裁决（② 探针续作 / ③ psg 链时身份 / ④ purelib 加固）的代码改动**尚未执行**；
   ③ ④ 会改被 pin 的脚本，**必须一次做完、只跑一次账本重建与一次 formal**。
5. `codex/butano-foundation-research` 的 `b78e3f74` 是 **WIP 快照不是已验收里程碑**：
   691 个文件未做全量构建/测试验收；其中
   `artifacts/macos-mgba-20261019-v1/manifest.json` 记录的二进制摘要与旧记录不同（重建后的新值）。

---

## 5. 本机可复现命令

```powershell
# 环境变量（新开的终端自动生效；本工具进程继承旧环境，需手动 set）
$env:LIBCAPSTONE_PATH = 'D:\Shell\Github\gba-naruto\build\python-deps\capstone\capstone\lib'
$env:PATH = 'D:\Shell\Github\gba-naruto\build\bin;' + $env:PATH

cd D:\Shell\Github\gba-naruto-reverse
python -m unittest tests.test_audit_reverse_engineering_coverage_count_liveness `
                     tests.test_data_table_b_partial_bank `
                     tests.test_build_battle_message_runtime_probe_slots
```

新检出必做的合同恢复（Windows）：

```powershell
python tools/prepare_rom_verifier_contracts_win.py --restore
python tools/prepare_rom_verifier_contracts_win.py   # 只检查
```

字节一致性自检（本文件配套脚本 `tools/eol_probe.py`）：

```powershell
python tools/eol_probe.py D:\Shell\Github\gba-naruto-reverse sequel/rom-byte-coverage.json
```

---

## 6. 本次留下的仓库内产物

- `tools/prepare_rom_verifier_contracts_win.py`（逆向树 `codex/reverse-engineering`）：
  Windows 版合同恢复工具，新增文件，**未改动任何被 pin 的文件**。
- `tools/eol_probe.py`（本 `master` 线）：工作区字节 vs blob 字节的逐文件比对探针，
  用来在任何机器上复验 §2.1 的换行符击穿问题。
- 本文件 + `docs/sequel-roadmap.md` 的平台约束条目（`master` 线）。
