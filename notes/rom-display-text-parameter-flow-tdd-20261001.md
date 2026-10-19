# 显示文本局部参数证明：TDD实现与真实ROM集成

> 后续[完整显示文本Tier-1](rom-display-text-delta-tier1-20261001.md)已通过，
> 本记录保留局部参数阶段历史；当前完整包尚未Tier-2晋升。

## 授权与任务模式

2026-10-01用户取消3个百分点研究限制，Goal恢复active并改为“直到完成或周额度剩20%”。
本轮进入实现，当前恢复时周使用52%，以80%使用为上限，不自动提交或push。
复用固定消费者闭包的脚本/TDD/独立raw verifier模式。单一writer，没有子代理或模拟器。

## 可复用实现与入口

`tools/rom_display_text_parameter_flow.py`提供prove_parameter_flow：输入ROM bytes、
已证明source site、sink、固定target与owner区间，独立按raw Thumb编码检查固定r0参数。
支持本批实际需要的立即数MOV/ADD、ADD/SUB、PC literal、SP load/store和高寄存器MOV。
未知效果、r0覆盖、SP/LR/PC目的MOV、早期控制流、路径越界及非显示BL均失败关闭。
复用现有独立显示verifier的_half与_thumb_call，不引入通用解释器或符号执行器。

开发者在逆向工作树运行：

```sh
python3 -m unittest discover -s tests -p test_rom_display_text_parameter_flow.py
```

实际重放脚本见永久receipt内replay.py；必须在仓库root、PYTHONPATH=.运行。
这不是游戏UI功能；没有新增游戏入口、加载页或资源编辑能力。

## 红绿重构与集成验收

先写8个测试及占位API。red guard exit1，valid-ROM测试因未实现而失败；覆盖参数变化的
拒绝原因测试也未满足，日志没有import依赖失败。然后最小实现，green exit0；重构为复用
现有raw读取/BL能力，再次8/8通过。所有阶段同heavy lock且non-degraded。

其中真实ROM集成逐条验证92路径、559次指令出现、75/17两桥分母与固定path SHA；
每条路径插入MOV r0的92个变异都拒绝。另覆盖高寄存器MOV、SP load、literal、BL目标、
早期分支/BX/POP/BL、不支持opcode、奇数地址、错误owner及无效integer contract。
原ROM哈希与自然可达/source CFG未声明的边界也有测试。

8项包含单元和真实ROM集成，没有新增CLI端点/导航/数据库/后台任务，因此没有此类wiring。
语法/空白检查通过；无仓库统一Python formatter配置，未声称运行不存在的格式工具。

## 结果与边界

复核另加一项低寄存器MOV编码范围测试，先失败（ValueError未抛出），再收紧高寄存器
MOV条件，green和重构后均9/9通过。最终92路径proof保持稳定。当前源码及最终日志见
[复核补充receipt](evidence/rom-display-text-parameter-flow-audit-20261001-v1/)；初轮8测试
源码/receipt保留历史。初轮implementation哈希固定，源码演进后不可冒充当前生产重放；
后续绑定最终补充receipt。这里的9测试包含真实ROM集成，尚未完整packet发布验收。

92条局部参数路径独立raw证明通过，两次proof报告逐字节一致。
模块不证明源CFG、进入source的执行条件或全部caller；source_cfg_verified及自然可达字段
明确false。调用者必须绑定六组已重放CFG、源指令归属及固定合同，不能把任意owner数值
作为CFG验收。该helper允许两种显示bridge，包合同仍需冻结每site实际callee/path身份。

85条/1,053B仍不是完整受管显示文本packet。下一步冻结消费合同，复用双parser独立重建
记录及unknown投影，TDD实现export/verifier/managed CLI发布与变异集成。
不得直接沿用67158命令脚本语法，旧1,668B脚本包保持独立。

[永久证据](evidence/rom-display-text-parameter-flow-tdd-20261001-v1/)包含red/green/refactor日志、
guard、源码快照、输入哈希、原始proof及稳定重放；尚无Tier-1 manifest或新增accepted claim。
canonical/proof保持原SHA，unknown87,631B、175 blockers、正式队列仍脚本1包/1,668B。
未运行mGBA、硬件或全量formal，未改ROM，未提交或push。
