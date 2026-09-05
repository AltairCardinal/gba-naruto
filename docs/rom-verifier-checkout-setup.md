# 从新检出恢复历史 ROM verifier 合同输入

首次运行 coverage auditor 或历史 CGB/MP2K verifier 前，在逆向仓库根目录执行：

```sh
python3 tools/prepare_rom_verifier_contracts.py --restore
python3 tools/prepare_rom_verifier_contracts.py
```

第一条命令从已提交的 `tools/data/rom-verifier-contracts-v1/` 恢复三份原始合同到旧
verifier 固定的仓库内 `build/experiments/active/*-contract/codex-r1-20260829/CONTRACT.json`。
第二条只检查，不写文件。JSON 输出列出精确来源、目标、size、SHA、新建与已存在数量；
成功时 `verified=true`。它只准备运行输入，`semantic_verification_performed=false`。
后续 ROM verifier、coverage/formal 重放仍须经 `tools/run_guarded.py` 和同一
`build/experiments/heavy.lock`，遵循既有分级验收政策。

三份原始合同分别为 CgbSound、CGB helper 和 MP2K dispatcher。其内容哈希已由对应
旧 verifier 的 `CONTRACT_SHA256` 固定；恢复工具同时固定旧 consumer 源码哈希。合同
源文件逐字节保留，没有改写任何旧 verifier、artifact manifest、coverage 或 proof。
这样可以复用历史证据身份，避免修改旧工具路径后让原有 manifest 和正式收据失效。
现有 experiment workspace 支持归档与晋升，没有精确恢复这些固定相对输入的入口，
因此新增此有限初始化命令；不另建 ROM exporter 或语义验收链。

恢复前会检查完整三文件库存、全部 source/consumer 身份及全部已有目标。已有内容
一致时不改写、不改 mtime；缺失时仅创建固定目标；已有内容冲突、缺失或篡改源文件、
非普通文件、符号链接、危险目录形态都会失败并返回非零。不要删除冲突文件来掩盖失败，
应先核对输出中的路径与已提交来源。每个新文件先完整写入、再以不覆盖方式原子发布。
异常中断可能留下已成功恢复的部分文件；再次执行会验证并复用它们。此命令不提供
跨三个文件的事务回滚，也不会删除用户文件。

验证入口：

```sh
python3 -m unittest tests.test_prepare_rom_verifier_contracts -v
```

测试覆盖新建、幂等、默认只读、三份输入变异/缺失、consumer 变更、额外成员、晚位目标
冲突、符号链接、目录和 FIFO；集成测试直接使用三个原始 consumer 校验恢复的合同。
数据依赖只来自当前检出的已提交文件；不需要其他工作树或旧实验目录。
