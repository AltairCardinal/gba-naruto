# ROM 字节级语义逆向当前交接（2026-09-05）

## 最新恢复点：验收包A已提交且clean checkout通过，历史闭包B待提交

`notes/rom-evidence-selector-repair-20260905.md` 是本轮最新状态。canonical已修复123个
JSON evidence selector；coverage为1c6af01a…df584b6、proof为c2862ea5…4857cbb，数值仍为
6,203,707 classified /87,749 unknown。3项投影测试和6项采用后集成测试通过；所有JSON
artifact selector可解析。两处project.json摘要拼写也已修正。旧before和失败收据均保留。

完整formal已在 `build/experiments/active/evidence-selector-repair/fast-audit-20260905/`
成功结束，session84261已关闭。08:40:40Z–09:21:38Z，106/106 contracts、ROM96/96、
coverage errors=0，非降级，峰值525.7109375MiB。global complete=false，175 blockers。
新永久报告/guard位于 `notes/evidence/rom-evidence-selector-repair-20260905/`，SHA分别为
`aa125c7e80ea4364522698c04557b3d6a819f77000c28c58871bc74cf13938bc` /
`3e1722f8979fa68723acf3e5940cf7eacd5beaabde6d19c2c14bf277a6736c54`。
当前余量74%，主index为空，HEAD为`47d9a60e668a5c3fe6e1123524864d21a2c93545`。
正式新结果无需再重复执行。

新的candidate-v4固定282输入、64根/160成员，32/21/11证据桥梁；独立验真和源文件
逐字节重建均成功。完整包身份与64根分母已填入contract，现代验收包已promote并作为A
提交（91文件）；AGENTS只提交本轮新增模式，原有改动仍未暂存。53项最终集成通过；A的
干净detached checkout另有48项测试和独立bundle verifier通过，报告SHA均为
`42e1d5628834efdf871a175d20feeba66d915b63daae66d669ac710f9821577c`。
`notes/legacy-artifact-acceptance-20260905.md`与合同文档记录全部身份和失败candidate-v3。
新提交run为`build/experiments/active/committed-artifact-acceptance/post-selector-repair-20260905/`，
其`clean-checkout`当前位于A；B仍有约807项相关变化待最终范围/门禁验收。恢复时先核对
`commit-b-existing-changes-tests-guard.json`实际状态，不启动重复heavy任务。
本仓库无持久hook，本次A/B用`git -c core.hooksPath=.githooks commit`显式启用现有入口。
下文旧106/96结果仅是修复前历史收据。

## 当前恢复状态

- 当前 Goal task：`01a06ff8-6905-78c1-9c36-ad357340ec4d`，用户确认后为 active，目标
  `unknown_bytes=0`。恢复前仍须实时读取 Goal、账户余量、存活代理、Git 与 heavy lock。
- 2026-09-05验收包A提交前账户 `usedPercent=26`，可验证余量74%；不高于5%时停止
  新逆向写入并保存恢复状态。未使用 reset credit，未获 push 授权。
- 逆向工作树 `/Users/altair/github/gba-naruto-reverse`、分支 `codex/reverse-engineering`。
  Butano 工作树未触碰。主代理唯一 writer；Luna/Sol 在本轮只读分析和复核。
- 原 Goal 暂停时76,122,071 tokens / 884,320秒，仅作历史计数，不能与当前 Goal 用量
  混合或伪造逐模型明细。旧交接全文保留在下述 run 的 `.before-tier2-doc-update` 文件。

## 权威 canonical 与当前验收

| classified | unknown | claims | segments | 分类率 |
| ---: | ---: | ---: | ---: | ---: |
| 6,203,707 | **87,749** | 16,891 | 18,664 | **98.60526720682780%** |

- ROM：6,291,456 bytes，SHA-256
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- coverage SHA-256：
  `1c6af01a54f3522ba277a4744b5b821d53588b853b3e7755902c65431df584b6`。
- proof SHA-256：
  `c2862ea520a39432c94fa2634f2ae5650077738c9474aa96ca15d387a4857cbb`。
- 本批四包已真实接入：fixed-index u8 tail 4B/1claim、story-selector dependency
  80B/1claim、task callback078E38 closure 778B/16claims、V21 116B/3claims。
  净增 **978B/21claims**，不是旧 canonical 加估算。CFG aggregate 为956 ARM、
  173,058 Thumb code bytes、174,046 promoted bytes、4,059 claims、54 kinds。
- coverage guard于06:01:04Z–06:32:46Z成功，exit0、非降级，峰值452.63671875MiB。
  真实canonical/proof/持久收据集成9/9通过。
- 修复前历史formal已成功：106/106 contracts、ROM gate96/96、coverage errors=0，
  06:38:31Z–07:20:01Z，非降级、峰值530.18359375MiB。完整报告仍为
  incomplete / 177 blockers。Tier-1队列归零；committed-artifact门仍待历史格式迁移。
- formal report / guard SHA-256：
  `099580ad012729bbce697779cae732ef8678a0966c2669dad51cce0f58f79f00` /
  `735b9505208758cd009c77d9a59d84f076d47181c9f2fb920d3bd4519f80d891`。
  这次历史run已结束；当前修复后的新formal已通过，见本文最新恢复点。

