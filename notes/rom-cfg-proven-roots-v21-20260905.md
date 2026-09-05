# CFG proven-roots V21 恢复与验收

## 任务模式与复用

复用 AGENTS.md 已登记的“固定直接分支 producer 证明的新 CFG 根与冻结基线增量”
模式及 V21 现有 exporter、独立 raw-input verifier、immutable precoverage；不另建
分类或审计链路。输入是哈希固定 ROM、producer/owner、局部 CFG 与旧 coverage；
产出是仅覆盖 current-unknown 的三条 claim，以及可独立重放的 artifact。
本轮高风险发布生命周期修复由主代理按 TDD 执行，Sol medium 只读核对接入路径。

## 恢复边界

- 当前 Goal task：`01a06ff8-6905-78c1-9c36-ad357340ec4d`，用户确认后工具返回 active。
- 恢复账户余量：81%，周期 10080 分钟；每个里程碑前读取，不高于 5% 时停止新写入。
- 唯一 run：`build/experiments/active/direct-root-overlap-cfg/root-063400-tier1-20260905/resume-20260905T052627Z/`。
  `resume-state.json`、`git-status-before.txt` 和 `originals/` 保存写入前身份。
- 正式 coverage 仍为 6,202,729 classified / 88,727 unknown；三个已验收待接入包共
  862 bytes / 18 claims。V21 草稿预计 116 bytes / 3 claims，尚不可计入 canonical。

## P1：中断发布留下 candidate 时误报成功

恢复只读检查发现 `verify_artifact()` 未区分显式 staging 验证与普通最终路径验收。
如果进程在 no-replace 发布目录后、写入 accepted manifest 前被硬终止，candidate
manifest 仍可被 CLI verifier 报告 `verified=true/contract_ok=true` 并退出 0。

先新增测试，将真实 exporter 产物的 manifest 回退为合法 candidate，模拟 accepted
收据尚未写入；要求普通验收失败，并拒绝把最终目录自身指定为 staging 的 intended
target。`lifecycle-red2-tests.log` 记录正确失败：`True is not false`，返回报告确为
`artifact_status=candidate`，`lifecycle-red2-guard.json` 为 exit 1、非降级。
首次 `lifecycle-red-guard.json` 同样 exit 1，但外层重定向未保留 guard 内子进程的断言
输出，因此保留原收据，并补第二次有断言日志的 RED；不把首份单独视为正确原因证据。

生命周期修复 GREEN 12/12；补 CLI exit=1 断言及接口文档后 refactor 回归再次 12/12，
均非降级（对应 `lifecycle-green-guard.json`、`lifecycle-refactor-guard.json`）。普通
最终路径只接受 accepted；candidate 必须有独立于最终目录的显式 staging intended target。

## P1：验收中的成员替换

随后独立 Sol 复核发现 artifact 的 payload/manifest 只有已打开 fd 前后 fstat，没有
把读取内容绑定到结束时的目录项；初始成员集合检查后增加文件也未失败关闭。发布者在
最终 verifier 后只查目录 inode，未检查成员变化。

先补三项测试，在读文件期间替换成员名、初始读取后替换 payload/manifest 或增加文件、
最终 verifier 返回后替换 payload；`member-race-red-tests.log` 记录 3 tests / 5 个正确
失败（未抛 ValueError 或错误返回 verified=true），guard exit 1、非降级。
修复复用 held dirfd，加入 opened/named 的 dev/ino/mode/size/mtime/ctime 绑定，以及
验收前后和发布最终阶段的成员集合/身份快照。它检测操作边界内观察到的替换，不声明
在工具返回之后文件系统无法再被外部修改。

成员竞态 GREEN 15/15、非降级；Sol 最终差量复核无 P0/P1。V21 已原子发布，candidate
和 official 独立验收通过，official 连续两次报告 SHA 一致。正式 payload 保持 116 bytes /
3 claims，精确边界未扩大。全部身份与 guard 哈希保存在本 run 的 `tier1-acceptance.json`，
SHA 为 `24d9090232a566f4f8b5416880182f2337b5eaf31bb6a1df598dff399b3ae7e7`。

