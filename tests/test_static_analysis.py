"""静态检查守卫：防止"搬走了代码却忘了搬 import"这类拆分事故。

背景（真实事故，全部由 undefined name 引起）：
- 拆出 combat/character_state/dm_prompts 后，`re` 没跟着搬；
- 拆出 backend/routers/ 后，`_os`、`WorldState`、`sse_event_generator` 漏搬；
- 更早的 `scenario_importer` 与 `pdf_extractor` 也各漏一个名字。

这些名字大多有 try/except 兜底，跑测试不一定会红，但线上会静默降级。
这里用 pyflakes 只检查 `undefined name`：不检查未使用的 import，
因为 dm_agent 的再导出是刻意保留的兼容面。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:  # pyflakes 属开发依赖，缺失时跳过而不是失败
    import pyflakes.api
    import pyflakes.messages
    from pyflakes.reporter import Reporter
except Exception:  # pragma: no cover - 本地未装开发依赖
    pyflakes = None
    Reporter = None


class _UndefinedNameReporter(Reporter if Reporter else object):
    """只收集 undefined name；静态检查自身的错误单独记录。"""

    def __init__(self):
        self.undefined: list[str] = []
        self.errors: list[str] = []

    def unexpectedError(self, filename, msg):  # pragma: no cover - 读取失败
        self.errors.append(f"{filename}: {msg}")

    def syntaxError(self, filename, msg, lineno, offset, text):  # pragma: no cover
        self.errors.append(f"{filename}:{lineno}: {msg}")

    def flake(self, message):
        if isinstance(message, pyflakes.messages.UndefinedName):
            self.undefined.append(
                f"{message.filename}:{message.lineno}: {message.message % message.message_args}")


@unittest.skipIf(pyflakes is None, "未安装 pyflakes（开发依赖）")
class TestNoUndefinedNames(unittest.TestCase):
    def test_backend_has_no_undefined_names(self):
        reporter = _UndefinedNameReporter()
        pyflakes.api.checkRecursive([str(ROOT / "backend")], reporter)
        self.assertEqual(reporter.errors, [], "静态检查本身出错")
        self.assertEqual(reporter.undefined, [], "存在未定义的名称（拆分时漏搬 import？）")


if __name__ == "__main__":
    unittest.main()
