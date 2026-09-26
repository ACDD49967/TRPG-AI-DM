"""懒加载 import 契约：函数体里的 `from backend... import X` 必须真的能解析。

这类写法 pyflakes 查不出来（它只做静态绑定分析，不解析被导入模块里到底有没有这个名字），
冒烟测试也常常够不到——只有真正调用那条分支才会炸。已经踩过三次：

1. `routers/scenarios_import.py` 里 `from backend.scenario_importer import detect_game_system`，
   而门面在拆分时漏了这个再导出 → 剧本导入端点 **HTTP 500**（且当时没有任何测试覆盖）；
2. `world_state_tools` 拆出后漏了 `_exec_update_scene`；
3. `dm_system_prompt` 压缩模式分支漏了 6 个提示词常量。

这里用 AST 把整个 backend 里"函数内的 backend 模块 import"全部找出来，逐个解析名字，
把这一类错误变成一条便宜的全量回归。
"""
import ast
import importlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _lazy_backend_imports() -> list[tuple[str, str, str, int]]:
    """返回 [(文件, 模块, 名字, 行号)]，只统计函数体内的 backend.* 导入。"""
    found: list[tuple[str, str, str, int]] = []
    for path in sorted(ROOT.glob("backend/**/*.py")):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:  # pragma: no cover - 语法错误会由别的测试先抓到
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.ImportFrom) or not inner.module:
                    continue
                if not inner.module.startswith("backend"):
                    continue
                for alias in inner.names:
                    if alias.name == "*":
                        continue
                    found.append((path.relative_to(ROOT).as_posix(), inner.module,
                                  alias.name, inner.lineno))
    return found


class TestBackendLazyImports(unittest.TestCase):
    def test_every_lazy_backend_import_resolves(self):
        problems: list[str] = []
        for file_rel, module_name, name, lineno in _lazy_backend_imports():
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:  # pragma: no cover - 模块本身都该能导入
                problems.append(f"{file_rel}:{lineno} 无法导入 {module_name}: {exc!r}")
                continue
            if not hasattr(module, name):
                # `from backend.engine import battlefield` 这种写法，属性可能还没挂上——
                # Python 会退化成导入子模块，这里按同样的规则再试一次。
                try:
                    importlib.import_module(f"{module_name}.{name}")
                except Exception:
                    problems.append(f"{file_rel}:{lineno} {module_name} 没有 {name}")
        self.assertEqual(problems, [], "函数内懒加载 import 指向了不存在的名字：\n" + "\n".join(problems))

    def test_scenario_importer_facade_reexports_import_chain(self):
        """剧本导入端点的懒加载链（曾经因为门面漏再导出而 500）。"""
        from backend.scenario_importer import (
            detect_game_system, extract_text, generate_scenario_from_text, split_text,
        )
        self.assertTrue(callable(detect_game_system))
        self.assertTrue(all(callable(fn) for fn in (extract_text, generate_scenario_from_text, split_text)))


if __name__ == "__main__":
    unittest.main()
