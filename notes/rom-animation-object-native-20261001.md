# 对象生命周期、回调、排序与两层终止符联合验证（2026-10-01）

状态：固定来源、人工状态及固定原生内核下，16 项测试、5,381 条轨迹和三组独立来源
verifier 通过。**自然 handle/group/slot 域、完整 renderer、全 writer、实机 BIOS 仍开放。
promotion=0，无游戏界面或 ROM 行为变更；不签发完整 bank。**

## 复用、执行方式与身份

沿用登记模式“冻结来源的 ARM/Thumb 迁移回调与协程／BIOS 有限夹具差分”：
脚本优先，复用原生 IRQ 包 v2、既有对象生命周期解释器、v2 CFG、text-bg callback
及 v20 来源 verifier。不启动子代理，不安装依赖，不另建 allocator、renderer 或排序器。
原生探针增加实际 scalar load 调用日志；load/store multiple 只记录实际调用，
不凭空重建逐字节总线事件。上限扩至 128 个代码区间、500,000 指令步、1,024 peek，
保留失败关闭的 PC/stop/budget 检查、相同 heavy lock 和非降级内存守卫。

权威收据：[manifest](evidence/rom-animation-object-native-20261001-v1/manifest.json)，
[完整合同](evidence/rom-animation-object-native-20261001-v1/object-native.json)。

| 输入／产物 | 身份 |
| --- | --- |
| ROM SHA256 | 1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b |
| 61 成员 manifest SHA256 | fb75aefaa155ee21c43af4c4e7afa25d3e5410b10c5bcebd81946e39ce365a73 |
| object-native.json SHA256 | 2a86e110b5f9447fef14015c4a4da31e8e52787777a9ea3684a2a6cf43f6a9c7 |
| provider-contract.json SHA256 | 7738f5270f3d593e0e5be17b5770bd53efa4f778c69e3a82aae03ba04e12e659 |
| 人工 baseline SHA1／大小 | e7ade0ed82bb0f2d3d52070b280a8c84bb8abbab／397,312B |
| 内置 BIOS SHA256 | ea370175428d57d0bb77cd6b8e3b3c56a63849ff2122de9e5c2ddf256c2d3836 |

549 个输入执行前后验 size/SHA，另绑定本包七项实现身份；provider 的 70 个文件及
完整构建宏保持冻结。mGBA commit 为 c16c3ff55585e71bee83c95539c2ecde15d728c8。
每个进程先实际 save/load/save，验证 baseline 一致。单 fixture 恢复人工零 RAM；
五阶段链只在首阶段恢复，后续保留 RAM，但人工设定各阶段入口、寄存器和银行 SP。
这不是自然游戏快照、自然事件时序或连续游戏调用链。

## 原指令结果

### 分配、回调、释放、扫描和复用

池为 03003BB8，128 个对象、stride 60。两 allocator 的 128 个单 free 槽及全满情况
均执行；全满返回 0。分配会设置 group/slot/timer，却保留 +2C..+30 的旧回调上下文。

五阶段链使用真实 626B4 分配，62940..62958 从 +28 读取实际 callback 0808AA51，
经 9C114 BX 调入 8AA50，随后真实 62788 disable、完整 627B0..6291A scan/sort，
最后重新分配同一对象。五组上下文共 25 条阶段轨迹，RAM 在阶段间不注入新值。
flags 21→22→20→21：扫描仅清 reserved bit1，高位 20 保留。context0 经回调变16，
随后复用仍为16；非零旧上下文会跳过首次 BIOS 初始化。这是原 ROM 行为观察，
**不证明游戏中会出现错误，也未修改游戏**。

### 管理器查找

655B4..655F0，literal655F0=0200A8A4；stride4D0，tag 位于 +13。
参数截为 u8，读取 index0..9，找到首个匹配则返回该记录。
**全部不匹配时返回 index10 对应的 0200D8C4，不返回 NULL，也不读取 index10 tag。**

256 个 needle × 11 个匹配／不匹配位置，共2,816条原生轨迹；逐项验证返回地址与
实际 tag 读取序列。另以准确64B叶函数合同绑定计数初始化、递增、9上界、返回乘法
和 literal，并在测试中修改上界验证拒绝。这是固定叶的原字节证书，不是通用符号
执行器；未穷举 256^10 种 tag 组合，未证明自然 tag、有效 manager 或私有 stack 域。
调用方不能仅以返回非零认定查找成功。

### 长回调快路径和尾部

8AA50 的 context=0 初始化将 +2C 置16、last slot置FF、pending置0，执行真实
9C0E0 / CpuSet 内置 BIOS；117个halfword、234B写 manager+1E，人工输入下值均为1。
三种context × 全256 manager slot，共768条快路径；pending重工作分支未冒充闭合。

条件入口8AC26..8ACB6使用明确对齐的池 handle 和人工 metadata byte，验证774组
byte边界及16组 handle 别名／写入顺序。metadata+12 非零清新对象 flags bit17；
metadata+3／+2 非零时清旧对象 bit17 并写 +10：分别384+4*m、398+4*m；零时置bit17。
本合同的所有别名排列中，group+14、slot+16、timer+18、callback+28 均未改变。
NULL 或池外 handle 在夹具预检拒绝；没有证明自然分配失败不可能，也未穷举全部
metadata 三元笛卡尔积。该条件尾入口不等于从完整回调自然到达它。

