"""充能能力：解析、冷却拦截与回合开始 d6 充能。"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import combat, dm_agent as dm, initiative, recharge_rules
from backend.engine.session import GameSessionState
from backend.engine.turn_start_effects import apply_turn_start_effects
from backend.engine.world_state import NpcEntry, WorldState


def _roll():
    return SimpleNamespace(roll=15, total=15, result=SimpleNamespace(value="失败"))


class TestRechargeRules(unittest.TestCase):
    def make_state(self) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "recharge", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14}},
        )
        state.world_state = WorldState(session_id="recharge", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "山谷"
        state.world_state.npcs = [
            NpcEntry(name="幼龙", attitude="敌对", hp=40, max_hp=40, ac=16, level=5,
                     alive=True, location="山谷",
                     traits=["Fire Breath (Recharge 5—6): exhale fire."]),
        ]
        state.world_state.scene.visible_npcs_here = ["幼龙"]
        state.turn_action_ledger = {}
        return state

    def test_parse_english_and_chinese_recharge(self):
        npc = NpcEntry(name="测试", traits=[
            "Fire Breath (Recharge 5—6): fire.",
            "寒冰吐息（充能6）：冰霜。",
        ])
        abilities = recharge_rules.parse_recharge_abilities(npc)
        self.assertEqual(abilities["Fire Breath"], 5)
        self.assertEqual(abilities["寒冰吐息"], 6)

    def test_recharge_argument_is_visible_in_model_tool_schema(self):
        from backend.engine.tools import ENEMY_ATTACK_TOOL, SAVE_DAMAGE_TOOL

        enemy_props = ENEMY_ATTACK_TOOL["function"]["parameters"]["properties"]
        save_props = SAVE_DAMAGE_TOOL["function"]["parameters"]["properties"]
        self.assertIn("recharge_ability", enemy_props)
        self.assertIn("recharge_ability", save_props)
        self.assertIn("actor", save_props)

    def test_used_ability_blocks_and_roll_recharges(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        self.assertTrue(recharge_rules.recharge_available(state, "幼龙", "Fire Breath", npc)[0])
        recharge_rules.mark_recharge_used(state, "幼龙", "Fire Breath", npc)
        ok, reason = recharge_rules.recharge_available(state, "幼龙", "Fire Breath", npc)
        self.assertFalse(ok)
        self.assertIn("尚未充能", reason)
        with patch.object(recharge_rules.random, "randint", return_value=6):
            text = recharge_rules.roll_recharge(state, "幼龙", npc)
        self.assertIn("充能成功", text)
        self.assertTrue(recharge_rules.recharge_available(state, "幼龙", "Fire Breath", npc)[0])

    def test_match_recharge_ability_from_action_text(self):
        npc = NpcEntry(name="幼龙", traits=["Fire Breath (Recharge 5—6): exhale fire."])
        self.assertEqual(
            recharge_rules.match_recharge_ability(npc, "它张开嘴使用 Fire Breath"),
            "Fire Breath",
        )

    def test_enemy_action_is_visible_in_model_tool_schema(self):
        from backend.engine.tools import ENEMY_ATTACK_TOOL

        props = ENEMY_ATTACK_TOOL["function"]["parameters"]["properties"]
        self.assertIn("enemy_action", props)


class TestRechargeIntegration(unittest.IsolatedAsyncioTestCase):
    def make_state(self) -> GameSessionState:
        return TestRechargeRules().make_state()

    async def test_enemy_attack_blocks_until_turn_start_recharge(self):
        state = self.make_state()
        initiative.start(state)
        with patch.object(combat, "combat_attack_roll", return_value=(_roll(), 0)):
            first = await dm.execute_tool(
                "enemy_attack",
                {"enemy_name": "幼龙", "recharge_ability": "Fire Breath"},
                state,
            )
        self.assertIn("幼龙", first)

        initiative.begin_player_turn(state)
        state.turn_tool_results = {}
        with patch.object(recharge_rules.random, "randint", return_value=2), \
             patch.object(combat, "combat_attack_roll", return_value=(_roll(), 0)):
            blocked = await dm.execute_tool(
                "enemy_attack",
                {"enemy_name": "幼龙", "recharge_ability": "Fire Breath"},
                state,
            )
        self.assertIn("尚未充能", blocked)

        initiative.begin_player_turn(state)
        state.turn_tool_results = {}
        with patch.object(recharge_rules.random, "randint", return_value=6), \
             patch.object(combat, "combat_attack_roll", return_value=(_roll(), 0)):
            recharged = await dm.execute_tool(
                "enemy_attack",
                {"enemy_name": "幼龙", "recharge_ability": "Fire Breath"},
                state,
            )
        self.assertNotIn("尚未充能", recharged)
        self.assertIn("幼龙", recharged)

    async def test_turn_start_effect_reports_failed_recharge(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        initiative.start(state)
        recharge_rules.mark_recharge_used(state, "幼龙", "Fire Breath", npc)
        with patch.object(recharge_rules.random, "randint", return_value=1):
            text = await apply_turn_start_effects(state, "幼龙", npc)
        self.assertIn("未充能", text)

    async def test_enemy_attack_auto_detects_recharge_from_action(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        initiative.start(state)
        with patch.object(combat, "combat_attack_roll", return_value=(_roll(), 0)):
            result = await dm.execute_tool(
                "enemy_attack",
                {"enemy_name": "幼龙", "enemy_action": "Fire Breath"},
                state,
            )
        self.assertIn("幼龙", result)
        ok, reason = recharge_rules.recharge_available(state, "幼龙", "Fire Breath", npc)
        self.assertFalse(ok, "从 enemy_action 匹配到充能能力后应进入冷却")
        self.assertIn("尚未充能", reason)

    async def test_save_damage_auto_detects_recharge_from_reason(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        initiative.start(state)
        await dm.execute_tool(
            "save_damage",
            {"actor": "幼龙", "targets": ["岚"], "dc": 10, "damage": 1,
             "reason": "Fire Breath", "damage_type": "火焰"},
            state,
        )
        ok, _reason = recharge_rules.recharge_available(state, "幼龙", "Fire Breath", npc)
        self.assertFalse(ok, "从 save_damage.reason 匹配到充能能力后应进入冷却")


if __name__ == "__main__":
    unittest.main()
