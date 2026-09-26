"""玩家侧伤害管线：抗性/免疫/易伤、临时生命值、范围伤害与阵亡联动。"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import combat
from backend.engine import dm_agent as dm
from backend.engine import player_damage as pd
from backend.engine import tool_executor as te
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


def _roll(value: str = "成功", total: int = 18):
    return SimpleNamespace(roll=15, total=total, result=SimpleNamespace(value=value))


class PlayerDamageBase(unittest.IsolatedAsyncioTestCase):
    def make_state(self, info: dict | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = {
            "hp": 30, "max_hp": 30, "ac": 16, "level": 3, "xp": 0,
            "game_system": "dnd5e", "char_class": "战士",
            "attributes": {"str": 16, "dex": 14, "con": 14},
            "saves": {"dex": {"value": 4, "proficient": True}},
            "proficiency_bonus": 2,
        }
        base.update(info or {})
        state = GameSessionState("pdmg", "char", "岚", base)
        state.world_state = WorldState(session_id="pdmg", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "碎石坡"
        state.turn_tool_results = {}
        state.turn_action_ledger = {}
        return state


class TestDamageMultiplier(PlayerDamageBase):
    async def test_no_source_means_full_damage(self):
        state = self.make_state()
        self.assertEqual(pd.multiplier_for(state, "火焰"), (1.0, ""))

    async def test_structured_resistance_immunity_vulnerability(self):
        state = self.make_state({
            "damage_resistances": ["火焰"],
            "damage_immunities": ["毒素"],
            "damage_vulnerabilities": ["冷冻"],
        })
        self.assertEqual(pd.multiplier_for(state, "fire")[0], 0.5)
        self.assertEqual(pd.multiplier_for(state, "毒素")[0], 0.0)
        self.assertEqual(pd.multiplier_for(state, "cold")[0], 2.0)
        self.assertEqual(pd.multiplier_for(state, "雷鸣")[0], 1.0)

    async def test_resistance_and_vulnerability_cancel(self):
        state = self.make_state({"damage_resistances": ["火焰"], "damage_vulnerabilities": ["火焰"]})
        multiplier, note = pd.multiplier_for(state, "火焰")
        self.assertEqual(multiplier, 1.0)
        self.assertIn("抵消", note)

    async def test_race_traits_and_equipped_items_are_sources(self):
        state = self.make_state({
            "race_traits": ["龙裔血脉：火焰抗性"],
            "inventory": {"items": [
                {"name": "霜巨人之戒", "equipped": True, "description": "穿戴者对冷冻伤害有抗性"},
                {"name": "抗酸斗篷", "equipped": False, "description": "强酸抗性"},
            ]},
        })
        self.assertEqual(pd.multiplier_for(state, "火焰")[0], 0.5, "种族特性应生效")
        self.assertEqual(pd.multiplier_for(state, "冷冻")[0], 0.5, "已装备物品应生效")
        self.assertEqual(pd.multiplier_for(state, "强酸")[0], 1.0, "未装备物品不应生效")

    async def test_known_spell_alone_does_not_grant_resistance(self):
        """只是"学会"防护能量不算生效——否则等于永久抗性。"""
        state = self.make_state({"known_spells": [
            {"name": "防护能量", "description": "目标获得一种伤害类型的抗性"}
        ]})
        self.assertEqual(pd.multiplier_for(state, "火焰")[0], 1.0)
        # 正在专注时才算生效，但仍需要写明类型（结构化字段/备注）
        state.character_info["concentration"] = {"spell": "防护能量", "damage_resistances": ["火焰"]}
        self.assertEqual(pd.multiplier_for(state, "火焰")[0], 0.5)


class TestApplyDamage(PlayerDamageBase):
    async def test_resistance_halves_and_rounds_down(self):
        state = self.make_state({"damage_resistances": ["火焰"]})
        outcome = await pd.apply(state, 9, "火焰", source="火球")
        self.assertEqual(outcome["applied"], 4)
        self.assertEqual(outcome["hp_after"], 26)
        self.assertIn("火焰抗性", outcome["description"])

    async def test_immunity_does_not_touch_hp(self):
        state = self.make_state({"damage_immunities": ["毒素"]})
        outcome = await pd.apply(state, 12, "毒素", source="毒云")
        self.assertEqual(outcome["applied"], 0)
        self.assertEqual(state.character_info["hp"], 30)
        events = [d for _, t, d in state.event_history if t == "game_event" and d.get("type") == "damage"]
        self.assertEqual(len(events), 1, "免疫也要给玩家一条可见说明")

    async def test_temporary_hp_absorbs_first(self):
        state = self.make_state({"temporary_hp": 5})
        outcome = await pd.apply(state, 8, "", source="地精伏击者A攻击")
        self.assertEqual(outcome["temp_absorbed"], 5)
        self.assertEqual(outcome["hp_damage"], 3)
        self.assertEqual(state.character_info["temporary_hp"], 0)
        self.assertEqual(state.character_info["hp"], 27)

    async def test_damage_to_zero_starts_dying_flow(self):
        state = self.make_state({"hp": 4})
        outcome = await pd.apply(state, 7, "", source="巨斧")
        self.assertEqual(outcome["hp_after"], 0)
        self.assertTrue(state.dying, "HP 归零应触发濒死安全网")
        self.assertTrue(any(str(h).startswith("[系统强制-濒死]") for h in state.pending_system_hints))

    async def test_vulnerability_doubles(self):
        state = self.make_state({"damage_vulnerabilities": ["冷冻"]})
        outcome = await pd.apply(state, 6, "冷冻", source="寒冰锥")
        self.assertEqual(outcome["applied"], 12)
        self.assertEqual(state.character_info["hp"], 18)


class TestDamageToolIntegration(PlayerDamageBase):
    def _patch_dice(self, enemy_damage: int = 4):
        def fake(attacker, ac, mod, dice):
            return _roll(), (0 if attacker == "你" else enemy_damage)
        return patch.object(combat, "combat_attack_roll", side_effect=fake)

    async def test_enemy_attack_applies_player_resistance(self):
        state = self.make_state({"damage_resistances": ["挥砍"]})
        state.world_state.npcs = [NpcEntry(name="地精伏击者A", attitude="敌对", hp=9, max_hp=9,
                                           ac=13, alive=True, location="碎石坡")]
        state.world_state.scene.visible_npcs_here = ["地精伏击者A"]
        with self._patch_dice(enemy_damage=8):
            line = await dm.execute_tool(
                "enemy_attack", {"enemy_name": "地精伏击者A", "damage_type": "挥砍"}, state)
        self.assertIn("造成 4 点伤害", line, "抗性后玩家应看到减半后的数字")
        self.assertIn("挥砍抗性", line)
        self.assertEqual(state.character_info["hp"], 26)
        combat_events = [d for _, t, d in state.event_history
                         if t == "game_event" and d.get("type") == "combat"]
        self.assertEqual(combat_events[-1]["extra"]["player_damage_taken"], 4)

    async def test_untyped_attack_ignores_resistance(self):
        state = self.make_state({"damage_resistances": ["挥砍"]})
        state.world_state.npcs = [NpcEntry(name="地精伏击者A", attitude="敌对", hp=9, max_hp=9,
                                           ac=13, alive=True, location="碎石坡")]
        state.world_state.scene.visible_npcs_here = ["地精伏击者A"]
        with self._patch_dice(enemy_damage=8):
            await dm.execute_tool("enemy_attack", {"enemy_name": "地精伏击者A"}, state)
        self.assertEqual(state.character_info["hp"], 22, "没声明伤害类型就按无抗性算")

    async def test_save_damage_can_target_the_player(self):
        state = self.make_state({"damage_resistances": ["火焰"]})
        state.world_state.scene.visible_npcs_here = ["红龙"]
        state.world_state.npcs = [NpcEntry(name="红龙", attitude="敌对", hp=90, max_hp=90, ac=18,
                                           alive=True, location="碎石坡")]
        with patch.object(combat.random, "randint", return_value=1):
            out = await dm.execute_tool("save_damage", {
                "targets": ["你"], "dc": 15, "damage": 20, "damage_type": "火焰",
                "ability": "dex", "reason": "红龙吐息"}, state)
        self.assertIn("玩家", out)
        # 豁免失败吃全额 20，但火抗减半 → 10
        self.assertEqual(state.character_info["hp"], 20)
        dice = [d for _, t, d in state.event_history if t == "dice_roll"]
        self.assertTrue(any("豁免" in str(d.get("skill")) for d in dice), "玩家豁免也要有骰子事件")

    async def test_update_state_can_set_and_remove_resistances(self):
        state = self.make_state()
        await dm.execute_tool("update_state", {"changes": {"damage_resistances_add": ["火焰"]},
                                               "reason": "获得火焰抗性"}, state)
        self.assertEqual(state.character_info["damage_resistances"], ["火焰"])
        await dm.execute_tool("update_state", {"changes": {"damage_resistances_add": ["火焰", "冷冻"]},
                                               "reason": "再获得"}, state)
        self.assertEqual(state.character_info["damage_resistances"], ["火焰", "冷冻"], "重复不叠加")
        await dm.execute_tool("update_state", {"changes": {"damage_resistances_remove": ["火焰"]},
                                               "reason": "效果结束"}, state)
        self.assertEqual(state.character_info["damage_resistances"], ["冷冻"])
        self.assertEqual(pd.multiplier_for(state, "冷冻")[0], 0.5)


class TestEnemySideResistance(unittest.IsolatedAsyncioTestCase):
    """对称性：玩家打敌人也要套用敌人的抗性/免疫/易伤（此前只有范围伤害会套）。"""

    def make_state(self, traits: list[str]) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "enemyres", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14},
             "inventory": {"items": [{"name": "长剑", "equipped": True}]}},
        )
        state.world_state = WorldState(session_id="enemyres", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "碎石坡"
        state.world_state.scene.visible_npcs_here = ["炎魔"]
        state.world_state.npcs = [NpcEntry(
            name="炎魔", attitude="敌对", hp=40, max_hp=40, ac=13, level=1, alive=True,
            location="碎石坡", attributes={"str": 12, "dex": 12}, traits=list(traits))]
        state.turn_tool_results = {}
        state.turn_action_ledger = {}
        return state

    def _patch_dice(self, player_damage: int):
        def fake(attacker, ac, mod, dice):
            return _roll(), (player_damage if attacker == "你" else 0)
        return patch.object(combat, "combat_attack_roll", side_effect=fake)

    async def test_typed_player_damage_is_halved_by_enemy_resistance(self):
        state = self.make_state(["火焰抗性"])
        with self._patch_dice(player_damage=10):
            line = await dm.execute_tool("combat_round", {
                "enemy_name": "炎魔", "player_action": "施放火焰斩", "damage_type": "火焰",
                "enemy_can_act": False}, state)
        self.assertIn("造成 5 点伤害", line)
        self.assertIn("火焰抗性", line)
        self.assertEqual(state.world_state.npcs[0].hp, 35)

    async def test_enemy_immunity_zeroes_player_damage(self):
        state = self.make_state(["免疫毒素"])
        with self._patch_dice(player_damage=12):
            line = await dm.execute_tool("combat_round", {
                "enemy_name": "炎魔", "player_action": "淬毒匕首刺击", "damage_type": "毒素",
                "enemy_can_act": False}, state)
        self.assertNotIn("造成 12 点伤害", line)
        self.assertIn("免疫毒素", line)
        self.assertEqual(state.world_state.npcs[0].hp, 40, "免疫不应扣血")

    async def test_weapon_name_in_action_infers_damage_type(self):
        state = self.make_state(["挥砍抗性"])
        with self._patch_dice(player_damage=8):
            line = await dm.execute_tool("combat_round", {
                "enemy_name": "炎魔", "player_action": "我挥长剑砍向炎魔",
                "enemy_can_act": False}, state)
        self.assertIn("造成 4 点伤害", line, "应从'长剑'推断出挥砍并减半")
        self.assertEqual(state.world_state.npcs[0].hp, 36)

    async def test_enemy_attack_infers_type_from_traits(self):
        state = GameSessionState(
            "inf", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14},
             "damage_resistances": ["挥砍"]},
        )
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state.world_state = WorldState(session_id="inf", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "碎石坡"
        state.world_state.scene.visible_npcs_here = ["地精伏击者A"]
        state.world_state.npcs = [NpcEntry(
            name="地精伏击者A", attitude="敌对", hp=9, max_hp=9, ac=13, alive=True,
            location="碎石坡", traits=["弯刀 1d6 挥砍"])]
        state.turn_tool_results = {}
        state.turn_action_ledger = {}
        with patch.object(combat, "combat_attack_roll", side_effect=lambda a, ac, m, d: (_roll(), 10)):
            line = await dm.execute_tool("enemy_attack", {"enemy_name": "地精伏击者A"}, state)
        self.assertIn("造成 5 点伤害", line, "特性里的挥砍应被识别并减半")
        self.assertEqual(state.character_info["hp"], 25)


if __name__ == "__main__":
    unittest.main()
