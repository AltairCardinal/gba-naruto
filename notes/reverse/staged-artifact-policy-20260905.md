# 已暂存 artifact 的提交门禁修复

## 复用与目的

继续使用 `.githooks/pre-commit` 调用的 `tools/check_staged_artifact_policy.py`。
当前逆向产物已广泛使用 `{sha256, size}` 成员收据；旧检查器只支持哈希字符串，会在
提交有效产物时误报 hash mismatch。它还读取工作树文件，可能把暂存区坏内容判为通过。

本次只修改原提交链路。临时 Git 仓库集成测试直接运行同一 CLI；不引入另一套发布器，
也不改写已冻结 artifact 的 manifest 或实验发布器身份。

## TDD 与独立复核

- 第一轮 RED：9 项测试出现8个失败分支，复现结构化收据误拒绝、错误长度诊断、
  非法收据类型，以及暂存 payload/manifest/symlink 与工作树不同步时的误判。
- GREEN：9/9。以 `git write-tree` 固定 index，成员从不可变 tree/blob 读取；只接受
  常规文件 mode，严格检查哈希和非负整数 size，兼容历史哈希字符串格式。
- Sol medium 只读复核发现两条 P1：HEAD 在目录发现期间变化，以及基线 blob/symlink
  被替换成新目录时因旧路径存在而被豁免。
- 第二轮 RED：2项测试/3个正确失败分支，含真实 `update-ref` 推进 HEAD 的故障注入。
  修复只解析一次 `HEAD^{tree}`，同一 OID 贯穿 diff 与类型查询；只有基线中的 tree
  才视为既有 artifact 目录。GREEN整套11/11，独立差量复核无新增P0/P1。
- 清理函数排版后重跑11项；原始日志和实现哈希见
  `notes/evidence/staged-artifact-policy-20260905/manifest.json`。

这些测试只操作各自几KB的临时 Git 仓库，数秒内结束，不执行 ROM、coverage、formal
或其他重任务。它们包含真实暂存、commit、blob读取、路径替换和HEAD变化的集成验证。

## 操作与边界

使用正常本地提交流程，或先执行 `python3 tools/check_staged_artifact_policy.py --root .`。
有效新 artifact 显示检查通过；缺失manifest、未accepted、成员不符、哈希/size错误、
符号链接等返回非零并指出对应目录或文件。未暂存的工作树修改不参与这次提交判断。

检查器验证的是开始时固定的两个 Git tree，不声称返回后外部进程不能再更改 index。
既有 artifact 目录仍由其独立 verifier 和 coverage/formal 合同验证；本次未扩大此hook
的历史职责。hook成功也不替代 ROM 字节语义或100%完成验收。
