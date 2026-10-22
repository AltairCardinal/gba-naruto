# 实验产物生命周期

## 工作树边界

| 工作 | 工作树 | 分支 |
|---|---|---|
| Butano 续作实现 | `/Users/altair/github/gba-naruto` | `codex/butano-foundation-research` |
| ROM 逆向与成果提取 | `/Users/altair/github/gba-naruto-reverse` | `codex/reverse-engineering` |

两个工作树共享 Git 对象，但文件目录彼此独立。逆向成果先在逆向分支形成
commit，Butano 分支按需 cherry-pick，因此可以访问成果而不会共同承受另一工作树的
临时文件、文件监视和未提交状态。

## 目录与状态

所有实验先进入被 Git 忽略的 `build/experiments/`：

```text
build/experiments/
├── active/<task>/<run-id>/       # 运行中或待验收，保持散文件
├── archive/<task>/<month>/       # 已完成，压成 tar.gz 和校验 sidecar
└── trash/<task>/<month>/         # 待删除缓冲区
```

只有通过验收的最小成果进入 `artifacts/<artifact-name>/`。实验原始日志、逐帧截图、
中间 ROM、重复导出和缓存不得直接写入 `artifacts/`。

## 操作流程

```bash
# 1. 建立唯一实验目录
python3 tools/experiment_workspace.py --root . init \
  --task fbff-runtime --run-id 20260730-01

# 2. 工具输出写入返回目录；准备提交的最小集合放入该 run 的 final/

# 3. 无需进入 Git 的实验完成后标记并归档
python3 tools/experiment_workspace.py --root . complete \
  --task fbff-runtime --run-id 20260730-01
python3 tools/experiment_workspace.py --root . archive \
  --task fbff-runtime --run-id 20260730-01

# 4. 需要进入 Git 的成果通过准入后提升，再归档原实验
python3 tools/experiment_workspace.py --root . promote \
  --task fbff-runtime --run-id 20260730-01 \
  --artifact-name character-fbff-runtime-v1
python3 tools/experiment_workspace.py --root . archive \
  --task fbff-runtime --run-id 20260730-01
```

`final/manifest.json` 使用 `git-artifact-promotion-v1`，必须声明
`artifact_status: accepted`、成功 verifier 的命令与退出码，并列出除 manifest
之外每个文件的 SHA-256。默认上限为 500 个文件、250 MiB；超过时必须写
`large_artifact_justification`。pre-commit hook 会再次检查新 `artifacts/`
目录，防止绕过提升流程。

## 归档与清理

```bash
# 只预览
python3 tools/experiment_workspace.py --root . maintenance

# 执行：归档 completed；30 天后移入 trash；再保留 7 天后删除
python3 tools/experiment_workspace.py --root . maintenance --apply
```

维护使用文件锁，且不会归档或删除 `active` 状态的实验。归档包含清单、哈希与
校验 sidecar；删除前有 7 天恢复窗口。

历史遗留的完全未跟踪产物可用以下命令加入仓库本地隔离清单：

```bash
python3 tools/quarantine_legacy_artifacts.py --root .          # 预览
python3 tools/quarantine_legacy_artifacts.py --root . --apply  # 可逆应用
```

该操作不移动、不删除文件，只更新 Git 的本地 `info/exclude` 并把审计记录写入
`build/experiments/`。含有任一已跟踪文件的成果目录不会被隔离；需要重新审计旧
目录时，移除隔离清单中的对应行即可。

