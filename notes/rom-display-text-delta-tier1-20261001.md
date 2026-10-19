# 固定 CFG 显示文本增量：受管 Tier-1 验收

## 结果与用户入口

92个固定调用点经六组已验真CFG、指令边界及独立raw参数流绑定，形成85条显示文本记录、
1,053B/85claims。实际受管final已通过独立重建、双重稳定报告和当前unknown投影。
这是直接66758/667A0→6626C的显示文本，不是67158命令脚本；旧脚本1包/1,668B不受影响。
本包未promote，canonical unknown87,631B、175 blockers及所有bank/gate声明保持。

只读验收入口（逆向工作树root）：

```sh
python3 tools/verify_rom_display_text_delta.py --root . --artifact-dir build/experiments/active/display-text-delta/tier1-20261001-v1/final
```

成功输出verified=true及92/85/1053；拒绝时输出verified=false/errors并exit1。
source冷重放可耗约一两分钟，JSON在验证结束时输出；不把暂时无stdout判为挂死。
缺ROM、合同、输入身份错误、symlink/extra文件或篡改均失败关闭；没有空分母成功包。
这是开发工具，没有新增游戏界面或可编辑资源入口，不声明Unicode或画面效果。

新包导出时先experiment_workspace init，再使用
`tools/export_rom_display_text_delta.py --root . --output <active-run>/final`。
只允许初始化且active的受管run，NO_REPLACE保证不能覆盖已有final；错误exit1，保留本次
拥有的失败stage供调查，不把半成品发布为final。复用shared output_parent、safe read及
已有原子写入/NO_REPLACE primitives，独立显示合同避免改写旧脚本packet/manifest。

## 输入合同与来源

最终合同SHA `ca0f7e4e384fdaffd7c7ae5dd73da1c6ff9bcc9ff5d5a0f211a8810f5f76e390`，56输入。
ROM固定1198ece...05b；immutable precoverage raw SHA为
`b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2`。
来源inventory-v2/v3、roots-v6/v17/v18、battle-controller分别50/14/12/2/12/2 site。
每个source从真实CFG block/已验证instruction range起点独立解码到site/sink，coarse
consumer slice不作membership；artifact、manifest及source verifier身份与precoverage claim绑定。
六组现有语义verifier实际调用一次并缓存；每次访问前重验冻结输入，不能复用漂移文件。
两桥capture/forward/parser目标、parser及SJIS窗口也均哈希固定。

exporter使用Capstone寄存器写集及现有_renderer_record_end；独立verifier使用有限raw
参数证明及_independent_renderer_end。只认首终止符及真实控制/SJIS宽度；limit固定在
immutable unknown segment内。0x463B16、0x458757、0x12F293等未消费suffix继续unknown。
固定候选分母不是全ROM消费者穷尽，source entry/path不宣称自然运行、ABI之外业务意义、
编辑/重定位安全或free-space。

## TDD、集成与复核

8项包测试先失败于未实现，再最小实现转绿；首个red尝试因fixture.run遮蔽unittest.run
而在运行前失败，已保留并明确排除，red-2才是有效功能红证据。
复核发现复用的unknown投影helper源码未列入初版输入。先加篡改身份失败测试，确认
未抛出ValueError，再将该helper及其依赖纳入最终56输入，转绿。
初版53输入合同/源码留在before-input-audit，已由最终合同取代，未发布为正式packet。

重构后9包测试+9参数测试=18/18通过：真实92site/85record、参数/literal/bridge/parser/
terminator变异、self-consistent payload+hash篡改、extra/symlink、受管/inactive路径、
NO_REPLACE、relocation、真实exporter/verifier CLI、current-unknown与immutable稳定报告隔离。
最终pub和两个独立重建报告一致；_current_projection单独绑定live coverage SHA，
85claims/1,053B全在current unknown中。live观察不进入payload或canonical claim身份。
语法/空白及文档链接检查另行执行；无统一Python formatter配置，不声称不存在的格式工具。

所有相关命令同heavy lock且non-degraded；完整测试峰值约415MiB，最终pub约271MiB。
未运行全量formal、mGBA或实体硬件，本次无新增runtime/画面声明。没有改ROM、canonical
或proof，没有commit/push。代码功能有对应单元及真实ROM/CLI集成测试。

## 阶段、持续复用和证据

[永久receipt](evidence/rom-display-text-delta-tier1-20261001-v1/)包含唯一受管final的原样副本、
TDD各阶段日志/guard、最终实现、合同、verifier稳定报告与current-projection.json。
源managed目录仍为build/experiments/active/display-text-delta/tier1-20261001-v1/final。
副本可不改manifest重放，未来修改实现必须以新版本/receipt取代，不改旧身份。

本包是显示文本类别的1包/1,053B，旧脚本是独立类别的1包/1,668B。总待接入两包/2,721B
仅供库存计数，不能当两同类packet凑4包；本次不触发10KiB/0.15pp/4同类的Tier-2门槛。
后续先积累相同显示文本合同或更大稳定工作包，里程碑时统一覆盖集成与formal。
当前immutable/独立投影设计允许canonical前进后稳定verify，同时重叠的live投影仍须拒绝。
