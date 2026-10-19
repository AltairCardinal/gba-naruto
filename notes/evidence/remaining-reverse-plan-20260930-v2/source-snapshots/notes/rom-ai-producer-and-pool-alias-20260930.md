# AI 固定入口分母与单位池别名（2026-09-30）

状态：raw编码扫描范围已独立复现，unit-pool地址别名已绑定；生命周期仍开放，
promotion=0。沿用固定producer/消费者窗口脚本模式，未升级到模型代理，未修改
任何生产工具或正式coverage/proof。前置为AI入口与渲染脚本依赖调查。

## 复用与扫描合同

复用`thumb_branch.iter_thumb_direct_branches`和`find_pointer_refs.scan_references`，
在整份6MiB ROM上一次收集五目标的Thumb BL/B形态，另查每个目标的精确tagged /
untagged word在每字节位置的出现。第二份脚本复用prebattle-menu独立verifier的
`_direct_target`，重扫BL/B/Bcond；复用boot-interwork的ARM B位移decoder，B/BL仅
清link bit以共享位移算术，按每4B排除cond=NV后查全ROM。指针独立复核用bytes.find。
两份脚本的BL/B及全部精确字样分母完全一致，新增Bcond/ARM检查仍无命中。

ROM SHA `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
owner关联使用immutable coverage raw SHA `b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2`。

| 固定目标（ROM offset） | 全ROM Thumb BL形态命中 | B/Bcond、ARM B/BL、精确指针 |
| --- | --- | --- |
| 84274 scorer | 85306 | 均0 |
| 851F8 planner | 7425A、7434E | 均0 |
| 6AA64 unit core | 6AC98、6AD54、6E2A0 | 均0 |
| 6ACAC source initializer | 6E31C、6E324 | 均0 |
| 6E1B4 formation | 7519E | 均0 |

9个BL形态都位于已有Thumb instruction-only或直接BL producer primary owner；
第一扫描保守标为instruction-owner candidate，并不另声明完整producer语义或自然
可达。原始字样不存在不等于computed/RAM/间接入口不存在，ARM直接分支也不切换
Thumb模式。不得把raw扫描分母解释为全函数incoming穷尽，尤其不能取消scorer
索引/writer/控制状态生命周期门禁。

永久收据`notes/evidence/rom-ai-five-root-producers-20260930-v1/`包含原始脚本、两份
结果、全部guard、工具回归与窗口。初扫18.6s、峰值172.24MiB；独立复核与回归3.1s、
峰值30.21MiB，均exit0、非降级。复用工具9/9测试通过；补充signed Thumb/ARM B/BL
canary9例及AL/NV raw scan正负2例通过。保留首次canary，仅新版真正检验NV被排除，
不把首版识别NV常量的断言当完整排除验证。代码/ROM/结果身份由收据绑定。

主脚本从仓库build run读取首扫结果的独立复核是本次实验的重放方式；永久目录保留
脚本和所有实际输出。恢复首扫实验时使用新run，不覆盖已completed原目录。

## formation caller与槽13别名

独立caller窗口75184..表明75188先调用6A99C清理，再7519E调用formation。新的有限
窗口6A99C..6A9E4绑定所有关键store/loop指令与两个已分类literal：

- 6A9A4的PC-load消费6A9E4=`020240C0`；r1从1开始，CMP12/BLS循环。
- 6A9C4的PC-load消费6A9E8=`02025884`；r1从0开始，CMP2/BLS循环。
- stride来自EA左移1，即1D4；识别的单位数据store为byte `+0`及word `+D0`。
- `020240C0 + 13×1D4 = 02025884`，所以主池slot13物理别名extra pool slot0。
  CD地址为`02025951`；上述清理数据store不是CD，不提供CD==0不变量。

这使slot13耗尽路径的义务更明确：不是简单“数组外必为空”的假设，而是另一组三槽
记录的生命周期，需绑定其复制、继承、关联单位写入和使用。主池slot14/15同理落入
extra1/2；这里只证明地址算术和已绑定局部clear形态，不证明这些slot自然进入planner。
栈写、异步状态变更、其他writer和整个RAM别名分母没有穷尽，不能从本窗口反向宣称
slot13一定保持FF或会自然发生表外读取。

永久收据`notes/evidence/rom-ai-unit-pool-alias-20260930-v1/`，两次输出逐字节一致。
重放命令：

```sh
python3 notes/evidence/rom-ai-unit-pool-alias-20260930-v1/replay_inventory.py .
```

## 下一完整里程碑

固定输入上的直接编码扫描可以复用，不再重复找同一批静态指针。下一步将6AA64的
extra-pool复制、6ACAC的关联CD写入、formation特殊lookup域、scorer/planner等待帧
及slot13控制状态合并为一个RAM字段生命周期工作包。必须找齐更新CD/CC/C0的
copy/inherit/clear与脚本入口，证明筛选及所有caller的支配约束；无法冻结入口不变量
则keep_unknown，转向另一个已锚定消费者簇。未达到Tier-2门槛，不重复formal。

## 验收清单

- [ ] 查看两份扫描结果 → 9个BL位置一致，其他已扫描编码/字样均0，promotion0。
- [ ] 查看guard与回归 → 非降级、exit0，9/9工具测试及新版canary通过。
- [ ] 重放slot13 inventory → address_alias_verified=true，initial_clear_proves_cd_zero=false。
- [ ] 查看当前coverage → 仍87,631 unknown，不把本轮raw分母或地址别名计为覆盖。
