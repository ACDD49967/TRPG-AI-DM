"""光照等级与视觉：明亮/微光/黑暗，黑暗视觉与微光视觉，以及它在攻击与潜行里的后果。"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import dm_agent as dm
from backend.engine import light_rules
from backend.engine.combat_advantage import enemy_attack_advantage, player_attack_advantage
from backend.engine.rules import AdvantageMode
from backend.engine.session import GameSessionState
from backend.engine.stealth_modifiers import best_observer, observers
from backend.engine.stealth_rules import is_hidden
from backend.engine.world_io import save_world, world_to_dict
from backend.engine.world_state import NpcEntry, WorldState

_TEMP_DIRS: list[tempfile.TemporaryDirectory] = []


def make_state(*, light: str = "", time: str = "夜里", darkvision: bool = False,
               npc_darkvision: bool = False) -> GameSessionState:
    tmp = tempfile.TemporaryDirectory()
    _TEMP_DIRS.append(tmp)   # 由 tearDownModule 统一清理
    traits = ["黑暗视觉"] if darkvision else []
    state = GameSessionState(
        "light", "char", "岚",
        {"game_system": "dnd5e", "char_class": "游荡者", "level": 3, "hp": 24, "max_hp": 24,
         "ac": 15, "xp": 0,
         "attributes": {"str": 10, "dex": 16, "con": 14, "wis": 14},
         "skill_proficiencies": ["隐匿", "察觉"],
         "race_traits": traits},
    )
    state.world_state = WorldState(session_id="light", _storage_dir=tmp.name)
    state.world_state.scene.current_location = "矿道"
    state.world_state.scene.current_time = time
    state.world_state.scene.light = light
    state.world_state.scene.visible_npcs_here = ["地精斥候"]
    state.world_state.npcs = [
        NpcEntry(name="地精斥候", attitude="敌对", hp=7, max_hp=7, ac=13, level=1, alive=True,
                 location="矿道", attributes={"dex": 14, "wis": 12},
                 traits=["黑暗视觉"] if npc_darkvision else []),
    ]
    state.turn_tool_results = {}
    state.turn_action_ledger = {}
    return state


def tearDownModule():
    while _TEMP_DIRS:
        _TEMP_DIRS.pop().cleanup()


class TestLightBasics(unittest.TestCase):
    def test_normalize_accepts_free_wording(self):
        self.assertEqual(light_rules.normalize_light("明亮"), light_rules.BRIGHT)
        self.assertEqual(light_rules.normalize_light("白天"), light_rules.BRIGHT)
        self.assertEqual(light_rules.normalize_light("dim"), light_rules.DIM)
        self.assertEqual(light_rules.normalize_light("黄昏"), light_rules.DIM)
        self.assertEqual(light_rules.normalize_light("漆黑一片"), light_rules.DARK)
        self.assertEqual(light_rules.normalize_light(""), "", "没写就不猜")
        self.assertEqual(light_rules.normalize_light("说不清"), "")

    def test_explicit_field_beats_time_inference(self):
        state = make_state(light="明亮", time="午夜")
        self.assertEqual(light_rules.scene_light(state), light_rules.BRIGHT,
                         "举着火把的午夜也是明亮")
        state.world_state.scene.light = ""
        self.assertEqual(light_rules.scene_light(state), light_rules.DARK, "没写就看时间")

    def test_vision_kind_reads_both_cards(self):
        state = make_state(darkvision=True, npc_darkvision=True)
        self.assertEqual(light_rules.vision_kind(state, "岚"), "darkvision")
        self.assertEqual(light_rules.vision_kind(state, "地精斥候"), "darkvision")
        plain = make_state()
        self.assertEqual(light_rules.vision_kind(plain, "岚"), "")
        plain.character_info["race_traits"] = ["微光视觉"]
        self.assertEqual(light_rules.vision_kind(plain, "岚"), "low_light")

    def test_effective_light_applies_vision(self):
        dark = make_state(light="黑暗")
        self.assertEqual(light_rules.effective_light(dark, "岚"), light_rules.DARK)
        self.assertFalse(light_rules.can_see(dark, "岚"))
        infravision = make_state(light="黑暗", darkvision=True)
        self.assertEqual(light_rules.effective_light(infravision, "岚"), light_rules.DIM)
        self.assertTrue(light_rules.can_see(infravision, "岚"))
        low = make_state(light="微光")
        low.character_info["race_traits"] = ["微光视觉"]
        self.assertEqual(light_rules.effective_light(low, "岚"), light_rules.BRIGHT)

    def test_passive_perception_penalty(self):
        self.assertEqual(light_rules.passive_perception_penalty(make_state(light="明亮"), "岚"), 0)
        self.assertEqual(light_rules.passive_perception_penalty(make_state(light="微光"), "岚"), -5)
        self.assertEqual(light_rules.passive_perception_penalty(make_state(light="黑暗"), "岚"), -5)
        see_in_dark = make_state(light="黑暗", darkvision=True)
        # 5e：黑暗视觉把黑暗当微光看，而微光=轻度遮蔽 → 依赖视觉的察觉仍有劣势（-5）
        self.assertEqual(light_rules.passive_perception_penalty(see_in_dark, "岚"), -5)

    def test_visibility_reasons(self):
        state = make_state(light="黑暗")
        adv, dis = light_rules.visibility_reasons(state, "岚", "地精斥候")
        self.assertEqual(adv, ["目标身处黑暗"])
        self.assertEqual(dis, ["黑暗中看不见目标"])
        both_see = make_state(light="明亮")
        self.assertEqual(light_rules.visibility_reasons(both_see, "岚", "地精斥候"), ([], []))
        no_light_field = make_state(light="", time="")
        self.assertEqual(light_rules.visibility_reasons(no_light_field, "岚", "地精斥候"), ([], []),
                         "连时间都没有就不给加减值")


class TestLightInCombat(unittest.TestCase):
    def test_darkness_gives_the_blind_attacker_disadvantage(self):
        state = make_state(light="黑暗")
        npc = state.world_state.npcs[0]
        decision = player_attack_advantage(
            state, {}, action="挥剑劈下", weapon="长剑", enemy_npc=npc,
            system="dnd5e", player_name="岚")
        self.assertEqual(decision.mode, AdvantageMode.NORMAL,
                         "自己看不见（劣势）+ 对方也看不见（优势）互相抵消")
        self.assertTrue(any("看不见" in r for r in decision.disadvantages))
        self.assertTrue(any("黑暗" in r for r in decision.advantages))

    def test_target_in_darkness_but_attacker_has_darkvision(self):
        state = make_state(light="黑暗", darkvision=True)
        npc = state.world_state.npcs[0]
        decision = player_attack_advantage(
            state, {}, action="挥剑劈下", weapon="长剑", enemy_npc=npc,
            system="dnd5e", player_name="岚")
        self.assertEqual(decision.mode, AdvantageMode.ADVANTAGE, "你看得见、对方看不见")
        self.assertTrue(any("黑暗" in r for r in decision.advantages))

    def test_enemy_attacking_from_darkness_gets_advantage(self):
        state = make_state(light="黑暗", npc_darkvision=True)
        npc = state.world_state.npcs[0]
        decision = enemy_attack_advantage(
            state, {}, enemy="地精斥候", enemy_npc=npc, enemy_action="刺出短矛",
            system="dnd5e")
        self.assertEqual(decision.mode, AdvantageMode.ADVANTAGE)


class TestLightInStealth(unittest.IsolatedAsyncioTestCase):
    async def test_pitch_dark_hides_without_rolling(self):
        state = make_state(light="黑暗")
        with patch("backend.engine.stealth_rules.random.randint") as roll:
            out = await dm.execute_tool("resolve_stealth", {"action": "hide"}, state)
        roll.assert_not_called()
        self.assertIn("没有黑暗视觉", out)
        self.assertTrue(is_hidden(state))

    async def test_darkvision_observer_still_forces_a_check(self):
        state = make_state(light="黑暗", npc_darkvision=True)
        with patch("backend.engine.stealth_rules.random.randint", return_value=15) as roll:
            out = await dm.execute_tool("resolve_stealth", {"action": "hide"}, state)
        self.assertEqual(roll.call_count, 1, "对方有黑暗视觉，就得照常掷")
        self.assertIn("隐匿", out)

    async def test_dim_light_lowers_observer_passive_perception(self):
        state = make_state(light="微光")
        # 地精斥候被动察觉 11，微光下依赖视觉 → -5
        self.assertEqual(best_observer(state, target="岚"), ("地精斥候", 6))
        self.assertIn(("地精斥候", 6), observers(state, target="岚"))


class TestLightSceneWiring(unittest.IsolatedAsyncioTestCase):
    async def test_update_scene_writes_light(self):
        state = make_state(light="")
        out = await dm.execute_tool(
            "update_scene", {"light": "黑暗", "light_source": "无光"}, state)
        self.assertIn("场景已更新", out)
        self.assertEqual(state.world_state.scene.light, "黑暗")
        self.assertEqual(state.world_state.scene.light_source, "无光")

    async def test_scene_event_carries_light(self):
        state = make_state()
        await dm.execute_tool("update_scene", {"light": "微光", "weather": "阴"}, state)
        events = [d for _, t, d in state.event_history if t == "scene_update"]
        self.assertTrue(events)
        self.assertEqual(events[-1].get("light"), "微光")

    async def test_clearing_light_is_explicit(self):
        """光照可以清空（回到"按时间推断"）；其它文本字段要显式写 clear 才清。"""
        state = make_state(light="黑暗")
        state.world_state.scene.weather = "雨"
        await dm.execute_tool("update_scene", {"light": "", "weather": ""}, state)
        self.assertEqual(state.world_state.scene.light, "", "空 light 视为清空")
        self.assertEqual(state.world_state.scene.weather, "雨", "传空默认忽略，避免误抹")
        await dm.execute_tool("update_scene", {"weather": "", "clear": ["weather"]}, state)
        self.assertEqual(state.world_state.scene.weather, "", "显式 clear 才清空")

    def test_journal_payload_carries_light(self):
        """笔记面板读的是 to_player_journal 的 scene，光照必须在这份载荷里。"""
        state = make_state(light="黑暗")
        state.world_state.scene.light_source = "无光"
        scene = state.world_state.to_player_journal()["scene"]
        self.assertEqual(scene["light"], "黑暗")
        self.assertEqual(scene["light_source"], "无光")

    def test_light_survives_a_save_round_trip(self):
        state = make_state(light="黑暗", time="夜里")
        save_world(state.world_state)
        payload = world_to_dict(state.world_state)
        self.assertEqual(payload["scene"]["light"], "黑暗")
        self.assertEqual(payload["scene"]["light_source"], "")


if __name__ == "__main__":
    unittest.main()
