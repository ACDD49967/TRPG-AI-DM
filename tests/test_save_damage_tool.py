"""save_damage 工具：范围/豁免伤害结算（后端规则，不再让 DM 手改 HP）。"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import combat, dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestSaveDamage(unittest.IsolatedAsyncioTestCase):
    def make_state(self, enemies: list[tuple[str, int, list[str]]] | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "save_dmg", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 5, "xp": 0, "game_system": "dnd5e",
             "char_class": "法师", "attributes": {"int": 18, "dex": 14}},
        )
        state.world_state = WorldState(session_id="save_dmg", _storage_dir=tmp.name)
        for name, hp, traits in (enemies or [("地精A", 20, []), ("地精B", 20, [])]):
            state.world_state.npcs.append(
                NpcEntry(name=name, attitude="敌对", hp=hp, max_hp=hp, ac=13, level=1,
                         alive=True, traits=list(traits)))
        state.turn_tool_results = {}
        state.turn_action_ledger = {}
        return state

    async def test_failed_and_successful_saves_apply_full_and_half(self):
        state = self.make_state()

        async def fake_persist(state_arg, npc, new_hp):
            npc.hp = max(0, int(new_hp))
            npc.alive = npc.hp > 0
            return 0

        # 第一次掷 2（失败，全额 20），第二次掷 19（成功，减半 10）
        with patch.object(dm.random, "randint", side_effect=[2, 19]), \
             patch.object(combat, "_persist_combat_damage", new=fake_persist):
            result = await dm.execute_tool("save_damage", {
                "targets": ["地精A", "地精B"], "dc": 15, "ability": "dex", "damage": 20,
                "reason": "火球术", "damage_type": "火焰",
            }, state)

        self.assertIn("地精A", result)
        self.assertIn("失败", result)
        self.assertIn("成功", result)
        hp = {n.name: n.hp for n in state.world_state.npcs}
        self.assertEqual(hp["地精A"], 0, "豁免失败应吃全额 20 点")
        self.assertEqual(hp["地精B"], 10, "豁免成功应减半为 10 点")

    async def test_immunity_negates_damage(self):
        state = self.make_state([("火元素", 30, ["免疫火焰"])])

        async def fake_persist(state_arg, npc, new_hp):
            npc.hp = max(0, int(new_hp))
            return 0

        with patch.object(dm.random, "randint", return_value=1), \
             patch.object(combat, "_persist_combat_damage", new=fake_persist):
            result = await dm.execute_tool("save_damage", {
                "targets": ["火元素"], "dc": 15, "ability": "dex", "damage": 20,
                "reason": "火球术", "damage_type": "火焰",
            }, state)
        self.assertIn("免疫火焰", result)
        self.assertEqual(state.world_state.npcs[0].hp, 30, "免疫应完全不受伤")

    async def test_resistance_and_vulnerability_apply(self):
        state = self.make_state([("岩石怪", 30, ["火焰抗性"]), ("枯木怪", 30, ["火焰易伤"])])

        async def fake_persist(state_arg, npc, new_hp):
            npc.hp = max(0, int(new_hp))
            return 0

        with patch.object(dm.random, "randint", return_value=1), \
             patch.object(combat, "_persist_combat_damage", new=fake_persist):
            await dm.execute_tool("save_damage", {
                "targets": ["岩石怪", "枯木怪"], "dc": 15, "ability": "dex", "damage": 20,
                "reason": "燃烧之手", "damage_type": "火焰",
            }, state)
        hp = {n.name: n.hp for n in state.world_state.npcs}
        self.assertEqual(hp["岩石怪"], 20, "抗性应减半")
        self.assertEqual(hp["枯木怪"], 0, "易伤应翻倍（20→40，扣满）")

    async def test_half_on_success_false_gives_zero_on_save(self):
        state = self.make_state([("地精A", 20, [])])

        async def fake_persist(state_arg, npc, new_hp):
            npc.hp = max(0, int(new_hp))
            return 0

        with patch.object(dm.random, "randint", return_value=20), \
             patch.object(combat, "_persist_combat_damage", new=fake_persist):
            await dm.execute_tool("save_damage", {
                "targets": ["地精A"], "dc": 12, "ability": "con", "damage": 18,
                "reason": "毒云", "half_on_success": False,
            }, state)
        self.assertEqual(state.world_state.npcs[0].hp, 20)

    async def test_dead_and_missing_targets_are_skipped(self):
        state = self.make_state([("地精A", 20, [])])
        state.world_state.npcs[0].alive = False
        state.world_state.npcs[0].hp = 0
        result = await dm.execute_tool("save_damage", {
            "targets": ["地精A", "不存在的目标"], "dc": 12, "damage": 10, "reason": "爆炸",
        }, state)
        self.assertIn("已阵亡", result)

    async def test_missing_targets_parameter_is_rejected(self):
        state = self.make_state()
        result = await dm.execute_tool("save_damage", {"dc": 12, "damage": 10}, state)
        self.assertIn("需要 targets", result)

    async def test_dice_damage_spec_is_supported(self):
        state = self.make_state([("地精A", 60, [])])

        async def fake_persist(state_arg, npc, new_hp):
            npc.hp = max(0, int(new_hp))
            return 0

        with patch.object(dm.random, "randint", return_value=1), \
             patch.object(combat, "_persist_combat_damage", new=fake_persist):
            result = await dm.execute_tool("save_damage", {
                "targets": ["地精A"], "dc": 15, "damage": "8d6", "reason": "火球术",
            }, state)
        self.assertIn("基础伤害", result)
        self.assertLess(state.world_state.npcs[0].hp, 60, "应造成伤害")

    async def test_condition_on_failure_only_hits_failed_saves(self):
        """毒气云这类范围效果：只有豁免失败的才附带状态。"""
        state = self.make_state()

        async def fake_persist(state_arg, npc, new_hp):
            npc.hp = max(0, int(new_hp))
            npc.alive = npc.hp > 0
            return 0

        # 地精A 掷 2（失败），地精B 掷 19（成功）
        with patch.object(dm.random, "randint", side_effect=[2, 19]), \
             patch.object(combat, "_persist_combat_damage", new=fake_persist):
            result = await dm.execute_tool("save_damage", {
                "targets": ["地精A", "地精B"], "dc": 15, "ability": "con", "damage": 6,
                "damage_type": "毒素", "condition_on_failure": "中毒", "condition_rounds": 10,
                "reason": "毒气云",
            }, state)

        self.assertIn("[中毒]", result)
        self.assertEqual([c["name"] for c in state.world_state.npcs[0].conditions], ["中毒"])
        self.assertEqual(state.world_state.npcs[0].conditions[0]["remaining_rounds"], 10)
        self.assertEqual(state.world_state.npcs[1].conditions, [], "豁免成功不附带状态")

    async def test_declared_save_advantage_rolls_twice(self):
        state = self.make_state()

        async def fake_persist(state_arg, npc, new_hp):
            npc.hp = max(0, int(new_hp))
            npc.alive = npc.hp > 0
            return 0

        # 优势掷两次取高：4 与 18 → 18 + 敏捷豁免 2 = 20 ≥ 15，成功
        with patch.object(dm.random, "randint", side_effect=[4, 18]) as roll, \
             patch.object(combat, "_persist_combat_damage", new=fake_persist):
            result = await dm.execute_tool("save_damage", {
                "targets": ["地精A"], "dc": 15, "ability": "dex", "damage": 10,
                "save_advantage": True, "save_advantage_reason": "抗毒", "reason": "毒雾",
            }, state)
        self.assertEqual(roll.call_count, 2, "声明的豁免优势要掷两次")
        self.assertIn("抗毒：豁免优势", result)


if __name__ == "__main__":
    unittest.main()
