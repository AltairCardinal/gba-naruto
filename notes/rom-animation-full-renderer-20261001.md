# 完整 renderer 入口、描述器 body 与序列边界验证（2026-10-01）

状态：人工单活动对象的真实分配→完整62924 callback/scan/sort/body/advance→返回，
3,684组去重状态、7,368条原生轨迹、5项集成测试及三来源verifier通过。
**自然入口、多个活动对象、pending重工作回调、全writer、画面帧和实机BIOS仍开放；
promotion=0，无ROM或游戏界面变更。** 完整函数返回不等于全游戏语义完成。

## 复用与固定身份

沿用原生有限夹具模式，追加既有对象包的一条完整入口链；不另建renderer或ARM解释器。
复用原生内核、固定BIOS、对象allocator、v2/text-bg/v20来源verifier及旧序列解释器。
只使用可复现脚本，无子代理；同heavy lock、非降级守卫，最多500,000原生指令步。

权威：[29成员manifest](evidence/rom-animation-full-renderer-20261001-v1/manifest.json)、
[完整合同](evidence/rom-animation-full-renderer-20261001-v1/full-renderer.json)。

| 身份 | SHA256 |
| --- | --- |
| manifest | 5fa2bf27a6c9ada98667aebb7bd258d9fbbfd7f9e31500ac33e817cbdf7e0b67 |
| full-renderer.json | 8c8d1355298fdfd402af4a23c08d30b70d49a4f63f3d918fdfc7bb5f1345fecf |
| full-traces.jsonl.gz，35,867,096B | 71c72b53c1ecaf0ebec8c57d0546df4c87a2d7da3af90ed203db316b6a51fd49 |
| 父对象包manifest | fb75aefaa155ee21c43af4c4e7afa25d3e5410b10c5bcebd81946e39ce365a73 |
| 条件caller模型manifest | 1aca46ee19d8af2ddf051f1daa1fbfec1cd660245578020f689303116ff78e70 |
| ROM | 1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b |

611个输入和三项实现执行前后验size/SHA。固定provider沿用父包70文件、完整ABI宏、
397,312B人工baseline及SHA1 e7ade0ed82bb0f2d3d52070b280a8c84bb8abbab。
每个进程先实际save/load/save验真，事件处理仍抑制。不是自然游戏状态或真实画面帧。
冻结58成员caller模型身份，但没有重新计算整张64,926指令前驱图或证明其自然stack域。

## 完整路径与人工前提

真实626B4分配slot127；其他127对象flags2，reserved但inactive。完整62924入口：
逐项扫描128个callback，实际从+28读取固定callback并经9C114进入8AA50，然后实际
627B0扫描／排序，再处理唯一活动对象、描述器body与advance，最后63336 BX返回，SP复原。
分配与renderer之间保留RAM，人工重设入口寄存器；scale/angle是明确的分配后RAM注入。

long callback固定旧context1、last slot0、pending0和manager slot0，选择已证明的快路径。
没有把新对象context0的初始化后续或pending1/2资源操作冒充自然闭合。31项旧双字段
条件结果里，排除两个8EE40短候选，剩29个caller参数接入；另外18项保留排除（含参数
未知）。同参数合并为去重夹具，不声称29条caller已自然运行或新证明callee preservation。

八个descriptor涉及七对table与group0/1；初始slot必须0，sequence sentinel slot拒绝。
人工矩阵包括九种flags、七种count边界、五种坐标，以及六种scale组合、八种angle和
三种坐标；另补已知caller的callback0参数。不是全部u8/halfword字段的笛卡尔积。

| 实际轨迹行为 | 结果 |
| --- | --- |
| 进入descriptor body并读取全部head | 3,020组 |
| flags20000隐藏或任一scale为0而跳过body | 664组 |
| 实际进入9C0E4 / SWI06 division | 369组 |
| 实际执行固定内置BIOS ARM指令步 | 225,908步 |
| 实际读取sequence sentinel后duration | 1,533组 |

