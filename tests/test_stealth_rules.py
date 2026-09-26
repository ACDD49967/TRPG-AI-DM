"""潜行/隐藏：隐匿对抗被动察觉、重甲劣势、出手暴露，以及接进优势管线。"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import combat
from backend.engine import dm_agent as dm
from backend.engine.action_economy import primary_action_available
from backend.engine.combat_advantage import enemy_attack_advantage, player_attack_advantage
from backend.engine.rules import AdvantageMode
from backend.engine.session import GameSessionState
from backend.engine.stealth_rules import (
    armor_disadvantage, best_observer, creature_stealth_modifier, is_hidden,
    observer_passive_perception, observers, stealth_modifier,
)
from backend.engine.world_state import NpcEntry, WorldState


_TEMP_DIRS: list[tempfile.TemporaryDirectory] = []


def make_state(*, npcs: bool = True) -> GameSessionState:
    tmp = tempfile.TemporaryDirectory()
    _TEMP_DIRS.append(tmp)   # 由 tearDownModule 统一清理，避免每个用例留一个临时目录
    state = GameSessionState(
        "stealth", "char", "岚",
        {"game_system": "dnd5e", "char_class": "游荡者", "level": 3, "hp": 24, "max_hp": 24,
         "ac": 15, "xp": 0,
         "attributes": {"str": 10, "dex": 16, "con": 14, "wis": 12},
         "skill_proficiencies": ["隐匿", "察觉"],
         "inventory": {"items": [{"name": "皮甲", "equipped": True}]}},
    )
    state.world_state = WorldState(session_id="stealth", _storage_dir=tmp.name)
    state.world_state.scene.current_location = "矿洞口"
    state.world_state.scene.visible_npcs_here = ["地精斥候"]
    if npcs:
        state.world_state.npcs = [
            NpcEntry(name="地精斥候", attitude="敌对", hp=7, max_hp=7, ac=13, level=1,
                     alive=True, location="矿洞口",
                     attributes={"dex": 14, "wis": 12}, skills=[]),
            NpcEntry(name="地精首领", attitude="敌对", hp=22, max_hp=22, ac=16, level=4,
                     alive=True, location="矿洞口",
                     attributes={"dex": 14, "wis": 14}, skills=["察觉"]),
        ]
    state.turn_tool_results = {}
    state.turn_action_ledger = {}
    return state


def tearDownModule():
    while _TEMP_DIRS:
        _TEMP_DIRS.pop().cleanup()


def _roll(damage: int = 3):
    return SimpleNamespace(roll=15, total=18, result=SimpleNamespace(value="成功")), damage


class TestStealthMath(unittest.TestCase):
    def test_player_stealth_modifier_adds_skill_proficiency(self):
        state = make_state()
        self.assertEqual(stealth_modifier(state), 5, "敏捷 +3，隐匿熟练 +2")

    def test_armor_disadvantage_only_for_real_heavy_armor(self):
        state = make_state()
        self.assertEqual(armor_disadvantage(state), "", "皮甲不该带来劣势")
        state.character_info["inventory"]["items"] = [{"name": "链甲", "equipped": True}]
        self.assertEqual(armor_disadvantage(state), "身着链甲")
        state.character_info["inventory"]["items"] = [{"name": "链甲衫", "equipped": True}]
        self.assertEqual(armor_disadvantage(state), "", "链甲衫不在此列")
        state.character_info["inventory"]["items"] = [{"name": "链甲", "equipped": False}]
        self.assertEqual(armor_disadvantage(state), "", "没穿就不算")

    def test_creature_passive_perception_from_card(self):
        state = make_state()
        scout, chief = state.world_state.npcs
        self.assertEqual(observer_passive_perception(scout), 11, "感知 12 → +1")
        self.assertEqual(observer_passive_perception(chief), 14, "感知 14 + 察觉熟练 2")
        self.assertEqual(observer_passive_perception(None), 10)

    def test_creature_stealth_modifier_uses_dex_and_skill(self):
        state = make_state()
        scout = state.world_state.npcs[0]
        self.assertEqual(creature_stealth_modifier(scout), 2, "敏捷 14 → +2")
        scout.skills = ["隐匿"]
        self.assertEqual(creature_stealth_modifier(scout), 4, "加 1 级熟练 +2")

    def test_best_observer_respects_visible_list_and_names(self):
        state = make_state()
        self.assertEqual(best_observer(state, target="岚"), ("地精斥候", 11),
                         "默认只算在场名单里的生物")
        self.assertEqual(best_observer(state, ["地精首领"], target="岚"), ("地精首领", 14),
                         "显式指定观察者时按指定名单")
        self.assertEqual(best_observer(state, [], target="地精斥候"), ("岚", 13),
                         "NPC 想藏起来时，玩家是观察者（被动察觉 13）")
        self.assertIn("岚", [name for name, _ in observers(state, target="地精斥候")])


class TestStealthTools(unittest.IsolatedAsyncioTestCase):
    async def test_hide_success_marks_hidden(self):
        state = make_state()
        with patch("backend.engine.stealth_rules.random.randint", return_value=15):
            out = await dm.execute_tool("resolve_stealth", {"action": "hide"}, state)
        self.assertIn("进入隐藏状态", out)
        self.assertIn("地精斥候的被动察觉 11", out)
        self.assertTrue(is_hidden(state))
        rolls = [e for _, t, e in state.event_history if t == "dice_roll"]
        self.assertIn("隐匿", rolls[-1]["skill"])

    async def test_hide_failure_is_reported_and_leaves_no_state(self):
        state = make_state()
        with patch("backend.engine.stealth_rules.random.randint", return_value=3):
            out = await dm.execute_tool("resolve_stealth", {"action": "hide"}, state)
        self.assertIn("没能藏住", out)
        self.assertIn("察觉到你", out)
        self.assertFalse(is_hidden(state))

    async def test_heavy_armor_rolls_twice_and_keeps_lower(self):
        state = make_state()
        state.character_info["inventory"]["items"] = [{"name": "链甲", "equipped": True}]
        with patch("backend.engine.stealth_rules.random.randint",
                   side_effect=[18, 4]) as roll:
            out = await dm.execute_tool("resolve_stealth", {"action": "hide"}, state)
        self.assertEqual(roll.call_count, 2, "重甲劣势掷两次")
        self.assertIn("劣势", out)
        self.assertFalse(is_hidden(state), "取较低值 4+5=9 < 11")

    async def test_declared_advantage_cancels_armor_disadvantage(self):
        state = make_state()
        state.character_info["inventory"]["items"] = [{"name": "链甲", "equipped": True}]
        with patch("backend.engine.stealth_rules.random.randint", return_value=10) as roll:
            await dm.execute_tool(
                "resolve_stealth", {"action": "hide", "advantage": "advantage",
                                    "advantage_reason": "隐身术"}, state)
        self.assertEqual(roll.call_count, 1, "优势与劣势抵消，不再掷两次")

    async def test_declared_dc_overrides_passive_perception(self):
        state = make_state()
        with patch("backend.engine.stealth_rules.random.randint", return_value=5):
            out = await dm.execute_tool(
                "resolve_stealth", {"action": "hide", "dc": 8, "reason": "哨兵在打瞌睡"}, state)
        self.assertIn("DM 指定 DC 8", out)
        self.assertTrue(is_hidden(state))

    async def test_no_observer_hides_without_rolling(self):
        state = make_state(npcs=False)
        with patch("backend.engine.stealth_rules.random.randint") as roll:
            out = await dm.execute_tool("resolve_stealth", {"action": "hide"}, state)
        roll.assert_not_called()
        self.assertIn("没有能看穿你的生物", out)
        self.assertTrue(is_hidden(state))

    async def test_reveal_clears_hidden_without_rolling(self):
        state = make_state()
        state.character_info["conditions"] = [{"name": "隐藏", "description": "藏好了"}]
        with patch("backend.engine.stealth_rules.random.randint") as roll:
            out = await dm.execute_tool("resolve_stealth", {"action": "reveal"}, state)
        roll.assert_not_called()
        self.assertFalse(is_hidden(state))
        self.assertIn("主动现身", out)

    async def test_reveal_without_hidden_warns(self):
        state = make_state()
        out = await dm.execute_tool("resolve_stealth", {"action": "reveal"}, state)
        self.assertIn("当前没有隐藏", out)

    async def test_npc_can_hide_from_the_player(self):
        state = make_state()
        with patch("backend.engine.stealth_rules.random.randint", return_value=15):
            out = await dm.execute_tool(
                "resolve_stealth", {"action": "hide", "target": "地精首领"}, state)
        self.assertTrue(is_hidden(state, "地精首领"))
        self.assertIn("岚的被动察觉 13", out)
        conditions = [c.get("name") for c in state.world_state.npcs[1].conditions]
        self.assertIn("隐藏", conditions)

    async def test_unknown_action_lists_options(self):
        state = make_state()
        out = await dm.execute_tool("resolve_stealth", {"action": "??"}, state)
        self.assertIn("hide", out)
        self.assertIn("reveal", out)

    async def test_same_turn_repeat_hide_is_not_rerolled(self):
        state = make_state()
        with patch("backend.engine.stealth_rules.random.randint", return_value=15) as roll:
            await dm.execute_tool("resolve_stealth", {"action": "hide"}, state)
            second = await dm.execute_tool("resolve_stealth", {"action": "hide"}, state)
        self.assertEqual(roll.call_count, 1, "同回合同参数不重掷")
        self.assertIn("重复调用已跳过", second)

    async def test_attacking_breaks_the_player_hidden_state(self):
        state = make_state()
        state.character_info["conditions"] = [{"name": "隐藏", "description": "藏好了"}]
        with patch.object(combat, "combat_attack_roll", side_effect=lambda *a, **k: _roll()):
            out = await dm.execute_tool(
                "combat_round", {"enemy_name": "地精斥候", "player_action": "挥剑"}, state)
        self.assertFalse(is_hidden(state), "出手后自动暴露")
        self.assertIn("暴露", out)

    async def test_npc_attacking_breaks_its_own_hidden_state(self):
        state = make_state()
        npc = state.world_state.npcs[0]
        npc.conditions = [{"name": "隐藏", "description": "潜伏中"}]
        with patch.object(combat, "combat_attack_roll", side_effect=lambda *a, **k: _roll(4)):
            out = await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)
        self.assertFalse(is_hidden(state, "地精斥候"))
        self.assertIn("暴露", out)


class TestStealthAdvantage(unittest.TestCase):
    def test_hidden_attacker_gains_advantage(self):
        state = make_state()
        state.character_info["conditions"] = [{"name": "隐藏", "description": "藏好了"}]
        npc = state.world_state.npcs[0]
        decision = player_attack_advantage(
            state, {}, action="挥剑劈下", weapon="长剑", enemy_npc=npc,
            system="dnd5e", player_name="岚")
        self.assertEqual(decision.mode, AdvantageMode.ADVANTAGE)
        self.assertTrue(any("未被看见" in r for r in decision.advantages))

    def test_hidden_target_imposes_disadvantage(self):
        state = make_state()
        npc = state.world_state.npcs[0]
        npc.conditions = [{"name": "隐藏", "description": "潜伏中"}]
        decision = player_attack_advantage(
            state, {}, action="挥剑劈下", weapon="长剑", enemy_npc=npc,
            system="dnd5e", player_name="岚")
        self.assertEqual(decision.mode, AdvantageMode.DISADVANTAGE)

    def test_hidden_enemy_attacker_gains_advantage(self):
        state = make_state()
        npc = state.world_state.npcs[0]
        npc.conditions = [{"name": "隐藏", "description": "潜伏中"}]
        decision = enemy_attack_advantage(
            state, {}, enemy="地精斥候", enemy_npc=npc, enemy_action="刺出短矛",
            system="dnd5e")
        self.assertEqual(decision.mode, AdvantageMode.ADVANTAGE)


class TestStealthRegistration(unittest.TestCase):
    def test_tool_is_visible_to_dm(self):
        from backend.engine.tools import DM_TOOLS

        names = {t["function"]["name"] for t in DM_TOOLS}
        self.assertIn("resolve_stealth", names)


class TestStealthActionEconomy(unittest.IsolatedAsyncioTestCase):
    async def test_player_hide_costs_the_main_action(self):
        state = make_state()
        with patch("backend.engine.stealth_rules.random.randint", return_value=15):
            await dm.execute_tool("resolve_stealth", {"action": "hide"}, state)
        self.assertFalse(primary_action_available(state, "岚"), "Hide 用掉一次动作")

    async def test_npc_hiding_does_not_cost_the_player_action(self):
        state = make_state()
        with patch("backend.engine.stealth_rules.random.randint", return_value=15):
            await dm.execute_tool(
                "resolve_stealth", {"action": "hide", "target": "地精首领"}, state)
        self.assertTrue(primary_action_available(state, "岚"),
                        "DM 让 NPC 藏起来不该扣玩家的动作")

    async def test_bonus_action_source_keeps_the_action_free(self):
        """盗贼狡诈动作把 Hide 当附赠：声明 action_source 后主行动还在。"""
        state = make_state()
        with patch("backend.engine.stealth_rules.random.randint", return_value=15):
            await dm.execute_tool(
                "resolve_stealth", {"action": "hide", "action_source": "bonus_action"}, state)
        self.assertTrue(primary_action_available(state, "岚"))


if __name__ == "__main__":
    unittest.main()