V21 单包与四包 projection 正确 RED 均为缺少新 builder；最小接入复用现有 projector。
初次 14 项中 13 项通过，唯一失败是测试中的预估 registry SHA 漏了 canonical 原有
staged kinds；`registry-diagnosis.json` 从实际 canonical kinds 独立构造九项 active staged
receipt，正确 hash 为 `c8ffed470f28393f8a829d3312ac74083d60ae4e719d82614993d6b973fa3f11`。
修正后四包类 2/2，未重跑已通过的旧 atomize 测试。三包历史 quick fixture 改用同一
immutable precoverage，以免 canonical 晋升后重复投影 sibling 导致自失效。

本批累计 978 bytes / 21 claims，满足四包 Tier-2 门槛。真实 canonical/proof 测试已正确
RED；一次 full rebuild、proof 同步、formal 尚待完成，当前不得宣称 canonical 已晋升。

## 不声明事项

完整重建跨 owner 的 `[0x06347C,0x063480)` BL，只提升 unknown 后半
`[0x06347E,0x063480)`；旧 owner 不重复计数。opaque callees 的栈/内存副作用未闭合，
`0x06348E` 继续是 frontier，structured return 为 0。不外推自然可达、相邻空洞、
free space、编辑/重定位或续作发布门。

## 本批真实 canonical 已重建，formal 待完成

上述“canonical未改写”只描述Tier-1阶段，已由本节取代。单次重建正式得到
6,203,707 classified / 87,749 unknown / 16,891 claims / 18,664 segments，
覆盖率98.60526720682780%，四包实际净增978 bytes / 21 claims。coverage SHA-256为
`f55cebff32db536bf9847dc7dc9b147a0c8868ee37ddf4cd66187b687eba8b96`，proof为
`fad9c2b1c6cc9af8385826e1a41a2e72209ae151e8a4e4ffa6de934a7dd38a5a`。
重建guard exit0、非降级，峰值452.63671875MiB；真实canonical/proof/永久收据集成9/9。

为使干净checkout可读到验收证据，先新增缺少永久manifest时的RED，然后把原始收据
逐字节复制到 `notes/evidence/rom-post-story-four-packet-tier2-20260905/` 并固定哈希，
测试改读该目录。原实验日志保留，没有移动或删除历史失败。唯一formal在同一run中
执行，尚待最终结果；新canonical并不代表unknown为零或全局发布门通过。

提交准备还发现旧hook不识别结构化size/hash且可能验证工作树而非index；独立TDD修复
已形成 `e4b626462` 本地提交，详情见 `notes/staged-artifact-policy-20260905.md`。
ROM证据需要带上历史依赖闭包，正在以显式路径、manifest及imports生成候选清单；
仍未把工作副本结果冒充 committed-artifact 验收。

### 正式formal结果

唯一formal于2026-09-05 07:20:01Z完成，106/106 contracts、ROM gate96/96全部通过，
coverage errors=0，非降级、峰值530.18359375MiB；report SHA为
`099580ad012729bbce697779cae732ef8678a0966c2669dad51cce0f58f79f00`，guard SHA为
`735b9505208758cd009c77d9a59d84f076d47181c9f2fb920d3bd4519f80d891`。
永久收据目录已加入报告及guard，Tier-1队列归零。全局complete=false/177blockers保留。

提交闭包预检在独立index内发现64个历史artifact根的149条现代promotion格式错误，
主index未修改。32个根有proof直接verifier，21个由aggregate调用独立verifier，11个
只是gzip/raw baseline binding。下一步需独立冻结迁移证据和完整Git成员分母；不能
改旧manifest哈希或绕过hook。formal通过与committed-artifact通过仍是两个不同验收项。
