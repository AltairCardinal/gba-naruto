# Butano 持久被动动作修正运行计划

日期：2026-07-27

## 里程碑

1. 哈希绑定 `0x0806D6B8`、双 pass、定义表、jump table 和两个动作初始化器调用点。
2. RED：领域 API 缺失；正式 catalog 未按被动修改主动技/忍具；覆盖矩阵仍把
   targets 13–19 当作无消费者。
3. GREEN：实现纯动作副本修正器，接入主动技等级物化后和忍具槽成本物化后。
4. 用正式 resolver 预览证明 catalog 修正不会在后续结算链丢失。
5. 更新覆盖矩阵为 direct query、inline stat、inline action modifier 三类证据。
6. 回归全部宿主 C++、相关 Python、格式、devkitARM 和受守护静音 mGBA。
7. 同步设计、运行记录和路线图；不自动提交，不签发非静音音频验收。

## 验收标准

- 两个百分比 target 在所有固定 target 之前执行；
- targets 13–19 的谓词、字段、公式、上下限/存储边界与 ROM 一致；
- 主动技先应用等级成长，忍具先绑定工具槽，再应用被动；
- 玩家、AI、browser、preview 和 resolver 都通过统一 catalog 消费修正后定义；
- 正式 resolver 对同一角色/目标的修正后动作产生更高伤害；
- 45 条被动中，除 ID 0 哨兵外均有已绑定 ROM 生产消费者；
- ARM 构建与静音运行无 crash/trap；静音路线只作结构回归，不宣称音频已修复。
