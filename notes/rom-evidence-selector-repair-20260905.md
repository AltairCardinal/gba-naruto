# ROM evidence selector 修复（2026-09-05）

当前：canonical/proof已采用，完整formal已通过，尚未完成committed-artifact验收。
这是历史artifact迁移独立检查发现的真实元数据修复，不增加任何ROM分类字节。

## 问题、边界与修复

四个fast-audit包把临时projection的序号写为 `/packet_records/N`，但原JSON不存在此键。
按原始数组分别改为 event 的 `/promotion/semantic_ranges/N`（40条）、sprite 的
`/classified_ranges/N`（4条）、V16代码的 `/promotion/ranges/N`（21条）、V16 literal的
`/promotion/claims/N`（51条）。V10另外7条代码claim误将基本块序号用于只有两项的
`code_ranges`：前两项错误指向合并区间，其余5项越界；改为实际匹配block的JSON路径。

共123个selector变化。所有claim的其余字段、排序、range、bytes_sha256、summary、segments
逐项保持一致：6,203,707 classified /87,749 unknown /16,891 claims /18,664 segments。
全部旧artifact及manifest原字节保持不变。168个指向verifier源码的selector属于报告域，
另有独立报告哈希和执行合同，不在本次JSON payload修复范围内。

proof同时更新coverage摘要、auditor摘要，以及两个历史gate的 `sequel/project.json`
单字符错误摘要。它们只绑定真实现存输入，不能由此宣称editor/clean rebuild已完成。

## TDD、复现与当前证据

- 新投影测试RED：3项，2个failure+121个error，恰好覆盖123个错误引用；非selector字段
  一致性检查通过。GREEN：3/3，重放真实四包与V10独立verifier，约150秒、非降级。
- 当前canonical/proof绑定RED：两项3failure+121error；采用后6项集成测试通过，包括旧四包
  字节分母、hole、proof183 evidence/96 command及新selector的实际range。
- 旧里程碑收据绑定的是修复前canonical。将它误与未来live canonical比较的测试已RED复现，
  现改为核对永久 `coverage-before.json.gz` 和 `proof-before.json`。旧收据manifest未改写，
  当前proof另由独立测试继续绑定live canonical。
- 全量selector扫描：10,419个JSON指针可解析，无JSON artifact指针错误；其余168个报告域
  selector单独保留，不以解析Python源文件的失败推导语义问题。

当前SHA-256：
- coverage `1c6af01a54f3522ba277a4744b5b821d53588b853b3e7755902c65431df584b6`
- proof `c2862ea520a39432c94fa2634f2ae5650077738c9474aa96ca15d387a4857cbb`
- auditor `e4c1f07efd2673d9229da8a7532d7874e615cbf1d7705ccd32171558df028509`

永久证据：`notes/evidence/rom-evidence-selector-repair-20260905/manifest.json`；其中旧前态、
源码before/after、RED/GREEN、准确123项差量均有文件摘要。实验与恢复状态位于
`build/experiments/active/evidence-selector-repair/fast-audit-20260905/`。

full formal使用同一heavy lock、idle7200s/wall10800s、无降级；它内部完整重建coverage并
复用该audit结果执行structured contracts。采用candidate后的静态测试不能代替这次验收。
正式结果为106/106 contracts、ROM96/96、coverage errors=0；运行08:40:40Z–09:21:38Z，
非降级，峰值525.7109375MiB。报告/guard摘要为
`aa125c7e80ea4364522698c04557b3d6a819f77000c28c58871bc74cf13938bc` /
`3e1722f8979fa68723acf3e5940cf7eacd5beaabde6d19c2c14bf277a6736c54`。
global complete=false /175 blockers；两个错误project摘要对应blocker已消除，剩余门如实保留。
永久证据追加了after覆盖快照和proof、原始formal三件及旧manifest前态，支持独立历史差量测试。
Goal继续active，不得使用失败candidate-v3或旧formal替代本次结果。
