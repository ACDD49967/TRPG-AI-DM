"""分层记忆系统回归：轮次压缩、剧情记忆去重与上下文渲染。

`engine/memory.py` 拆成 memory_plot / memory_context 之前没有任何测试覆盖，
这里把拆开后必须保持的语义钉住（尤其是
`build_essential_context` 不含最近对话、`build_context` 含）。
"""
import unittest

from backend.engine.memory import DialogueTurn, MemorySystem


class TestDialogueMemory(unittest.TestCase):
    def test_add_turn_records_events(self):
        mem = MemorySystem()
        mem.add_turn("我调查灰石村", "你发现了脚印", ["察觉 d20=15"])
        self.assertEqual(len(mem.turns), 1)
        self.assertEqual(mem.turns[0].player_input, "我调查灰石村")
        self.assertEqual(mem.turns[0].events, ["察觉 d20=15"])
        self.assertIsInstance(mem.turns[0], DialogueTurn)

    def test_compaction_trims_old_turns_into_summary(self):
        mem = MemorySystem(summary_trigger=3, max_active_turns=4)
        for i in range(1, 8):
            mem.add_turn(f"第{i}次行动", f"第{i}次结果", [f"事件{i}"])
        self.assertEqual(len(mem.turns), 4, "只保留最近 max_active_turns 轮")
        self.assertIn("先前发生的事", mem.summary)
        self.assertIn("第1次行动", mem.summary)
        self.assertNotIn("第7次行动", mem.summary)

    def test_short_history_does_not_summarise(self):
        mem = MemorySystem(summary_trigger=8, max_active_turns=10)
        for i in range(3):
            mem.add_turn(f"行动{i}", "结果")
        self.assertEqual(mem.summary, "")
        self.assertEqual(len(mem.turns), 3)


class TestPlotMemory(unittest.TestCase):
    def test_world_fact_dedup(self):
        mem = MemorySystem()
        mem.add_world_fact("灰石村有地精出没")
        mem.add_world_fact("灰石村有地精出没")
        self.assertEqual(mem.world_facts, ["灰石村有地精出没"])

    def test_major_event_updates_same_title_and_caps_list(self):
        mem = MemorySystem()
        mem.add_major_event("灰石村遇袭", "地精夜袭", impact="村民受伤", turn=2)
        mem.add_major_event("灰石村遇袭", "地精夜袭（修订）", impact="村民轻伤", turn=3)
        self.assertEqual(len(mem.major_events), 1, "同标题视为同一事件")
        self.assertEqual(mem.major_events[0]["turn"], 3)
        for i in range(70):
            mem.add_major_event(f"事件{i}")
        self.assertLessEqual(len(mem.major_events), 60, "大事件列表要有上限")

    def test_blank_title_is_ignored(self):
        mem = MemorySystem()
        mem.add_major_event("   ")
        self.assertEqual(mem.major_events, [])

    def test_hidden_thread_status_validation_and_update(self):
        mem = MemorySystem()
        mem.add_hidden_thread("幕后黑手", "有人在资助地精", status="乱写的状态", progress="发现印记")
        self.assertEqual(mem.hidden_threads[0]["status"], "未触发", "非法状态回落到未触发")
        mem.update_hidden_thread("幕后黑手", status="进行中", progress="追到营地")
        self.assertEqual(mem.hidden_threads[0]["status"], "进行中")
        self.assertEqual(mem.hidden_threads[0]["progress"], "追到营地")

    def test_update_unknown_thread_creates_minimal_entry(self):
        mem = MemorySystem()
        mem.update_hidden_thread("新暗线", status="进行中")
        self.assertEqual(len(mem.hidden_threads), 1)
        self.assertEqual(mem.hidden_threads[0]["key"], "新暗线")

    def test_character_impact_dedup(self):
        mem = MemorySystem()
        mem.add_character_impact("铁匠老张", "被地精打伤", event="夜袭", turn=2)
        mem.add_character_impact("铁匠老张", "被地精打伤", event="夜袭", turn=3)
        self.assertEqual(len(mem.character_impacts), 1)
        self.assertEqual(mem.character_impacts[0]["turn"], 3)
        mem.add_character_impact("铁匠老张", "")
        self.assertEqual(len(mem.character_impacts), 1, "空影响不记录")


class TestMemoryContext(unittest.TestCase):
    def make_mem(self) -> MemorySystem:
        mem = MemorySystem()
        mem.add_turn("我调查灰石村", "你发现了地精斥候的脚印", ["察觉 d20=15"])
        mem.add_world_fact("灰石村有地精出没")
        mem.add_major_event("灰石村遇袭", "地精夜袭", impact="村民受伤", turn=2)
        mem.add_hidden_thread("幕后黑手", "有人在资助地精", status="进行中", progress="发现印记")
        mem.add_hidden_thread("已了结的线", "旧线索", status="已完成")
        mem.add_character_impact("铁匠老张", "被地精打伤", event="夜袭", turn=2)
        return mem

    def test_build_context_contains_everything(self):
        text = self.make_mem().build_context()
        self.assertIn("## 大事件记忆", text)
        self.assertIn("灰石村遇袭", text)
        self.assertIn("## 暗线进度", text)
        self.assertIn("幕后黑手", text)
        self.assertIn("## 重要人物影响", text)
        self.assertIn("铁匠老张", text)
        self.assertIn("## 重要世界事实", text)
        self.assertIn("## 最近发生的事", text)
        self.assertIn("我调查灰石村", text)

    def test_essential_context_excludes_recent_turns(self):
        text = self.make_mem().build_essential_context()
        self.assertNotIn("## 最近发生的事", text, "模块化回合不该重复注入最近对话")
        self.assertIn("灰石村遇袭", text)
        self.assertIn("幕后黑手", text)

    def test_completed_threads_are_hidden(self):
        text = self.make_mem().build_essential_context()
        self.assertNotIn("已了结的线", text, "只列未触发/进行中的暗线")

    def test_shared_blocks_are_identical_prefix(self):
        """两段上下文共有部分必须逐字相同（拆分后抽出的 _render_shared_blocks）。"""
        mem = self.make_mem()
        essential = mem.build_essential_context()
        full = mem.build_context()
        self.assertTrue(full.startswith(essential))
        self.assertEqual(essential, full[:len(essential)])

    def test_summary_is_included(self):
        mem = MemorySystem(summary_trigger=3, max_active_turns=4)
        for i in range(1, 8):
            mem.add_turn(f"第{i}次行动", "结果")
        self.assertIn("## 之前的故事摘要", mem.build_context())


if __name__ == "__main__":
    unittest.main()
