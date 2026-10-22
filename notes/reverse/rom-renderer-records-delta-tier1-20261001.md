# Renderer旧语法记录的受管合并增量包

本包合并12B和1,656B两批同合同记录，从ROM与已接受CFG重新构建，原12B包不作为
可信输入。唯一候选输出位于
`build/experiments/active/renderer-records-delta/combined-tier1-20261001-v1/final/`。
不直接生成artifacts，不覆盖原包、历史源码或manifest；未到Tier-2门槛暂不promote。

## 模式、复用与可见入口

复用“固定后续CFG字面量消费者的批量筛选与旧语法记录预检”及公开冻结packet模式，
以可复现脚本执行。生产实现沿现有fixed-consumer链追加：复用renderer/training parser、
两个独立参数流实现、来源raw verifier、FD锚定I/O与已测试的atomic no-replace primitives。
没有新opcode、新解释器或另一套导航/状态管理。

不能直接修改旧包：41site/1124B合同及后续12B历史收据固定了分母与源码身份。
新的29record以同一public contract和受管入口维护，避免两个相近publisher继续分叉。
独立verifier不导入新producer，分别重建47site；producer用training parser，verifier用
renderer parser。共享的是冻结输入/元数据约束，不能以共享assembler代替原始输入重放。

入口是离线CLI：

```sh
python3 tools/export_rom_renderer_records_delta.py --root . --output build/experiments/active/renderer-records-delta/combined-tier1-20261001-v1/final
python3 tools/verify_rom_renderer_records_delta.py --root . --artifact-dir build/experiments/active/renderer-records-delta/combined-tier1-20261001-v1/final
```

运行仍须经run_guarded并使用`build/experiments/heavy.lock`。export只接受初始化且active的
受管实验，拒绝artifacts、symlink、已存在目标和已完成实验；首次成功后重复export拒绝
覆盖，verify可重复执行。输入缺失、漂移、额外成员或语法变化会失败关闭并给出错误，
不会自动升级权限、补空记录或重新解释新opcode；失败owned staging保留用于调查。
该功能没有游戏页面或加载UI，反馈由exit code、JSON与guard/log提供。

## 冻结输入与精确边界

Public contract：`tools/data/rom-renderer-records-delta-contract-v1.json`，SHA
`59b4c53393c58fb0f3f25f78a3963908fe10984afa0e26036981dffaddc1eec6`。
固定39项输入，包括CFG/语法artifact和helper源码、FD发布primitive及immutable precoverage。
每次build/replay均先复核全部身份，之后才访问来源缓存。

- ROM SHA1198ece7…59d05b，6,291,456B。
- 来源：原v2/v3 inventory及proven-roots v1/v3/v6；来源raw verifier重新运行成功，
  不根据preflight列表猜测instruction membership。
- 目标池0..1CD0、42AB..542E、578C..7554；root必须在固定旧unknown分母中。
- 47site = 34accepted + 13excluded；29record、29claims、1,668B，两两无重叠。
  排除的2/6/7/8仍不在parser合同内，不吞并相邻prefix、间隙或包络区域。
- immutable precoverage为已归档的b568db6f…cf06d2原始coverage；包不读取mutable live
  coverage筛选root。接入后可继续稳定重放，不形成自失效环。

当前unknown的逐claim检查单独由coverage adapter执行，结果写入本轮acceptance receipt；
accepted payload/report仅绑定稳定的immutable投影，不把live phase/coverage SHA写入claim
identity。未来auditor仍须在投影前再次检查实际current unknown，不能将本轮receipt算成
未来已经完成的Tier-2验收。

不声明自然执行、全ROMconsumer穷尽、共享任务恢复、完整字符集、padding/free-space、
可编辑、回写或重定位安全。opcode6的RAM文本依赖及新handler合同仍由原预检追踪。

## TDD与发布验证

- 红：9项测试因新export入口不存在而失败，保存完整日志与非降级guard。
- 绿：真实ROM、独立重建、CLI、no-replace、manifest消费、迁移后稳定重放、self-consistent
  hash篡改、额外成员、source-cache身份漂移和精确unknown投影共9项通过。
- 补充红：skip整ROM身份的测试接口曾未拒绝671D4推进7→8变化，真实失败为
  `ValueError not raised`。最小修复固定核对interpreter/parser/SJIS的ROM范围哈希。
- 清理import/元数据读取后完整回归10项通过；随后额外验证completed实验拒绝写入，
  1项定向集成通过，无生产代码再改动。总计11项检查通过，不称一次11项完整suite。
- candidate先由独立verifier重建，再生成accepted manifest、重放、核对stage/published
  inode并atomic no-replace。只有成功报告写入清单，不预填伪造的验证结果。
- accepted manifest可搬迁重放，不绑定临时目录路径；移到artifacts前仍须按管理工具
  promote，不能以目录copy测试代替真实promote操作。

源码语法/空白、contract JSON、输入哈希检查通过；没有新增formatter配置。
未运行mGBA，因为没有runtime声明。未跑全量formal/canonical rebuild，因为1包/1,668B
低于4包/10KiB/0.15个百分点集中验收门槛。canonical仍87,631B未知、175全局阻塞；
不把预计收益相减后的85,963B当作正式unknown。没有commit或push，Goal active。

## 历史补正与后续维护

原`artifacts/rom-low-script-delta-v1/`直接写入artifacts，不满足本工作树的受管发布规则。
其TDD和静态结论可复验，但新包从raw输入重新建立这12B的证据，取代原包的待补正状态。
原包/收据保持字节身份，仅作历史，不可再次注册其12B形成重复claims；旧export入口不得
用于新发布。未来Tier-2只接入本合并包，旧正式41site/1124B包不受影响。

永久收据：`notes/evidence/rom-renderer-records-delta-tier1-20261001-v1/`。
管理run上面的final路径，完成后其metadata必须为completed；后续验证仍可读，新增实验
需新run ID。首次contract脚本的v1文件名错误尝试保留，v2冻结脚本结果为准。

后续优先增加有固定消费者/字段分母的其他缺口包，或补齐2/6/7/8完整合同，达到Tier-2
阈值再统一auditor wiring TDD、promote、canonical/proof同步和非降级formal。不能为了
凑包数拆开相邻同信任边界记录，也不能重复审计本包代替新逆向证据。

## 可执行验收

- [ ] 运行verify CLI → verified=true，47site、29record、promotion_bytes1668。
- [ ] 查看payload/exclusions → 34accepted、13excluded，新opcode仍未支持。
- [ ] 查看acceptance receipt → 两次报告相同、current unknown投影1668B，canonical未变。
- [ ] 尝试直接导出到artifacts或已完成实验 → 被拒绝，已有结果不被覆盖。
- [ ] 查看canonical → unknown87,631B，本包未被伪称Tier-2接入。
