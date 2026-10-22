# 地图资源：完整固定变异写回、关联索引与安全拒绝

## 结果和开发者入口

166 个 content、217 个物理槽、249 个逻辑引用已贯通独立提取/编码、既有 importer、
真实 build CLI 和输出重读。一次全部资源 no-op 与基础 6MiB ROM 逐字节相同，
166 次独立变异中 70 个资源接受，写入 91 槽/105 引用；96 个容量拒绝，ROM 和报告
均未发布。全部固定变异通过 47 地图的结构/关联索引检查，域拒绝为 0。

固定变异仍是 palette byte2、其他角色 byte0 的 low-bit toggle；关联检查只证明
importer 的布局/图块/调色板边界，碰撞码及自然游戏行为不由此证明。接受分布为
bg_palette 2、collision_grid 14、metatile_definitions 27、primary_layout 25、alternate_layout 2。
**tile_graphics 的 34 个固定变异全部溢出**，不能宣传地图图像已能任意原槽编辑。

每个成功 ROM 与独立编码重建的全 ROM 精确一致，所有物理槽/逻辑 alias 解压为修改
内容，地图头表 0x53D910..0x53DEF0 的47×32B及槽外原字节保持不变。入口是开发者 CLI：

```sh
python3 tools/experiment_workspace.py init --task map-roundtrip --run-id manual-01
python3 tools/run_guarded.py \
  --summary build/experiments/active/map-roundtrip/manual-01/guard.json \
  --lock-file build/experiments/heavy.lock --max-tree-rss-mib 768 \
  --wall-timeout-s 240 --idle-timeout-s 7200 -- \
  python3 tools/audit_map_resource_fixed_roundtrip.py --root . \
  --run build/experiments/active/map-roundtrip/manual-01
```

正常结束 verified=true/exit0，并保存 run/roundtrip/result.json；fixture/cases 内有 spec、
编辑数据、日志、成功 ROM/report 和 readback。执行约80秒，CLI 在结束时返回完整 JSON。
需要全部冻结输入，缺失/symlink/身份漂移、非受管/非active路径、重用结果目录均失败
关闭。非预期失败或错误字节/别名给出 verified=false/errors、exit1，保留已有实验产物。
96 个预期拒绝属于成功验收矩阵的一部分，不能解读为编辑成功。没有游戏/编辑器UI变化，
没有 DB、重定位、模拟器或实体硬件实验，也不声称完整 release clean checkout。

## 复用边界与独立验收

使用登记表“冻结资源身份证据恢复与固定 slot 全分母写回矩阵”，脚本优先，无子代理。
直接复用 import_map_resources、build_mod/PatchSafetyGate、独立 map capacity verifier 的
codec、内容身份、固定 slot 和 header-pointer alias；没有新 ROM patcher/allocator。

第二族共用 tools/fixed_resource_roundtrip.py：复用上一族受管 run、安全写入、材料化输入
和 edit 结构，新增 recipe 参数让 CLI 选择 map schema/catalog/patch type。地图新增关联
域验证使用 struct.iter_unpack 独立检查 layout 两个u16索引及 metatile tile/palette字段，
检查全部逻辑地图及 flip 位掩码。不能直接使用 battle-effect 的固定 recipe，因为它的
spec schema、patch type 和指针表结构不同，且没有关联地图维度/索引关系。旧 battle
工具及合同不变，以免破坏历史精确重放；当前共用 adapter 保留冻结版本，并由收据存
代码供后续恢复。新能力追加在既有 importer/build 验收链，没有另建编辑器功能。

184 项输入合同 tools/data/map-resource-fixed-roundtrip-contract-v1.json SHA=
04bc6b6aa47fc4f8e924e9f203cb69bbf5e239ba430b5be17bc222efbe58dc78；新工具自身 SHA 另绑定到 result/manifest。构建 fixture 仅六个
hash-bound工具、ROM、catalog和导出bin。子构建明确 PYTHONPATH/DB_PATH/语言和hashseed，
不继承环境中的 DB/输出覆盖；每项从同一不可变原 ROM 开始，不串联变异 ROM。

## 旧测试失配与容量收据恢复

预检旧容量收据仍接受。合并相关测试后，发现三个历史测试仍使用不安全编码时期的
135/31 内容、163/54 槽计数及首个 graphics 成功样本；实际安全编码是70/96、91/126，
原两个 graphics 样本均溢出。保留失败日志，测试改用有容量证明的 collision_grid
b5519b9ecc7124c0da001af9f3901f2a1ef2bbd94799366474a12b016db66c91（7物理别名），
未改 importer 或编码器，不放宽拒绝。34 graphics 溢出的负证据由新完整矩阵覆盖。

