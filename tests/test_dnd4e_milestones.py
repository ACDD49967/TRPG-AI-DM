"""4e 里程碑：每两次遭遇 +1 行动点，延长休息后重新计数。

行动点此前只有"花"的路径（action_economy.spend_action_point 会扣点、点不足会拒绝），
却没有"得"的路径：提示词写着"每达成里程碑 +1"，代码里只能靠 DM 手写 update_state。
"""
import unittest
from unittest.mock import AsyncMock, patch

from backend.engine.milestones import (
    ACTION_POINT_CAP, COUNTER_KEY, encounter_count, record_encounter_end,
)
from backend.engine.rest_tools import _exec_rest
from backend.engine.session import GameSessionState


def adventurer(action_points: int = 1, system: str = "dnd4e") -> GameSessionState:
    return GameSessionState(
        "mile", "char", "岚",
        {"game_system": system, "char_class": "战士", "level": 3,
         "hp": 20, "max_hp": 40, "healing_surges": 5, "max_healing_surges": 9,
         "surge_value": 10, "action_points": action_points,
         "attributes": {"str": 16, "con": 14, "dex": 12, "int": 10,
                        "wis": 10, "cha": 10}},
        username="mile-user",
    )


def hints(state: GameSessionState) -> list[str]:
    return [h for h in (state.pending_system_hints or []) if h.startswith("[系统强制-里程碑")]


class TestDnd4eMilestones(unittest.IsolatedAsyncioTestCase):
    async def test_first_encounter_only_counts(self):
        state = adventurer()
        state.in_combat = False
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            gained = await record_encounter_end(state, was_in_combat=True)
        self.assertEqual(gained, 0)
        self.assertEqual(encounter_count(state), 1)
        self.assertEqual(state.character_info["action_points"], 1, "一次遭遇还没到里程碑")
        self.assertFalse(hints(state))

    async def test_second_encounter_is_a_milestone(self):
        state = adventurer()
        state.in_combat = False
        state.character_info[COUNTER_KEY] = 1
        with patch("backend.engine.character_state.push_event", new=AsyncMock()) as event:
            gained = await record_encounter_end(state, was_in_combat=True)
        self.assertEqual(gained, 1)
        self.assertEqual(state.character_info["action_points"], 2)
        self.assertTrue(hints(state), "里程碑要给主 DM 一条提示")
        self.assertIn("action_source=action_point", hints(state)[0])
        events = [d for _, t, d in state.event_history if t == "game_event"]
        self.assertEqual(events[-1]["type"], "milestone")
        self.assertEqual(events[-1]["extra"], {"encounters": 2, "action_points": 2, "gained": 1})
        self.assertTrue(event.await_count >= 1)

    async def test_ongoing_combat_does_not_count(self):
        state = adventurer()
        state.in_combat = True
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            gained = await record_encounter_end(state, was_in_combat=True)
        self.assertEqual(gained, 0)
        self.assertEqual(encounter_count(state), 0, "还在打就不算遭遇结束")

    async def test_non_4e_systems_are_ignored(self):
        state = adventurer(system="dnd5e")
        state.in_combat = False
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            gained = await record_encounter_end(state, was_in_combat=True)
        self.assertEqual(gained, 0)
        self.assertEqual(encounter_count(state), 0)
        self.assertFalse(hints(state))

    async def test_action_points_stop_at_the_cap(self):
        state = adventurer(action_points=ACTION_POINT_CAP)
        state.in_combat = False
        state.character_info[COUNTER_KEY] = 1
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            gained = await record_encounter_end(state, was_in_combat=True)
        self.assertEqual(gained, 0)
        self.assertEqual(state.character_info["action_points"], ACTION_POINT_CAP)
        self.assertIn("上限", hints(state)[0])

    async def test_extended_rest_resets_the_counter(self):
        state = adventurer(action_points=2)
        state.character_info[COUNTER_KEY] = 3
        with patch("backend.engine.character_state.push_event", new=AsyncMock()), \
             patch("backend.engine.time_rules.finish_long_rest", new=AsyncMock(return_value="")), \
             patch("backend.engine.time_rules.advance", new=AsyncMock(return_value={"summary": ""})):
            await _exec_rest({"rest_type": "long"}, state)
        self.assertEqual(encounter_count(state), 0, "延长休息后里程碑重新计数")
        self.assertEqual(state.character_info["action_points"], 1, "延长休息后回到 1 点")


class TestMilestonesEndToEnd(unittest.IsolatedAsyncioTestCase):
    """整条链：把敌人打到 0 HP → 战斗收场 → 遭遇计数 → 第二次成里程碑。"""

    def make_state(self):
        import tempfile

        from backend.engine.world_state import NpcEntry, WorldState

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = adventurer()
        state.world_state = WorldState(session_id="mile", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "洞窟"
        self.npc_cls = NpcEntry
        return state

    def hostile(self, name: str):
        return self.npc_cls(name=name, attitude="敌对", location="洞窟",
                            hp=5, max_hp=5, ac=12, level=1, alive=True)

    async def test_two_encounters_produce_a_milestone(self):
        from backend.engine import dm_agent as dm
        from backend.engine.combat_state import _refresh_combat_state

        state = self.make_state()
        with patch("backend.engine.character_state.push_event", new=AsyncMock()), \
             patch("backend.engine.combat_rewards.push_event", new=AsyncMock()):
            for wave in range(2):
                npc = self.hostile(f"地精{wave}")
                state.world_state.npcs = [npc]
                _refresh_combat_state(state)
                self.assertTrue(state.in_combat, "有存活敌人时应处于战斗中")
                await dm._persist_combat_damage(state, npc, 0)
                self.assertFalse(state.in_combat, "敌人被清空后战斗应结束")

        self.assertEqual(encounter_count(state), 2, "两次收场算两次遭遇")
        self.assertEqual(state.character_info["action_points"], 2, "第二次遭遇达成里程碑 +1")
        events = [d for _, t, d in state.event_history if t == "game_event"]
        self.assertTrue(any(e.get("type") == "milestone" for e in events))


if __name__ == "__main__":
    unittest.main()
