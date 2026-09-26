"""子 Agent 成本 A/B 开关：DND_SKIP_AGENTS 只影响被点名的任务，且不会清空上下文。"""
import os
import unittest
from unittest.mock import patch

from backend.engine.dm_brief_tasks import build_dm_brief_tasks, skipped_agent_keys


def build(module: str = "social") -> list[dict]:
    return build_dm_brief_tasks(
        player_input="我朝对面喊话", module=module, lite=False, system="dnd5e",
        char_info="岚 Lv3", retrieved=[], memory_text="记得玛拉欠你一次",
        recent_text="上一轮你走进酒馆", world_text="石桥镇：玛拉在场",
        world_compact="石桥镇", graph_text="玛拉—神父：敌对",
    )


class TestAgentSkipSwitch(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("DND_SKIP_AGENTS", None)

    def test_default_is_no_skip(self):
        self.assertEqual(skipped_agent_keys(), set())
        self.assertEqual([t["key"] for t in build()], ["world", "memory", "graph"],
                         "默认编队不能变")

    def test_named_keys_are_dropped(self):
        with patch.dict(os.environ, {"DND_SKIP_AGENTS": "graph"}):
            self.assertEqual([t["key"] for t in build()], ["world", "memory"])
        with patch.dict(os.environ, {"DND_SKIP_AGENTS": " graph , memory "}):
            self.assertEqual([t["key"] for t in build()], ["world"])

    def test_skipping_everything_keeps_the_top_priority_task(self):
        with patch.dict(os.environ, {"DND_SKIP_AGENTS": "world,memory,graph"}):
            tasks = build()
        self.assertEqual([t["key"] for t in tasks], ["world"],
                         "实验开关不能把子 Agent 上下文清空")

    def test_combat_still_has_its_two_agents(self):
        with patch.dict(os.environ, {"DND_SKIP_AGENTS": "graph"}):
            self.assertEqual([t["key"] for t in build("combat")], ["rules", "world"])


if __name__ == "__main__":
    unittest.main()
