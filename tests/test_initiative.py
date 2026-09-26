"""先攻与回合归属：顺序由后端决定，同一单位本轮回合用尽后不得再动。"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import combat, initiative
from backend.engine import dm_agent as dm
from backend.engine import tool_executor as te
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


def _roll(value: str = "成功", total: int = 18):
    return SimpleNamespace(roll=15, total=total, result=SimpleNamespace(value=value))


class _FixedRandom:
    """固定骰：保证先攻顺序可预测。"""

    def __init__(self, values: list[int]):
        self.values = list(values)

    def randint(self, a: int, b: int) -> int:
        value = self.values.pop(0) if self.values else a
        return max(a, min(b, value))


class TestInitiativeTracker(unittest.TestCase):
    def make_state(self, enemies: list[tuple[str, int]] | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "init", "char", "岚",
            {"hp": 20, "max_hp": 20, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14}},
        )
        state.world_state = WorldState(session_id="init", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "碎石坡"
        state.world_state.npcs = [
            NpcEntry(name=name, attitude="敌对", hp=hp, max_hp=hp, ac=13, level=1, alive=True,
                     location="碎石坡", attributes={"dex": 12})
            for name, hp in (enemies or [("地精斥候", 7)])
        ]
        state.world_state.scene.visible_npcs_here = [n.name for n in state.world_state.npcs]
        state.turn_tool_results = {}
        state.turn_action_ledger = {}
        return state

    def test_player_wins_ties_and_order_is_by_initiative(self):
        state = self.make_state()
        # 玩家 d20=10+2=12；地精 d20=15+1=16 → 地精先动
        tracker = initiative.start(state, rng=_FixedRandom([10, 15]))
        self.assertEqual([c.name for c in tracker.order], ["地精斥候", "岚"])
        self.assertTrue(tracker.order[0].side == "enemy")

    def test_tie_prefers_player(self):
        state = self.make_state()
        # 玩家 d20=15+2=17；地精 d20=16+1=17 → 平手时玩家优先
        tracker = initiative.start(state, rng=_FixedRandom([15, 16]))
        self.assertEqual([c.name for c in tracker.order], ["岚", "地精斥候"])

    def test_enemy_turn_exhausts_and_blocks_second_action(self):
        state = self.make_state()
        initiative.start(state, rng=_FixedRandom([10, 15]))
        allowed, reason = te.consume_action(state, "地精斥候")
        self.assertTrue(allowed)
        blocked, reason = te.consume_action(state, "地精斥候")
        self.assertFalse(blocked)
        self.assertIn("主行动已经结算过", reason)
        # 变体名字（带注解）同样被归一，不能绕过去
        blocked_variant, _ = te.consume_action(state, "地精斥候（受伤）")
        self.assertFalse(blocked_variant)

    def test_multi_turn_creature_may_act_twice_per_round(self):
        state = self.make_state()
        tracker = initiative.start(state, rng=_FixedRandom([10, 15]))
        tracker.grant_turns("地精斥候", 1, note="多重回合")
        self.assertTrue(te.consume_action(state, "地精斥候")[0])
        self.assertTrue(te.consume_action(state, "地精斥候")[0], "两个回合的生物本轮能动两次")
        self.assertFalse(te.consume_action(state, "地精斥候")[0], "第三个回合必须被拒")

    def test_extra_action_does_not_consume_a_turn(self):
        state = self.make_state()
        initiative.start(state, rng=_FixedRandom([10, 15]))
        self.assertTrue(te.consume_action(state, "地精斥候", "legendary_action")[0])
        self.assertTrue(te.consume_action(state, "地精斥候")[0], "传奇动作不占用它的回合")

    def test_begin_player_turn_advances_round_and_resets_turns(self):
        state = self.make_state()
        initiative.start(state, rng=_FixedRandom([10, 15]))
        te.consume_action(state, "地精斥候")
        # 敌人动过、玩家还没动：待行动列表里只剩玩家
        self.assertEqual([c.name for c in initiative.tracker_for(state).pending()], ["岚"])
        hint = initiative.begin_player_turn(state)
        tracker = initiative.tracker_for(state)
        self.assertEqual(tracker.round, 2)
        self.assertIn("第2轮", hint)
        self.assertIn("地精斥候", hint)
        self.assertTrue(all(c.turns_left == 1 for c in tracker.alive()), "新一轮所有人恢复回合额度")
        self.assertEqual(len(tracker.pending()), 2, "新一轮玩家与敌人都待行动")

    def test_unknown_actor_falls_back_to_ledger(self):
        """不在先攻表内的单位（召唤物等）仍走账本，不被先攻表卡死。"""
        state = self.make_state()
        initiative.start(state, rng=_FixedRandom([10, 15]))
        self.assertTrue(te.consume_action(state, "召唤的狼")[0])
        self.assertFalse(te.consume_action(state, "召唤的狼")[0])

    def test_traits_detect_multi_turn(self):
        self.assertEqual(initiative.turns_per_round_from_traits(["每轮可行动两次（多重回合）"]), 2)
        self.assertEqual(initiative.turns_per_round_from_traits(["普通生物"]), 1)
        self.assertEqual(initiative.turns_per_round_from_traits(None), 1)

    def test_payload_and_summary_shape(self):
        state = self.make_state()
        tracker = initiative.start(state, rng=_FixedRandom([10, 15]))
        payload = tracker.payload()
        self.assertEqual(payload["round"], 1)
        self.assertEqual(payload["current"], "地精斥候")
        self.assertTrue(payload["order"][0]["is_current"])
        self.assertIn("先攻顺序", initiative.hint(state))


class TestInitiativeIntegration(unittest.IsolatedAsyncioTestCase):
    def make_state(self, enemies: list[tuple[str, int]] | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "init2", "char", "岚",
            {"hp": 20, "max_hp": 20, "ac": 16, "level": 1, "gb": 0, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14}},
        )
        state.world_state = WorldState(session_id="init2", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "碎石坡"
        state.world_state.npcs = [
            NpcEntry(name=name, attitude="敌对", hp=hp, max_hp=hp, ac=13, level=1, alive=True,
                     location="碎石坡", attributes={"dex": 12})
            for name, hp in (enemies or [("地精斥候", 7)])
        ]
        state.world_state.scene.visible_npcs_here = [n.name for n in state.world_state.npcs]
        state.turn_tool_results = {}
        state.turn_action_ledger = {}
        return state

    def _patch_dice(self, player_damage: int = 3, enemy_damage: int = 4):
        def fake(attacker, ac, mod, dice):
            return _roll(), (player_damage if attacker == "你" else enemy_damage)
        return patch.object(combat, "combat_attack_roll", side_effect=fake)

    async def test_first_attack_starts_initiative_and_reports_order(self):
        state = self.make_state()
        with patch.object(initiative, "roll_initiative", side_effect=[18, 5]), self._patch_dice():
            await dm.execute_tool(
                "combat_round", {"enemy_name": "地精斥候", "player_action": "挥剑"}, state)

        tracker = initiative.tracker_for(state)
        self.assertIsNotNone(tracker, "第一次交战应建立先攻表")
        events = [d for _, t, d in state.event_history if t == "game_event" and d.get("type") == "initiative"]
        self.assertEqual(len(events), 1, "应先攻顺序只推送一次")
        self.assertIn("先攻顺序", events[0]["description"])
        self.assertTrue(any(str(h).startswith(initiative.HINT_PREFIX)
                            for h in state.pending_system_hints), "DM 应收到先攻提示")

    async def test_enemy_cannot_act_twice_in_same_round(self):
        state = self.make_state([("地精斥候", 7), ("野狼", 11)])
        with self._patch_dice():
            first = await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)
            second = await dm.execute_tool("enemy_attack", {"enemy_name": "野狼"}, state)
            third = await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)
            # 参数不同的重复调用绕过"相同调用去重"，必须由先攻表拦下
            fourth = await dm.execute_tool(
                "enemy_attack", {"enemy_name": "地精斥候", "note": "再来一次"}, state)
        self.assertIn("地精斥候", first)
        self.assertIn("野狼", second)
        self.assertTrue(
            "主行动已经结算过" in third or "重复调用已跳过" in third,
            f"第三次调用应被拒绝，实际：{third[:80]}",
        )
        self.assertIn("主行动已经结算过", fourth)
        hp_losses = 20 - state.character_info["hp"]
        self.assertEqual(hp_losses, 8, "两名敌人各一次攻击")

    async def test_player_cannot_attack_twice_in_same_round(self):
        state = self.make_state()
        with self._patch_dice():
            first = await dm.execute_tool(
                "combat_round", {"enemy_name": "地精斥候", "player_action": "挥剑"}, state)
            second = await dm.execute_tool(
                "combat_round", {"enemy_name": "地精斥候", "player_action": "再砍一刀"}, state)
        self.assertIn("战斗结算", first)
        self.assertIn("主行动已经结算过", second)

    async def test_defeated_enemy_is_marked_in_tracker(self):
        state = self.make_state([("地精斥候", 7), ("野狼", 11)])
        with (patch.object(initiative, "roll_initiative", side_effect=[20, 1, 1]),
              self._patch_dice(player_damage=9)):
            await dm.execute_tool(
                "combat_round", {"enemy_name": "地精斥候", "player_action": "挥剑"}, state)
        tracker = initiative.tracker_for(state)
        self.assertIsNotNone(tracker, "场上还有野狼，先攻表应保留")
        enemy = tracker.find("地精斥候")
        self.assertFalse(enemy.alive)
        self.assertEqual(enemy.turns_left, 0)

    async def test_combat_end_clears_tracker(self):
        state = self.make_state()
        with patch.object(initiative, "roll_initiative", side_effect=[20, 1]), self._patch_dice(player_damage=9):
            await dm.execute_tool(
                "combat_round", {"enemy_name": "地精斥候", "player_action": "挥剑"}, state)
        combat._refresh_combat_state(state)
        self.assertIsNone(initiative.tracker_for(state), "敌人全灭后先攻表应清空")

    async def test_time_stop_grants_extra_turns_from_backend(self):
        from backend.engine import spell_tools
        state = self.make_state()
        initiative.start(state, rng=_FixedRandom([15, 5]))
        # 时间停止的实现已搬到 spell_tools，patch 目标跟着实现走
        with patch.object(spell_tools.random, "randint", return_value=3):
            note = await spell_tools._apply_time_stop(state, "时间暂停")
        self.assertIn("额外 4 个回合", note)
        player = initiative.tracker_for(state).find("岚")
        self.assertEqual(player.turns_per_round, 5, "1d4+1=4，加上原本的 1 个回合")
        events = [d for _, t, d in state.event_history if t == "game_event" and d.get("type") == "time_stop"]
        self.assertEqual(len(events), 1)

    async def test_non_time_stop_spell_grants_nothing(self):
        from backend.engine import spell_tools
        state = self.make_state()
        initiative.start(state, rng=_FixedRandom([15, 5]))
        note = await spell_tools._apply_time_stop(state, "火球术")
        self.assertEqual(note, "")
        self.assertEqual(initiative.tracker_for(state).find("岚").turns_per_round, 1)

    async def test_initiative_survives_save_serialization(self):
        from backend.save_manager import _serialize_dynamic
        state = self.make_state()
        initiative.start(state, rng=_FixedRandom([10, 15]))
        te.consume_action(state, "地精斥候")
        dyn = _serialize_dynamic(state)
        self.assertIsNotNone(dyn["initiative"])
        restored = initiative.InitiativeTracker.from_dict(dyn["initiative"])
        self.assertEqual(restored.round, 1)
        self.assertEqual([c.name for c in restored.order], ["地精斥候", "岚"])
        self.assertEqual(restored.find("地精斥候").turns_used, 1)


if __name__ == "__main__":
    unittest.main()
