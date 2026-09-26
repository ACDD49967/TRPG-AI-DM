"""毒药/毒素：抗毒识别、豁免、失败附加「中毒」、状态免疫与默认值。"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import dm_agent as dm
from backend.engine.condition_apply import condition_names
from backend.engine.poison_rules import has_poison_resilience, poison_save_advantage
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState

_TEMP_DIRS: list[tempfile.TemporaryDirectory] = []


def make_state(*, immune: bool = False) -> GameSessionState:
    tmp = tempfile.TemporaryDirectory()
    _TEMP_DIRS.append(tmp)   # 由 tearDownModule 统一清理
    state = GameSessionState(
        "poison", "char", "岚",
        {"game_system": "dnd5e", "char_class": "战士", "level": 3, "hp": 30, "max_hp": 30,
         "ac": 16, "xp": 0,
         "attributes": {"str": 16, "dex": 14, "con": 14},
         "skill_proficiencies": ["运动"]},
    )
    state.world_state = WorldState(session_id="poison", _storage_dir=tmp.name)
    state.world_state.scene.current_location = "毒沼边"
    state.world_state.npcs = [
        NpcEntry(name="沼泽巨蟒", attitude="敌对", hp=20, max_hp=20, ac=14, level=4, alive=True,
                 location="毒沼边", attributes={"str": 16, "dex": 12, "con": 14}),
        NpcEntry(name="毒素傀儡", attitude="敌对", hp=25, max_hp=25, ac=15, level=5, alive=True,
                 location="毒沼边", attributes={"con": 16},
                 traits=["状态免疫：中毒"] if immune else ["构装体"]),
    ]
    state.turn_tool_results = {}
    state.turn_action_ledger = {}
    return state


def tearDownModule():
    while _TEMP_DIRS:
        _TEMP_DIRS.pop().cleanup()


class TestPoisonResilience(unittest.TestCase):
    def test_marker_matching(self):
        self.assertTrue(has_poison_resilience(["矮人坚韧：对抗毒素的豁免有优势"]))
        self.assertTrue(has_poison_resilience("抗毒"))
        self.assertFalse(has_poison_resilience(["普通人类"]))
        self.assertFalse(has_poison_resilience(None))

    def test_player_resilience_reads_race_traits(self):
        state = make_state()
        self.assertEqual(poison_save_advantage(state, "岚"), "")
        state.character_info["race_traits"] = ["矮人坚韧：对抗毒素的豁免有优势，且有毒素伤害抗性"]
        self.assertEqual(poison_save_advantage(state, "岚"), "抗毒")

    def test_creature_resilience_reads_traits(self):
        state = make_state()
        self.assertEqual(poison_save_advantage(state, "沼泽巨蟒"), "")
        state.world_state.npcs[0].traits = ["抗毒", "两栖"]
        self.assertEqual(poison_save_advantage(state, "沼泽巨蟒"), "抗毒")


class TestPoisonTool(unittest.IsolatedAsyncioTestCase):
    async def test_player_failure_takes_damage_and_poisoned(self):
        state = make_state()
        # 体质 +2：掷 3 → 5 < DC 11，失败
        with patch("backend.engine.combat_save_damage.random.randint", return_value=3):
            out = await dm.execute_tool(
                "apply_poison", {"dc": 11, "damage": "8", "source": "毒蛇咬伤"}, state)
        self.assertEqual(state.character_info["hp"], 22, "8 点毒素伤害")
        self.assertIn("中毒", condition_names(state, "岚"))
        self.assertIn("毒素", out)

    async def test_player_success_takes_nothing(self):
        state = make_state()
        with patch("backend.engine.combat_save_damage.random.randint", return_value=18):
            out = await dm.execute_tool(
                "apply_poison", {"dc": 11, "damage": "8"}, state)
        self.assertEqual(state.character_info["hp"], 30, "成功不吃伤害")
        self.assertNotIn("中毒", condition_names(state, "岚"))
        self.assertIn("成功", out)

    async def test_half_on_success_when_declared(self):
        state = make_state()
        with patch("backend.engine.combat_save_damage.random.randint", return_value=18):
            await dm.execute_tool(
                "apply_poison", {"dc": 11, "damage": "8", "half_on_success": True}, state)
        self.assertEqual(state.character_info["hp"], 26, "成功减半 = 4")

    async def test_resilience_grants_save_advantage(self):
        state = make_state()
        state.character_info["race_traits"] = ["矮人坚韧：对抗毒素的豁免有优势"]
        # 优势掷两次取高：3 与 15 → 15+2=17 ≥ 11，成功
        with patch("backend.engine.combat_save_damage.random.randint",
                   side_effect=[3, 15]) as roll:
            out = await dm.execute_tool(
                "apply_poison", {"dc": 11, "damage": "8"}, state)
        self.assertEqual(roll.call_count, 2, "抗毒让豁免掷两次")
        self.assertIn("抗毒", out)
        self.assertEqual(state.character_info["hp"], 30)

    async def test_explicit_advantage_flag_overrides_detection(self):
        state = make_state()
        state.character_info["race_traits"] = ["矮人坚韧：对抗毒素的豁免有优势"]
        with patch("backend.engine.combat_save_damage.random.randint", return_value=18) as roll:
            out = await dm.execute_tool(
                "apply_poison",
                {"dc": 11, "damage": "8", "save_advantage": False}, state)
        self.assertEqual(roll.call_count, 1, "显式关掉优势后只掷一次")
        self.assertNotIn("抗毒", out)

    async def test_npc_target_writes_npc_card(self):
        state = make_state()
        with patch("backend.engine.combat_save_damage.random.randint", return_value=3):
            out = await dm.execute_tool(
                "apply_poison",
                {"target": "沼泽巨蟒", "dc": 13, "damage": "10", "source": "淬毒短刃"}, state)
        self.assertEqual(state.world_state.npcs[0].hp, 10)
        self.assertIn("中毒", condition_names(state, "沼泽巨蟒"))
        self.assertIn("沼泽巨蟒", out)

    async def test_condition_rounds_default_ten(self):
        state = make_state()
        with patch("backend.engine.combat_save_damage.random.randint", return_value=3):
            await dm.execute_tool("apply_poison", {"dc": 11, "damage": "1"}, state)
        poisoned = next(c for c in state.character_info["conditions"] if c["name"] == "中毒")
        self.assertEqual(poisoned["remaining_rounds"], 10, "5e 常见毒药为 1 分钟")

    async def test_condition_immunity_blocks_the_state_but_not_the_damage(self):
        state = make_state(immune=True)
        with patch("backend.engine.combat_save_damage.random.randint", return_value=3):
            out = await dm.execute_tool(
                "apply_poison", {"target": "毒素傀儡", "dc": 13, "damage": "6"}, state)
        self.assertEqual(state.world_state.npcs[1].hp, 19, "伤害照常结算")
        self.assertNotIn("中毒", condition_names(state, "毒素傀儡"))
        self.assertNotIn("[中毒]", out)

    async def test_condition_false_only_deals_damage(self):
        state = make_state()
        with patch("backend.engine.combat_save_damage.random.randint", return_value=3):
            await dm.execute_tool(
                "apply_poison", {"dc": 11, "damage": "5", "condition": False}, state)
        self.assertEqual(state.character_info["hp"], 25)
        self.assertNotIn("中毒", condition_names(state, "岚"))

    async def test_defaults_are_placeholders(self):
        state = make_state()
        with patch("backend.engine.combat_save_damage.random.randint", return_value=3):
            out = await dm.execute_tool("apply_poison", {}, state)
        self.assertIn("DC 11", out, "缺省 DC 11 只是占位，卡面数值优先")
        self.assertIn("毒素", out)

    async def test_same_turn_repeat_is_not_rerolled(self):
        state = make_state()
        with patch("backend.engine.combat_save_damage.random.randint", return_value=3) as roll:
            await dm.execute_tool("apply_poison", {"damage": "5"}, state)
            second = await dm.execute_tool("apply_poison", {"damage": "5"}, state)
        self.assertEqual(roll.call_count, 1, "同回合同参数不重掷豁免")
        self.assertIn("重复调用已跳过", second)
        self.assertEqual(state.character_info["hp"], 25, "不会扣两次血")

    async def test_alias_parameter_names_are_accepted(self):
        """模型可能写成 targets/poison_dc/poison_damage：别名不能让它白跑一趟。"""
        state = make_state()
        with patch("backend.engine.combat_save_damage.random.randint", return_value=3):
            out = await dm.execute_tool(
                "apply_poison",
                {"targets": ["沼泽巨蟒"], "poison_dc": 13, "poison_damage": "6",
                 "kind": "injected"}, state)
        self.assertEqual(state.world_state.npcs[0].hp, 14)
        self.assertIn("中毒", condition_names(state, "沼泽巨蟒"))
        self.assertIn("伤口", out, "injected 应显示为伤口型毒素")


class TestPoisonRegistration(unittest.TestCase):
    def test_tool_is_visible_to_dm(self):
        from backend.engine.tools import DM_TOOLS

        names = {t["function"]["name"] for t in DM_TOOLS}
        self.assertIn("apply_poison", names)


if __name__ == "__main__":
    unittest.main()
