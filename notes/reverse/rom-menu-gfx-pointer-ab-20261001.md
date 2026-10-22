# Menu-ui gfx_ptr_0：旧样本重发与单字段自然加载合同

## 当前结果与范围

已完成两条有不同证据边界的链路。旧头像内容 A/B 使用当前 renderer 全量重算并两次
独立复验通过，语义 payload 与旧结果逐字节相同；旧 artifact 原样保留，原命令仍因
历史 implementation hash 不匹配拒绝。新实验沿生产 relocation 构建并只改变 record 1
的 gfx_ptr_0，自然 ShowPortrait(0,1,0) 加载后只改变屏幕 (56,48) 一个像素。

新 bank 合同保留 63 records × 10 fields=630 单元，覆盖只有 record1/gfx_ptr_0，
其余 629 明确未覆盖。record0 的全零字段、额外 special variant5、其他画像、变体和
切换路线均不外推。旧内容实验不能冒充本次指针隔离；本次指针隔离也不能证明
palette_ptr_0 或整个头像表。正式 catalog/proof/canonical 没有变化。

## 模式、复用与输入构建

采用登记表的“冻结资源指针单字段 A/B 与可恢复快照自然路径合同”，脚本优先、
无子代理。直接复用 build_menu_portrait_pixel_ab 的生产分配和父 ledger；复用
path/hash/JSON 小工具、PatchSafetyGate、layout/regions、旧独立 portrait packing/
LZ77、state reader、renderer、guard、Lua 和原子 NO_REPLACE 发布 primitives。

新边界追加在父资源链路之后。旧 verifier 的内容编辑 schema 与本次 pointer A/B
不同，且旧实现/manifest 已冻结，故新增独立 verifier，不改写旧 schema 或降低 hash
检查；CLI 是开发者入口，没有新增游戏菜单或 GUI 编辑器。重构检查保留已有组件，
避免为字段验证另建图像 codec、资源分配器或模拟器控制链。

- 原 ROM SHA：1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b。
- bank SHA：8e9cf0a4289ff2701ad9643181532a6e8283177875b38d34d6eced5948a6cfe7。
- 冻结父 build manifest SHA：1b2ec1560b5492ef90c354646f44a5f9ba872384ae3e6831984030474811bd69。
- 父 baseline：202301cc...95fc3a；父 candidate：26a08a91...42311。
- 新 allocation：[0xA80D6C,0xA81A56)，3306B，位于 menu-portraits/A80000..B00000，
  owner=menu_portrait_resources。重放全部父 allocation 到同一个 gate 检查碰撞；
  两份新 ROM 都带新图像，不能把旁边 FF 字节认领为原 ROM free space。
- 唯一字段 0x5A4E14：0x08A80000→0x08A80D6C，只有 0x5A4E14/0x5A4E15 两字节不同。
  palette 指针保持 0x08A80CEC，其他 records 和 variants 逐字节相同。
- 新 baseline SHA：5e1c7a4d3c00a9d506b5ba81fd2cf0fbd174675a9aa31f4dbba5b66ae7ac4323。
  新 candidate SHA：c8e707b8484782934cc07e9497219eec4028cf761123b3ae4ba3d14978e63442。
- 图像解压为 6400B，只有 stream index5184 从52变14（canvas40,40）；encoded SHA
  efbda517fad5e0e4306fddbe9e5d2bbff4efba86d1a6df973e72d053bc6611d4，decoded SHA
  68cef61a871dc615f25502d40840735f2493a7b97c8514236d6dc083527e1d41。

独立复验不调用新 builder：从 source portrait 独立 packing/编码恢复父 ROM，插入同一
新流再改唯一指针，重建两份完整 16MiB ROM 并核对固定 SHA。另一个独立 LZ77 decoder
在构建测试中核对两个 pointer 真正解出的数据。独立 raw 构建脚本实际重跑两次通过，
不是复制首次 report 来声称重放。

## 真实快照与因果归因

输入为 `artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-9.ss9`，SHA
5635916176865f63b12154ea1c68e202393baaf6e1427473fb6be8a84b18eba8，格式0x01000007。
IWRAM 0x030011F0 的 cursor=0x08031F42，下一 ShowPortrait 命令位于0x08031F6E，
输入中尚无目标6400B graphics。三个 zero 样本验证该快照可恢复且无输入重放一致。
两个单输入样本只使用 A down5/up13/capture80；新捕获格式为0x0100000B。

c16 binary SHA=ef2386a5...d54b；进程本地缓存 library SHA=0f84fde8...25b0b，source
commit/exported gitCommit 均为 c16c3ff55585e71bee83c95539c2ecde15d728c8，source tree clean、
dlopen 检查通过。复用先前核对的 DYLD_LIBRARY_PATH，但本轮仍重新核对身份。
五个 fresh run 显式统一 heavy.lock，启动门槛4096MiB、owned-tree 上限1536MiB；
均 completed/exit0/success-marker/非降级，峰值约60MiB；PGID/listener 无残留。
无新 crash、不清除 latch、不修改系统库/旧 binary 或原 ROM 的 save sidecar。

- VRAM [0x06010000,0x06011900) 完整匹配被选择的6400B图像。
- PRAM [0x05000200,0x05000280) 完整匹配原调色板，baseline/candidate相同。
- 六域差异仅 EWRAM offset0x3CC0（绝对0x02003CC0）和 VRAM offset0x11440
  （绝对0x06011440）各一字节52→14；IO/IWRAM/OAM/PRAM没有差异。
