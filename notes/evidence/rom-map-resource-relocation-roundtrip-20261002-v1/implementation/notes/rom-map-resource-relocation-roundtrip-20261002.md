# 地图资源：完整批次重定位与实际构建重读

## 结果和使用入口

既有重定位链路现在有真实 build CLI 的固定批次验收。197项冻结输入，166个去重内容、
217个原物理槽、249个地图头引用。四个成功案例输出完整16MiB ROM：

| 案例 | 迁移内容 | 重指向引用 | 占用跨度/剩余区域字节 |
| --- | ---: | ---: | ---: |
| 全166项原样迁移 | 166 | 249 | 385,086 / 663,490 |
| 全166项同时固定变异 | 166 | 249 | 385,243 / 663,333 |
| 仅原槽溢出的96项同时变异 | 96 | 144 | 337,507 / 711,069 |
| 首个图像追加一个32B tile | 1 | 1 | 13,959 / 1,034,617 |

五类负例：非法layout索引、错误区域owner、合法结构但区域容量溢出、两个独立spec
从同一起点分配不同内容、缺失ROM layout。它们都在发布ROM/report前拒绝，基础ROM不变。
96项包括上一轮全部34个图像溢出项；本次证明这些固定变异在上述完整批次能迁移，
不是96个任意单项/子集/排序、所有尺寸变化或自然游戏语义的穷尽证明。

开发者入口，在逆向工作树初始化新run：

```sh
python3 tools/experiment_workspace.py init --task map-relocation-roundtrip --run-id manual-01
python3 tools/run_guarded.py \
  --summary build/experiments/active/map-relocation-roundtrip/manual-01/guard.json \
  --lock-file build/experiments/heavy.lock --max-tree-rss-mib 768 \
  --wall-timeout-s 180 --idle-timeout-s 7200 -- \
  python3 tools/audit_map_resource_relocation_roundtrip.py --root . \
  --run build/experiments/active/map-relocation-roundtrip/manual-01
```

约24秒后输出 verified=true/exit0；run/roundtrip/result.json有结果，fixture/cases下有
完整spec/project、日志、接受ROM/report/readback。五个预期拒绝不算工具失败或编辑成功。
缺输入、symlink、身份漂移、非受管/非active输出或重复roundtrip目录失败关闭；非预期
输出/ledger/构建错误返回verified=false/errors、exit1并保留诊断。没有游戏或编辑器UI
变化、没有DB，也没有mGBA、自然导航或实体硬件实验；开发者可查看或使用实验ROM，
它不是完整项目release或clean-checkout构建。

## 复用、冻结输入与独立验收

任务模式是“冻结分区所有权与固定资源全集的批量重定位写回”。先按相近固定slot/指针
A/B模式脚本预检，再扩展冻结批次，未升级模型或启动子代理。输入是ROM、catalog/bin、
layout、区域所有权、既有旧收据、codec/构建实现及固定变异；操作是已有重定位器生成、
真实构建、独立整ROM/所有alias/ledger重读和拒绝验真；产出完整结果/manifest/可重放闭包。

直接复用 import_map_resource_relocations、ImageResourceRegions、RomLayout、build_mod/
PatchSafetyGate，以及旧独立资源/来源verifier；没有新allocator、ROM patcher或编辑器。
复用固定slot的安全读取、受管run、材料化输入和独立linked_domain。新增
resource_relocation_build_cli.py 只把完整spec、多spec冲突和显式layout接到既有CLI，
为后续重定位族共用。固定slot v1 recipe不能表达这些元数据；其代码/合同保持原样，
以便原验收入口继续有效。地图头/u32来源指针与各资源语义仍独立维护。

合同 tools/data/map-resource-relocation-roundtrip-contract-v1.json SHA=
ce9f3b7902991a9ac12a28961e438dee563762a18a799cb6f1fab4c81fdcb991。复制八工具、ROM、catalog/layout/registry到无DB fixture，子构建
仅继承明确Python路径、PATH/语言/hashseed和不存在的DB路径；环境DB/output变量不继承。
每个case从同一原6MiB ROM及**空fixture父allocation ledger**开始，输出扩展为16MiB。
不是读取或证明用户当前完整release父ROM/全部既有分配。每个成功report的所有allocation
和pointer声明均逐项独立核对，包括owner/区域、偏移、长度、原/新字节、内容身份与类型。

