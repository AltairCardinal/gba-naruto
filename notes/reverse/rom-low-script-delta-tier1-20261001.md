# 低地址固定消费者：两条脚本记录的 Tier-1 增量验收

后续已由[受管合并包](rom-renderer-records-delta-tier1-20261001.md)重新从raw输入验收并取代。
原包保持历史身份，不用于新注册或再次生成；新包29records/1,668B包含原两条12B记录，未Tier-2。

后续审计补正（2026-10-01）：静态合同、TDD与原始CLI证据有效，但直接生成artifacts违反
逆向工作树的受管final/promote要求。正式发布门未满足，当前仅作静态验证候选，不计入
可接入Tier-2队列；后续须新版本/包装补正，保留原artifact、源码哈希与收据。
以下“正式Tier-1”字样为上一轮当时报告，已由本补正取代。

状态：`artifacts/rom-low-script-delta-v1/` 独立验证通过，两条记录、12B、2 claims。
这是正式静态合同包，**尚未接入 canonical / Tier-2**；未知仍87,631B，175项全局阻塞
未移除。原预检中的accepted0仅描述当时状态，本记录是后续验收结果。

## 模式、复用与边界

按AGENTS登记的“公开合同闭合的小型冻结逆向工作包”处理，执行方式为可复现脚本。
输入ROM、v2/v3 CFG、六个literal/解释器参数流、旧命令语法与输出边界均已冻结。

1. 可直接复用现有renderer exporter参数流、training parser、安全no-replace发布，以及
   renderer verifier的独立参数流/parser和CFG验真，不增加opcode或新调度器模型。
2. 不抽取改写旧实现：已有artifact和历史收据固定它们的源码哈希；本包绑定这些哈希，
   每次重放先验真，避免缓存绕过身份检查。
3. 追加到已有固定消费者分类链，新增delta artifact和覆盖率adapter，不改旧41site包。
4. 单独保存artifact的技术原因是旧消费分母和1124B manifest不可变；维护者仍使用同类
   export/verify入口，并能独立回放新旧证据，无需覆盖历史验收结果。

## 固定分母与接受范围

扫描全部已验证v2/v3 Thumb block的PC-relative literal，目标范围固定为
578C..7554、42AB..542E、CEA..12F0。重新枚举六个site，不用候选列表代替扫描。
每site重放到67158的参数流，固定site/target/callsite/path-byte哈希向量。
六个源点另用Capstone按原block解码验证指令边界；全ROM消费者不作穷尽声明。

| 消费点 | root | 结论 |
| --- | --- | --- |
| 79A8A、79B1C | 42B5 | 接受42B5..42BD，8B，opcodes1,0 |
| 79AD8、79B2E | 42BD | unsupported opcode2，排除 |
| 79AEC、79B42 | 42C2 | 接受42C2..42C6，4B，opcodes3,4,0 |

producer使用training parser，verifier使用独立renderer parser；后者不导入本包producer。
两者共享的是冻结合同常量和旧输入身份，分别重建消费者和记录。
42AB..42B5前缀、42BD..42C2间隙、42C6之后，以及其他两个研究池均不产生新claims。
不声明自然执行、任务恢复不变量、可编辑性、回写或重定位安全。

## TDD、发布与覆盖率消费

- 红：正式exporter不存在时真实测试因ModuleNotFoundError失败；守卫exit1，非降级。
  首次详细错误来自工具输出，收据明确标为observation，未伪装成原始log。
- 绿：首轮6测试中5通过；真实CLI集成暴露manifest缺少verifier exit_code。
  改为candidate独立重建成功后生成accepted清单、再次验真、no-replace发布并复验。
- 第二红：覆盖率adapter未实现，真实测试因AttributeError失败，保存原始log。
- 最小实现后7/7通过；清理发布流程并补充对抗回归后8/8通过。
  覆盖literal/sink/记录/终止符变异、额外site、自洽hash篡改、额外成员、防覆盖、symlink、
  cached CFG身份漂移、真实CLI与标准promotion manifest集成。
- adapter先验证accepted包，再检查coverage segments连续、无重叠且全ROM分母完整。
  两个claim只能落入unknown；任何已分类交集或缺失区间均拒绝。

真实CLI入口：

```sh
python3 tools/export_rom_low_script_delta.py --root . --output artifacts/rom-low-script-delta-v1
python3 tools/verify_rom_low_script_delta.py --root . --artifact artifacts/rom-low-script-delta-v1
```

生产重放仍须包在`tools/run_guarded.py`并使用`build/experiments/heavy.lock`。
第一条现已执行；重复执行会拒绝覆盖。第二条返回verified=true、errors=[]、12B。
这是离线工具，没有游戏页面或加载UI；成功通过exit0和JSON反馈，输入身份/范围/成员
错误返回拒绝，缺ROM/CFG不生成已接受输出，没有自动修复或权限升级路径。

语法/空白检查通过；没有配置额外Python formatter。没有运行mGBA：本包不声称运行时
行为。未运行全量formal/coverage：尚未达到4包/10KiB/0.15个百分点集中验收门槛。
旧canonical哈希b568db6f…cf06d2保持不变，没有更新proof或提交/push。

## 收据与恢复点

永久收据：`notes/evidence/rom-low-script-delta-tier1-20261001-v1/`。
管理run：`build/experiments/active/low-script-delta/tier1-20261001-v1/`。
输入绑定ROM SHA1198ece7…59d05b、artifact/源码/test哈希、旧CFG/语法helper身份；
收据保存红绿日志、失败尝试、守卫结果和精确coverage投影，不能以单包static gate替代formal。

下一步不应反复重验这个已通过的小包。当前待Tier-2只有1包/12B，后续应优先补齐其他
固定消费者或解释器消费合同，再集中接入。7/8的125B候选仍受完整handler/context合同
约束；opcode2/6记录、computed roots和其他13,637B研究区保持未接受。

## 可执行验收

- [ ] 运行verify CLI → verified=true、record_count2、promotion_bytes12。
- [ ] 查看payload → 六site、四accepted site、42BD仍在excluded_roots。
- [ ] 查看projection收据 → 仅42B5..42BD、42C2..42C6，canonical_changed=false。
- [ ] 重放8测试 → 防覆盖/额外成员/自洽篡改/漂移输入均被拒绝。
- [ ] 查看canonical → unknown87,631B，未把Tier-1收益计入正式完成度。
