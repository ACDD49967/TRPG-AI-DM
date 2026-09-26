"""声明动作必须被工具结算：分发误判时的兜底与强制重试。"""
import unittest

from backend.engine import dm_agent as dm
from backend.engine.dm_modules import _classify


class TestDispatchKeywords(unittest.TestCase):
    def test_combat_phrasing_without_obvious_keywords(self):
        for text in ("我转身对付地精弓手。", "我挥剑劈向它。", "我冲上去扑倒它。",
                     "我追击那只逃跑的地精。"):
            self.assertEqual(_classify(text), "combat", text)

    def test_exploration_is_not_combat(self):
        for text in ("我环顾四周，观察有没有值得注意的东西。", "我走向铁匠铺，问问他最近有没有陌生人经过。"):
            self.assertIn(_classify(text), ("scene", "social", "memory", "graph", "narrative", "rules"), text)
            self.assertNotEqual(_classify(text), "combat", text)


class TestSettlementIntent(unittest.TestCase):
    def test_intent_groups(self):
        self.assertEqual(dm.required_settlement_group("我举剑砍下去"), "attack")
        self.assertEqual(dm.required_settlement_group("我逼它吐火"), "enemy_action")
        self.assertEqual(dm.required_settlement_group("我引诱它攻击我"), "enemy_action")
        self.assertEqual(dm.required_settlement_group("我对它施放魔法飞弹"), "cast")
        self.assertEqual(dm.required_settlement_group("我在原地短休"), "rest")
        self.assertEqual(dm.required_settlement_group("我看看四周有什么"), "")

    def test_required_tools_mapping(self):
        self.assertEqual(dm._SETTLEMENT_TOOLS["attack"], {"combat_round"})
        self.assertEqual(dm._SETTLEMENT_TOOLS["enemy_action"], {"enemy_attack"})
        self.assertEqual(dm._SETTLEMENT_TOOLS["cast"], {"cast_spell"})
        self.assertEqual(dm._SETTLEMENT_TOOLS["rest"], {"take_rest"})


if __name__ == "__main__":
    unittest.main()
