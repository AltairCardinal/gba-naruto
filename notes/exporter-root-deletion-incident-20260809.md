# 导出器误删工作树事故（2026-08-09）

## 结论

本次事故由 `tools/export_rom_cfg_seeds.py` 的危险输出替换逻辑与一条错误的安全
回归测试共同触发。事故前实现接受任意 `output_dir`，若目录存在便直接执行
`shutil.rmtree(output_dir)`；测试又在真实逆向工作树中调用
`export_rom_cfg_seeds(ROOT, ROOT)`，因此把仓库根目录当成旧 artifact 删除。

这是实现和测试隔离缺失导致的真实数据安全缺陷，不是 Git、mGBA、内存压力或
Codex 容量问题。

## 影响

- `/Users/altair/github/gba-naruto-reverse` 的工作树文件被删除，只留下测试随后
  写入根目录的 `manifest.json` 与 `rom-cfg-seeds.json`。
- Git 对象库、`codex/reverse-engineering` 分支、HEAD
  `2c87985e5bb3b96b1c6724e422b116602cabfe86` 与主工作树均未受损。
- 事故前未提交源码、测试和文档没有 Git snapshot；它们通过 Codex 会话中已成功
  的 `apply_patch` 事件恢复。生成型 artifact 必须按依赖重新构建，不能仅靠补丁
  重放恢复。

## 恢复证据

- 权威会话日志：
  `/Users/altair/.codex/sessions/2026/07/15/rollout-2026-07-15T20-22-30-019f65ba-8399-7601-bb67-b98df6baf887.jsonl`
- 仓库外事故证据：
  `/Users/altair/github/gba-naruto-recovery-evidence-20260809/`
- 切换正式分支前的完整状态、binary patch、60 个未跟踪文件清单、逐文件 SHA 与
  未跟踪文件归档：
  `/Users/altair/github/gba-naruto-recovery-evidence-20260809/reattach-20260809-2018/`
- 原事故残留目录：
  `/Users/altair/github/gba-naruto-reverse-incident-20260809/`
- 原残留 `manifest.json` SHA-256：
  `e3d93306d59641d89014e6864a15a57778da61cc823d868424be07c3086b7785`
- 原残留 `rom-cfg-seeds.json` SHA-256：
  `cf5224e93eac0d3e5fe44f04e6578402cf9b8ca74cd4a9fbb83843af2d0025a6`

恢复过程在隔离 detached worktree 中重放 287 条已成功补丁；事故前记录过的九个
关键源码/测试哈希全部吻合。随后重新生成 boot、CFG seed、M4A、direct CpuSet、
对白、章节脚本、renderer 文本、unbound LZ77、类似表裁决与 ROM coverage。
恢复后的 coverage 仍为 5,846,562 classified、444,894 unknown、5,557 claims、
8,693 segments，与事故前统计完全一致。正式 proof 执行 26 个 verifier，25 个
合同通过，唯一失败仍是预期的 semantic-complete coverage 门；因此没有把恢复
误报为逆向完成。

恢复工作树随后附着回 `codex/reverse-engineering` 并由 `git worktree move`
恢复至原路径。移动前后的 tracked binary patch、状态清单、未跟踪文件清单和
逐文件 SHA 全部一致。

## 已实施修复

`export_rom_cfg_seeds.py` 与 `export_rom_boot_framebuffers.py` 现在都在任何构建、
建目录或替换动作之前：

1. 拒绝仓库根目录及其祖先；
2. 拒绝输出 symlink、非目录和外来目录；
3. 只允许替换文件集合、schema 与文件哈希均匹配的本 artifact；
4. 先把旧 artifact 原子重命名为随机 backup，再安装临时目录；失败时恢复 backup；
5. 只有安装成功后才删除已验证的旧 artifact。

两个导出器均有真实入口回归，直接调用 `export_*(ROOT, ROOT)` 必须在写入前失败，
并验证 `rom/base.gba` 与导出器源码仍存在且字节不变。boot 9 项测试、CFG seed
8 项测试均通过。

类似表 verifier 新增 `--regenerate-scan`，使 114 条固定扫描分母与 114 条裁决可由
正式 CLI 重建，不再依赖临时 Python 写文件命令。

## 尚未关闭的同类风险

只读全仓扫描还发现：

- 14 个 P0 导出器可在缺少根目录/所有权校验时递归删除任意输出目录；
- 9 个 P1 导出器只检查容易伪造的 `artifact_id`，仍可删除混入用户文件的目录。

这些入口在迁移到共享安全输出事务并通过根目录、祖先、foreign directory、
symlink、额外文件和合法重复导出测试前，视为禁用。当前恢复链没有调用它们。

## 后续强制规则

- 不得在真实工作树上用危险实现验证根目录拒绝；先测试纯 validator，或在完整的
  disposable 临时仓库副本中做端到端负例。
- 导出器不得直接对 CLI 提供的路径执行 `rmtree`。所有目录级替换必须经共享的
  边界、所有权与哈希校验，并使用可回滚原子替换。
- 新导出器必须同时覆盖 repository root、ancestor、symlink、foreign directory、
  forged/extra-file artifact 与合法重复生成。
- 生成型 artifact 不等于源码恢复；恢复验收必须分别核对源码补丁、生成物、独立
  verifier、coverage 与 formal proof。
- 本事故不改变 100% 逆向终点。Goal 保持 active，只有严格 proof 的全部 gate
  满足时才能宣称完成。
