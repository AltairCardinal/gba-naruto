# Butano 持久被动属性重算运行计划

日期：2026-07-27

## 里程碑

1. 哈希绑定 `0x0806D964`、24 槽循环、定义表、双 pass 顺序和 flat jump table。
2. RED：缺失领域 API；已训练 HP 被动加载后仍是纯等级 HP；容量被动不能扩大整备容量。
3. GREEN：抽取统一持久被动重算，接入 progression、scenario loader 与 campaign 整备。
4. 修正覆盖矩阵，把 targets 1–11 从“无直接消费者”改为“函数内联属性消费者”。
5. 回归全部宿主 C++、Python 证据测试、格式检查、devkitARM 和受守护静音 mGBA。
6. 同步领域记录与路线图；不自动提交，不宣称非静音音质已修复。

## 验收标准

- 同时存在百分比 HP 和固定 HP 被动时，先百分比、后固定加值；
- targets 1–11 的字段、公式、上下限与 ROM jump table 一致；
- progression 中已学习的被动经真实 scenario loader 改变战斗实例及 `base_*`；
- 忍具容量被动经 campaign service 改变容量判断，但不越过九格物理装备数组；
- 锁定、未学习和空槽不生效；
- 本切片验收时覆盖矩阵报告 35 条已有 ROM 生产消费者、10 条尚未闭合；后续动作修正
  里程碑将其更新为 44/1；
- ARM 构建与静音运行无 crash/trap；静音路线只作结构回归，不签发音频验收。
