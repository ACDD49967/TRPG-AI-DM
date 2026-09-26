"""突袭：先攻 tracker 标记首轮不能行动，警觉/免疫特性与读档都要保留。"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import combat, initiative, tool_executor as te
from backend.engine import dm_agent as dm
from backend.engine.initiative_model import InitiativeTracker
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


def _roll(total: int = 18):
    return SimpleNamespace(roll=15, total=total, result=SimpleNamespace(value="成功"))


def _make_state(tmp: tempfile.TemporaryDirectory, feats: list[dict] | None = None) -> GameSessionState:
    state = GameSessionState(
        "surprise", "char", "岚",
        {"hp": 20, "max_hp": 20, "ac": 16, "level": 3, "game_system": "dnd5e",
         "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14},
         "feats": list(feats or [])},
    )
    state.world_state = WorldState(session_id="surprise", _storage_dir=tmp.name)
    state.world_state.scene.current_location = "碎石坡"
    state.world_state.npcs = [
        NpcEntry(name="地精斥候", attitude="敌对", hp=7, max_hp=7, ac=13,
                 level=1, alive=True, location="碎石坡", attributes={"dex": 12}),
    ]
    state.world_state.scene.visible_npcs_here = ["地精斥候"]
    state.turn_tool_results = {}
    state.turn_action_ledger = {}
    return state


class _FixedRandom:
    def __init__(self, values: list[int]):
        self.values = list(values)

    def randint(self, a: int, b: int) -> int:
        value = self.values.pop(0) if self.values else a
        return max(a, min(b, value))


class TestSurpriseTracker(unittest.TestCase):
    def make_state(self, feats: list[dict] | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return _make_state(tmp, feats)

    def test_surprised_side_is_blocked_until_next_round(self):
        state = self.make_state()
        tracker = initiative.start(state, rng=_FixedRandom([10, 15]))
        self.assertEqual(tracker.mark_surprised("enemy"), ["地精斥候"])
        allowed, reason = te.consume_action(state, "地精斥候")
        self.assertFalse(allowed)
        self.assertIn("突袭回合", reason)
        self.assertTrue(te.consume_action(state, "岚")[0], "突袭方仍可行动")
        tracker.begin_round()
        self.assertTrue(te.consume_action(state, "地精斥候")[0], "下一轮解除突袭")

    def test_alert_feat_is_immune_to_surprise(self):
        state = self.make_state([{"id": "alert", "name": "警觉"}])
        tracker = initiative.start(state, rng=_FixedRandom([10, 15]))
        self.assertEqual(tracker.mark_surprised("player"), [])
        self.assertFalse(tracker.find("岚").surprised)
        self.assertTrue(te.consume_action(state, "岚")[0])

    def test_surprise_flag_survives_serialization(self):
        state = self.make_state()
        tracker = initiative.start(state, rng=_FixedRandom([10, 15]))
        tracker.mark_surprised("enemy")
        restored = InitiativeTracker.from_dict(tracker.to_dict())
        self.assertTrue(restored.find("地精斥候").surprised)
        self.assertFalse(restored.find("岚").surprised)


class TestSurpriseIntegration(unittest.IsolatedAsyncioTestCase):
    def make_state(self, feats: list[dict] | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return _make_state(tmp, feats)

    def _patch_dice(self):
        def fake(attacker, ac, mod, dice, **kwargs):
            return _roll(), 3 if attacker == "你" else 4
        return patch.object(combat, "combat_attack_roll", side_effect=fake)

    async def test_player_surprise_blocks_enemy_counterattack(self):
        state = self.make_state()
        with self._patch_dice():
            first = await dm.execute_tool(
                "combat_round",
                {"enemy_name": "地精斥候", "player_action": "突袭挥剑", "surprise": True},
                state,
            )
        self.assertIn("突袭回合", first)
        self.assertEqual(state.character_info["hp"], 20, "被突袭的敌人不应反击")
        tracker = initiative.tracker_for(state)
        self.assertTrue(tracker.find("地精斥候").surprised)

        initiative.begin_player_turn(state)
        with self._patch_dice():
            second = await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)
        self.assertIn("造成 4 点伤害", second)
        self.assertEqual(state.character_info["hp"], 16, "下一轮敌人恢复正常行动")

    async def test_enemy_surprise_blocks_player_action_until_next_round(self):
        state = self.make_state()
        with self._patch_dice():
            ambush = await dm.execute_tool(
                "enemy_attack", {"enemy_name": "地精斥候", "surprise": True}, state)
            blocked = await dm.execute_tool(
                "combat_round", {"enemy_name": "地精斥候", "player_action": "挥剑"}, state)
        self.assertIn("造成 4 点伤害", ambush)
        self.assertIn("突袭回合", blocked)
        self.assertEqual(state.world_state.npcs[0].hp, 7, "被突袭的玩家不应完成攻击")

        initiative.begin_player_turn(state)
        with self._patch_dice():
            allowed = await dm.execute_tool(
                "combat_round",
                {"enemy_name": "地精斥候", "player_action": "挥剑", "enemy_can_act": False},
                state,
            )
        self.assertIn("战斗结算", allowed)
        self.assertEqual(state.world_state.npcs[0].hp, 4)

    async def test_alert_feat_allows_player_to_act_in_surprise_round(self):
        state = self.make_state([{"id": "alert", "name": "警觉"}])
        with self._patch_dice():
            await dm.execute_tool(
                "enemy_attack", {"enemy_name": "地精斥候", "surprise": True}, state)
            allowed = await dm.execute_tool(
                "combat_round",
                {"enemy_name": "地精斥候", "player_action": "反击", "enemy_can_act": False},
                state,
            )
        self.assertIn("战斗结算", allowed)
        self.assertEqual(state.world_state.npcs[0].hp, 4)


if __name__ == "__main__":
    unittest.main()
