"""亡灵坚韧：0 HP 时体质豁免保命，光耀/暴击压制。"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import combat, combat_damage, condition_rules, initiative
from backend.engine import dm_agent as dm
from backend.engine.rules import RollResult
from backend.engine.session import GameSessionState
from backend.engine.turn_start_effects import apply_turn_start_effects
from backend.engine.undead_fortitude import (
    fortitude_dc,
    has_undead_fortitude,
    resolve_undead_fortitude,
)
from backend.engine.world_state import NpcEntry, WorldState


class TestUndeadFortitudeRules(unittest.TestCase):
    def test_detects_english_and_chinese_traits(self):
        self.assertTrue(has_undead_fortitude(NpcEntry(name="僵尸", traits=["Undead Fortitude."])))
        self.assertTrue(has_undead_fortitude(
            NpcEntry(name="僵尸", traits=["亡灵坚韧：不会轻易倒下。"])))
        self.assertFalse(has_undead_fortitude(NpcEntry(name="僵尸", traits=["Keen Smell"])))
        self.assertFalse(has_undead_fortitude(None))

    def test_dc_is_five_plus_damage(self):
        self.assertEqual(fortitude_dc(10), 15)
        self.assertEqual(fortitude_dc(0), 6)


class TestUndeadFortitudeIntegration(unittest.IsolatedAsyncioTestCase):
    def make_state(self, *traits: str) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "undead-fort", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 10}},
        )
        state.world_state = WorldState(session_id="undead-fort", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "墓地"
        state.world_state.npcs = [
            NpcEntry(name="僵尸", attitude="敌对", hp=9, max_hp=22, ac=8, level=1,
                     alive=True, location="墓地", attributes={"con": 16},
                     traits=list(traits or ["Undead Fortitude."])),
        ]
        state.world_state.scene.visible_npcs_here = ["僵尸"]
        return state

    async def test_successful_save_keeps_zombie_at_one_hp(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        # 第一次 randint 是僵尸对抗法术的豁免（1 → 失败全额），第二次是亡灵坚韧（20 → 成功）
        with patch.object(combat_damage.random, "randint", side_effect=[1, 20]):
            out = await dm.execute_tool(
                "save_damage",
                {"targets": ["僵尸"], "dc": 12, "damage": 30, "damage_type": "火焰",
                 "ability": "con", "reason": "火球术"},
                state,
            )
        self.assertIn("亡灵坚韧", out)
        self.assertIn("HP 9→1", out)
        self.assertEqual(npc.hp, 1)
        self.assertTrue(npc.alive, "站住后仍活着，不该结算经验")
        rolls = [d for _, t, d in state.event_history if t == "dice_roll"]
        self.assertTrue(any("亡灵坚韧" in str(d.get("skill")) for d in rolls))

    async def test_failed_save_lets_the_zombie_die(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        with patch.object(combat_damage.random, "randint", side_effect=[1, 1]):
            out = await dm.execute_tool(
                "save_damage",
                {"targets": ["僵尸"], "dc": 12, "damage": 30, "damage_type": "火焰",
                 "ability": "con", "reason": "火球术"},
                state,
            )
        self.assertIn("亡灵坚韧", out)
        self.assertIn("已阵亡", out)
        self.assertEqual(npc.hp, 0)
        self.assertFalse(npc.alive)

    async def test_radiant_damage_suppresses_the_trait(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        with patch.object(combat_damage.random, "randint", side_effect=[1]) as rnd:
            out = await dm.execute_tool(
                "save_damage",
                {"targets": ["僵尸"], "dc": 12, "damage": 30, "damage_type": "光耀",
                 "ability": "con", "reason": "至圣斩"},
                state,
            )
        self.assertIn("光耀伤害压制", out)
        self.assertEqual(npc.hp, 0)
        self.assertEqual(rnd.call_count, 1, "光耀不触发亡灵坚韧，不应多掷一次")

    async def test_without_the_trait_nothing_changes(self):
        state = self.make_state("Keen Smell")
        npc = state.world_state.npcs[0]
        with patch.object(combat_damage.random, "randint", side_effect=[1]) as rnd:
            out = await dm.execute_tool(
                "save_damage",
                {"targets": ["僵尸"], "dc": 12, "damage": 30, "damage_type": "火焰",
                 "ability": "con", "reason": "火球术"},
                state,
            )
        self.assertNotIn("亡灵坚韧", out)
        self.assertEqual(npc.hp, 0)
        self.assertEqual(rnd.call_count, 1)

    async def test_player_melee_kill_triggers_the_save(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        hit = SimpleNamespace(roll=18, total=23, result=RollResult.SUCCESS)
        with patch.object(combat, "combat_attack_roll", return_value=(hit, 9)), \
                patch.object(combat.random, "randint", return_value=20):
            out = await dm.execute_tool(
                "combat_round",
                {"enemy_name": "僵尸", "player_action": "挥长剑劈砍",
                 "enemy_can_act": False},
                state,
            )
        self.assertIn("亡灵坚韧", out)
        self.assertNotIn("被击败", out)
        self.assertEqual(npc.hp, 1)
        self.assertTrue(npc.alive)

    async def test_critical_hit_ignores_the_trait(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        hit = SimpleNamespace(roll=20, total=25, result=RollResult.CRITICAL_SUCCESS)
        with patch.object(combat, "combat_attack_roll", return_value=(hit, 9)):
            out = await dm.execute_tool(
                "combat_round",
                {"enemy_name": "僵尸", "player_action": "挥长剑劈砍",
                 "enemy_can_act": False},
                state,
            )
        self.assertIn("暴击压制", out)
        self.assertIn("被击败", out)
        self.assertEqual(npc.hp, 0)
        self.assertFalse(npc.alive)

    async def test_ongoing_damage_kill_also_rolls(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        npc.conditions = [{
            "name": "中毒", "remaining_rounds": 2,
            "damage_per_turn": "1d6", "damage_type": "毒素",
        }]
        initiative.start(state)
        with patch.object(condition_rules.random, "randint", return_value=20):
            text = await apply_turn_start_effects(state, "僵尸", npc)
        self.assertIn("亡灵坚韧", text)
        self.assertEqual(npc.hp, 1)
        self.assertTrue(npc.alive)

    async def test_resolve_helper_returns_structured_result(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        with patch("backend.engine.undead_fortitude.random.randint", return_value=20):
            result = await resolve_undead_fortitude(
                state, npc, "僵尸", damage=10, damage_type="火焰")
        self.assertTrue(result["applied"])
        self.assertEqual(result["dc"], 15)
        self.assertEqual(result["hp"], 1)
        self.assertIn("站住", result["note"])


if __name__ == "__main__":
    unittest.main()
