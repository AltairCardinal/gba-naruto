# Butano Foundation and Cost Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在新分支上部署固定版本的 Butano、构建可运行的最小 GBA ROM，并形成《木叶战记》基础系统功能等价重建的证据化成本预研。

**Architecture:** Butano 21.7.1 以固定 commit 的 submodule 存放在 `third_party/butano`，其源码和 `docs/` HTML 同时作为本地参考。项目通过锁定 digest 的 devkitPro Docker 镜像构建；现有 `sequel/content` 继续作为唯一内容源，Butano 工程只增加新的构建目标，不复制现有内容模型。

**Tech Stack:** Git submodule、Butano 21.7.1、现代 C++23、GNU Make、devkitARM、devkitPro Docker、Python 3 `unittest`、mGBA guarded runtime smoke。

## Global Constraints

- Butano 固定为 tag `21.7.1`、commit `112a1827c9c6d9e6041a7e93e66f04c4561a6415`。
- 分支名固定为 `codex/butano-foundation-research`，从当前 HEAD 创建。
- 不回滚、不暂存、不提交现有 `AGENTS.md`、`docs/sequel-roadmap.md` 和 build/artifact 用户改动。
- 未获明确授权不得 commit 或 push；本计划中的检查点只运行测试和检查 diff。
- 只使用 devkitPro 官方 `devkitpro/devkitarm:20260610` 镜像，并在首次拉取后把 repo digest 写入锁文件。
- 不在宿主机全局安装 devkitARM。
- 所有功能性文件严格执行红、绿、重构；集成 wiring 必须有能在路径、版本或构建命令损坏时失败的测试。
- 本轮不实现正式地图、战斗、AI、剧情或存档系统；最小 ROM 仅用于部署验收。
- 若运行 mGBA，必须通过 `tools/run_guarded.py` 的 `heavy` lock，不直接启动高开销运行。
- 成本按功能等价口径，以有 Butano/GBA 经验的单个工程师人周估算，不包含完整内容制作和旧存档兼容。

---

## File Map

- `.gitmodules`：声明 Butano 官方 submodule 来源。
- `.gitignore`：忽略本项目的 Butano 编译中间物与 `.gba` 输出。
- `third_party/butano`：固定到 21.7.1 commit 的源码、示例、许可证和离线文档。
- `butano-sequel/Makefile`：最小 ROM 的 Butano 构建 wiring。
- `butano-sequel/src/main.cpp`：显示部署状态并响应 A 键的最小主循环。
- `tools/butano/verify_setup.py`：纯本地检查 submodule、版本、文档、项目文件和工具链锁。
- `tools/butano/lock_toolchain.sh`：拉取官方镜像并把不可变 repo digest 写入锁文件。
- `tools/butano/build.sh`：读取锁文件、检查 Docker、执行容器构建。
- `tools/butano/toolchain.lock`：Butano 和 devkitARM 的不可变版本记录。
- `tests/test_butano_setup.py`：verifier 单元测试和真实仓库 wiring 测试。
- `tests/test_butano_build.py`：Docker 构建与 ROM header 集成测试。
- `tests/test_butano_research_docs.py`：本地参考和成本报告结构测试。
- `docs/butano-local-reference.md`：本地源码、文档、许可证和构建使用说明。
- `docs/butano-konoha-systems-cost.md`：系统清单、成本、风险和里程碑。
- `docs/sequel-roadmap.md`：仅以安全追加方式记录预研状态。

---

### Task 1: 创建分支并实现部署完整性检查器

**Files:**
- Create: `tests/test_butano_setup.py`
- Create: `tools/butano/verify_setup.py`

**Interfaces:**
- Consumes: 仓库根目录 `Path`。
- Produces: `collect_setup_errors(root: Path) -> list[str]`；CLI 成功返回 0，配置错误返回 2。

- [ ] **Step 1: 创建并核对新分支**

Run:

```bash
git switch -c codex/butano-foundation-research
git branch --show-current
git status --short --branch
```

Expected: 当前分支为 `codex/butano-foundation-research`；原有用户改动仍原样存在。

- [ ] **Step 2: 写检查器的失败测试**

Create `tests/test_butano_setup.py`:

```python
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY_PATH = ROOT / "tools" / "butano" / "verify_setup.py"


class ButanoSetupTest(unittest.TestCase):
    @staticmethod
    def _load_verifier():
        spec = importlib.util.spec_from_file_location("verify_setup", VERIFY_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_collect_setup_errors_reports_every_missing_contract(self):
        verifier = self._load_verifier()
        with tempfile.TemporaryDirectory() as temp_dir:
            errors = verifier.collect_setup_errors(Path(temp_dir))

        self.assertEqual(
            errors,
            [
                "missing .gitmodules entry for third_party/butano",
                "missing Butano checkout: third_party/butano",
                "missing offline docs: third_party/butano/docs/index.html",
                "missing minimal project Makefile: butano-sequel/Makefile",
                "missing minimal project source: butano-sequel/src/main.cpp",
                "missing toolchain lock: tools/butano/toolchain.lock",
            ],
        )

    def test_cli_returns_two_for_incomplete_repository(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [sys.executable, str(VERIFY_PATH), "--root", temp_dir],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("Butano setup is incomplete", result.stderr)
```

- [ ] **Step 3: 运行红灯测试**

Run:

```bash
python3 -m unittest tests.test_butano_setup -v
```

Expected: ERROR/FAIL，原因是 `tools/butano/verify_setup.py` 尚不存在。

- [ ] **Step 4: 写最小检查器实现**

Create `tools/butano/verify_setup.py`:

```python
#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


EXPECTED_BUTANO_COMMIT = "112a1827c9c6d9e6041a7e93e66f04c4561a6415"


def _git_head(path: Path) -> str | None:
    if not path.is_dir():
        return None
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def collect_setup_errors(root: Path) -> list[str]:
    errors: list[str] = []
    gitmodules = root / ".gitmodules"
    gitmodules_text = gitmodules.read_text(encoding="utf-8") if gitmodules.is_file() else ""
    if "third_party/butano" not in gitmodules_text:
        errors.append("missing .gitmodules entry for third_party/butano")

    butano = root / "third_party" / "butano"
    if not butano.is_dir():
        errors.append("missing Butano checkout: third_party/butano")
    else:
        actual_commit = _git_head(butano)
        if actual_commit != EXPECTED_BUTANO_COMMIT:
            errors.append(
                f"Butano commit mismatch: expected {EXPECTED_BUTANO_COMMIT}, got {actual_commit or 'unreadable'}"
            )

    if not (butano / "docs" / "index.html").is_file():
        errors.append("missing offline docs: third_party/butano/docs/index.html")
    if not (root / "butano-sequel" / "Makefile").is_file():
        errors.append("missing minimal project Makefile: butano-sequel/Makefile")
    if not (root / "butano-sequel" / "src" / "main.cpp").is_file():
        errors.append("missing minimal project source: butano-sequel/src/main.cpp")
    if not (root / "tools" / "butano" / "toolchain.lock").is_file():
        errors.append("missing toolchain lock: tools/butano/toolchain.lock")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the local Butano deployment")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    errors = collect_setup_errors(args.root.resolve())
    if errors:
        print("Butano setup is incomplete:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    print("Butano setup is complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 运行绿灯测试并检查格式**

Run:

```bash
python3 -m unittest tests.test_butano_setup -v
python3 -m py_compile tools/butano/verify_setup.py tests/test_butano_setup.py
git diff --check
```

Expected: 2 tests PASS，Python 编译与 diff 检查成功。

---

### Task 2: 固定 Butano 源码、离线文档与最小工程 wiring

**Files:**
- Modify: `.gitmodules`
- Modify: `.gitignore`
- Create: `third_party/butano` gitlink and checkout
- Create: `butano-sequel/Makefile`
- Create: `butano-sequel/src/main.cpp`
- Modify: `tests/test_butano_setup.py`

**Interfaces:**
- Consumes: `third_party/butano/butano/butano.mak`、`third_party/butano/common` 字体资源。
- Produces: Make target `butano-sequel.gba`；真实仓库调用 `verify_setup.py` 时只允许工具链锁尚未建立这一项错误。

- [ ] **Step 1: 写真实仓库 wiring 的失败测试**

Append to `ButanoSetupTest` in `tests/test_butano_setup.py`:

```python
    def test_repository_wiring_only_waits_for_toolchain_lock(self):
        verifier = self._load_verifier()
        errors = verifier.collect_setup_errors(ROOT)
        self.assertEqual(errors, ["missing toolchain lock: tools/butano/toolchain.lock"])

    def test_generated_butano_outputs_are_ignored(self):
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "butano-sequel/build/main.o",
                "butano-sequel/butano-sequel.gba",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