独立容量verifier的raw codec重读217个旧槽，并与旧地图资源读取结果比较；对实际输出
从基础ROM+FF扩展、4B对齐计划、已登记map-resources区0x980000..0xA80000和249个header
重新构造完整bytes，与输出精确比较。全部249逻辑引用（含未迁移者）重新解压，全部217
旧compressed record保持原样，区域间隙与其他字节不变。全保留ROM SHA与旧独立收据
64fc632d2d2ee3e61f3f1ce211420d8145640a27dc2a40063bc8d011b6218403精确一致。

全ROM source pointer分母只扫描1,572,864个4B对齐u32，217源偏移的出现集合恰好对应
249个header引用；它不穷尽未对齐/计算消费者、自然可达性或指针业务语义。区域容量负例
使用固定16KiB pattern重复64次追加到图像，codec独立证明超过1MiB，结构/关联域合法。
pattern绑定hash，避免随机输入漂移或大基数字典耗尽内存。不是任意碰撞码合法性的证明。

## TDD、集成与收据

初始4项测试在未实现API上正确RED，最小实现4项GREEN；抽出重定位CLI adapter后，
新4项及旧importer/relocation audit/区域测试12项共**16/16通过**，104.59s、262.80MiB，非降级。
包括真实目录迁移CLI全部9case、污染DB/output环境隔离、217/249完整重读、五种安全拒绝、
输入和run门，以及真实旧槽篡改、漏报alias、report伪owner、拒绝后残留ROM四种故障拒绝。
旧测试还覆盖tile/map两族同gate整批兼容，不扩大成所有资源族兼容。格式验证AST、尾空白
与限定git diff --check；没有统一formatter配置。没有UI/runtime/hardware测试可声明。

正式run map-relocation-roundtrip/fixed-20261002-v1，9真CLI，23.81s、201.41MiB、非降级；
result SHA=1f49e9a1e8ae6d8018edf74e89629feea3d5961c2a23262ff31a56413044797d。
[永久收据](evidence/rom-map-resource-relocation-roundtrip-20261002-v1/)保存196项非ROM输入、
合同/实现/测试、原样旧证据、全部TDD/guard、完整结果、228个case/编辑zip成员及逐成员身份。
四个可重建16MiB ROM及fixture输入不重复保存，省略表明确SHA/size/reason；source inventory
绑定源run，不能说收据包含全部原始ROM。没有覆盖旧artifact或前一族收据。

永久replay.py只需外部root提供正确ROM：复制197输入/合同/工具共199文件到另一目录，
再次执行9CLI，完整result精确相同；23.80s、216.98MiB、非降级。主读取hook禁止供给ROM
root在验真期间被读，不单独禁止旧工作树；196项材料明确取自收据，八个构建工具也是复制
版本。hook不覆盖新构建子进程，不声称全进程文件访问审计。重放使用新受管输出目录。

## 正式边界与下一里程碑

canonical/proof/bank SHA均不变，unknown=87,631B，typed bank正式0，175仍是历史formal
blockers。没有晋升完整graphics或resource_roundtrip的七case；没有修改完成政策、commit、
push或Butano工作树。上一轮“图像全部原槽拒绝”仍成立，本轮仅补了指定重定位方案。

下一闭环回到自然地图消费证据：先集中复验 map41-primary-layout-pixel-ab 与
map41-visual-resource-matrix 的旧raw/producer/guard/零对照、47×9字段分母和可恢复快照，
再决定绑定maps的typed部分合同或从同一自然路径捕获新的迁移A/B；不从离线重定位推导
自然像素，更不把maps误当已否证的encounter-zones独立bank。字段历史名称与六实际资源
角色需逐地址核对，避免把palette/布局旧别名当新语义；flags和其余46map保持待证明。

## 几分钟验收

- [ ] 新run执行命令 → 9CLI，4接受/5拒绝；全部166内容和96溢出子集列出。
- [ ] 查看接受readback → 所有249引用重读、217旧槽不变、16MiB整ROM/ledger一致。
- [ ] 查看任一拒绝case → 明确错误原因，没有ROM/report。
- [ ] 向空root仅提供ROM并执行收据replay → 199文件闭包、完整result精确相同。
- [ ] 查看scope → 空fixture父ledger/对齐u32分母，runtime/UI/硬件/全release仍为false。
