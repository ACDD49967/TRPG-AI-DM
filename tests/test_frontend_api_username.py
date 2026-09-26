"""静态守卫：前端直连 /api/game/* 的调用必须带上 username。

真实事故：后端会话接口按 username 查归属，漏传就落到 default，非 default 账号一律 404。
受影响的有四处（手动存档、DM 工具新增角色、两个机翻按钮），都只在账号不是 default 时才炸，
而自动存档走后端内部调用、不受影响，所以一直没被发现。

判定刻意宽松：该行或前后几行出现过 username 就算通过，覆盖 `?username=`、
`params.set('username', ...)` 与 `fd.append('username', ...)` 三种写法。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = ROOT / "frontend" / "src"
DIRECT_GAME_FETCH = re.compile(r"fetch\(\s*`/api/game/")
# 往回看 6 行：useGraphState 是先 params.set('username', ...) 再拼 URL 的写法
NEIGHBORHOOD = 6


def scan_offenders(files: list[Path]) -> list[str]:
    """返回"直连 /api/game 但附近没有 username"的位置清单。"""
    offenders: list[str] = []
    for path in files:
        if path.suffix not in (".ts", ".tsx"):
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if not DIRECT_GAME_FETCH.search(line):
                continue
            window = lines[max(0, index - NEIGHBORHOOD): index + 3]
            if any("username" in item for item in window):
                continue
            try:
                rel = path.relative_to(ROOT).as_posix()
            except ValueError:  # 自测用的临时文件不在仓库里
                rel = path.name
            offenders.append(f"{rel}:{index + 1}: {line.strip()[:110]}")
    return offenders


class TestFrontendGameApiUsername(unittest.TestCase):
    def _scan_text(self, text: str) -> list[str]:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.tsx"
            path.write_text(text, encoding="utf-8")
            return scan_offenders([path])

    def test_scanner_flags_a_missing_username(self):
        """先证明扫描器真的会报，否则它只是个永远通过的空转。"""
        sample = "\n".join([
            "const r = await fetch(`/api/game/${sessionId}/save`, {",
            "  method: 'POST',",
            "});",
        ])
        self.assertTrue(self._scan_text(sample), "漏 username 的调用必须被报出来")

    def test_scanner_accepts_the_three_legit_shapes(self):
        samples = [
            "const r = await fetch(`/api/game/${sid}/save?username=${u}`);",
            "const params = new URLSearchParams();\nparams.set('username', u);\n"
            "const r = await fetch(`/api/game/${sid}/graph?${params.toString()}`);",
            "fd.append('username', u);\n"
            "await fetch(`/api/game/${sid}/npc/image`, { method: 'POST', body: fd });",
        ]
        for sample in samples:
            with self.subTest(sample=sample.splitlines()[0]):
                self.assertEqual(self._scan_text(sample), [])

    def test_frontend_sources_pass_the_guard(self):
        offenders = scan_offenders(sorted(FRONTEND_SRC.rglob("*")))
        self.assertEqual(
            offenders, [],
            "这些前端调用没带 username，非 default 账号会 404：\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
