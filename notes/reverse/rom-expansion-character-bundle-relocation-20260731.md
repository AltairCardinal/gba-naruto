# ROM 扩容与角色战斗视觉变长迁移（2026-07-31）

## 结论

续作构建已从隐含的 6 MiB 边界升级为显式、可审计的 16 MiB ROM 布局。角色战斗
视觉不再只能原位修改固定长度内容：一个资源的 palette、raw 4bpp graphics、
frame/component 区、frame 指针表、animation timeline、animation 指针表现在可作为
原子 bundle 重建到扩展分区，并同步重写该资源的全部逻辑 descriptor 别名。

本成果闭合的是“格式、容量、精确指针与构建安全”。它没有把修改后全部角色的运行时
选择、相机、priority、blend 或最终像素时序等价提前标为完成。

## 统一 ROM 布局

权威布局为 `sequel/rom-layout.json`：

- immutable base：`0x000000..0x5FFFFF`，6 MiB，SHA-256
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`；
- build target：`0x1000000`，16 MiB，新增字节填充 `0xFF`；
- profile ceiling：`0x2000000`，32 MiB；
- 角色 bundle 分区：`0x600000..0x7FFFFF`，owner
  `character_battle_visuals`；
- 后续图像分区：`0x800000..0xBFFFFF`；
- 后续音频、文字和配置分区：`0xC00000..0xFFFFFF`。

`tools/rom_layout.py` 与 `tools/patch_safety.py` 会拒绝：

- 基准 ROM 哈希或尺寸不符；
- 非二次幂 target、超过 profile 上限、分区重叠或 owner 不符；
- 普通 `game_effective`/`audit_only` 补丁越过 immutable base；
- expansion 写入没有完整 partition/owner 声明；
- expansion 虚拟旧值不是该分区声明的 `0xFF`。

对白、章节脚本和 DB audit 的既有 allocator 也必须与注册分区完全一致，不能各自
维护一套可能漂移的边界。

## GBA 与 mGBA 扩容证据

Nintendo AGB Programming Manual AGB-06-0001-002-B13 第 3.2.2.1 节把
`0x08000000` 起的 Wait State 0 定义为 32 MiB Game Pak ROM 空间。用于复核的
mGBA 源码 commit 为
`d8bad14b4540f9114246c0281d74985cf81adc68`；其 GBA memory 定义同样给出
`GBA_SIZE_ROM0=0x02000000`，loader 接受不超过 32 MiB 的 ROM。

仅有静态范围仍不足以证明本机执行。`rom-expansion-20260731-run01` 把复位入口临时
跳到首个扩展地址 `0x08600000`；该 stub 从 `0x08600100` 读取
`0x4258474D`，写入 EWRAM `0x0203FFF0` 后返回原入口 `0x080000C0`。mGBA 在第一帧和
第 60 帧均读到相同 marker，PC 随后位于 `0x085CCC88`，原游戏继续显示 Bear Team
启动画面。

证据位于 `artifacts/rom-expansion-profile-v1/`：

- `manifest.json` 是仓库统一的 accepted promotion 清单，`profile.json` 保存
  本领域的完整扩容结论；
- `boot-frame-60.ss9` 是可复用验证快照；
- `boot-frame-60.png` 是同帧截图；
- `runtime-evidence.json`、`guard-summary.json` 和 `build-manifest.json`
  固定 ROM、地址、工具与运行结果；
- 资源守卫峰值 tree RSS 为 `66.44140625 MiB`，未降级、无新增 crash report、
  无本次拥有的 mGBA 进程残留。

快照随后由独立 `rom-expansion-restore-20260731-run01` 直接加载，并在零输入30帧后
再次读到 ROM/EWRAM marker `0x4258474D`；恢复帧从60推进到90，PC为
`0x085CCC80`，截图 RGB SHA-256 与原捕获完全相同。恢复运行峰值tree RSS为
`66.67578125 MiB`，`completed/0`、非降级。对应
`restore-evidence.json`、`restore-guard-summary.json`和
`restore-frame-30.png`证明该快照不是只写未读的占位文件。

该证据证明首个扩展分区上的 CPU 取指、ROM 数据读取和回到原游戏启动路径；不单独
证明每个 16 MiB 地址、任意实体卡带实现或迁移后资源的游戏语义。

## 角色视觉 bundle 作者格式

`tools/import_character_battle_bundles.py` 接受
`character-battle-bundle-import-v1` JSON。每项按 `resource_id` 与完整原
descriptor/slot rows 定位，可：

- 使用任意 1..1024 个完整 32-byte 4bpp tile；
- 使用一份 32-byte BGR555 palette；
- 新增或删除 frame、component、animation、keyframe；
- 编辑 component 的 tile、H/V flip、s16 局部坐标和 12 种已验证 OBJ 尺寸；
- 编辑 keyframe 的 frame 引用与非零 hold；
- 若省略结构字段，则逐字节保留原 component/timeline 区，包括唯一
  `0x0825A8E4=fffb0000` trailer。

构建器先生成全部 payload、内部指针和 descriptor redirects，再一次性通过
immutable-base、allocation、重叠和旧值门禁。任何 tile/frame 越界、来源哈希失配、
重复 resource、分区溢出或未知精确指针都会在写输出 ROM 前拒绝整项计划。

## 全量容量与引用审计

`artifacts/character-battle-bundle-relocation-v1/` 保存全 250 资源的无修改迁移
spec、`relocation-audit.json` 和 accepted promotion manifest，不保存可重复生成的
完整 ROM。结果为：

| 项目 | 结果 |
|---|---:|
| resource | 250/250 |
| logical descriptor slot | 342/342 |
| frame | 2,004/2,004 |
| component | 2,190/2,190 |
| animation | 784/784 |
| keyframe | 3,187/3,187 |
| 4bpp tile | 60,430 |
| bundle bytes | 2,020,612 |
| partition remaining | 76,540 |
| aligned semantic reference | 3,815 |
| unknown external reference | 0 |

唯一额外精确数值位于 file `0x446CC8`：它恰好等于 resource 117 graphics 指针
`0x08220E80`，但该四字节处于严格 LZ77 record
`0x4414E4..0x4491D8` 的压缩负载内；该 record 自身由 `0x5A8014` 的对齐指针引用。
因此它被单独登记为 `pointed_lz77_payload_coincidence`，不是需要重写的指针字段。
任何不在被指针引用的严格 LZ77 payload 内的额外匹配仍会失败。

独立验证器不导入 importer/exporter，重新读取 base ROM、layout、catalog 和
author spec，重建所有 bundle、内部指针、342 个 descriptor 和整个 16 MiB 输出；
最终 ROM SHA-256 为
`8ad97b9f3ab623d487fc6aa17d3bc9caaeb7fb0d17302801b46f4ef1cc6fca22`，
`errors=[]`。重签 manifest 后篡改压缩负载巧合的来源位置也会被拒绝。

tracked 全量迁移 spec 是“原样保持”审计输入，只允许
`character-battle-bundle-import-v1`、空 `edits` 和固定审计元数据；即使同步重签
spec SHA，向它加入 `frames`、`animations` 或 `palette_file` 等作者字段也会被
独立验证器拒绝。任意作者编辑能力由 importer 的正反测试验证，不能借全量
preservation 审计替代具体编辑语义测试。

## 复验

```bash
python3 -m unittest \
  tests.test_rom_layout \
  tests.test_patch_safety \
  tests.test_import_character_battle_bundles \
  tests.test_character_battle_bundle_relocation_audit -v

python3 tools/verify_rom_expansion_profile.py \
  --manifest artifacts/rom-expansion-profile-v1/manifest.json

python3 tools/verify_character_battle_bundle_relocation_audit.py \
  --artifact artifacts/character-battle-bundle-relocation-v1
```

全量迁移导出与独立验证均经 `tools/run_guarded.py` 的 shared heavy lock 执行，
最近一次峰值 tree RSS 分别约 `94.84 MiB` 和 `53.77 MiB`，均为
`completed/0`、非降级。

最终相关回归覆盖 ROM layout、安全门禁、扩容 probe/快照恢复、角色 bundle、
既有 palette/graphics/structure、地图、特效、regular BG、菜单立绘、编辑器构建
隔离、legacy patch 防护和 artifact promotion 门禁，共 107 项，均通过；回归
峰值 tree RSS 为 `145.83 MiB`。
