# Cutscene ID 1 secondary_ptr：隔离 ROM 与自然路径观测

## 当前阶段

已完成 A/B 输入构建、独立 raw 构建核对和五份真实 mGBA 捕获。
单输入路径观察到“胜利”字样的白色描边变为青色，778 个像素变化。
只有 PRAM 0x05000382 的一个字节 FF→E0，IO/VRAM/OAM/IWRAM/EWRAM 五域完全相同。
基准 RGB SHA 051162ea...be7bc8 与已验收 primary_ptr 旧基准一致。
三份零输入对照的六个内存域和 RGB 完全一致，尚未按键时 candidate 无额外影响。

**独立运行时语义 verifier、篡改测试及正式 artifact 发布仍待完成。** 本条是捕获观测，
不能提前将该字段写入正式 coverage，也不是 8×2 字段穷尽验收。第一表图形/调色板与
第二表 definition/animation 分开，实体 GBA、其他 ID 和编辑器入口都没有本轮验证。

## 可复用输入工具与 TDD

在已 init 的新受管 run 内构建输入：

```sh
python3 tools/build_cutscene_obj_secondary_ptr_ab.py --root . --output <active-run>/build
```

工具只接受空的、canonical 且不经过 symlink 的输出目录；已有内容拒绝并保留。
缺源文件、旧父构建身份漂移、布局所有权或碰撞错误时 exit 非零，不产生成功 manifest。
成功输出 build-manifest.json 和两份 ROM，runtime_verified=false；构建过程中等待结果。
这是开发工具，没有新增游戏菜单。ROM 是实验输入，不能当作已发布续作功能。

复用 build_cutscene_obj_id1_pixel_ab 的完整生产 relocation，而非另建资源编码链。
父 ROM 固定 4da5caf8...33c16，父 manifest 固定
34e8cf88ed9d57ff6a6e5c4148d3a3af8f055c50923b7e62f0e369e3dc356e3f。
复用 encode_gba_lz77、RomLayout、ImageResourceRegions、PatchSafetyGate 和 apply_patch。
从冻结的全部父 allocation 算出末端，再登记新 palette allocation；重放全部父 allocation
到同 gate 防碰撞，登记分区/region 验证边界，不凭原 ROM 中的 FF 认领 free space。
新流两份 ROM 都有，candidate 仅替换 0x53DF7C 的 ID 1 secondary_ptr，避免把数据改动
混入指针因果。旧 parent/build/export/verifier/manifest 全部保持原样。

3 项新测试先在未实现 stub 上失败，再最小实现转绿；首个 GREEN 因 macOS /var→/private/var
临时路径不满足 canonical 输出要求失败，日志保留。fixture 改为 resolve 后的路径，
保持生产 symlink 拒绝规则，第二次 GREEN 通过。检查后无需额外重构，最终相关 8 项
测试含真实 ROM、真实 CLI、非空/symlink 保留、旧 primary/parent 构建回归全部通过。
独立 raw 检查复用旧 verifier 的独立 _lz77，而非 builder parser；清除唯一新 allocation
恢复父 ROM 精确 SHA，恢复唯一 pointer 字段恢复整个 baseline，palette 仅 color1 改变。

## 固定地址与身份

- 源 ROM：1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b。
- baseline：762ea6794d93eb7bac79f2d1ccd58bfe8f67a625d3ff4be2aff2ddf8aefa5816。
- candidate：76974bcda32477926fe2397b4a48b87bdf956eacc5af7db4f41966026ce67c9d。
- 两份均16MiB，只在0x53DF7C/0x53DF7D不同；旧pointer 0x08BA1664，新pointer 0x08BA1FF0。
- 新 allocation：[0xBA1FF0,0xBA2006)，22B压缩流→32B palette，color1 0x7FFF→0x7FE0。
  region=cutscene-obj-bundle，owner=cutscene_obj_resources，在登记的 BA0000..BB0000 内。
