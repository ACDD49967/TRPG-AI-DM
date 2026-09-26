"""对抗动作：擒抱 / 推撞 / 逃脱——对抗检定、体型限制、无法行动与行动经济。"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import combat
from backend.engine import dm_agent as dm
from backend.engine.condition_apply import condition_names
from backend.engine.contest_rules import (
    acrobatics_modifier, athletics_modifier, can_action_target, defense_modifier, is_helpless,
    grappling_targets, release_grapples_by, size_index,
)
from backend.engine import player_damage
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState

_TEMP_DIRS: list[tempfile.TemporaryDirectory] = []


def make_state(*, npcs: bool = True) -> GameSessionState:
    tmp = tempfile.TemporaryDirectory()
    _TEMP_DIRS.append(tmp)   # 由 tearDownModule 统一清理
    state = GameSessionState(
        "contest", "char", "岚",
        {"game_system": "dnd5e", "char_class": "战士", "level": 3, "hp": 30, "max_hp": 30,
         "ac": 16, "xp": 0,
         "attributes": {"str": 16, "dex": 14, "con": 14},
         "skill_proficiencies": ["运动", "察觉"],
         "inventory": {"items": [{"name": "长剑", "equipped": True}]}},
    )
    state.world_state = WorldState(session_id="contest", _storage_dir=tmp.name)
    state.world_state.scene.current_location = "碎石坡"
    state.world_state.scene.visible_npcs_here = ["地精", "岩石巨像"]
    if npcs:
        state.world_state.npcs = [
            NpcEntry(name="地精", attitude="敌对", hp=7, max_hp=7, ac=13, level=1, alive=True,
                     location="碎石坡", attributes={"str": 12, "dex": 12}, skills=[]),
            # 体型写进特性文本（巨型比中型大出两级以上，擒抱无效）
            NpcEntry(name="岩石巨像", attitude="敌对", hp=60, max_hp=60, ac=17, level=8,
                     alive=True, location="碎石坡", attributes={"str": 20, "dex": 8},
                     traits=["巨型构装体", "免疫毒素"], skills=[]),
        ]
    state.turn_tool_results = {}
    state.turn_action_ledger = {}
    return state


def tearDownModule():
    while _TEMP_DIRS:
        _TEMP_DIRS.pop().cleanup()


def _roll(damage: int = 3):
    return SimpleNamespace(roll=15, total=18, result=SimpleNamespace(value="成功")), damage


class TestContestModifiers(unittest.TestCase):
    def test_athletics_and_acrobatics_come_from_the_card(self):
        state = make_state()
        self.assertEqual(athletics_modifier(state, "岚"), 5, "力量 +3，运动熟练 +2")
        self.assertEqual(acrobatics_modifier(state, "岚"), 2, "敏捷 +2，无杂技熟练")
        self.assertEqual(athletics_modifier(state, "地精"), 1, "地精力量 12 → +1")

    def test_defense_modifier_defaults_to_the_better_option(self):
        state = make_state()
        goblin = state.world_state.npcs[0]
        goblin.attributes = {"str": 10, "dex": 16}
        goblin.skills = ["杂技"]
        self.assertEqual(defense_modifier(state, "地精"), 5, "取更优的敏捷（杂技）")
        self.assertEqual(defense_modifier(state, "地精", "str"), 0, "指定力量就按力量算")

    def test_size_index_reads_traits_text(self):
        state = make_state()
        self.assertEqual(size_index(state, "岚"), 2, "未写体型的角色按中型")
        self.assertEqual(size_index(state, "地精"), 2)
        self.assertEqual(size_index(state, "岩石巨像"), 4, "特性里的「巨型」")
        self.assertEqual(size_index(state, "地精", "小型"), 1, "override 优先")

    def test_can_action_target_blocks_two_sizes_up(self):
        state = make_state()
        self.assertEqual(can_action_target(state, "岚", "地精"), "")
        blocked = can_action_target(state, "岚", "岩石巨像")
        self.assertIn("大出两级以上", blocked)

    def test_helpless_detection(self):
        state = make_state()
        self.assertFalse(is_helpless(state, "地精"))
        state.world_state.npcs[0].conditions = [{"name": "昏迷", "description": "被击晕"}]
        self.assertTrue(is_helpless(state, "地精"))


class TestContestTools(unittest.IsolatedAsyncioTestCase):
    async def test_grapple_success_applies_condition(self):
        state = make_state()
        with patch("backend.engine.contest_rules.random.randint", side_effect=[18, 3]):
            out = await dm.execute_tool(
                "resolve_contest", {"action": "grapple", "target": "地精"}, state)
        self.assertIn("被擒抱", out)
        self.assertIn("擒抱", condition_names(state, "地精"))
        rolls = [e for _, t, e in state.event_history if t == "dice_roll"]
        self.assertIn("擒抱", rolls[-1]["skill"])

    async def test_grapple_failure_leaves_no_condition(self):
        state = make_state()
        with patch("backend.engine.contest_rules.random.randint", side_effect=[3, 18]):
            out = await dm.execute_tool(
                "resolve_contest", {"action": "grapple", "target": "地精"}, state)
        self.assertIn("失败", out)
        self.assertNotIn("擒抱", condition_names(state, "地精"))

    async def test_tie_stays_with_the_defender(self):
        state = make_state()
        player = state.character_info
        player["attributes"] = {"str": 10, "dex": 10}
        player["skill_proficiencies"] = []
        goblin = state.world_state.npcs[0]
        goblin.attributes = {"str": 10, "dex": 10}
        goblin.skills = []
        with patch("backend.engine.contest_rules.random.randint", side_effect=[12, 12]):
            out = await dm.execute_tool(
                "resolve_contest", {"action": "grapple", "target": "地精"}, state)
        self.assertIn("失败", out, "平局算防御方守住")
        self.assertNotIn("擒抱", condition_names(state, "地精"))

    async def test_shove_can_knock_prone_or_push(self):
        state = make_state()
        with patch("backend.engine.contest_rules.random.randint", side_effect=[18, 3]):
            prone = await dm.execute_tool(
                "resolve_contest",
                {"action": "shove", "target": "地精", "mode": "prone"}, state)
        self.assertIn("俯卧", condition_names(state, "地精"))
        self.assertIn("半速移动", prone)
        # 换一回合（清空行动账本与同回合去重表）再试推撞
        state.turn_action_ledger = {}
        state.turn_tool_results = {}
        state.world_state.npcs[0].conditions = []
        with patch("backend.engine.contest_rules.random.randint", side_effect=[18, 3]):
            push = await dm.execute_tool(
                "resolve_contest",
                {"action": "shove", "target": "地精", "mode": "push"}, state)
        self.assertIn("推开 5 尺", push)
        self.assertNotIn("俯卧", condition_names(state, "地精"), "推开不附带俯卧")

    async def test_escape_removes_own_grapple(self):
        state = make_state()
        state.character_info["conditions"] = [{"name": "擒抱", "description": "被地精抓住"}]
        with patch("backend.engine.contest_rules.random.randint", side_effect=[15, 3]):
            out = await dm.execute_tool(
                "resolve_contest", {"action": "escape", "target": "地精"}, state)
        self.assertIn("挣脱", out)
        self.assertNotIn("擒抱", condition_names(state, "岚"))

    async def test_escape_without_grapple_warns(self):
        state = make_state()
        out = await dm.execute_tool(
            "resolve_contest", {"action": "escape", "target": "地精"}, state)
        self.assertIn("没有被擒抱", out)

    async def test_size_limit_refuses_without_rolling(self):
        state = make_state()
        with patch("backend.engine.contest_rules.random.randint") as roll:
            out = await dm.execute_tool(
                "resolve_contest", {"action": "grapple", "target": "岩石巨像"}, state)
        roll.assert_not_called()
        self.assertIn("大出两级以上", out)

    async def test_helpless_target_succeeds_automatically(self):
        state = make_state()
        state.world_state.npcs[0].conditions = [{"name": "麻痹", "description": "被定住"}]
        with patch("backend.engine.contest_rules.random.randint") as roll:
            out = await dm.execute_tool(
                "resolve_contest", {"action": "grapple", "target": "地精"}, state)
        roll.assert_not_called()
        self.assertIn("自动成功", out)
        self.assertIn("擒抱", condition_names(state, "地精"))

    async def test_npc_grappling_the_player_writes_the_player_card(self):
        state = make_state()
        with patch("backend.engine.contest_rules.random.randint", side_effect=[18, 3]):
            out = await dm.execute_tool(
                "resolve_contest",
                {"action": "grapple", "attacker": "地精", "target": "岚"}, state)
        self.assertIn("擒抱", condition_names(state, "岚"))
        self.assertIn("地精 擒抱", out)

    async def test_npc_contest_does_not_spend_the_player_action(self):
        state = make_state()
        with patch("backend.engine.contest_rules.random.randint", side_effect=[18, 3]):
            await dm.execute_tool(
                "resolve_contest",
                {"action": "grapple", "attacker": "地精", "target": "岚"}, state)
        with patch.object(combat, "combat_attack_roll", side_effect=lambda *a, **k: _roll()):
            out = await dm.execute_tool(
                "combat_round", {"enemy_name": "地精", "player_action": "挥剑反击"}, state)
        self.assertNotIn("主行动已经结算过", out, "NPC 的擒抱不该扣玩家的主行动")

    async def test_player_contest_spends_the_main_action(self):
        state = make_state()
        with patch("backend.engine.contest_rules.random.randint", side_effect=[18, 3]):
            await dm.execute_tool(
                "resolve_contest", {"action": "grapple", "target": "地精"}, state)
        second = await dm.execute_tool(
            "resolve_contest", {"action": "shove", "target": "地精"}, state)
        self.assertIn("主行动已经结算过", second)

    async def test_multiattack_can_declare_an_extra_contest(self):
        state = make_state()
        with patch("backend.engine.contest_rules.random.randint", side_effect=[18, 3, 18, 3]):
            first = await dm.execute_tool(
                "resolve_contest", {"action": "grapple", "target": "地精"}, state)
            second = await dm.execute_tool(
                "resolve_contest",
                {"action": "shove", "target": "地精", "action_source": "multiattack"}, state)
        self.assertIn("擒抱", first)
        self.assertIn("俯卧", second, "声明多段攻击后可以合法再动一次")

    async def test_unknown_action_lists_options(self):
        state = make_state()
        out = await dm.execute_tool("resolve_contest", {"action": "??", "target": "地精"}, state)
        self.assertIn("grapple", out)
        self.assertIn("shove", out)
        self.assertIn("escape", out)

    async def test_missing_target_is_rejected(self):
        state = make_state()
        out = await dm.execute_tool("resolve_contest", {"action": "grapple"}, state)
        self.assertIn("需要 target", out)

    async def test_alias_parameter_names_are_accepted(self):
        """真实探针里模型写过 contestant_a/contest_kind：别名不能让它白跑一趟。"""
        state = make_state()
        with patch("backend.engine.contest_rules.random.randint", side_effect=[18, 3]):
            out = await dm.execute_tool(
                "resolve_contest",
                {"contestant_a": "你", "contestant_b": "地精", "contest_kind": "grapple",
                 "reason": "玩家徒手抓地精"}, state)
        self.assertIn("擒抱", condition_names(state, "地精"))
        self.assertIn("岚 擒抱", out, "「你」要归一到角色名")

    async def test_grappler_dying_releases_its_grapple(self):
        """5e：擒抱者无法行动时擒抱立即结束——后端自动收口，不指望 DM 记得清。"""
        state = make_state()
        with patch("backend.engine.contest_rules.random.randint", side_effect=[18, 3]):
            await dm.execute_tool(
                "resolve_contest",
                {"action": "grapple", "attacker": "地精", "target": "岚"}, state)
        self.assertIn("擒抱", condition_names(state, "岚"))
        from backend.engine.combat_rewards import _persist_combat_damage

        await _persist_combat_damage(state, state.world_state.npcs[0], 0)
        self.assertNotIn("擒抱", condition_names(state, "岚"), "擒抱者倒下后应自动挣脱")

    async def test_player_dying_releases_its_grapple(self):
        state = make_state()
        with patch("backend.engine.contest_rules.random.randint", side_effect=[18, 3]):
            await dm.execute_tool("resolve_contest", {"action": "grapple", "target": "地精"}, state)
        self.assertIn("擒抱", condition_names(state, "地精"))
        await player_damage.apply(state, 999, damage_type="钝击", reason="被砸中")
        self.assertNotIn("擒抱", condition_names(state, "地精"), "玩家倒地后应松开")

    async def test_escape_against_a_downed_grappler_is_automatic(self):
        state = make_state()
        state.character_info["conditions"] = [
            {"name": "擒抱", "description": "被地精擒抱", "grappled_by": "地精"}]
        npc = state.world_state.npcs[0]
        npc.hp, npc.alive = 0, False
        with patch("backend.engine.contest_rules.random.randint") as roll:
            out = await dm.execute_tool(
                "resolve_contest", {"action": "escape", "target": "地精"}, state)
        roll.assert_not_called()
        self.assertIn("轻易挣脱", out)
        self.assertNotIn("擒抱", condition_names(state, "岚"))


class TestContestRegistration(unittest.TestCase):
    def test_tool_is_visible_to_dm(self):
        from backend.engine.tools import DM_TOOLS

        names = {t["function"]["name"] for t in DM_TOOLS}
        self.assertIn("resolve_contest", names)


class TestGrappleLinks(unittest.TestCase):
    def test_grappling_targets_reads_the_structured_link(self):
        state = make_state()
        state.world_state.npcs[0].conditions = [
            {"name": "擒抱", "description": "被岚擒抱", "grappled_by": "岚"}]
        self.assertEqual(grappling_targets(state, "岚"), ["地精"])

    def test_unrelated_conditions_are_ignored(self):
        state = make_state()
        state.world_state.npcs[0].conditions = [
            {"name": "俯卧", "description": "被推倒"},
            {"name": "擒抱", "description": "被别人抓着", "grappled_by": "岩石巨像"},
        ]
        self.assertEqual(grappling_targets(state, "岚"), [])


if __name__ == "__main__":
    unittest.main()