- 像素 (56,48) RGB=[239,189,165]→[99,74,57]；其他38,399像素完全相同。
  baseline RGB SHA=aada62ba...a22bc，candidate RGB SHA=f4ffd0ce...a79ed，均与旧内容
  A/B 的固定截图一致。各截图必须由自己的 state 经当前 renderer 逐字节重现。

### 工作区前缀的未解语义

曾误假设 EWRAM [0x02002880,0x02004180) 完整保留图像，第一轮 GREEN 正确失败。
检查发现前128B已不同于graphics；尝试把它当作本条头像palette时，独立assert仍失败，
未把该猜测写入实现。旧样本也存在同样的前缀现象。该前缀没有128B完整ROM出现、
不匹配catalog中的portrait palettes，用途或写入者仍未证明。

最终检查 [0x02002900,0x02004180) 6272B图像后缀，并固定前128B观察身份 SHA
963fe19839f2b2692d60b90eaae9b85ca5cebefc5a93d78e26e193b061def29e；完整VRAM图像检查
没有放宽。report 显式 scratch_prefix_semantics_verified=false，不认领前缀语义或ROM
字节。原失败log、错误假设和修正观察保留，source-green2是在未落盘修正前的失败重放。

## 合同、发布和使用

合同 `tools/data/menu-gfx-pointer-contract-v1.json` 固定40输入，SHA
 ec6a3d46f77fe4c3ce4a43bfb5814d8859fbc7dc891c73568403dcac53727552。
其中35输入来自捕获前plan，5个独立验真/发布依赖另行冻结，不能说捕获前已核对40个。
raw.tar只含43个原始成员；工作包另有 evidence.json、两PNG和 accepted manifest。

入口为三个CLI：build_menu_portrait_pointer_ab.py、export_menu_portrait_pointer_ab.py、
verify_menu_portrait_pointer_ab.py。构建只接受空的canonical非symlink目录，输出两ROM
及 runtime_verified=false 的 build manifest。发布只向 init/active run 的新目录写入，
完成后才出现 final/accepted；等待期间是同步运行。缺ROM/快照、身份漂移、输出冲突、
非法路径或损坏记录均失败关闭，用户文件不覆盖，失败stage保留。verifier输出JSON和
exit code，verified=false/errors不是空数据；已有目录拒绝，不执行收据中的历史命令。

受管 final：`build/experiments/active/menu-portrait-pointer-ab/contract-20261001-v1/final/`。
永久 receipt：`notes/evidence/rom-menu-gfx-pointer-ab-20261001-v1/`。
旧样本重发另在 `notes/evidence/rom-menu-portrait-refresh-20261001-v1/`，不替换旧artifact。

复验先用 experiment_workspace init 建立独立active run，再执行：

```sh
python3 tools/run_guarded.py --summary <active-run>/verify-guard.json \
  --lock-file build/experiments/heavy.lock --cwd . \
  --min-available-mib 4096 --max-tree-rss-mib 1536 \
  --wall-timeout-s 240 --idle-timeout-s 120 -- \
  python3 tools/verify_menu_portrait_pointer_ab.py --root . \
  --artifact-dir build/experiments/active/menu-portrait-pointer-ab/contract-20261001-v1/final \
  --bank-contract
```

proposal只是离线部分合同。真实auditor CLI绑定实际manifest/evidence、record与field IDs；
结构化contract通过，完整bank门因629个未覆盖单元继续拒绝。没有变更bank-proofs或
正式typed计数，没有把旧guard、旧0.10.5捕获说成这次c16新运行。

## TDD、验证和下一步

新builder3项先在stub上失败后转绿；source13项先红，再经工作区前缀假设修正转绿；
发布/审计7项先红再绿。发布首轮GREEN中frame512模板残留造成KeyError，修正为实际
frame80后通过，原失败日志保留。最终26项通过（新23项 + 旧builder2/旧exporter1），
含实际CLI、完整源码身份、正确共享锁、零/单输入、恶意tar、resigned scope/pixels、
symlink/extra file、NO_REPLACE、重放和严格门拒绝。最终测试guard非降级，峰值约207MiB。
六个新增Python文件语法/尾随空白检查通过；仓库无专用formatter配置。旧renderer失效
artifact的原测试仍会正确拒绝，不回退旧实现；当前新重发收据实际重算/独立验真成功。
完整formal与实体硬件未跑，前者无正式晋升触发，后者仍external；未commit/push。

下一主线返回458混合池flags/slot生命周期闭包；已有旧primary证据的typed迁移留待合并
工作包，避免继续把额度切成单像素样本。本文的自然加载种子可供后续批量矩阵复用，
但未增加新的正式记录声明，也未减少unknown87,631B或旧formal的175 blockers。

## 几分钟验收

- [ ] 查看verification.json → verified=true、isolated_pointer_field_ab=true、cells_total=630。
- [ ] 查看pixel_changes → 仅(56,48)一像素按上述RGB变化；两截图其余像素一致。
- [ ] 查看partial-bank-proposal.json → record1/gfx_ptr_0一单元、629未覆盖。
- [ ] 查看auditor-integration.json → contract_ok=true，完整bank complete=false。
- [ ] 查看旧样本重发result.json → payload identical，old members unchanged，runtime_launch=false。
- [ ] 查看scratch_prefix_semantics_verified → false，不把前缀推测当成已完成逆向。
