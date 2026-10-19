# 后续CFG文本候选：实际调用路径与投入边界

状态：只读规划预检，promotion=0，未完成Tier-1。复用固定CFG字面量筛选、现有两套
renderer parser和窄窗口raw BL核对模式；不启动子代理，不重复来源完整审计。
永久证据位于`notes/evidence/rom-fixed-text-route-preflight-20261001-v1/`。

## 固定输入与方法

ROM SHA `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`；
canonical SHA `b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2`。
读取上一轮永久screen，而不是只依赖未跟踪active目录。21个目标仍限定在
463914..463B18，源来自v17/v18已晋升域；本轮未重跑来源semantic verifier。

每个literal检查原半字编码、PC对齐计算和指针word，从site最多44B且不越owner末尾
读到首BL；Capstone寄存器write分析只作有限局部筛选，BL目标由独立signed位级解码
交叉核对。有限窗口内目标寄存器没有被改写；这不能代替完整独立taint/CFG合同。
callee窗口以raw hex与SHA保存，parser两套实现逐record比较终点。

## 路径分母与仅供规划的消费量

| 首BL目标 | site数 | 假设消费字节 | 验收前仍需补足 |
| --- | ---: | ---: | --- |
| 66758 / r0 | 13 | 346 | 来源raw verifier、完整消费者分母及独立参数流；桥接范围SHA匹配已有合同 |
| 667A0 / r0 | 1 | 6 | 可复用battle-condition-result-text桥接，SHA已匹配；新site身份与数据流仍需验真 |
| 90A20 / r0 | 2 | 102 | 新wrapper保存在sb的指针经过655B4再于90A6C传给66758；需独立wrapper/ABI合同 |
| 66EFC / r1 | 2 | 22 | 原始循环与截断语法的独立证明；本次两条局部模拟均遇源NUL停止 |
| 9C3EC / r1、r2=3 | 2 | 6 | 固定长度byte-copy callee合同，仅3B，不认领首NUL之后的间隙 |
| 92E80 / r0 | 1 | 未估算 | 额外状态、分支、callee与消费边界未闭合，保持排除 |

20个假设range互不重叠，合计482B，全部属于固定账本unknown。该数是**假设投影**，
不能算已接受records或净晋升；没有直接产出claims。13个直接renderer合346B；复用另一
已有桥接后为14site/352B；再证明90A20 wrapper才是16site/454B。
两个66EFC源分别463A9C..463AA5（9B）、463AA8..463AB5（13B），本例没有触发计数截断，
不能用两例未截断来证明普通NUL语法对其他输入成立。

## 对下一包的调整

优先做已有renderer grammar的14site/352B，并在同一包内决定是否纳入90A20两点。
该wrapper合同可共享给其他消费者，收益不只此102B；但先固定callee保存义务，不能
因为sb是惯常callee-saved寄存器就直接假定实际实现遵守ABI。
66EFC两个候选只有22B，应暂缓为其新建消费合同；9C3EC六字节亦不单独触发Tier-2。
该簇总量不足1KiB，所以完成上述同类delta后，应按总体方案转向低脚本消费者或AI
完整生命周期，不无限深挖剩余一个复杂callee。

形式实现仍必须TDD、独立来源/数据流验证、失败关闭变异和发布/CLI集成；本次研究
脚本不是生产功能，也没有用快速预检替代这些验收。正式队列仍1包/1,668B，canonical
unknown仍87,631B，175 blockers不变。

## 重放与验证

在逆向工作树根运行（新输出应放入新初始化run）：

```sh
PYTHONPATH=. python3 notes/evidence/rom-fixed-text-route-preflight-20261001-v1/routes.py
```

需要匹配冻结ROM、canonical和上一轮永久screen及两套parser输入身份；账本前进后须
从固定快照调查，不放宽SHA断言。该命令只读、stdout JSON，不发布artifact。
两次输出逐字节一致，13/1/2/2/2/1分母、bridge SHA和无重叠482B投影检查通过；
两次guard exit0、非降级。未运行mGBA、完整来源verifier或formal，无自然运行、Unicode、
编辑/重定位或RAM容量安全声明。未修改生产工具、ROM、coverage/proof，未提交。

- [ ] 查看routes.json → 21sites分成六类，92E80没有hypothetical_read_range。
- [ ] 查看两条66EFC row → source_nul与9/13B，没有宣称截断分支验收通过。
- [ ] 对照路线 → 先复用352B已有桥接，其他按合同投入决定，不计482B为正式收益。
