# 六组 CFG 来源语义 verifier 实际重放

## 任务模式与范围

复用“固定producer/消费者闭包的已有独立verifier重放”模式，以脚本串行执行。
输入为前轮92site来源矩阵及其绑定的artifact/manifest/verifier身份；同一heavy lock，
每组wall180s/idle120s，不启用降级，不运行canonical rebuild或全量formal。

## 实际结果

| 来源 | 调用点 | 结果 | 采样最大RSS MiB |
| --- | ---: | --- | ---: |
| inventory-v2 | 50 | verified=true / exit0 | 139.1 |
| inventory-v3 | 14 | verified=true / exit0 | 150.7 |
| roots-v6 | 12 | verified=true / exit0 | 178.2 |
| roots-v17 | 2 | verified=true / exit0 | 235.8 |
| roots-v18 | 12 | verified=true / exit0 | 243.2 |
| battle-controller | 2 | verified=true / exit0 | 76.2 |

六组全部errors=[]、non-degraded。历史来源的语义复验已完成，不再是下一显示文本包的
未验证依赖；不代表该包的92个新source参数路径或85条记录已经Tier-1通过。
下一步可统一绑定这些receipt后，冻结literal-to-66758/667A0桥接及6626C显示边界合同。
命令脚本67158的旧delta合同仍不能用于显示文本；公共发布/投影能力可以复用。

## 首轮采集失误与修正

首轮harness把run_guarded stdout当成child报告，而guard默认不转发child stdout。
因此首轮result.json中verified=false是无效采集分类，不是三个source语义失败结论；
v2/v3 guard实际exit0，v6直接CLI exit1且未捕获traceback，不能推断具体原因。
修正为PYTHONPATH=.的CLI上下文及明确child输出重定向，使用全新attempt2目录，保留
首轮所有文件。修正后每组同时核对guard、child JSON、exit status与errors字段。
不是功能TDD的红绿证据，也未修改生产工具来迎合失败。

## 证据与边界

[完整封存receipt](evidence/rom-renderer-source-replay-20261001-v1/)包含两个harness版本、
首轮记录、attempt2逐组child报告/guard/stderr及result.json。原始guard和child报告独立保存。
没有为了稳定报告重复六组审计；验收不涉及瞬时字段绑定新claim。
unknown87,631B、175 blockers、正式Tier-1队列1包/1,668B保持，promotion=0。
生产功能测试、CLI新实现集成测试、mGBA/硬件与formal未执行；未提交或push。