### 完整排序及序列推进

完整627B0..6291A已返回，SP复原；20组优先级、升降序、相等、signed16边界和混合
active/reserved 模式，对照独立 insertion oracle。先比较 flags&C0，再 flags&300；
相等时按40000启用深度排序，signed16深度降序。02000000选择+1A，否则+6。
旧“10000启用深度”测试假设被原指令反例否定，失败版本保留。

672条既有人工序列输入与旧 bounded Thumb executor 对比最终flags/group/slot/timer、
序列读取顺序和 visited；原生 BL 的第二个 Thumb halfword PC仅为该比较规范化，
完整原生轨迹仍保留。全部一致。另保留 group/slot/table 在 freeze 检查之前已读取
的 selection 轨迹，flags8不能免除入口指针／索引的有效性义务。

## 两层终止符边界

八个描述器共24个entry：629E6..62A0A执行实际 sequence index→descriptor table→
首head绑定；631F6..63208执行实际 stride14 / next head / -1分支，共32条轨迹。
人工跳过每个entry的 renderer body，仅核对这些条件入口的 head 读取与终止分支。
每个 head 读取宽度2；最后 sentinel head 后2B suffix在此路径未读取。
**未执行完整body，因此不把24×14 entry、496B候选或suffix正式认领。**

序列 mode20 的临时指针则可能推进4B并继续读取 sentinel duration，旧672轨迹与原生
轨迹对上；不能把 sequence sentinel 的零 suffix 也说成未读取。
sequence head=-1不能作为有效 descriptor index；新夹具在绑定前拒绝这一输入。
自然 slot 是否永远不进入 sentinel、group1 freeze能否保持及外部 writer域仍开放。

## 失败证据、TDD 与重放

- red-tests／joint-red-tests／descriptor-red-tests／sort-alternate-red-tests 保存缺失能力
  或缺失API导致的失败；绿阶段16项集成测试实际执行当前 ROM 和原生内核。
- 原边界上限、629B0停止点、错误排序mask、flags全部清零假设的失败及对应版本保留。
- 批次v1因旧 audit 绑定的 ignored analysis.py 已漂移而拒绝；冻结文本中的历史脚本
  自身也不同于该旧身份。因此该build输入明确记录为未消费／未执行，其他输入验真；
  相关 pair/descriptor heads 从当前固定 ROM 和原指令轨迹独立核对。不声称旧audit
  生成器完整复现，也不修改它的历史manifest。
- 批次v2日志重定向触发守卫idle超时；修复可观察进度后v3通过。缓存不可变来源区间
  的重构后v4再通过；两次native-traces.jsonl.gz逐字节相同。
- v4守卫：165.43s、峰值201.8MiB、非降级。三来源 verifier 是本轮实际重跑，
  不是由manifest身份替代语义验证；不等于重证全部历史45组或88,472指令。
- 首次永久重放因封存复制丢失执行位，在任何原生case执行前失败；原失败保留，
  二进制恢复执行位，内容SHA及61成员manifest未改变。永久重放v2通过：167.61s、240.2MiB、非降级，16测试／5,381轨迹／三来源复验，
  两个输出逐字节相同。[永久重放收据](evidence/rom-animation-object-native-portability-20261001-v1/manifest.json)
  保留失败、修复方式、成功guard及报告；原61成员manifest保持。

在仓库根执行（需固定本地provider文件与动态库；新的run-id不得重用）：

```sh
python3 tools/experiment_workspace.py init --task animation-object-native-replay --run-id review-20261001-v1
python3 tools/run_guarded.py --summary build/experiments/active/animation-object-native-replay/review-20261001-v1/guard.json --lock-file build/experiments/heavy.lock --min-available-mib 512 --max-tree-rss-mib 1536 --wall-timeout-s 600 --idle-timeout-s 120 -- python3 notes/evidence/rom-animation-object-native-20261001-v1/replay_receipt.py build/experiments/active/animation-object-native-replay/review-20261001-v1/output build/experiments/active/animation-object-native-replay/review-20261001-v1/replay.log
python3 tools/experiment_workspace.py complete --task animation-object-native-replay --run-id review-20261001-v1
```

保存的 seal_receipt.py 是历史封存脚本，使用copyfile，不能假定它保留执行位；Git应
保留 mgba-arm-probe 的 executable mode。复用首选永久 replay_receipt.py，缺库／
哈希变动／执行位缺失／来源漂移均应停止并保留失败，不绕过 verifier。

## 正式账本与下一步

canonical仍6,203,825已分类／87,631未知字节；coverage、proof、bank-proofs SHA均与
本批输入相同。本批未增加Tier-1分类库存、未触发Tier-2、未重跑global formal。
107/107、97/97、175blockers仅是此前历史结果。Butano分支未改；无commit/push。

下一包应从实际完整 renderer入口62924贯通 callback、scan/sort、descriptor body、
BIOS arithmetic和完整返回，统一验证 group/slot/timer 与两层读取边界；已有条件片段
不再拆新包重复证明。到未证明来源或实际内核预算边界停止。随后把有效新域合并
回47caller／全writer模型；无法证明自然不变量时转向bank字段矩阵和round-trip债务，
保留开放域，禁止靠人为清零或跳过body换取promotion。