- 输入快照 scenario-41-combat-popup.ss9，SHA 01f478cf...300a，实际版本0x01000007。
- c16 mGBA binary SHA ef2386a5...d54b；固定 Lua zero/input 两脚本身份及所有 repository
  输入完整 SHA 在 runtime receipt 的 repository-input-identity.json。
- 按键唯一 A，down5/up13/capture512；zero 基准两次、zero candidate 一次、input 两份。
- candidate RGB：a279454f9ea1f124e9522cdcfa3e8372cd06977474751645d384b5713139f41c。
  bbox inclusive=[42,49,195,110]；各域差异和三零输入一致性见 semantic-observation.json。

## 动态库失效、恢复和采集错误

第一次启动在 DYLD 阶段因 @rpath/libmgba.0.11.dylib 缺失 SIGABRT，未执行 Lua/ROM。
guard 记录 mgba-crash-report/125，写全局 latch，原始 IPS 和 latch 已复制到失败 run。
停止扩张实验，核对缓存库：source tree clean、git HEAD 和库导出的 gitCommit 都是
c16c3ff55585e71bee83c95539c2ecde15d728c8，ctypes dlopen 依赖测试通过。
缓存库 SHA 0f84fde81a26843207dcac5080da014e38fa0d66726498bc3a6b6d6b5c925b0b。

只对本次进程设置 DYLD_LIBRARY_PATH 为已核对的缓存 build 目录，没有修改 binary、
rpath、系统库或旧 manifest。确认未处理报告只有本次 owned 报告、PGID 无残留后，
在 heavy lock 下调用现有 clear_crash_latch 审计接口，保存 history 和更新基线。
不直接删除 latch、不关闭崩溃报告、不改资源守卫，不用 current-desktop d8 profile
冒充 c16 身份。acknowledgement 只处理已归因崩溃，本身不是新 runtime 证明或权限来源。

恢复后的首个 zero 已由 guard 成功捕获，但采集脚本误用了 validate_completion_marker
及 zero bundle API 的签名，后处理退出。原脚本/日志保留，capture-v2.py 修正调用，
复验该已落盘 zero 的 marker、audit、sentinel、state、PNG 与 staged ROM，不重启它。
随后四份 fresh run 均完成。五个 guard 均 success-marker/exit0/非降级，峰值约60.1MiB，
所有 owned PGID 和 listener 检查通过，未新增 crash，source ROM 无 .sav sidecar。

## 持久产物与下一步

[永久 receipt](evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/)包含三个独立受管 run：
build-20261001-v1、首次失败 runtime-20261001-v1、成功 runtime-recovery-20261001-v1。
保存 TDD、构建 manifest、独立 raw 结果、失败/修复证据、全部五份 raw state/PNG/audit/
sentinel/guard/launch、方法脚本及输入身份。16MiB派生 ROM 可用 builder 重建，不重复
纳入永久 receipt；source managed 路径和精确 SHA 保留。

下一包一次完成独立 verifier、resigned raw/manifest 变异、bank 单元 IDs 合同和受管
发布。runtime report 的 semantic_verification_pending=true 不能先改成已验收。
在同一库身份下继续已有快照，库缺失或新崩溃再次失败关闭。未重跑全量 formal，
canonical/proof/bank-proofs 不变，unknown87,631B、175 blockers仍是旧正式事实。
没有 commit/push，也未向 Butano 复制未提交材料。

## 几分钟验收

- [ ] 查看 semantic-observation.json → 778像素，仅 PRAM offset0x382 一字节变化。
- [ ] 查看三份 zero observed.json → 六域/RGB SHA相同，均inputs=[]。
- [ ] 查看 build manifest → 唯一secondary_ptr变更，runtime_verified=false。
- [ ] 查看五个 guard/residue → completed/0/success-marker、非降级、owned PGID clean。
- [ ] 查看失败 IPS/preflight/recovery audit → DYLD原因、同commit库、留痕清除及新run。