旋转路径调用真实61A80／61ACC及ROM三角表；缩放路径执行真实division及内置BIOS。
只证明固定内核／人工银行SP下的行为，不替代实机BIOS、异步IRQ、OAM提交或像素验收。

## 独立比较与终止符

所有调用的slot/timer和序列advance读取顺序与旧bounded Thumb executor一致。
group若进入真实62798 reset helper才归零，否则保持初始group；测试覆盖group1。
flags比较单独剔除renderer自身的01000000标记，其他flags与旧advance一致；原始
完整flags仍保留在每条轨迹及报告，不以忽略高位掩盖其他字段变化。

八个descriptor的24个entry、8个sentinel：实际629FC首head与631FE后续head序列
对上ROM逐项重建。隐藏／zero-scale样本应没有这组head读取。可见body中的相关ROM
读取逐项检查不超过最后sentinel head末端；**descriptor sentinel后2B suffix未读**。
sequence mode20则可读sentinel+2的duration，两层零suffix不能共用结论。

这次body已执行，取代前包“仅head路径、body未执行”的实验边界；前包收据保留且
仍正确描述它自己的范围。496B候选不因此晋升：全writer、自然入口域、正式独立
exporter/parser/publication合同尚未闭合。多个活动对象／OAM满／队列满亦未覆盖。

## 验证与失败记录

red与transform-red保存缺失模块／scale-angle API导致的失败；绿阶段5项集成测试
实际执行固定ROM。批次v1因caller分母误计30/17而拒绝；模型实际31双字段中排除两个
短候选后为29/18，修正计数并保留失败版本。v2通过3,684组；不可变代码窗口及前提
注释重构后v3再次通过，完整raw gzip逐字节相同。

v3守卫447.40s、峰值227.2MiB、非降级。三来源verifier本轮实际重跑；不是重证全ROM
或全部历史artifact。封存使用copy2保留文件权限，避免前包copyfile执行位问题。
[永久重放收据](evidence/rom-animation-full-renderer-portability-20261001-v1/manifest.json)通过：
444.13s、峰值286.7MiB、非降级；5测试、三来源verifier、3,684组完整调用、7,368轨迹
重新执行，full-renderer.json与35.9MB raw gzip均逐字节一致。

重放需固定本地provider，通常约8分钟；必须使用新的run-id：

```sh
python3 tools/experiment_workspace.py init --task animation-full-renderer-replay --run-id review-20261001-v1
python3 tools/run_guarded.py --summary build/experiments/active/animation-full-renderer-replay/review-20261001-v1/guard.json --lock-file build/experiments/heavy.lock --min-available-mib 512 --max-tree-rss-mib 1536 --wall-timeout-s 600 --idle-timeout-s 120 -- python3 notes/evidence/rom-animation-full-renderer-20261001-v1/replay_receipt.py build/experiments/active/animation-full-renderer-replay/review-20261001-v1/output build/experiments/active/animation-full-renderer-replay/review-20261001-v1/replay.log
python3 tools/experiment_workspace.py complete --task animation-full-renderer-replay --run-id review-20261001-v1
```

## 剩余债务与后续选择

自然长回调重工作路径、跨帧复用、多个活动对象和完整writer分母仍开放。继续沿同一
人工片段扩大样本不会自动补齐这些前提；该路线暂不再拆局部包重复验证。
下一里程碑转向有效bank的旧证据合同迁移，先复用data-table-b的自然message0指针
A/B和完整79×1分母，恢复可移植binary身份，做ID0/text_ptr的typed partial合同／CLI
接线；其他78项保持未验证。不改旧manifest，不把一个样本写成完整bank，不新增GUI
捕获替代已有可复验原始archive。随后按共同消费者批量扩矩阵和round-trip。

canonical仍87,631B未知；coverage/proof/bank-proofs三SHA与输入一致。没有新Tier-1
或Tier-2分类／global formal；107/107、97/97及175blockers是历史结果。无commit/push，
Butano分支未改。入口为永久重放脚本和合同文件，当前不提供新的游戏操作入口。
