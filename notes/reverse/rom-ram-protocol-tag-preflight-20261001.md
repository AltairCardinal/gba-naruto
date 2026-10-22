# 12EE 混合池：renderer 文本与 RAM 条件标签预检

## 目的与复用方式

任务模式为“固定来源 literal 到已知消费者的有限局部筛选”，复用任务登记表的脚本优先方式。
输入是固定 ROM、canonical coverage 与大段锚点筛选；输出是可重放候选，不是 Tier-1 合同。
无需模型代理或运行模拟器。显示文本追加既有 renderer delta 链路；RAM 标签另设消费合同，
因为固定宽度及条件比较语义与 renderer 不同，但可复用 raw CFG、来源身份及受管验证能力。

## 实际结果

`0x12EE10..0x12F298` 的115个显式 Thumb LDR 形态，在同一 coverage owner 内最多追64B，
首个调用或控制边界即停止。首调用66758有57项、667A0有12项、68660有1项、85A40有12项、
85B8C有14项、9C3EC有1项；其余18项未在范围内到达首调用。形态不是完整来源 CFG 证明。

固定 r0 保存至已有 renderer 桥的候选去重为60条/578B。现有 exporter 与独立 parser
边界一致，范围不重叠且全部仍属 unknown；这仍只是假设消费边界。加上前两处352B和123B，
三池合计1,053B候选，不能加进正式coverage、Tier-1队列或验收收益。

局部 r2 固定来源保存至 RAM 标签 initializer 的候选25条：11条 emit、14条 match。
85A40 将 r2 写入 RAM 03005E30；85B8C 写入03005E34；两个 reader 分别从这些字段取指针。
初始化 payload 指针/长度使用另一个字段，不能把标签和 payload 混为一条生命周期。

## 原始地址与消费差异

- emit：85B1C→85B1E读取03005E30，85B26逐字节读取，85B34/85B36固定循环14次。
  NUL不停止，可能读取到对齐区或下个标签；不能用 renderer 首NUL边界代替。
- match：85C5A→85C5C读取03005E34，85C62/64/66检查NUL，85C78/7A限制14字节。
  85C6C可因首个不匹配提前退出；报告的NUL或14字节前缀是假设匹配时最大读取范围，
  不是每次必读范围。后续85CDC错误路径调用857B8。
- 两者先调用857E4，再受 readiness、共享标记和stage约束。stage1才消费标签；后续stage
  处理payload。没有证明所有共享状态writer、初始化至poll路径或自然执行。

源窗口85A40..85D00和857E4..85850的原字节、SHA与线性反汇编已封存。
线性窗口包含literal，不应作为新CFG声明；也不由这些指令推断协议业务名称或硬件用途。

## 下一步合同与停止条件

优先冻结60条显示文本的来源/桥接合同，复用现有双parser与delta adapter，不另建解析器。
RAM标签只有在完成caller参数、所有相关RAM writer、stage/readiness及错误路径闭包后才准入。
若无法冻结这些状态，保留候选并搁置，不通过反复扩小窗口替代证明。
9C3EC固定复制独立于标签和renderer，继续使用固定长度消费者边界。

## 验证及证据

[封存目录](evidence/rom-ram-protocol-tag-preflight-20261001-v1/)含protocol.py、protocol-v2.json、
逐字节一致的protocol-replay.json、guard、输入工具身份和validation.json。
两次最终脚本均exit0、non-degraded，并使用同一heavy lock。原protocol.json版本保留。
只读校验首次误用不存在的segment.kind字段，已记录并改为实际primary_class再次通过；
这不是功能TDD红绿记录。未执行来源完整verifier、集成/运行时测试或全量formal。
canonical SHA b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2、
proof SHA 465a13104b6c9a6d0ea418ca513dd0be732438634f1124a3a531c893b11db568保持不变。
promotion=0，正式队列仍1包/1,668B；未改ROM、功能代码，未提交或push。