本批 run：
`build/experiments/active/direct-root-overlap-cfg/root-063400-tier1-20260905/resume-20260905T052627Z/`。
永久收据：`notes/evidence/rom-post-story-four-packet-tier2-20260905/`，manifest逐文件绑定。
新集成测试读取永久路径，不依赖被Git忽略的实验目录。

## V21 的证据与边界

复用固定direct producer + bounded CFG模式，root063400，70 instructions、17blocks，
144 full code bytes、4 literal bytes。只接受06108A producer；06131C的coarse
consumer_code_slice不能作为instruction membership。旧owner切过06347C的BL，完整
解码后只晋升unknown后半；净112code+4literal=116bytes。06348E间接frontier保留，
structured return=0；不证明opaque callee栈/内存副作用或自然运行时可达。

- manifest SHA：`b9625a5e45c66bc510deb2a83ceb01882c6ef4fd381ef28fc499d83ec2680f62`。
- payload SHA：`4dba6f7d880a790d92045d838eb78dd253f512d8d3a42b2c3858acf1187c1f9c`。
- verifier SHA：`6d20f681fdd033f2ce25a10ef4d512bc898c9a4b7f97d40adf75f0f3d9a59c7d`。
- 两次稳定report SHA：`4611b27fc0bc643f1de3062f75adf7c52de2e1d51b1fcee1f2078058d88003c8`。
- 本轮按TDD关闭candidate误验收及成员替换竞态两个P1，packet15/15；原始失败日志保留。
  完整经过见 `notes/rom-cfg-proven-roots-v21-20260905.md`。

## 提交闭包与恢复下一步

1. 首先实时检查Goal/账户/代理/Git。恢复点 `resume-state-after-tier2.json`，独立index
   `candidate-index-v2/v3`只保存失败预检；主index仍为空。不要将其直接复制到主index。
2. 当前ROM证据提交闭包候选为2,631文件，其中756变化（731新文件+25修改）；均有
   claim/proof/manifest/import引用来源。32-bank动态路径已显式补入，231个未解析token
   经只读核对是fixture/可选输入/推导测试名等，不能盲目创建对应文件。
3. `candidate-staged-policy-v3.log`记录64个历史root/149errors：schema42、status27、
   verifier现代收据64、库存格式16。现有证据桥梁分为32个proof直接verifier、21个
   aggregate调用独立verifier、11个仅绑定gzip/raw baseline。最后一类不能叫每根语义verifier。
4. 必须先冻结历史迁移合同：保留旧manifest原SHA，固定完整成员路径/mode/size/SHA；
   分别绑定直接command/script/contract、aggregate每包verifier/report或baseline原始身份。
   新机制必须TDD、独立verifier、staged Git objects验真及父级复核。尚未实现任何豁免；
   不可改旧manifest哈希伪造modern receipt，不可绕过hook，也不可把任意allowlist当语义证据。
5. 门禁修复已提交`e4b626462`，11/11集成测试通过，独立差量review无新增P0/P1。
   只在迁移和最终路径/hash快照验收后，按精确changed paths提交ROM证据。路径清单包含
   未变tracked依赖，stage时只选实际变化，避免既有ignored目录的无关pathspec拒绝。
6. 更新后的notes和formal收据会使旧v2清单部分哈希过期；最终提交前生成新编号快照。
   旧scene-source precoverage的test生产哈希与当前archive重放测试不同，这是已记录历史
   转换；不可改历史manifest伪造生产身份。两个既有全局gate中的sequel/project.json
   旧hash一字符差异已在selector修复包关闭，并由新的formal重新验收。
7. 本地提交只在相关闭包范围内，push仍需单独授权。保留全部用户已有修改与失败收据。

## 下一批候选（均未晋升）

- 三短入口07ADE8、07B89C、09C12C：21instructions、46code+8literal=54B，5claims
  候选；两个2-byte holes继续unknown。已核对15个已知producer子集与两个opaque
  target的精确artifact块；仍需guarded全ROM target-limited producer分母和新冻结baseline。
  Luna max只读尝试未返回可验证结果后中止，Sol medium完成机械核对。
- dispatcher07DCB8：consumer上界#0x13提示20slots，既有table只认领19slots；候选
  prefix26code+4literal、末slot4B及新target6code=40B。需完整raw dispatcher/index
  及opaque目标边界合同，不能改写旧19slot证据或吞2-byte hole。
- callback07B8B8：pointer07C634→consumer07C612→call07C61C→registrar061D8C，
  callback/arg写入061DC0/061DC6，在061C68/061C6A读取并由061C6C→09C114的BXr1
  调用。但小窗无法证明[r6+1]为二值，固定slot2/3及wrapper索引域仍未闭合；入口仅58B
  候选，不能把整个2088B包络晋升。
- 53F89C..541368与54136F..542204两个大段没有可冻结consumer/index，零比例、伪LZ77
  头或0xAC步长形态不能分类。训练表和低脚本池同样必须补实际索引/字段写入域。

候选细节和read-only报告在同一run的 `next-candidate-scout.json` 与
`candidate-review-followup.json`。下一包仍以脚本优先；公开合同完全冻结后才交Luna max
小包，Luna不适用的可拆只读任务用Sol medium，本体负责最终证据链和验收。

“100%”只表示每字节都有可复验分类且unknown为零，不等于全部动态业务命名或续作发布
门全部完成。当前仍有87,749 unknown，本Goal未完成；后段缺少充分样本，不新增工期承诺。
