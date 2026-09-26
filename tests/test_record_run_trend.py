"""体检趋势工具：不同 -Turns 的跑法不能互相比较（真实误报过一次）。"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from dist import _record_run


def _row(ts: str, turns: int, tokens: int) -> dict:
    return {"ts": ts, "long_run_turns": turns, "total_tokens": tokens,
            "model_calls": max(1, turns * 3), "passed": True, "failures": 0}


class TestTrendComparison(unittest.TestCase):
    def _show(self, rows: list[dict]) -> str:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        history = Path(tmp.name) / "history.jsonl"
        history.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        buf = io.StringIO()
        with patch.object(_record_run, "HISTORY", history), redirect_stdout(buf):
            _record_run.show()
        return buf.getvalue()

    def test_different_turn_counts_do_not_trigger_a_regression_warning(self):
        """真实误报：3 回合的 77k 与 6 回合的 285k 被直接比总量。"""
        rows = [_row("2026-01-01T00:00:00", 3, 77_000),
                _row("2026-01-02T00:00:00", 3, 76_996),
                _row("2026-01-03T00:00:00", 6, 285_375)]
        out = self._show(rows)
        self.assertNotIn("值得看看是不是回退", out)
        self.assertIn("暂不判定回退", out, "同类历史不足时要说明，而不是乱报警")

    def test_same_turn_counts_warn_on_a_real_regression(self):
        rows = [_row("2026-01-01T00:00:00", 3, 60_000),
                _row("2026-01-02T00:00:00", 3, 61_000),
                _row("2026-01-03T00:00:00", 3, 120_000)]
        out = self._show(rows)
        self.assertIn("值得看看是不是回退", out)
        self.assertIn("每回合 tokens", out)

    def test_same_turn_counts_within_tolerance_stay_quiet(self):
        rows = [_row("2026-01-01T00:00:00", 3, 60_000),
                _row("2026-01-02T00:00:00", 3, 61_000),
                _row("2026-01-03T00:00:00", 3, 66_000)]
        out = self._show(rows)
        self.assertNotIn("值得看看是不是回退", out)

    def test_build_record_adds_per_turn_metrics(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "regression_report.json").write_text(json.dumps({
            "ts": "2026-01-01T00:00:00", "long_run_turns": 6, "passed": True, "problems": [],
            "long_run": {"totals": {"total_tokens": 285_000, "model_calls": 57, "failures": 0},
                         "turn_wall_ms": [1000], "turn_first_output_ms": [500]},
            "compare": {"deep": {"tokens_median": 89836}, "lite": {"tokens_median": 65292}},
            "compare_runs": 1,
        }), encoding="utf-8")
        with patch.object(_record_run, "REGRESSION", root / "regression_report.json"), \
             patch.object(_record_run, "FIRST_RUN", root / "ui_first_run_report.json"):
            record = _record_run.build_record()
        self.assertEqual(record["tokens_per_turn"], 47_500, "285000 / 6")
        self.assertEqual(record["calls_per_turn"], 9.5)
        self.assertFalse(record["journey_passed"], "没有首次体验报告时按未通过记")


if __name__ == "__main__":
    unittest.main()
