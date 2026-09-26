"""多规则系统整链：CoC 的理智/幸运/重伤，4e 的里程碑→行动点→血竭→回复力。

两条链各自的单点规则都有测试，但没人连着走一遍：
- CoC：SAN 损失 → 强制智力检定提示 → SAN 归零永久疯狂；幸运被夹在 0-99；
  单次重伤（≥ 半血上限）触发阈值结算。
- 4e：打完一场遭遇记里程碑 → +1 行动点（上限 3）→ 用行动点换额外行动且真的扣点
  → 掉到半血以下打血竭标记 → 短休花回复力回血。
"""
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from backend.engine import combat, dm_agent as dm
from backend.engine.character_state import _exec_update_state
from backend.engine.milestones import ACTION_POINT_CAP, record_encounter_end
from backend.engine.player_damage import apply as apply_damage
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState

_TEMP_DIRS: list = []


def hero(system: str, **info) -> GameSessionState:
    tmp = tempfile.TemporaryDirectory()
    _TEMP_DIRS.append(tmp)
    base = {"game_system": system, "char_class": "战士", "level": 3,
            "hp": 30, "max_hp": 30, "ac": 16,
            "attributes": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10}}
    base.update(info)
    state = GameSessionState(f"{system}-chain", "char", "岚", base, username=f"{system}-user")
    state.world_state = WorldState(session_id=f"{system}-chain", _storage_dir=tmp.name)
    state.world_state.npcs = [NpcEntry(name="地精", attitude="敌对", hp=7, max_hp=7,
                                       ac=13, alive=True)]
    state.turn_tool_results = {}
    state.turn_action_ledger = {}
    return state


def game_events(state: GameSessionState, kind: str) -> list[dict]:
    return [d for _, t, d in state.event_history if t == "game_event" and d.get("type") == kind]


class TestCocChain(unittest.IsolatedAsyncioTestCase):
    async def test_sanity_loss_then_permanent_insanity(self):
        state = hero("coc", hp=10, max_hp=10, san=10, max_san=55, luck=50,
                     char_class="记者")
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"san": -6}, "reason": "目击神话生物"}, state)
        hint = next(h for h in state.pending_system_hints if h.startswith("[系统强制-理智"))
        self.assertIn("智力", hint)
        self.assertEqual(game_events(state, "sanity")[-1]["extra"]["san_lost"], 6)

        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"san": -4}, "reason": "SAN 归零"}, state)
        self.assertTrue(state.character_info.get("permanent_insanity"), "SAN 归零进入永久疯狂")

    async def test_luck_is_clamped_between_zero_and_99(self):
        state = hero("coc", hp=10, max_hp=10, san=50, max_san=55, luck=5)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"luck": -20}, "reason": "孤注一掷"}, state)
            self.assertEqual(state.character_info["luck"], 0, "幸运不能扣成负数")
            await _exec_update_state({"changes": {"luck": 200}, "reason": "奖励"}, state)
            self.assertLessEqual(state.character_info["luck"], 99, "幸运上限 99")

    async def test_single_major_wound_knocks_out(self):
        state = hero("coc", hp=12, max_hp=12, san=50, max_san=60, luck=40)
        outcome = await apply_damage(state, 7, damage_type="", reason="被刀刺中", source="邪教徒")
        self.assertEqual(state.character_info["hp"], 5)
        self.assertTrue(game_events(state, "major_wound") or outcome["note"],
                        "单次伤害超过半血上限应触发重伤结算")


class Test4eChain(unittest.IsolatedAsyncioTestCase):
    async def test_milestone_then_spend_action_point(self):
        state = hero("dnd4e", action_points=1, hp=40, max_hp=40,
                     healing_surges=5, max_healing_surges=9, surge_value=10)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            # 两场遭遇 = 一个里程碑 → +1 行动点
            # 记账时机是 in_combat 的 True→False 跳变：调用时必须是"已脱离战斗"
            state.in_combat = False
            await record_encounter_end(state, was_in_combat=True)
            state.in_combat = False
            await record_encounter_end(state, was_in_combat=True)
        self.assertEqual(state.character_info["action_points"], 2, "里程碑 +1 行动点")
        self.assertLessEqual(state.character_info["action_points"], ACTION_POINT_CAP)

        with patch.object(combat, "combat_attack_roll",
                          return_value=(type("H", (), {"roll": 18, "total": 22,
                                                      "result": type("R", (), {"value": "成功"})()})(), 3)):
            await dm.execute_tool("combat_round", {
                "enemy_name": "地精", "player_action": "用行动点再补一剑",
                "action_source": "action_point", "enemy_can_act": False}, state)
        self.assertEqual(state.character_info["action_points"], 1, "花掉 1 点行动点")

    async def test_bloodied_then_healing_surge(self):
        state = hero("dnd4e", hp=40, max_hp=40, healing_surges=3,
                     max_healing_surges=9, surge_value=10, action_points=1)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"hp": -22}, "reason": "巨人挥锤"}, state)
        self.assertTrue(state.character_info["bloodied"], "半血以下打血竭标记")
        self.assertTrue(game_events(state, "bloodied"))

        out = await dm.execute_tool(
            "take_rest", {"rest_type": "short", "reason": "撤回营地短休"}, state)
        self.assertLess(state.character_info["healing_surges"], 3, "短休要花回复力")
        self.assertGreater(state.character_info["hp"], 18, "短休要把血回上来")
        self.assertIn("回复力", out)


if __name__ == "__main__":
    unittest.main()
