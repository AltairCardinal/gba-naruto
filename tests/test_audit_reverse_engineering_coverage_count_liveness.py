"""覆盖计数的「活账本一致性」守卫。

背景
----
2026-10-20 池 3 晋升（unknown 87,631 → 86,089）打破了 proof 回归套件里的
**12 个测试**。根因不是晋升本身，而是：套件把「会随每次晋升变化的累计量」
写成了字面量（149,280 / 6,142,176 / 15,940 / 17,344 / 148,778 / 25,284 / …），
而这些字面量在每次晋升后都会变成历史值。

本文件是**元守卫**：它不再等 93 个测试跑完才报告失败，而是在秒级时间内
直接回答两个问题——

1. proof 合同里声明的 ``/summary/*`` 断言，是否与活账本逐项相等；
2. 任何测试文件里，是否还存在「拿字面量去比一个活账本键」的写法。

只要这两个问题任一为否，晋升链就会在**跑重活之前**失败关闭，
而不是在 45 分钟的套件末尾才吐出一串 F。

三类量的分类是本守卫的核心契约：

- **全局量 / 累计型**（随晋升变化）→ 必须写成 ``LIVE_COVERAGE_SUMMARY[...]`` 派生；
- **批次增量**（落地后固定）→ 必须保持硬编码，那是真正的回归护栏；
- **历史收据里的历史值**（有意钉住过去）→ 允许，但必须登记在
  ``HISTORICAL_PINNED`` 里并由本守卫复核其字面量没被悄悄放宽。

不在活账本里的键一律跳过——对拍不了就不假装验证过。
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "sequel/rom-byte-coverage.json"
SPEC = ROOT / "sequel/reverse-engineering-proof.json"
TESTS_DIR = ROOT / "tests"
PROOF_TEST = TESTS_DIR / "test_audit_reverse_engineering_proof.py"

#: 必须保持「派生」而非字面量的全局量 / 累计量。
#:
#: ``consumer_code_slice_*`` 同属累计型：它是消费者代码切片族的累计总量，
#: 本轮实测随池 3 晋升从 25,284 / 111 变为 27,404 / 116。
GLOBAL_KEYS = (
    "unknown_bytes",
    "classified_bytes",
    "claim_count",
    "segment_count",
    "cfg_reachable_thumb_code_bytes",
    "cfg_promoted_unknown_bytes",
    "cfg_primary_claim_count",
    "cfg_code_claim_kind_count",
    "cfg_code_claim_kind_denominator_sha256",
    "consumer_code_slice_bytes",
    "consumer_code_slice_claim_count",
)

#: 有意钉住**历史收据**里历史值的断言：文件名 → {summary 键: 历史字面量}。
#:
#: 这两处读的是 9-30 那次晋升冻结下来的 ``formal-report.json``，
#: 钉的是收据**当时**记录的 unknown_bytes = 87,631。
#: 它们不是活账本断言——活账本现在是 86,089，差值正是池 3 的 1,542 B。
#: 登记在此处是为了让「历史钉」不会悄悄扩大覆盖面。
HISTORICAL_PINNED = {
    "test_rom_small_cfg_batch_canonical.py": {"unknown_bytes": 87_631},
    "test_rom_renderer_script_pointer_pool_canonical.py": {"unknown_bytes": 87_631},
}

COVERAGE_VERIFIER = "tools/audit_rom_byte_coverage.py"


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _const_int(node: ast.AST) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    return None


def _subscript_chain(node: ast.AST) -> list[str] | None:
    """把 ``a["b"]["c"]`` 还原成 ``["b", "c"]``；任一层不是字符串常量则返回 None。"""
    keys: list[str] = []
    while isinstance(node, ast.Subscript):
        value = _const_str(node.slice)
        if value is None:
            return None
        keys.append(value)
        node = node.value
    keys.reverse()
    return keys


def _summary_key(node: ast.AST) -> str | None:
    """把一个下标表达式解析成它指向的 summary 键名。

    支持三种写法：

    - ``coverage["contract"]["assertions"]["/summary/unknown_bytes"]``
    - ``rom_gate["rom_coverage_audit"]["summary"]["unknown_bytes"]``
    - ``coverage["summary"]["unknown_bytes"]``
    """
    keys = _subscript_chain(node)
    if not keys:
        return None
    if keys[-1].startswith("/summary/"):
        return keys[-1][len("/summary/") :]
    if len(keys) >= 3 and keys[-3] == "rom_coverage_audit" and keys[-2] == "summary":
        return keys[-1]
    if len(keys) >= 2 and keys[-2] == "summary":
        return keys[-1]
    return None


LIVE_LEDGER_PATH = "sequel/rom-byte-coverage.json"


def _target_names(node: ast.AST) -> list[str]:
    """取赋值目标的「最后一段标识符」（``cls.coverage`` → ``coverage``）。"""
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [node.attr]
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in node.elts:
            names.extend(_target_names(element))
        return names
    return []


def _live_ledger_names(source: str) -> set[str]:
    """找出本文件里**绑定到活账本**的变量名。

    两步：先找出指向活账本路径的常量（例如 ``COVERAGE = ROOT / "…"``），
    再找出读取这些常量或直接读取该路径的赋值目标。
    """
    tree = ast.parse(source)
    path_globals: set[str] = set()
    live_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None:
            continue
        rendered = ast.unparse(value)
        targets = (
            [node.target]
            if isinstance(node, ast.AnnAssign)
            else node.targets
        )
        names = [name for target in targets for name in _target_names(target)]
        if LIVE_LEDGER_PATH in rendered:
            live_names.update(names)
            path_globals.update(names)
            continue
        # 只认「真的读了那个路径常量」的赋值：COVERAGE.read_text() / .read_bytes()
        for name in path_globals:
            if re.search(rf"\b{re.escape(name)}\.(read_text|read_bytes)\b", rendered):
                live_names.update(names)
                break
    return live_names


def _base_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _chain_base(node: ast.AST) -> ast.AST:
    """沿下标链走到最内层的基对象。"""
    while isinstance(node, ast.Subscript):
        node = node.value
    return node


def _summary_key_scoped(node: ast.AST) -> tuple[str | None, str | None, str]:
    """解析 summary 指针，返回 (键, 基对象名, 形态)。

    形态：

    - ``spec_pointer`` —— ``…["/summary/<key>"]``（来自 proof spec 的合同断言）；
    - ``audit_summary`` —— ``…["rom_coverage_audit"]["summary"]["<key>"]``；
    - ``direct_summary`` —— ``<对象>["summary"]["<key>"]``（直接读某个 summary）。
    """
    keys = _subscript_chain(node)
    if not keys:
        return None, None, "none"
    if keys[-1].startswith("/summary/"):
        return keys[-1][len("/summary/") :], _base_name(_chain_base(node)), "spec_pointer"
    if len(keys) >= 3 and keys[-3] == "rom_coverage_audit" and keys[-2] == "summary":
        return keys[-1], _base_name(_chain_base(node)), "audit_summary"
    if len(keys) >= 2 and keys[-2] == "summary":
        return keys[-1], _base_name(_chain_base(node)), "direct_summary"
    return None, None, "none"


def _scoped_literal_assertions(
    source: str,
) -> list[tuple[int, str, int, str, str | None]]:
    """列出所有「字面量 vs summary 键」的断言，并标注形态与基对象名。

    返回 (行号, 键, 字面量, 形态, 基对象名)。
    """
    tree = ast.parse(source)
    found: list[tuple[int, str, int, str, str | None]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "assertEqual"
            and len(node.args) == 2
        ):
            continue
        left, right = node.args
        for literal_side, pointer_side in ((left, right), (right, left)):
            literal = _const_int(literal_side)
            if literal is None:
                continue
            key, base, kind = _summary_key_scoped(pointer_side)
            if key is None:
                continue
            found.append((node.lineno, key, literal, kind, base))
    return found


def _literal_assertions(source: str) -> list[tuple[int, str, int]]:
    """列出所有「字面量 vs summary 键」的断言，返回 (行号, 键, 字面量)。"""
    tree = ast.parse(source)
    found: list[tuple[int, str, int]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "assertEqual"
            and len(node.args) == 2
        ):
            continue
        left, right = node.args
        for literal_side, pointer_side in ((left, right), (right, left)):
            literal = _const_int(literal_side)
            if literal is None:
                continue
            key = _summary_key(pointer_side)
            if key is None:
                continue
            found.append((node.lineno, key, literal))
    return found


_HEX64 = re.compile(r"[0-9a-f]{64}")
#: 累计型计数表达式（引号无关——ast.unparse 输出单引号形式）
#: 只匹配 `len(item['verifiers'])` 与 `*_verifier_count`，
#: 不要泛化到任意 `len(item[...])`（那是单 artifact 的稳定字段长度）。
_CUMULATIVE_COUNT_RE = re.compile(
    r"len\(item\[['\"]verifiers['\"]\]\)|[\w]*verifier_count['\"]\]"
)


def _digest_assertions(source: str) -> list[tuple[int, str, str]]:
    """列出所有「64 位十六进制字面量 vs 某个 spec 条目」的断言。

    返回 (行号, 摘要, 目标描述)。目标描述形如
    ``script_sha256`` 或 ``path:sequel/rom-byte-coverage.json``。
    """
    tree = ast.parse(source)
    found: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "assertEqual"
            and len(node.args) == 2
        ):
            continue
        left, right = node.args
        for literal_side, other_side in ((left, right), (right, left)):
            if not (
                isinstance(literal_side, ast.Constant)
                and isinstance(literal_side.value, str)
                and _HEX64.fullmatch(literal_side.value)
            ):
                continue
            if not isinstance(other_side, ast.Subscript):
                continue
            key = _const_str(other_side.slice)
            if key is None:
                continue
            if key == "script_sha256":
                found.append((node.lineno, literal_side.value, "script_sha256"))
            elif not key.startswith("/") and "/" in key:
                # 只把「仓库相对路径」当文件摘要目标。
                # `/summary/..._denominator_sha256` 这类 JSON pointer 是
                # **区间/分母派生哈希**，不是文件摘要，不受本规则约束。
                found.append((node.lineno, literal_side.value, f"path:{key}"))
    return found


def _cumulative_count_equalities(source: str) -> list[tuple[int, str, int]]:
    """列出所有「把累计型计数钉成等号」的断言，返回 (行号, 表达式)。"""
    tree = ast.parse(source)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "assertEqual"
            and len(node.args) == 2
        ):
            continue
        left, right = node.args
        for literal_side, other_side in ((left, right), (right, left)):
            if _const_int(literal_side) is None:
                continue
            rendered = ast.unparse(other_side)
            # ast.unparse 输出的是**单引号**形式，匹配必须引号无关。
            if _CUMULATIVE_COUNT_RE.search(rendered):
                found.append((node.lineno, rendered[:120], _const_int(literal_side)))
    return found


#: 「量」表达式：随批次／晋升变化的数值。
#:
#: 只有这种表达式出现在**第二个**参数时，字面量才是合法的上下界；
#: 出现在第一个参数就说明上下界写反了。
_QUANTITY_CALL_NAMES = frozenset(
    {"len", "sum", "max", "min", "abs", "round", "int", "sorted", "set", "list", "dict"}
)
#: 下标键看起来像一个「量」的判据（``*_count`` / ``*_bytes`` / ``verifiers`` …）。
_QUANTITY_KEY_RE = re.compile(
    r"(?:_count|_bytes|_num\b|^count$|^bytes$|^num$|verifiers|_total|_size)"
)
#: 变量名看起来像一个「量」的判据。
_QUANTITY_NAME_RE = re.compile(
    r"(?:^LIVE_|^live_|_count$|_bytes$|_total$|_COUNT$|_BYTES$|_TOTAL$)"
)


def _module_level_constant_names(tree: ast.Module) -> set[str]:
    """取模块级「常量」的变量名。

    两种来源都算：

    - 本文件直接赋值的数值常量（``VERIFIER_TIMEOUT_SECONDS = 3600``）；
    - 从别处导入的名字（``from … import VERIFIER_TIMEOUT_SECONDS``）——
      导入的通常是跨文件共享的量（超时、计数、容量），与字面量比较时
      方向写反同样是坏点。
    """
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            value = node.value
            if (
                isinstance(value, ast.Constant)
                and isinstance(value.value, int)
                and not isinstance(value.value, bool)
            ):
                for target in node.targets:
                    names.update(_target_names(target))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def _is_quantity_expression(node: ast.AST, constants: set[str]) -> bool:
    """判断表达式是否代表「一个会随批次变化的量」。

    判定必须**窄**：宁可漏掉部分真越界，也不能误伤
    「固定地址 vs 固定区间端点」这类写法——
    ``assertGreaterEqual(0x735C6, DISPATCH_RANGE[0])`` 语义是正确的
    （断言默认目标落在派发窗口内），把整数下标的区间端点误判成「量」就会误报。

    ``constants`` 是同文件里模块级数值常量的名字；拿它们当「量」是安全的，
    因为与字面量比较时结果只取决于常量本身，不随批次漂移。
    """
    if isinstance(node, ast.Call):
        return isinstance(node.func, ast.Name) and node.func.id in _QUANTITY_CALL_NAMES
    if isinstance(node, ast.BinOp):
        # 算术表达式一定是算出来的值。
        return True
    if isinstance(node, ast.Subscript):
        key = _const_str(node.slice)
        if key is None:
            # 整数下标（``RANGE[0]``）是**固定区间端点**，不是量。
            return False
        return bool(_QUANTITY_KEY_RE.search(key))
    if isinstance(node, ast.Name):
        return bool(_QUANTITY_NAME_RE.search(node.id)) or node.id in constants
    return False


def _reversed_bound_assertions(source: str) -> list[tuple[int, str]]:
    """列出所有「上下界断言参数顺序写反」的调用点。

    ``assertGreaterEqual(实际值, 下限)`` / ``assertLessEqual(实际值, 上限)``
    的**第一个参数必须是实际值**。字面量写在第一位、量表达式写在第二位时，
    断言方向就反了（``96 not greater than or equal to 109``），
    而这种写法语法完全合法，任何「有没有用 assertEqual」的检查都抓不到。
    """
    tree = ast.parse(source)
    constants = _module_level_constant_names(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("assertGreaterEqual", "assertLessEqual")
            and len(node.args) >= 2
        ):
            continue
        first, second = node.args[0], node.args[1]
        if _const_int(first) is None:
            continue
        if not _is_quantity_expression(second, constants):
            continue
        found.append((node.lineno, ast.unparse(node)[:120]))
    return found


def _global_derived_in_scoped_contracts(
    source: str,
) -> list[tuple[int, str, str]]:
    """找出「单验证器合同 / 合成夹具」里引用全局派生量的地方。

    两种形态：

    - ``assertEqual({…}, verifier["contract"]["assertions"])``——整字典对拍，
      全局覆盖合同从不整字典对拍，所以这一定是单验证器合同；
    - ``_reuse_rom_coverage_contract(…, contract, payload, …)``——合成夹具。
    """
    tree = ast.parse(source)
    found: list[tuple[int, str, str]] = []

    def mentions_global(node: ast.AST) -> bool:
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Subscript)
                and isinstance(child.value, ast.Name)
                and child.value.id == "LIVE_COVERAGE_SUMMARY"
            ):
                return True
        return False

    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "assertEqual"
            and len(node.args) == 2
        ):
            continue
        for dict_side, other_side in ((node.args[0], node.args[1]), (node.args[1], node.args[0])):
            if not isinstance(dict_side, ast.Dict):
                continue
            keys = _subscript_chain(other_side)
            if not keys or "assertions" not in keys:
                continue
            if "contract" not in keys:
                continue
            if mentions_global(dict_side):
                found.append(
                    (node.lineno, "per-verifier contract", ast.unparse(dict_side)[:120])
                )
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_reuse_rom_coverage_contract"
        ):
            continue
        for argument in node.args:
            if isinstance(argument, ast.Dict) and mentions_global(argument):
                found.append(
                    (node.lineno, "synthetic fixture", ast.unparse(argument)[:120])
                )
    return found


def _sha256_of(path: Path) -> str | None:
    """返回文件的 SHA-256；文件不存在时返回 None。"""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


class CoverageCountLivenessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.live = json.loads(LEDGER.read_text(encoding="utf-8"))["summary"]
        cls.spec = json.loads(SPEC.read_text(encoding="utf-8"))
        coverage = next(
            item
            for item in cls.spec["gates"]["rom_byte_coverage"]["verifiers"]
            if item["command"][1] == COVERAGE_VERIFIER
        )
        cls.assertions = coverage["contract"]["assertions"]

    def test_spec_coverage_assertions_exist_in_live_ledger(self) -> None:
        """spec 声明的每个 /summary/* 断言都必须在活账本里有对应键。"""
        missing = sorted(
            pointer[len("/summary/") :]
            for pointer in self.assertions
            if pointer.startswith("/summary/")
            and pointer[len("/summary/") :] not in self.live
        )
        self.assertEqual([], missing)

    def test_spec_coverage_assertions_equal_live_ledger(self) -> None:
        """spec 声明的每个 /summary/* 断言值必须与活账本逐项相等。"""
        mismatched = []
        for pointer, declared in self.assertions.items():
            if not pointer.startswith("/summary/"):
                continue
            key = pointer[len("/summary/") :]
            if key not in self.live:
                continue
            if self.live[key] != declared:
                mismatched.append((key, declared, self.live[key]))
        self.assertEqual([], mismatched)

    def test_no_test_source_hardcodes_a_live_ledger_quantity(self) -> None:
        """任何测试文件都不得拿字面量去比一个**活账本**里存在的键。

        判定分两种：

        - ``/summary/<key>`` 指针（来自 proof spec 的合同断言）与
          ``["rom_coverage_audit"]["summary"][<key>]`` 形态——它们指向的
          就是活账本的值，一律不得写死；
        - ``<对象>["summary"][<key>]`` 形态——只有当该对象**确实绑定到
          活账本**（本文件里从 ``sequel/rom-byte-coverage.json`` 读出来）时
          才算活账本断言；否则它是夹具／历史收据的摘要，**写死是对的**。

        唯一例外是**登记过的历史钉**——它们钉的是冻结收据里的历史值。
        """
        stale: list[tuple[str, int, str, int, int]] = []
        for path in sorted(TESTS_DIR.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "/summary/" not in source and "summary" not in source:
                continue
            live_names = _live_ledger_names(source)
            allowed = HISTORICAL_PINNED.get(path.name, {})
            for line, key, literal, kind, base in _scoped_literal_assertions(source):
                if kind == "direct_summary" and base not in live_names:
                    # 夹具／历史收据的摘要，不是活账本断言。
                    continue
                current = self.live.get(key)
                if current is None:
                    continue
                if current == literal:
                    continue
                if allowed.get(key) == literal:
                    continue
                stale.append((path.name, line, key, literal, current))
        self.assertEqual([], stale)

    def test_no_test_source_pins_a_stale_digest(self) -> None:
        """任何测试文件都不得把**文件摘要**钉成字面量。

        覆盖三类会随晋升／脚本改动而过期的摘要：

        - ``evidence["<path>"]`` —— 证据文件摘要（账本每次晋升都变）；
        - ``X["script_sha256"]`` —— 验证器脚本摘要（脚本被改就会变）；
        - 任何直接写死 64 位十六进制、并拿去与活文件对拍的字面量。

        正确写法是**与活文件对拍**（``_sha256(ROOT / path)``），
        断言的是「spec 声称的摘要 == 文件真实摘要」，
        既不随晋升过期，又真的能抓出 spec 与磁盘不一致。
        """
        spec_scripts: dict[str, set[str]] = {}
        for gate in self.spec["gates"].values():
            for verifier in gate.get("verifiers", []):
                for part in verifier.get("command", []):
                    if part.endswith(".py") and (ROOT / part).is_file():
                        spec_scripts.setdefault(verifier.get("script_sha256"), set()).add(
                            part
                        )
                        break

        stale: list[tuple[str, int, str]] = []
        for path in sorted(TESTS_DIR.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "[0-9a-f]" not in source and "script_sha256" not in source:
                continue
            for line, digest, target in _digest_assertions(source):
                if target == "script_sha256":
                    scripts = spec_scripts.get(digest)
                    if not scripts:
                        stale.append(
                            (path.name, line, f"{digest[:16]}…（spec 里已无此脚本摘要）")
                        )
                        continue
                    for script in sorted(scripts):
                        actual = _sha256_of(ROOT / script)
                        if actual != digest:
                            stale.append(
                                (
                                    path.name,
                                    line,
                                    f"{digest[:16]}… != {str(actual)[:16]}… ({script})",
                                )
                            )
                    continue
                relative = target.split(":", 1)[1]
                actual = _sha256_of(ROOT / relative)
                if actual is None:
                    stale.append((path.name, line, f"{digest[:16]}…（文件不存在 {relative}）"))
                elif actual != digest:
                    stale.append(
                        (
                            path.name,
                            line,
                            f"{digest[:16]}… != {actual[:16]}… ({relative})",
                        )
                    )
        self.assertEqual([], stale)

    def test_cumulative_counts_use_at_least_not_equal(self) -> None:
        """累计型计数必须写成「至少」，不得用 assertEqual 钉死。

        覆盖两种会随批次增长而变红的写法：

        - ``assertEqual(N, sum(len(item["verifiers"]) …))``
        - ``assertEqual(N, gate["…_verifier_count"])`` 且 N 是**全局**量级
          （≥ 90；单 bank／单 artifact 的 ``contracted_verifier_count == 1``
          是稳定的批次量，不在其列）

        这类断言的**原意是下限**（「不比这个批次落地时更少」），
        钉成等号就等于宣称「数量永远不变」——每次晋升都会打破。

        作用域限于 proof 套件模块：其他模块里的 ``*_verifier_count``
        多为单 bank／单 artifact 的稳定计数，语义不同。
        """
        offenders: list[tuple[str, int, str]] = []
        source = PROOF_TEST.read_text(encoding="utf-8")
        for line, expr, pinned in _cumulative_count_equalities(source):
            if "_verifier_count" in expr and pinned < 90:
                continue
            offenders.append((PROOF_TEST.name, line, expr))
        self.assertEqual([], offenders)

    def test_at_least_assertions_put_the_expression_first(self) -> None:
        """``assertGreaterEqual(实际值, 下限)`` —— **实际值必须在第一个参数**。

        这条是本轮真实踩过的坑：把 ``assertEqual(N, expr)`` 批量改成
        ``assertGreaterEqual(N, expr)`` 时**参数顺序写反了**，
        断言变成「下限 ≥ 实际值」，于是 21 个测试全红
        （`96 not greater than or equal to 109`）。

        顺序写反不会让语法出错、也不会被任何"有没有用 assertEqual"的
        检查抓到——所以必须单独立一条守卫。
        """
        offenders: list[tuple[str, int, str]] = []
        for path in sorted(TESTS_DIR.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "assertGreaterEqual" not in source and "assertLessEqual" not in source:
                continue
            for line, rendered in _reversed_bound_assertions(source):
                offenders.append((path.name, line, rendered[:120]))
        self.assertEqual([], offenders)

    def test_bound_order_detector_is_not_vacuous(self) -> None:
        """反向自检：检测器本身必须能认出「写反」与「写对」。

        没有这一条，规则一旦收窄到什么都不匹配，上面那条守卫就会**永远绿**，
        而它保护的正是一类「语法完全合法、只在运行时炸」的错。
        """
        reversed_case = textwrap.dedent(
            """
            VERIFIER_TIMEOUT_SECONDS = 3600
            self.assertGreaterEqual(96, len(gate["verifiers"]))
            self.assertLessEqual(1800, len(gate["evidence"]))
            self.assertGreaterEqual(1800, VERIFIER_TIMEOUT_SECONDS)
            """
        )
        correct_cases = textwrap.dedent(
            """
            VERIFIER_TIMEOUT_SECONDS = 3600
            self.assertGreaterEqual(len(gate["verifiers"]), 96)
            self.assertLessEqual(len(gate["evidence"]), 1800)
            self.assertGreaterEqual(0x735C6, DISPATCH_RANGE[0])
            self.assertGreaterEqual(VERIFIER_TIMEOUT_SECONDS, 1_800)
            """
        )
        self.assertEqual(3, len(_reversed_bound_assertions(reversed_case)))
        self.assertEqual([], _reversed_bound_assertions(correct_cases))

    def test_per_verifier_contracts_do_not_use_global_derived_values(self) -> None:
        """单验证器合同与合成夹具**不得**引用全局派生量。

        这是本轮踩过的真回归：``classified_bytes`` / ``unknown_bytes``
        既是全局覆盖量的键名，也是**单验证器批次合同**和**合成夹具**里的键名。
        按键名批量派生时，单验证器合同的批次值（816 / 2,740 / 414）
        和夹具值（7）被错换成活账本全局量，直接打破 4 个测试。

        判定方式：**整字典对拍**只用于单验证器合同
        （全局覆盖合同永远是逐键对拍），因此
        「整字典里出现 LIVE_COVERAGE_SUMMARY 引用」即是越界；
        合成夹具同理。
        """
        offenders: list[tuple[str, int, str]] = []
        for path in sorted(TESTS_DIR.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "LIVE_COVERAGE_SUMMARY" not in source:
                continue
            for line, kind, detail in _global_derived_in_scoped_contracts(source):
                offenders.append((path.name, line, f"{kind}: {detail}"))
        self.assertEqual([], offenders)

    def test_historical_pins_are_still_pinned_to_the_old_value(self) -> None:
        """反向护栏：登记过的历史钉必须**仍然**钉在旧值上。

        如果有人把历史钉改成活账本当前值，登记就失去意义；
        如果有人把登记清空，覆盖面就被悄悄扩大了。
        """
        for name, pinned in HISTORICAL_PINNED.items():
            source = (TESTS_DIR / name).read_text(encoding="utf-8")
            for key, literal in pinned.items():
                observed = [
                    value
                    for _, asserted_key, value in _literal_assertions(source)
                    if asserted_key == key
                ]
                self.assertIn(
                    literal,
                    observed,
                    f"{name} 应当仍然钉住 {key}={literal}（9-30 收据的历史值）",
                )
                self.assertNotEqual(
                    self.live[key],
                    literal,
                    f"{name} 的 {key} 历史钉不得与活账本当前值相同，否则它不再是历史钉",
                )

    def test_global_quantities_are_derived_not_hardcoded(self) -> None:
        """全局量 / 累计量必须写成派生引用，不得回到字面量。"""
        source = PROOF_TEST.read_text(encoding="utf-8")
        hardcoded = sorted(
            (line, key, literal)
            for line, key, literal in _literal_assertions(source)
            if key in GLOBAL_KEYS
        )
        self.assertEqual([], hardcoded)

    def test_batch_increments_remain_hardcoded(self) -> None:
        """反向护栏：批次增量必须保持硬编码，不能被「一并派生」掉。

        取两个稳定的批次增量指针做样本——它们落地后不再变化，
        硬编码才是对它们的真正保护。
        """
        source = PROOF_TEST.read_text(encoding="utf-8")
        for key in (
            "positions_aux_dispatch_bytes",
            "cutscene_obj_alignment_gap_bytes",
        ):
            literals = [
                literal
                for _, asserted_key, literal in _literal_assertions(source)
                if asserted_key == key
            ]
            self.assertTrue(literals, f"批次增量 {key} 应当保持硬编码")
            self.assertEqual(
                {self.live[key]},
                set(literals),
                f"批次增量 {key} 的硬编码值必须与账本一致",
            )


if __name__ == "__main__":
    unittest.main()
