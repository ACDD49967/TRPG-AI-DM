"""生命阈值兜底：4e 血竭（Bloodied）与 CoC 7e 单次重伤/致死。

两条规则此前只写在规则文本里（`rules_4e` 的"降到一半以下进入血竭"、
CoC 段的"归 0 时重伤昏迷"），代码里没有任何记账或提示。
"""
import unittest
from unittest.mock import AsyncMock, patch

from backend.engine.character_state import _exec_update_state
from backend.engine.player_damage import apply as apply_damage
from backend.engine.session import GameSessionState


def hero(system: str = "dnd4e", hp: int = 40, max_hp: int = 40) -> GameSessionState:
    return GameSessionState(
        "hp", "char", "岚",
        {"game_system": system, "char_class": "战士", "level": 1,
         "hp": hp, "max_hp": max_hp, "ac": 16,
         "attributes": {"str": 16, "con": 14, "dex": 12, "int": 10, "wis": 10, "cha": 10}},
        username="hp-user",
    )


def events(state: GameSessionState, kind: str) -> list[dict]:
    return [d for _, t, d in state.event_history if t == "game_event" and d.get("type") == kind]


def hints(state: GameSessionState, prefix: str) -> list[str]:
    return [h for h in (state.pending_system_hints or []) if h.startswith(prefix)]


class TestBloodied(unittest.IsolatedAsyncioTestCase):
    async def test_4e_half_hp_marks_bloodied(self):
        state = hero("dnd4e", hp=40, max_hp=40)
        # 只挡掉状态事件的广播；bloodied 自己的事件要落进 event_history 供断言
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"hp": -22}, "reason": "巨人挥锤"}, state)
        self.assertEqual(state.character_info["hp"], 18)
        self.assertTrue(state.character_info["bloodied"], "4e 半血以下要打血竭标记")
        self.assertTrue(events(state, "bloodied"))
        updates = [d for _, t, d in state.event_history if t == "state_update"]
        self.assertTrue(any(d.get("bloodied") is True for d in updates),
                        "血竭要同步给前端状态（4e 角色卡显示标记）")
        self.assertIn("血竭", hints(state, "[系统强制-血竭")[0])

    async def test_4e_healing_above_half_clears_it(self):
        state = hero("dnd4e", hp=18, max_hp=40)
        state.character_info["bloodied"] = True
        # 只挡掉状态事件的广播；bloodied 自己的事件要落进 event_history 供断言
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"hp": 10}, "reason": "治疗药水"}, state)
        self.assertEqual(state.character_info["hp"], 28)
        self.assertFalse(state.character_info["bloodied"])
        self.assertTrue(events(state, "bloodied_cleared"))

    async def test_5e_has_no_bloodied_rule(self):
        state = hero("dnd5e", hp=40, max_hp=40)
        # 只挡掉状态事件的广播；bloodied 自己的事件要落进 event_history 供断言
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"hp": -22}, "reason": "巨人挥锤"}, state)
        self.assertFalse(state.character_info.get("bloodied"))
        self.assertFalse(events(state, "bloodied"))


class TestCocMajorWound(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for target in ("backend.engine.character_state.push_event",
                       "backend.engine.player_damage.push_event"):
            patcher = patch(target, new=AsyncMock())
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_single_hit_over_half_max_is_a_major_wound(self):
        state = hero("coc", hp=12, max_hp=12)
        await apply_damage(state, 7, "穿刺", reason="触手贯穿")
        self.assertTrue(hints(state, "[系统强制-重伤"), "单次 ≥ 半血要有重伤提示")
        self.assertIn("体质", hints(state, "[系统强制-重伤")[0])
        self.assertEqual(events(state, "major_wound")[-1]["extra"]["fatal"], False)

    async def test_single_hit_over_max_hp_is_fatal(self):
        state = hero("coc", hp=12, max_hp=12)
        await apply_damage(state, 13, "钝击", reason="被碾碎")
        text = hints(state, "[系统强制-重伤")[0]
        self.assertIn("致命伤", text)
        self.assertEqual(events(state, "major_wound")[-1]["extra"]["fatal"], True)

    async def test_small_hits_stay_quiet(self):
        state = hero("coc", hp=12, max_hp=12)
        await apply_damage(state, 3, "钝击", reason="蹭伤")
        self.assertFalse(hints(state, "[系统强制-重伤"))
        self.assertFalse(events(state, "major_wound"))

    async def test_5e_damage_does_not_trigger_major_wound(self):
        state = hero("dnd5e", hp=40, max_hp=40)
        await apply_damage(state, 25, "挥砍", reason="巨斧")
        self.assertFalse(hints(state, "[系统强制-重伤"))


if __name__ == "__main__":
    unittest.main()