```

- [ ] **Step 2: 运行红灯测试**

Run:

```bash
python3 -m unittest tests.test_butano_setup.ButanoSetupTest.test_repository_wiring_only_waits_for_toolchain_lock -v
```

Expected: FAIL，错误同时列出缺少 submodule、离线文档、Makefile、源码和锁文件。

- [ ] **Step 3: 添加并固定官方 submodule**

Run:

```bash
git submodule add --depth 1 https://github.com/GValiente/butano.git third_party/butano
git -C third_party/butano checkout --detach 112a1827c9c6d9e6041a7e93e66f04c4561a6415
git -C third_party/butano rev-parse HEAD
test -f third_party/butano/LICENSE
test -f third_party/butano/docs/index.html
```

Expected: HEAD 精确等于 `112a1827c9c6d9e6041a7e93e66f04c4561a6415`，许可证和离线文档存在。

- [ ] **Step 4: 忽略最小工程的生成物**

Append to `.gitignore`:

```gitignore

# Butano build artifacts
butano-sequel/build/
butano-sequel/*.gba
butano-sequel/*.elf
butano-sequel/*.map
```

- [ ] **Step 5: 写最小 Butano Makefile**

Create `butano-sequel/Makefile`:

```make
TARGET          :=  butano-sequel
BUILD           :=  build
LIBBUTANO       :=  ../third_party/butano/butano
PYTHON          :=  python3
SOURCES         :=  src
INCLUDES        :=  include ../third_party/butano/common/include
DATA            :=
GRAPHICS        :=  ../third_party/butano/common/graphics
AUDIO           :=
AUDIOBACKEND    :=  null
AUDIOTOOL       :=
DMGAUDIO        :=
DMGAUDIOBACKEND :=  null
ROMTITLE        :=  KONOHA BASE
ROMCODE         :=  KNBT
USERFLAGS       :=
USERCXXFLAGS    :=
USERASFLAGS     :=
USERLDFLAGS     :=
USERLIBDIRS     :=
USERLIBS        :=
DEFAULTLIBS     :=
STACKTRACE      :=
USERBUILD       :=
EXTTOOL         :=

ifndef LIBBUTANOABS
export LIBBUTANOABS := $(realpath $(LIBBUTANO))
endif

include $(LIBBUTANOABS)/butano.mak
```

- [ ] **Step 6: 写最小 ROM 主循环**

Create `butano-sequel/src/main.cpp`:

```cpp
#include "bn_core.h"
#include "bn_keypad.h"
#include "bn_sprite_ptr.h"
#include "bn_sprite_text_generator.h"
#include "bn_vector.h"

#include "common_variable_8x16_sprite_font.h"

int main()
{
    bn::core::init();

    bn::sprite_text_generator text_generator(common::variable_8x16_sprite_font);
    text_generator.set_center_alignment();

    bn::vector<bn::sprite_ptr, 32> text_sprites;
    text_generator.generate(0, -12, "BUTANO READY", text_sprites);
    text_generator.generate(0, 12, "PRESS A", text_sprites);

    while(true)
    {
        if(bn::keypad::a_pressed())
        {
            text_sprites.clear();
            text_generator.generate(0, -12, "BUTANO READY", text_sprites);
            text_generator.generate(0, 12, "INPUT OK", text_sprites);
        }

        bn::core::update();
    }
}
```

- [ ] **Step 7: 运行 wiring 绿灯边界**

Run:

```bash
python3 -m unittest tests.test_butano_setup -v
python3 tools/butano/verify_setup.py
```

Expected: 单元测试全部 PASS；CLI 此时只因 `tools/butano/toolchain.lock` 缺失返回 2。

---

### Task 3: 锁定 Docker 工具链并建立可复现构建

**Files:**
- Create: `tools/butano/lock_toolchain.sh`
- Create: `tools/butano/build.sh`
- Create: `tools/butano/toolchain.lock`
- Create: `tests/test_butano_build.py`
- Modify: `tests/test_butano_setup.py`

**Interfaces:**
- Consumes: Docker CLI/daemon、镜像 tag `devkitpro/devkitarm:20260610`。
- Produces: shell-compatible `toolchain.lock` 中的 `DEVKITARM_IMAGE`、`BUTANO_VERSION`、`BUTANO_COMMIT`；`build.sh [project-dir]`；输出 `butano-sequel/butano-sequel.gba`。

- [ ] **Step 1: 写锁文件和构建入口的失败测试**

Create `tests/test_butano_build.py`:

```python
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "tools" / "butano" / "toolchain.lock"


class ButanoBuildTest(unittest.TestCase):
    def test_toolchain_lock_uses_immutable_digest(self):
        values = {}
        for line in LOCK.read_text(encoding="utf-8").splitlines():
            key, value = line.split("=", 1)
            values[key] = value
        self.assertEqual(values["BUTANO_VERSION"], "21.7.1")
        self.assertEqual(
            values["BUTANO_COMMIT"],
            "112a1827c9c6d9e6041a7e93e66f04c4561a6415",
        )
        self.assertRegex(
            values["DEVKITARM_IMAGE"],
            r"^devkitpro/devkitarm@sha256:[0-9a-f]{64}$",
        )

    @unittest.skipUnless(
        os.environ.get("RUN_BUTANO_INTEGRATION") == "1",
        "set RUN_BUTANO_INTEGRATION=1 to build the ROM",
    )
    def test_minimal_rom_builds_with_expected_header(self):
        subprocess.run(
            [str(ROOT / "tools" / "butano" / "build.sh")],
            cwd=ROOT,
            check=True,
        )
        rom = ROOT / "butano-sequel" / "butano-sequel.gba"
        data = rom.read_bytes()
        self.assertGreater(len(data), 192)
        self.assertEqual(data[0xA0:0xAC].rstrip(b"\0"), b"KONOHA BASE")
        self.assertEqual(data[0xAC:0xB0], b"KNBT")
```

Replace the repository wiring assertion from Task 2 with:

```python
    def test_repository_wiring_is_complete(self):
        verifier = self._load_verifier()
        self.assertEqual(verifier.collect_setup_errors(ROOT), [])
```

- [ ] **Step 2: 运行红灯测试**

Run:

```bash
python3 -m unittest tests.test_butano_build.ButanoBuildTest.test_toolchain_lock_uses_immutable_digest -v
```

Expected: ERROR，原因是 `tools/butano/toolchain.lock` 尚不存在。

- [ ] **Step 3: 写工具链锁定脚本**

Create `tools/butano/lock_toolchain.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../.." && pwd -P)
image_tag=devkitpro/devkitarm:20260610

docker info >/dev/null
docker pull "$image_tag"
repo_digest=$(docker image inspect --format '{{index .RepoDigests 0}}' "$image_tag")
case "$repo_digest" in
    devkitpro/devkitarm@sha256:*) ;;
    *) echo "Unable to resolve immutable devkitARM digest: $repo_digest" >&2; exit 2 ;;
esac

lock_file="$repo_root/tools/butano/toolchain.lock"
printf '%s\n' \
    'BUTANO_VERSION=21.7.1' \
    'BUTANO_COMMIT=112a1827c9c6d9e6041a7e93e66f04c4561a6415' \
    "DEVKITARM_IMAGE=$repo_digest" \
    > "$lock_file"
echo "Locked $repo_digest"
```

- [ ] **Step 4: 启动 Docker Desktop 并生成不可变锁**

Run:

```bash
chmod +x tools/butano/lock_toolchain.sh
open -a Docker
docker info --format '{{.ServerVersion}} {{.Architecture}}'
tools/butano/lock_toolchain.sh
```

Expected: Docker daemon 可用；镜像拉取成功；`toolchain.lock` 的 `DEVKITARM_IMAGE` 是 `devkitpro/devkitarm@sha256:` 加 64 位十六进制摘要。若 daemon 启动需要等待，每次轮询不超过 30 秒并在 5 分钟总时限后停止。

- [ ] **Step 5: 写固定镜像构建脚本**

Create `tools/butano/build.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../.." && pwd -P)
project_dir=${1:-butano-sequel}

python3 "$repo_root/tools/butano/verify_setup.py" --root "$repo_root"
source "$repo_root/tools/butano/toolchain.lock"

case "$DEVKITARM_IMAGE" in
    devkitpro/devkitarm@sha256:*) ;;
    *) echo "Invalid DEVKITARM_IMAGE in toolchain.lock" >&2; exit 2 ;;
esac

if ! docker info >/dev/null 2>&1; then
    echo "Docker Desktop is not running; start it and retry." >&2
    exit 2
fi

docker run --rm \
    --user "$(id -u):$(id -g)" \
    --volume "$repo_root:/workspace" \
    --workdir "/workspace/$project_dir" \
    "$DEVKITARM_IMAGE" \
    make -j2
```

Run:

```bash
chmod +x tools/butano/build.sh
```

- [ ] **Step 6: 运行绿灯单元和集成测试**

Run:

```bash
python3 -m unittest tests.test_butano_setup tests.test_butano_build -v
RUN_BUTANO_INTEGRATION=1 python3 -m unittest tests.test_butano_build -v
shasum -a 256 butano-sequel/butano-sequel.gba
```

Expected: 非 Docker 测试 PASS、集成测试 PASS，ROM header 为 `KONOHA BASE` / `KNBT`，并输出 SHA-256。

- [ ] **Step 7: 构建官方图形和音频示例**

Run:

```bash
tools/butano/build.sh third_party/butano/examples/sprites
tools/butano/build.sh third_party/butano/examples/audio
test -f third_party/butano/examples/sprites/sprites.gba
test -f third_party/butano/examples/audio/audio.gba
```

Expected: 两个官方示例均生成 `.gba`。若镜像或资源条件阻止其中一项，保存原始错误并在最终报告中明确标记，不修改上游示例绕过失败。

---

### Task 4: 编写本地参考和基础系统成本报告

**Files:**
- Create: `tests/test_butano_research_docs.py`
- Create: `docs/butano-local-reference.md`
- Create: `docs/butano-konoha-systems-cost.md`

**Interfaces:**
- Consumes: Butano 21.7.1 官方源码/文档、仓库现有逆向证据。
- Produces: 可执行本地参考入口；13 类基础系统的三点成本估算与总量边界。

- [ ] **Step 1: 写文档契约的失败测试**

Create `tests/test_butano_research_docs.py`:

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ButanoResearchDocsTest(unittest.TestCase):
    def test_local_reference_has_required_entrypoints(self):
        text = (ROOT / "docs" / "butano-local-reference.md").read_text(encoding="utf-8")
        for required in (
            "21.7.1",
            "112a1827c9c6d9e6041a7e93e66f04c4561a6415",
            "third_party/butano/docs/index.html",
            "tools/butano/build.sh",
            "zlib",
        ):
            self.assertIn(required, text)

    def test_cost_report_covers_every_foundation_system(self):
        text = (ROOT / "docs" / "butano-konoha-systems-cost.md").read_text(encoding="utf-8")
        for required in (
            "核心循环与场景",
            "外围流程与部署",
            "章节脚本与对白",
            "地图、碰撞与寻路",
            "单位与战斗实例",
            "回合与行动状态机",
            "技能、伤害与效果",
            "AI 与任务目标",
            "成长、训练与奖励",
            "存档与恢复",
            "UI、文本与图形演出",
            "音频转换与播放",
            "内容转换、调试与验收",
            "40–66–106",
            "旧存档兼容",
            "功能边界",
        ):
            self.assertIn(required, text)
```

- [ ] **Step 2: 运行红灯测试**

Run:

```bash
python3 -m unittest tests.test_butano_research_docs -v
```

Expected: ERROR，原因是两份文档尚不存在。

- [ ] **Step 3: 编写本地参考文档**

Create `docs/butano-local-reference.md`，必须包含：

```markdown
# Butano 本地参考与构建

## 固定版本

- Butano: 21.7.1
- Commit: `112a1827c9c6d9e6041a7e93e66f04c4561a6415`
- License: zlib；第三方许可证见 `third_party/butano/licenses/`

## 本地入口

- 源码：`third_party/butano/butano/`
- 离线文档：`third_party/butano/docs/index.html`
- 示例：`third_party/butano/examples/`
- 完整游戏参考：`third_party/butano/games/`

## 初始化与构建

```bash
git submodule update --init --recursive third_party/butano
open -a Docker
tools/butano/build.sh
```

## 失败处理

运行 `python3 tools/butano/verify_setup.py` 获取缺失路径、版本不匹配或工具链锁错误；构建脚本不会静默修复 submodule，也不会改用浮动镜像 tag。
```

在同一文件中加入以下准确链接：

```markdown
## 官方资料

- [Butano 官方仓库](https://github.com/GValiente/butano)
- [21.7.1 release](https://github.com/GValiente/butano/releases/tag/21.7.1)
- [Getting Started](https://gvaliente.github.io/butano/getting_started.html)
- [Modules](https://gvaliente.github.io/butano/modules.html)
- [Examples](https://gvaliente.github.io/butano/examples.html)
- [Importing assets](https://gvaliente.github.io/butano/import.html)
- [FAQ](https://gvaliente.github.io/butano/faq.html)
- [Changelog](https://gvaliente.github.io/butano/changelog.html)
```

升级流程固定为：新建独立变更、更新 submodule、检查 release/changelog 与许可证、重新锁定工具链、重跑官方图形/音频示例和最小 ROM；不得直接跟踪浮动 `master`。

- [ ] **Step 4: 编写成本预研报告**

Create `docs/butano-konoha-systems-cost.md`，按以下固定标题组织：

```markdown
# 木叶战记基础系统 Butano 功能等价重建成本预研

## 执行结论
## 估算口径与功能边界
## 现有能力复用决策
## 成本总表
## 分系统分析
## 推荐里程碑
## 日历工期与团队配置
## 可选项与明确排除项
## 证据与参考资料
```

成本总表使用以下估算，不在各系统之间重复计算工作：

| 系统 | 乐观 | 最可能 | 悲观 |
|---|---:|---:|---:|
| 核心循环与场景 | 1.5 | 2.5 | 4 |
| 外围流程与部署 | 2 | 3.5 | 5 |
| 章节脚本与对白 | 3 | 5 | 8 |
| 地图、碰撞与寻路 | 4 | 6 | 9 |
| 单位与战斗实例 | 2 | 3 | 5 |
| 回合与行动状态机 | 4 | 7 | 10 |
| 技能、伤害与效果 | 5 | 8 | 13 |
| AI 与任务目标 | 5 | 9 | 16 |
| 成长、训练与奖励 | 2 | 3.5 | 6 |
| 存档与恢复 | 1.5 | 2.5 | 4 |
| UI、文本与图形演出 | 4 | 7 | 11 |
| 音频转换与播放 | 2 | 3 | 5 |
| 内容转换、调试与验收 | 4 | 6 | 10 |
| 合计 | 40 | 66 | 106 |

在“分系统分析”下建立与成本表完全同名的 13 个三级标题。每节固定写“用户入口与反馈、现有证据、Butano 可复用、自建能力、风险、功能边界”六项。正文必须满足：

- 用 `40–66–106` 工程师人周表示三点总量；建议立项预算为 70–90 人周；
- 把单人日历时间写为约 16–24 个月，把两名资深工程师写为约 9–14 个月，并说明 GBA 性能与系统集成不能线性并行；
- 给出 12–18 人周的单章垂直切片门槛，覆盖一张地图、完整玩家/AI 回合、4–6 名单位、8–12 个技能、剧情前后演出和存读档；
- 对每个系统列出用户入口、加载/空/错误行为、现有证据、Butano 可复用能力、自建部分、风险和功能边界；
- 把 AI/目标、技能效果链、战棋行动状态机标为最高风险；
- 把旧存档兼容列为额外 4–8 人周的可选项，不计入总表；
- 明确内容生产、美术重制、剧本文案、逐帧还原和原作素材再分发不在范围内；
- 引用 `docs/sequel-roadmap.md` 及相关 `notes/scenario-*`、成长、章节、地图、音频和存档证据文件；
- 说明 13 `runtime_verified` / 10 `code_verified` / 9 `disproved` 是 bank 身份成熟度，不等同于完整玩法规格。

- [ ] **Step 5: 运行文档绿灯测试**

Run:

```bash
python3 -m unittest tests.test_butano_research_docs -v
git diff --check -- docs/butano-local-reference.md docs/butano-konoha-systems-cost.md tests/test_butano_research_docs.py
```

Expected: 2 tests PASS，Markdown 和测试文件无 whitespace 错误。

---

### Task 5: 运行时验收、路线图追加和最终回归

**Files:**
- Modify: `docs/sequel-roadmap.md` only by appending a dated subsection
- Create: `build/butano-smoke-20260721/` runtime evidence if mGBA smoke runs

**Interfaces:**
- Consumes: `butano-sequel/butano-sequel.gba`、现有 `tools/run_guarded.py` 与 `tools/mgba-headless-snapshot.py`。
- Produces: 冷启动 60 帧无崩溃的 guarded 证据和完整验证清单；本轮不把按键后的画面写成运行时已证明。

- [ ] **Step 1: 核对固定的 guarded mGBA 入口**

Run:

```bash
test -f tools/run_guarded.py
test -f tools/mgba-headless-snapshot.py
test -x /usr/local/bin/mgba
python3 -m py_compile tools/run_guarded.py tools/mgba-headless-snapshot.py
/usr/local/bin/mgba --version
```

Expected: `/usr/local/bin/mgba` 和两个 Python 入口均存在；不得绕过 heavy lock 直接运行。

- [ ] **Step 2: 在资源准入允许时执行冷启动 smoke**

Run:

```bash
mkdir -p build/butano-smoke-20260721
MGBA_BIN=/usr/local/bin/mgba python3 tools/run_guarded.py \
  --summary build/butano-smoke-20260721/guard-summary.json \
  --lock-file build/resource-guard/heavy.lock \
  --cwd /Users/altair/github/gba-naruto \
  --min-available-mib 4096 \
  --max-tree-rss-mib 1536 \
  --wall-timeout-s 60 \
  --idle-timeout-s 30 \
  -- \
  python3 tools/mgba-headless-snapshot.py \
    --rom butano-sequel/butano-sequel.gba \
    --mode snapshot \
    --dump 0x02000000:16 \
    --frames 60 \
    --output build/butano-smoke-20260721/snapshot.json \
    --timeout 30
mgba --version
shasum -a 256 butano-sequel/butano-sequel.gba
```

Expected: guard summary 为 `completed/0`，snapshot JSON 非空，60 帧内无崩溃。该 runner 不注入按键或截图，因此 `PRESS A → INPUT OK` 只由源码和编译覆盖，最终报告明确标记为未做运行时输入验收。若 runner 不支持该 ROM 或资源守卫拒绝，停止扩张实验，保留诊断，并只声明构建通过。

- [ ] **Step 3: 安全追加路线图状态**

在 `docs/sequel-roadmap.md` 末尾追加：

```markdown
### 2026-07-21 Butano 功能等价重建预研

- Butano 21.7.1 已固定到 commit `112a1827c9c6d9e6041a7e93e66f04c4561a6415`，源码、许可证、示例和离线 HTML 文档位于 `third_party/butano/`。
- 最小工程、固定 devkitARM Docker 工具链与验证入口见 `docs/butano-local-reference.md`。
- 全部基础系统功能等价重建的三点估算为 40–66–106 工程师人周，建议立项预算 70–90 人周；系统边界、风险和里程碑见 `docs/butano-konoha-systems-cost.md`。
- 本轮只完成工具链部署与成本预研，不表示地图、战斗、AI、剧情、成长或存档系统已经在 Butano 中实现。
```

应用前先检查用户对该文件的现有 diff，只追加，不改写已有行。

- [ ] **Step 4: 运行完整验证**

Run:

```bash
python3 -m py_compile tools/butano/verify_setup.py tests/test_butano_setup.py tests/test_butano_build.py tests/test_butano_research_docs.py
python3 -m unittest tests.test_butano_setup tests.test_butano_build tests.test_butano_research_docs -v
RUN_BUTANO_INTEGRATION=1 python3 -m unittest tests.test_butano_build -v
python3 tools/butano/verify_setup.py
git diff --check
git status --short --branch
git diff --stat
git submodule status third_party/butano
```

Expected: Python 编译成功；所有非 Docker 与 Docker 集成测试 PASS；verifier 返回 0；diff 无 whitespace 错误；submodule 前缀无 `-`、`+` 或 `U`，commit 为固定 SHA。

- [ ] **Step 5: 人工范围复核**

Review:

```bash
git diff -- .gitmodules butano-sequel tools/butano tests/test_butano_setup.py tests/test_butano_build.py tests/test_butano_research_docs.py docs/butano-local-reference.md docs/butano-konoha-systems-cost.md docs/sequel-roadmap.md docs/superpowers
```

Expected: 只包含本计划授权的文件；用户已有改动没有被覆盖；没有暂存文件、commit 或 push。
