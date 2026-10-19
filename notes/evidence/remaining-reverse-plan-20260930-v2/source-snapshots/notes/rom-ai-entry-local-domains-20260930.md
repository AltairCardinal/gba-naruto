# AI 入口局部值域与下一闭包（2026-09-30）

状态：只闭合固定局部谓词，不证明完整scorer索引域，promotion=0、keep_unknown。
继承`notes/rom-ai-config-writer-preflight-20260930.md`的source/writer预检。任务模式为
已有instruction-only owner中的有限消费者窗口与状态依赖预检，按AGENTS优先复用
脚本完成，未调用子代理。已有v2直接BL分母与planner extractor可复用，无需重新
扫描同一目标或另建decoder；缺口是生命周期与跨callee不变量，不能靠读取表内容填补。

## 操作入口与可复现输入

```sh
python3 tools/analyze_rom_ai_entry_domains.py --root .
python3 -m unittest tests.test_analyze_rom_ai_entry_domains
```

成功输出JSON：三个局部域、原始指令及owner、未闭合义务；verified=true仅指固定输入
和这些局部检查通过，promotion_bytes恒为0。文件缺失、输入摘要或指令owner变化时
返回非零和错误JSON，保持keep_unknown。离线命令无加载页面、权限申请或游戏入口；
输入错误不会改ROM或账本。scorer域未闭合时不产生可晋升的claims。

- ROM固定`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- owner来自永久哈希固定的最新coverage-after archive，raw SHA为
  `b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2`；
  不读取mutable canonical，后续新增claims不会令此预检自失效。
- planner完整函数继续复用既有hash-gated `extract_battle_ai_planner.py`。
- 四个窗口及重新聚焦的secondary窗口、formation fallback原字节来源、RED/GREEN、
  内容重放和最终report保存在`notes/evidence/rom-ai-entry-local-domains-20260930-v1/`。
  线性解码会跨literal并可能提前停止，不能从截断窗口声称后半段无指令；本次保留
  首份secondary截断输出，并重新从742EE聚焦获取实际7434E调用。

## 入口证据及范围

| 路径 | 已验证局部操作 | 独立谓词的配置域 | 不能外推的内容 |
| --- | --- | --- | --- |
| 主producer7425A | 74240比较FF、74242相等跳过；74244比较0、74246非零选中 | 1..254 | 非“<=7”，且未包含循环耗尽路径 |
| 次producer7434E | 74306/74334筛CC==1，74314/74340筛C0&70==0 | 任意u8 | 这里没有CD值域检查，不能沿用主路径的FF门 |
| planner851F8 | 8521E比较CD==0，非零进入正常准备 | 1..255 | 不是scorer全局域，中间有复制/业务callee |

主producer74250的`BLS 74212`在r5增到13后会落入74252；次producer74322的`BHI
74346`也允许耗尽出口落入调用准备。不能只沿“成功挑选单位”的分支证明planner
永远收到槽1..12。74254/74348调用67158后才传r5给planner，RAM/CD保持及callee行为
仍缺证明。这里指出静态义务，不声称自然执行会选择槽13或触发表外读。

已复用的v2原始固定target Thumb BL扫描覆盖整个6MiB ROM，851F8目标记录两个直接
BL：7425A、7434E。payload SHA `a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba`，
manifest SHA `a3683f3d21ec5a162b4cdb97c70b639ff261d9ff5e0f3bb4941848205bb4d9ca`。
本工具明示raw_scan_replayed_here=false，是哈希固定历史分母引用，不能冒充新扫描。
B/Bcond、ARM、指针注册、computed入口与scorer84274的完整incoming分母仍开放。

## 固定内容给出的下一步线索

复用positions extractor的1728条矩阵：仅按ROM内容与selector的wrap-u8分支条件分组。
普通source且raw affiliation=1共211条，raw+0E分别0:3、1:162、2:11、3:4、4:10、
5:3、6:12、7:6；另一24条affiliation=1属于FA/FB/FC特殊路径，raw+0E全部FF，但
该分支的实际CD来自5411E4+lookup*AC+2，不能把source+0E当writer结果。
FD/FE/FF路径123条仍为raw affiliation0、raw+0E FF。

formation6E2E0..6E324显示普通affiliation非0直接调用6ACAC；affiliation0先按模板
寻找，找不到才调用6ACAC。结合前次6AD6E/6AD90写入点，有条件解释普通敌方数据
为何符合0..7，但本次不证明矩阵index域、raw affiliation等同实时CC、callee保持、
模板/特殊lookup来源或之后状态变更。内容重放两次一致，不增加canonical字节。

## TDD、独立核对与维护

先5项RED确认入口缺失，再最小实现GREEN。追加owner显式非指令标志RED，修复
失败关闭；追加历史BL分母字段RED后复用固定输入引用。最终7/7测试通过，包括
真实archive/ROM集成、连续CLI输出一致、改ROM失败关闭、consumer slice或显式
instruction_only=false不能替代指令owner。格式diff检查及两份Python源码编译通过。

公开输出明确只检查局部谓词，不是独立raw CFG verifier、生命周期证明或待晋升包。
后续扩展必须冻结新增入口的指令/producer/writer证据和失败关闭测试；不能把这个
verified=true拿去绕过CFG或table完整索引门禁。

下一完整里程碑：复用851F8历史direct-BL分母，补84274与initializer的其他incoming
模式、slot13出口、67158及中间callee副作用、所有CD writer/copy/inherit与控制状态。
闭合后才冻结8行AI候选或5411E4记录的消费分母；失败则继续keep_unknown并转到下一
个已有消费者锚点的簇，不扩张任意RAM may-read包。

## 验收清单

- [ ] 运行入口命令 → 三个局部域如上，decision=keep_unknown、promotion_bytes=0。
- [ ] 检查primary/secondary窗口 → 主路径有FF检查，次路径筛CC而非CD。
- [ ] 检查loop出口及deferred_obligations → 槽13及callee依赖仍显式列出。
- [ ] 运行7项测试 → 全通过；检查永久manifest → 输入及实现摘要一致。

后续67158依赖调查见`notes/rom-ai-renderer-script-dependencies-20260930.md`：
它是已有渲染命令解释器，两条preplanner的固定参数流已复用原始helper重放。
脚本语法可复用，等待帧/callee状态保持仍开放；后段两个literal点因缺指令owner
被排除，未放宽原入口检查或增加canonical bytes。

后续固定五目标raw编码分母与槽13别名已核对，见
`notes/rom-ai-producer-and-pool-alias-20260930.md`。直接/条件Thumb、ARM和精确
字样分母可复用，但computed入口保持开放；slot13实际对应extra pool slot0，
clear函数只识别byte0与wordD0清理，不提供CD==0，需追踪extra池复制生命周期。
