# 接线点全量枚举：两侧盘点与九态矩阵（2026-10-22）

日期：2026-10-22
工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）
逆向树 `/Users/altair/github/gba-naruto-reverse`，commit `821d0937e058245aa7e6d29f23f96c7fc78e7375`

配套：`notes/butano-usable-backlog-20261022.md`（存量分诊）、`docs/butano-reverse-gap-roadmap.md`、
`docs/butano-wiring-roadmap.md`（执行路线图）

## 0. 结论

**「查明所有接线」的办法是把两端都枚举出来，并且把「声明」的两套载体都读出来。**

| 状态 | 族数 | 含义 |
| --- | ---: | --- |
| `imported-and-gated` | **54** | ROM 导入器钉了 manifest 哈希、文件已复制进复刻树、且有测试门禁 |
| `wired-and-gated` | **12** | provenance 头注释载体声明了它，且有测试门禁 |
| `verified-against` | 1 | 只被 `verify_*` 当**证据**核对，复刻侧不消费其 payload |
| `local-derivation-missing` | **26** | 复刻侧有 exporter（用族名做 schema 标识），但**本地产物不在工作树里** |
| `on-shelf` | **71** | 已闭合且带 payload，**无人接**（资产直取 30 + 一次生成器 41） |
| `unclassified` | 12 | 在货架上但分层判不出来，要人读 |
| `not-importable` | 51 | 控制流／覆盖分母／审计证据——约束行为，不是素材 |
| `no-material` | 37 | 既没接、也没材料 |

⇒ **带声明的接线共 66 族，而且 66 族全部有门禁**（54 导入器 + 12 provenance）。
**真正的缺口收敛成三块**：26 族本地产物缺失、71 族无人接、sink 侧无声明载体。

## 1. 接线点的定义与两侧枚举

**接线点 = （逆向族, 复刻产物）二元组。** 查全的前提是两端都枚举：

| 端 | 枚举方式 | 工具 |
| --- | --- | --- |
| source | index 里 `kind == "artifact"` 的全部族 | `tools/build_reverse_results_index.py` |
| sink | 生成器声明的 `GENERATED_PRODUCTS` + 载体里的 `reverse-source` 声明 | `tools/audit_butano_reverse_provenance.py` |

**只看一端就会漏**：只看 sink 看不见「有源没人接」；只看 source 看不见「产物没有来源声明」。

### 1.1 ⚠️ 声明有**两套载体**，只读一套会低估接线

本轮第一版工具只读 provenance 头注释载体，得出「**只有 12 族有声明的接线**」。
**这个结论是错的**，第 2 节的更正记录留着证据。

实际上还有第二套载体：两个 ROM 导入器
（`tools/butano/import_rom_pixel_ab_baselines.py`、`tools/butano/import_rom_relocation_specs.py`）
用**自己的合同**绑族——`FamilySpec(family, manifest_sha256)`，
运行期回查 manifest、逐文件重算哈希、把文件复制进复刻树。
**54 族走的是这条载体**（32 个 pixel-A/B 基准 + 22 个 relocation/writeback），
产物就在 `artifacts/butano-reverse-m3-import-v1/{pixel-ab,relocation}/` 下，
而且 `tests/test_rom_pixel_ab_baseline_import.py` 与
`tests/test_rom_relocation_spec_import.py` **给这两个导入器做了门禁**。

⇒ **「接线登记表」不是一套，是一个家族至少两套载体；审计器只覆盖了其中一套。**

## 2. 本轮的两处自我更正（留档）

1. **「只有 12 族有声明的接线」⇒ 错。** 漏了导入器载体。实际 **66 族**。
   证法：`import_rom_*` 的 `*_FAMILIES` 常量里逐族钉了 manifest SHA-256，
   且 `artifacts/butano-reverse-m3-import-v1/` 下确实有 32 + 22 个族的产物副本。
