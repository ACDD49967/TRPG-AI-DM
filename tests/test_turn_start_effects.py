"""回合开始效果：阳光超敏伤害、每轮一次与光照边界。"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import combat, dm_agent as dm, initiative
from backend.engine import combat_state
from backend.engine.combat_rewards import _persist_combat_damage
from backend.engine.session import GameSessionState
from backend.engine.turn_start_effects import apply_turn_start_effects, record_damage_type
from backend.engine.world_state import NpcEntry, WorldState


def _roll(total: int = 18):
    return SimpleNamespace(roll=15, total=total, result=SimpleNamespace(value="成功"))


class TestTurnStartEffects(unittest.IsolatedAsyncioTestCase):
    def make_state(self, time: str = "正午", weather: str = "晴空万里",
                   traits: list[str] | None = None,
                   hp: int = 30) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "turn-start", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14}},
        )
        state.world_state = WorldState(session_id="turn-start", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "钟楼顶"
        state.world_state.scene.current_time = time
        state.world_state.scene.weather = weather
        state.world_state.npcs = [
            NpcEntry(
                name="吸血鬼", attitude="敌对", hp=hp, max_hp=30, ac=15, level=5,
                alive=True, location="钟楼顶",
                traits=list(traits or [
                    "Sunlight Hypersensitivity. The vampire takes 20 radiant damage "
                    "when it starts its turn in sunlight.",
                ]),
            ),
        ]
        state.world_state.scene.visible_npcs_here = ["吸血鬼"]
        state.turn_tool_results = {}
        state.turn_action_ledger = {}
        return state

    async def test_sunlight_hypersensitivity_triggers_before_enemy_action(self):
        state = self.make_state()
        with patch.object(combat, "combat_attack_roll", return_value=(_roll(), 0)):
            result = await dm.execute_tool("enemy_attack", {"enemy_name": "吸血鬼"}, state)
        self.assertIn("阳光超敏", result)
        self.assertEqual(state.world_state.npcs[0].hp, 10)
        self.assertEqual(state.world_state.npcs[0].alive, True)

    async def test_sunlight_hypersensitivity_is_quiet_at_dusk(self):
        state = self.make_state(time="黄昏", weather="晴")
        with patch.object(combat, "combat_attack_roll", return_value=(_roll(), 0)):
            result = await dm.execute_tool("enemy_attack", {"enemy_name": "吸血鬼"}, state)
        self.assertNotIn("阳光超敏", result)
        self.assertEqual(state.world_state.npcs[0].hp, 30)

    async def test_effect_applies_once_per_round(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        initiative.start(state)
        first = await apply_turn_start_effects(state, "吸血鬼", npc)
        second = await apply_turn_start_effects(state, "吸血鬼", npc)
        self.assertIn("阳光超敏", first)
        self.assertEqual(second, "")
        self.assertEqual(npc.hp, 10)

        initiative.begin_player_turn(state)
        third = await apply_turn_start_effects(state, "吸血鬼", npc)
        self.assertIn("阳光超敏", third)
        self.assertEqual(npc.hp, 0)

    async def test_regeneration_heals_with_cap(self):
        state = self.make_state(
            traits=["Regeneration: The troll regains 10 hit points at the start of its turn. "
                    "If the troll takes acid or fire damage, this trait doesn't function."],
            hp=25,
        )
        npc = state.world_state.npcs[0]
        text = await apply_turn_start_effects(state, "吸血鬼", npc)
        self.assertIn("再生", text)
        self.assertEqual(npc.hp, 30)

    async def test_regeneration_is_blocked_by_recent_fire(self):
        state = self.make_state(
            traits=["Regeneration: The troll regains 10 hit points at the start of its turn. "
                    "If the troll takes acid or fire damage, this trait doesn't function."],
            hp=15,
        )
        npc = state.world_state.npcs[0]
        record_damage_type(state, "吸血鬼", "火焰")
        text = await apply_turn_start_effects(state, "吸血鬼", npc)
        self.assertIn("抑制", text)
        self.assertEqual(npc.hp, 15, "近期火焰伤害应阻止再生")
        self.assertNotIn("吸血鬼", getattr(state, "recent_damage_types", {}),
                         "判断后要清掉近期伤害记录，避免永久抑制")

    async def test_pending_regeneration_revives_at_turn_start_without_xp(self):
        state = self.make_state(
            traits=["Regeneration: The troll regains 10 hit points at the start of its turn."],
            hp=1,
        )
        npc = state.world_state.npcs[0]
        initiative.start(state)
        await _persist_combat_damage(state, npc, 0)
        self.assertFalse(npc.alive)
        self.assertIn("吸血鬼", state.pending_regeneration)
        self.assertEqual(state.character_info.get("xp", 0), 0, "待再生期间不应先发经验")

        combat_state._refresh_combat_state(state)
        self.assertTrue(state.in_combat, "待再生敌人应保持战斗未结束")
        self.assertIsNotNone(initiative.tracker_for(state))

        text = await apply_turn_start_effects(state, "吸血鬼", npc)
        self.assertIn("重新站起", text)
        self.assertTrue(npc.alive)
        self.assertEqual(npc.hp, 10)
        self.assertNotIn("吸血鬼", state.pending_regeneration)
        self.assertEqual(state.character_info.get("xp", 0), 0)
        revived = initiative.tracker_for(state).find("吸血鬼")
        self.assertTrue(revived.alive)
        self.assertEqual(revived.turns_used, 0)

    async def test_blocked_pending_regeneration_awards_deferred_xp(self):
        state = self.make_state(
            traits=["Regeneration: The troll regains 10 hit points at the start of its turn. "
                    "If the troll takes acid or fire damage, this trait doesn't function."],
            hp=1,
        )
        npc = state.world_state.npcs[0]
        initiative.start(state)
        await _persist_combat_damage(state, npc, 0)
        record_damage_type(state, "吸血鬼", "火焰")

        text = await apply_turn_start_effects(state, "吸血鬼", npc)
        self.assertIn("无法复活", text)
        self.assertFalse(npc.alive)
        self.assertEqual(npc.hp, 0)
        self.assertNotIn("吸血鬼", state.pending_regeneration)
        self.assertTrue(npc.xp_awarded)
        self.assertGreater(state.character_info.get("xp", 0), 0, "再生失败后才补发经验")

    async def test_pending_regeneration_survives_save_dynamic_state(self):
        state = self.make_state(
            traits=["Regeneration: The troll regains 10 hit points at the start of its turn."],
            hp=1,
        )
        npc = state.world_state.npcs[0]
        initiative.start(state)
        await _persist_combat_damage(state, npc, 0)

        from backend.save_restore import restore_state_from_save
        from backend.save_serialize import _serialize_dynamic

        dyn = _serialize_dynamic(state)
        self.assertIn("吸血鬼", dyn["pending_regeneration"])
        restored, _sid = restore_state_from_save({
            "session": {"character_info": {}, "dynamic_state": dyn},
            "username": "save-check",
        })
        self.assertIn("吸血鬼", restored.pending_regeneration)

    async def test_pending_regeneration_stays_in_combat_snapshot(self):
        state = self.make_state(
            traits=["Regeneration: The troll regains 10 hit points at the start of its turn."],
            hp=1,
        )
        npc = state.world_state.npcs[0]
        initiative.start(state)
        await _persist_combat_damage(state, npc, 0)
        snapshot = combat_state._build_combat_snapshot(state, [], "吸血鬼", 0)
        self.assertEqual(snapshot[0]["hp"], 0)
        self.assertTrue(snapshot[0]["pending_regen"])


if __name__ == "__main__":
    unittest.main()
