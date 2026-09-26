"""存档必须带上完整世界状态，且 NPC 血量与存活标记保持一致。

两个回归点（都由 6 回合真实模型长跑探针暴露）：
1. `save_serialize` 以前"先落盘再读回硬编码 world_states/<sid>.json"，
   会话的 `_storage_dir` 不是默认目录时，存档里的 world_state 会静默为空；
2. `adjust_npc` 只改 hp，HP 归零后 `alive` 仍是 True，与
   `_persist_combat_damage` 的约定不一致。
"""
import tempfile
import unittest
from pathlib import Path

from backend import save_manager as saves
from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


def make_state(tmp: Path) -> GameSessionState:
    state = GameSessionState("save-world", "char", "岚",
                             {"hp": 20, "max_hp": 20, "ac": 15, "game_system": "dnd5e"})
    state.world_state = WorldState(session_id="save-world", _storage_dir=str(tmp / "custom_world_dir"))
    state.world_state.scene.current_location = "旧商道"
    state.world_state.npcs = [
        NpcEntry(name="地精斥候", attitude="敌对", hp=9, max_hp=9, ac=13, alive=True),
        NpcEntry(name="地精弓手", attitude="敌对", hp=8, max_hp=8, ac=14, alive=True),
    ]
    return state


class TestSaveIncludesWorld(unittest.TestCase):
    def test_world_state_is_serialized_from_memory_not_hardcoded_dir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_root = saves.SAVE_ROOT
            saves.SAVE_ROOT = root / "saves"
            try:
                state = make_state(root)
                payload = saves.create_save(state, label="世界状态回归")
            finally:
                saves.SAVE_ROOT = old_root

        world = (payload.get("session") or {}).get("world_state") or {}
        names = [n.get("name") for n in (world.get("npcs") or [])]
        self.assertEqual(names, ["地精斥候", "地精弓手"], "非默认存储目录下也必须写入世界状态")
        self.assertEqual((world.get("scene") or {}).get("current_location"), "旧商道")
        self.assertEqual(world.get("npcs")[0].get("hp"), 9)

    def test_world_state_matches_live_hp_after_damage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_root = saves.SAVE_ROOT
            saves.SAVE_ROOT = root / "saves"
            try:
                state = make_state(root)
                state.world_state.npcs[0].hp = 0
                state.world_state.npcs[0].alive = False
                payload = saves.create_save(state, label="战后存档")
            finally:
                saves.SAVE_ROOT = old_root

        world = (payload.get("session") or {}).get("world_state") or {}
        saved = {n.get("name"): n for n in (world.get("npcs") or [])}
        self.assertEqual(saved["地精斥候"]["hp"], 0)
        self.assertFalse(saved["地精斥候"]["alive"], "阵亡状态必须一起进存档")


class TestAdjustNpcVitals(unittest.IsolatedAsyncioTestCase):
    async def test_hp_zero_syncs_alive_false(self):
        with tempfile.TemporaryDirectory() as td:
            state = make_state(Path(td))
            npc = state.world_state.npcs[0]
            await dm.execute_tool(
                "adjust_npc",
                {"name": "地精斥候", "field": "hp", "delta": -9, "reason": "被解决"}, state)
            self.assertEqual(npc.hp, 0)
            self.assertFalse(npc.alive, "HP 归零后 alive 必须同步为 False")
            # 死掉的敌人不能再攻击
            out = await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)
            self.assertIn("已阵亡", out)

    async def test_damage_above_zero_keeps_alive_flag(self):
        with tempfile.TemporaryDirectory() as td:
            state = make_state(Path(td))
            npc = state.world_state.npcs[0]
            await dm.execute_tool(
                "adjust_npc",
                {"name": "地精斥候", "field": "hp", "delta": -3, "reason": "轻伤"}, state)
            self.assertEqual(npc.hp, 6)
            self.assertTrue(npc.alive)

    async def test_healing_does_not_auto_revive(self):
        with tempfile.TemporaryDirectory() as td:
            state = make_state(Path(td))
            npc = state.world_state.npcs[0]
            npc.hp = 0
            npc.alive = False
            await dm.execute_tool(
                "adjust_npc",
                {"name": "地精斥候", "field": "hp", "delta": 5, "reason": "治疗"}, state)
            self.assertEqual(npc.hp, 5)
            self.assertFalse(npc.alive, "回血不自动复活，避免覆盖剧情状态；要复活请显式改 alive")

    async def test_update_world_state_hp_zero_also_syncs_alive(self):
        """`update_world_state(update_npc, hp=…)` 是另一条改血路径，同样要同步 alive。"""
        with tempfile.TemporaryDirectory() as td:
            state = make_state(Path(td))
            npc = state.world_state.npcs[1]
            await dm.execute_tool(
                "update_world_state",
                {"action": "update_npc", "target": "地精弓手",
                 "changes": {"hp": 0}, "reason": "被魔法飞弹收掉"}, state)
            self.assertEqual(npc.hp, 0)
            self.assertFalse(npc.alive, "update_npc 改到 0 HP 也必须同步 alive=False")
            out = await dm.execute_tool("enemy_attack", {"enemy_name": "地精弓手"}, state)
            self.assertIn("已阵亡", out)


if __name__ == "__main__":
    unittest.main()