2. **「81 族只是提到名字」⇒ 也不准确。** 81 里的 54 是真接线（导入器载体），
   22 是 `verify_*` 当证据核对，5 是待判裸引用。
   而剩下 26 族的真实性质是**第四种状态**：复刻侧有 exporter 用族名做 schema 标识、
   本该写进本树 `artifacts/<family>/`，但**那份本地产物不在工作树里**
   （2026-10-19 那次 artifacts 清理带走的，见
   `notes/s49-fidelity-handover-20261019.md` §1）。它们的 manifest 本地与逆向树
   **一个都没有**，所以既不是「接了」也不是「重导出了」。

> **教训**：「声明」这件事**先要问有几套载体**，再问有没有。
> 一个测量器漏读一套载体，报出来的数字会差 **54 族**（26%）。
> 抽查时**必须按「引用方式」而不是按「有没有被引用」分类**——
> 名字出现的地方，可能是导入器的钉哈希、可能是 verifier 的证据核对、
> 可能是 exporter 的 schema 标识，三者的接线含义完全不同。

## 3. sink 侧盘点

| 面 | 数量 | 有接线声明载体吗 |
| --- | ---: | --- |
| 生成器产物（`generated_*.h`） | 27 | ✅ 已登记（38 个声明产物：24 绑定族 + 14 声明「不消费逆向结果」+理由） |
| 手写头（`konoha/*.h`，非 generated） | 110 | ❌ 无载体 |
| 内容库（`sequel/content/*/bank.json`） | 34 | ❌ 无载体 |
| 图形资产（`butano-sequel/graphics/`） | 1819 | ❌ 无载体 |
| 运行时源码（`game/src/*.cpp`） | 4 | ❌ 无载体 |
| 门禁（`tests/test_*.py`） | 372 | — |

现有的声明载体只有一种：C++ 头注释
（`// reverse-source: <family> @ <manifest-sha256>` / `// reverse-source-rom: 0x…` / `none`）。
**导入器是第二套载体，但它的声明不在产物里**——钉在导入器源码的常量里。

> ⚠️ **粒度提醒**：1819 个图形资产逐个声明不现实。
> `GENERATED_PRODUCTS` 的设计意图就是**按生成器登记**，不按文件。

## 4. 边界声明

- 「有门禁」是**上界**：测试提到产物路径或导入其生成器模块都算，但可能只是文档类测试。
- sink 侧的未登记面**只是盘点**，不是缺陷判定——手写头与内容库本来就不消费逆向族 payload。
- 本工具**不判定「该接哪个族」**：那是按子系统的设计决定，不是脚本能读出来的事实。
- 全部读数由脚本从当次三份收据重算（索引 / 差异清单 / 货架），
  **逆向树一变就变**，不得写死。

## 5. 复现

```bash
/usr/local/bin/python3 tools/measure_butano_wiring_coverage.py \
    --root . \
    --backlog artifacts/butano-usable-backlog-v1/backlog.json \
    --gap artifacts/butano-reverse-gap-v1/gap.json \
    --index artifacts/reverse-results-index-v1/index.json \
    --reverse-root /Users/altair/github/gba-naruto-reverse \
    --out-dir artifacts/butano-wiring-coverage-v1
```

收据：`artifacts/butano-wiring-coverage-v1/{wiring.json,wiring.md}`
门禁：`tests/test_measure_butano_wiring_coverage.py`（9 项全绿）

> ⚠️ **自指坑（第二例）**：这份收据同样**逐族点名**了 264 个族，
> 落在 `artifacts/` 扫描根下会让差异清单把它当成引用 ⇒ 读数漂移。
> 已加进 `measure_butano_reverse_gap.py` 的 `EXCLUDED_PREFIXES`，
> 修复后**连跑三次读数逐字节一致**（`sha=488144c5a781…`）。
> **每多一份逐族枚举的收据，就必须同步扩一次排除表。**