测试源码身份改变后，旧 artifacts/map-resource-writeback-v1 正确拒绝，原目录未改。
当前 exporter 在两个新目录重建，独立 verifier/_expected_payload 均通过，两份输出
逐字节相同，去掉 implementation 后新旧完整 payload 相同。
[容量恢复收据](evidence/rom-map-resource-capacity-refresh-20261002-v1/)13成员，manifest SHA=
cea0bb94ab0d4c5088f8f5d4b95cba53256922a0cfc6f23def7a7be5054863c0；15.51s、35.69MiB、非降级。
合同指向新永久 refresh 目录，没有直接刷新旧 hash 或认领新的运行时证据。

## TDD、真实接线与重放

初始6项测试在未实现API上因正确原因失败；最小实现6项通过。第一次GREEN被默认
60s静默阈值中止，守卫终止自有进程树并保留日志；不将静默推断为挂死。后续同锁、
固定内存/总时间上限，显式 idle7200s。重构资源路径复用后加真实域拒绝集成测试，
最终新7项 + importer9项 + VRAM4项 + 旧 battle7项 = **27/27通过**（149.63s、161.53MiB）。
包含目录迁移的167 CLI、污染环境隔离、全部alias、两种layout半索引、tile/palette界限、
flip flags、共享地图中只有第二个alias非法，以及真实CLI四个非法索引在容量前拒绝。
三种故障：槽外篡改、漏报物理alias、拒绝后残留ROM均不允许发布 verified 结果。

正式 run=map-roundtrip/fixed-20261002-v1，167 CLI，guard=completed、非降级，
峰值 122.45MiB，结果 SHA=94c5bd87d495beb604ff9f1a3c09b1365c9d33f1bac628387e1a520eed838e10。
随后用永久收据 replay.py，复制184输入/合同/工具共186文件到另一目录，主验真进程
禁止读取源工作树，全部167CLI再次执行，完整 result 精确相同。构建子进程使用六个
复制工具；禁止读取钩子不覆盖子构建进程，不能外推全进程文件访问隔离。
永久重放优先取收据内冻结源码/合同，其余输入仍按合同逐项验身份。

[完整矩阵收据](evidence/rom-map-resource-fixed-roundtrip-20261002-v1/)含结果、TDD/guard、
固定实现、可执行永久重放、case归档及逐成员身份。cases.zip 保存各 spec/project、
编辑数据、日志、成功报告及readback；case-members.json 验证全部zip成员。约426MiB
可重建输出ROM及冻结fixture输入留在源受管run，省略项的SHA/size/reason明确登记，
不能说永久收据包含完整原始ROM。原始run完成后的 inventory也绑定在收据中。

## 正式状态和下一闭环

canonical/proof/bank-proofs SHA均保持，unknown=87,631B，正式 typed bank=0，175仍为
历史formal blockers。两个资源族的固定矩阵不能提升为整个 graphics release case；
其他资源、任意编辑、全部消费者、自然像素和实体硬件依然开放。未commit/push，
未改 Butano 工作树。格式采用AST、无尾空白、限定git diff --check；仓库没有统一formatter。

下一里程碑优先复验已有 import_map_resource_relocations / map-resource-relocation audit、
ImageResourceRegions / RomLayout / build_mod，处理本次96个溢出资源（含全部34图像）。
先冻结 expanded_ff父分区、map-resources所有权、完整allocation ledger和指针出现分母；
一个批次验证保留/变异、实际构建、所有alias重指向、旧槽不变和跨资源不冲突。
无法证明未知消费者或容量时仍拒绝。不是再创建分配器，也不跳过UI/自然运行验收。

## 几分钟验收

- [ ] 新run执行上述命令 → verified=true，166/217/249，167CLI，70接受、96容量拒绝。
- [ ] 打开 result.json → 接受项91槽/105引用重读通过，34图像项全部明确拒绝。
- [ ] 检查任一拒绝case → stderr容量说明，ROM/report均不存在。
- [ ] 使用收据 replay.py --root . --output 新受管run → portability.json 的 result_exact=true。
- [ ] 重放新测试 → 四类非法关联索引拒绝；不会把离线结果当自然游戏/UI/硬件完成。

## 仅提供ROM的收据闭包复验

收据 implementation/ 还保存全部183项非ROM输入（每项与合同hash一致），ROM单独供给。
第二次永久脚本复验的 --root 仅含 rom/base.gba，其余输入取自收据：167CLI重跑，完整
result再次相同。第一次重放76.49s/135.73MiB、第二次76.47s/136.33MiB，均非降级。
第二次读取钩子禁止 supplied-ROM root 的读取，并未单独禁止原工作树；第一次主进程
钩子禁止原工作树，两次构建工具均是复制的固定六文件，子进程钩子依旧不外推。
这证明本固定矩阵的输入闭包和重放可移植性，没有扩大成完整项目clean-release验收。

重放应使用新的受管输出目录，勿重用已有文件；外部 --root 只需正确hash的 rom/base.gba。
原CLI则仍要求仓库中的完整合同输入，并会因当前代码/输入身份漂移失败关闭。
