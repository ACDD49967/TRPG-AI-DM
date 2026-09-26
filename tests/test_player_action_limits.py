"""玩家行动经济与状态限制：施法/休息计入行动、昏迷死亡不能行动、战斗中不能休息。"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import dm_agent as dm
from backend.engine import tool_executor as te
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestPlayerActionLimits(unittest.IsolatedAsyncioTestCase):
    def make_state(self, hp: int = 20, enemies: list[tuple[str, str]] | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "limits", "char", "岚",
            {"hp": hp, "max_hp": 20, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "法师",
             "spell_slots": {"spell_slots": [3, 2], "pact_slots": 0},
             "attributes": {"str": 10, "dex": 14, "con": 12, "int": 16}},
        )
        state.world_state = WorldState(session_id="limits", _storage_dir=tmp.name)
        for name, attitude in (enemies or []):
            state.world_state.npcs.append(
                NpcEntry(name=name, attitude=attitude, hp=7, max_hp=7, ac=13, alive=True))
        state.turn_tool_results = {}
        state.turn_action_ledger = {}
        return state

    async def test_casting_and_resting_share_the_same_primary_action(self):
        state = self.make_state()
        with patch.object(te, "_handlers", return_value={"cast_spell": self._ok, "take_rest": self._rest}):
            first = await dm.execute_tool("cast_spell", {"name": "魔法飞弹", "level": 1}, state)
            second = await dm.execute_tool("cast_spell", {"name": "燃烧之手", "level": 1}, state)
            third = await dm.execute_tool("take_rest", {"rest_type": "short"}, state)

        self.assertEqual(first, "施法成功")
        self.assertIn("主行动已经结算过", second, "一回合不能连放两个不同法术")
        self.assertIn("主行动已经结算过", third, "施法后不能再休息")

    async def test_bonus_action_spell_is_allowed_once(self):
        state = self.make_state()
        calls: list[dict] = []

        async def handler(args, st):
            calls.append(args)
            return "施法成功"

        with patch.object(te, "_handlers", return_value={"cast_spell": handler}):
            await dm.execute_tool("cast_spell", {"name": "魔法飞弹", "level": 1}, state)
            bonus = await dm.execute_tool(
                "cast_spell", {"name": "治疗真言", "level": 1, "action_source": "bonus_action"}, state)
            again = await dm.execute_tool(
                "cast_spell",
                {"name": "治疗真言", "level": 1, "action_source": "bonus_action", "note": "再来一次"},
                state,
            )
        self.assertEqual(bonus, "施法成功")
        self.assertIn("已用完", again)
        self.assertEqual(len(calls), 2, "主行动 + 一次附赠动作施法，第三次必须被拒")

    async def test_unconscious_player_cannot_act(self):
        state = self.make_state(hp=0)
        state.dying = True
        with patch.object(te, "_handlers", return_value={
                "combat_round": self._ok, "cast_spell": self._ok, "take_rest": self._rest}):
            attack = await dm.execute_tool("combat_round", {"enemy_name": "地精"}, state)
            cast = await dm.execute_tool("cast_spell", {"name": "魔法飞弹", "level": 1}, state)
        self.assertIn("昏迷", attack)
        self.assertIn("昏迷", cast)

    async def test_dead_player_cannot_act_until_revived(self):
        state = self.make_state(hp=0)
        state.character_dead = True
        with patch.object(te, "_handlers", return_value={"combat_round": self._ok}):
            blocked = await dm.execute_tool("combat_round", {"enemy_name": "地精"}, state)
        self.assertIn("死亡", blocked)

        # 复活（HP 恢复为正）后解除锁定
        await dm._exec_update_state({"changes": {"hp": 5}, "reason": "复活术"}, state)
        self.assertFalse(state.character_dead)
        with patch.object(te, "_handlers", return_value={"combat_round": self._ok}):
            allowed = await dm.execute_tool("combat_round", {"enemy_name": "地精"}, state)
        self.assertEqual(allowed, "执行成功")

    async def test_rest_is_refused_in_combat(self):
        state = self.make_state(enemies=[("地精斥候", "敌对")])
        state.world_state.scene.current_location = "村外小径"
        state.world_state.npcs[0].location = "村外小径"
        state.world_state.scene.visible_npcs_here = ["地精斥候"]
        dm._refresh_combat_state(state)
        self.assertTrue(state.in_combat)
        result = await dm.execute_tool("take_rest", {"rest_type": "long"}, state)
        self.assertIn("战斗中无法休息", result)

    async def test_in_combat_clears_when_all_hostiles_die(self):
        state = self.make_state(enemies=[("地精斥候", "敌对"), ("村民", "中立")])
        state.world_state.scene.current_location = "碎石坡"
        state.world_state.npcs[0].location = "碎石坡"
        dm._refresh_combat_state(state)
        self.assertTrue(state.in_combat)
        for npc in state.world_state.npcs:
            if npc.attitude == "敌对":
                npc.alive = False
                npc.hp = 0
        dm._refresh_combat_state(state)
        self.assertFalse(state.in_combat)
        result = await dm.execute_tool("take_rest", {"rest_type": "short"}, state)
        self.assertNotIn("战斗中无法休息", result)

    async def test_distant_hostile_does_not_block_rest(self):
        state = self.make_state(enemies=[("山贼", "敌对")])
        state.world_state.scene.current_location = "灰石村"
        state.world_state.npcs[0].location = "北面山洞"
        dm._refresh_combat_state(state)
        self.assertFalse(state.in_combat, "远处敌人不应让玩家无法在村里休息")
        result = await dm.execute_tool("take_rest", {"rest_type": "short"}, state)
        self.assertNotIn("战斗中无法休息", result)

    async def _ok(self, args, state):
        return "施法成功" if "name" in args else "执行成功"

    async def _rest(self, args, state):
        return "🛌 短休: +8HP，短休资源已恢复"


if __name__ == "__main__":
    unittest.main()
