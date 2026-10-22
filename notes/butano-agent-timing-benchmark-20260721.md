# Butano Codex 单代理开发计时基准（2026-07-21）

## 运行身份

- run ID：`butano-agent-benchmark-20260721-01`
- 执行者：当前 Codex 主代理，内联，无子代理/外部模型
- 分支：`codex/butano-foundation-research`
- Butano：21.7.1，commit `112a1827c9c6d9e6041a7e93e66f04c4561a6415`
- devkitARM：`devkitpro/devkitarm@sha256:116afba8df8453961de2936ffab20dd441edf4d682856c1ec8b0e53d7ed0bbf5`
- 计时口径：写第一个失败测试前开始，相关绿测、重构复验和集成全部完成后结束；覆盖模型思考、编辑、命令和调试墙钟。
- 排除：不计逆向补证、内容生产、旧存档兼容和用户等待。

原始事件位于 `build/butano-agent-benchmark-20260721-01/B1.json` 至 `B6.json`。`build/` 为运行产物目录，因此本记录持久保存关键字段。

## 实测结果

| ID | UTC 开始 | UTC 结束 | 秒 | 事件数 | 结果 |
|---|---|---|---:|---:|---|
| B1 | 10:32:07.053418Z | 10:34:58.705363Z | 171.651955 | 3 | 行动状态机红绿重构通过 |
| B2 | 10:35:26.235841Z | 10:40:03.020387Z | 276.784552 | 4 | 寻路通过；记录一次测试宏编译返工 |
| B3 | 10:40:32.523955Z | 10:44:09.751959Z | 217.228009 | 3 | 事务效果链通过 |
| B4 | 10:44:51.544984Z | 10:49:47.611419Z | 296.066437 | 4 | 章节 VM 通过；记录一次测试宏编译返工 |
| B5 | 10:50:31.048085Z | 10:53:51.464453Z | 200.416729 | 3 | 版本化 CRC 双槽 codec 通过 |
| B6 | 10:54:20.616135Z | 11:04:18.905635Z | 598.289769 | 5 | 自检 ROM 干净构建通过；warning 触发未知 effect 回归修复 |
| **合计** | — | — | **1760.437451** | **22** | **29.34 分钟** |

## 红绿与返工证据

- B1–B5 的首个失败均为预期 header 不存在，证明测试先于实现。
- B2 和 B4 的第一次实现后编译暴露 `assert` 宏无法直接包含模板/initializer list 逗号；仅修正测试表达式括号后转绿。
- B6 的第一次集成测试因 Makefile、self-test symbol 和 `ALL PASS` 不存在而失败。
- B6 首次链接成功但 ARM 编译器报告两个 `-Wswitch-default` warning。新增未知 effect 枚举回归测试后观察到真实失败（exit 250），再加入 fail-closed 分支；最终干净 ROM 构建无 warning。

## 产物规模与验证

- C++ benchmark 内核、自检和测试：1262 行。
- 宿主机：五个 `test_*.cpp` 均以 `-std=c++23 -Wall -Wextra -Werror -pedantic` 编译并运行。
- GBA：`main.cpp` 与 `self_test.cpp` 在固定 devkitARM 镜像中干净交叉编译、链接和 gbafix。
- 集成断言：ROM title `KONOHA BASE`、game code `KNBT`、ELF 含 `run_self_tests` 与 `ALL PASS`。
- 自检 ROM 可见 B1–B5 PASS/FAIL、总结果和 `PRESS A`/`INPUT OK`；受 Homebrew Qt/Cocoa frontend 限制，未自动验证画面。

## 外推输入

- 中位逻辑样本：217.228009 秒（0.060341 小时）。
- 最慢逻辑样本：296.066437 秒（0.082241 小时）。
- 集成样本：598.289769 秒（0.166192 小时）。
- 全系统拆分：900 个逻辑单元、160 个集成单元。
- 乐观：80.9 Codex 连续墙钟小时。
- 基准：121.3 小时。
- 保守：191.2 小时。

完整逐系统输入、公式和日历换算见 `docs/butano-konoha-systems-cost.md`。

## 可复验命令

```sh
python3 tools/butano/run_cpp_benchmark_tests.py
python3 -m unittest tests.test_butano_benchmark_harness tests.test_butano_research_docs -v
RUN_BUTANO_INTEGRATION=1 python3 -m unittest tests.test_butano_build -v
python3 tools/butano/verify_setup.py
```

运行真实 mGBA 验收时必须继续使用 `tools/run_guarded.py` 的 heavy lock，不能为了得到画面而取消内存和超时保护。
