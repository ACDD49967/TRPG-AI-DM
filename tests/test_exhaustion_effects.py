"""力竭的机械后果：检定劣势（1 级起）、豁免劣势（3 级起）、与优势互相抵消。

这几条规则此前只写在提示词里（"1 级检定劣势 / 3 级攻防劣势"），实际由 AI 自觉执行；
现在由后端在 `dice_roll` / `save_damage` 里直接套用。
"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import dice_tools
from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState

_TEMP_DIRS: list = []   # 持有引用，避免测试结束时 TemporaryDirectory 被 GC 报 ResourceWarning


def make_state(exhaustion: int = 0, system: str = "dnd5e") -> GameSessionState:
    tmp = tempfile.TemporaryDirectory()
    _TEMP_DIRS.append(tmp)
    state = GameSessionState(
        "exhaust", "char", "岚",
        {"hp": 30, "max_hp": 30, "ac": 15, "level": 3, "game_system": system,
         "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14},
         "exhaustion": exhaustion},
    )
    state.world_state = WorldState(session_id="exhaust", _storage_dir=tmp.name)
    state.world_state.scene.current_location = "商道"
    state.world_state.scene.visible_npcs_here = ["地精"]
    state.world_state.npcs = [NpcEntry(name="地精", attitude="敌对", hp=20, max_hp=20,
                                       ac=13, alive=True, location="商道")]
    return state


def last_roll(state, kind: str = "dice_roll") -> dict:
    rolls = [d for _, t, d in state.event_history if t == kind]
    assert rolls, f"没有 {kind} 事件"
    return rolls[-1]


class TestExhaustionOnChecks(unittest.IsolatedAsyncioTestCase):
    async def test_exhaustion_one_forces_check_disadvantage(self):
        state = make_state(exhaustion=1)
        with patch.object(dice_tools.random, "randint", side_effect=[3, 18]):
            out = await dm.execute_tool(
                "dice_roll", {"skill_name": "察觉", "dc": 12, "reason": "找痕迹"}, state)
        event = last_roll(state)
        self.assertEqual(event["advantage"], "disadvantage")
        self.assertIn("力竭", event["advantage_note"])
        self.assertEqual(event["roll"], 3, "劣势取两次中的较低值")
        self.assertIn("力竭", out)

    async def test_exhaustion_zero_keeps_normal_roll(self):
        state = make_state(exhaustion=0)
        with patch.object(dice_tools.random, "randint", side_effect=[3]):
            await dm.execute_tool("dice_roll", {"skill_name": "察觉", "dc": 12}, state)
        event = last_roll(state)
        self.assertNotIn("advantage", event)
        self.assertEqual(event["roll"], 3)

    async def test_declared_advantage_cancels_exhaustion(self):
        state = make_state(exhaustion=2)
        with patch.object(dice_tools.random, "randint", side_effect=[3]):
            await dm.execute_tool(
                "dice_roll",
                {"skill_name": "察觉", "dc": 12, "advantage": "advantage",
                 "advantage_reason": "高处视野好"}, state)
        event = last_roll(state)
        self.assertIn("抵消", event.get("advantage_note", ""))
        self.assertEqual(event["roll"], 3, "优势与劣势抵消后只掷一次")

    async def test_coc_is_not_affected(self):
        state = make_state(exhaustion=3, system="coc")
        with patch.object(dice_tools.random, "randint", side_effect=[20]):
            await dm.execute_tool("dice_roll", {"skill_name": "侦查", "dc": 50}, state)
        event = last_roll(state)
        self.assertNotIn("力竭", str(event.get("advantage_note", "")))


class TestExhaustionOnSaves(unittest.IsolatedAsyncioTestCase):
    async def test_exhaustion_three_forces_save_disadvantage(self):
        state = make_state(exhaustion=3)
        with patch("backend.engine.combat_save_damage.random.randint", side_effect=[18, 4]):
            await dm.execute_tool(
                "save_damage",
                {"targets": ["岚"], "dc": 15, "damage": 10, "damage_type": "火焰",
                 "ability": "dex", "reason": "火球术"}, state)
        event = last_roll(state)
        self.assertEqual(event["advantage"], "disadvantage")
        self.assertIn("力竭", event["advantage_note"])
        self.assertEqual(event["roll"], 4, "劣势取较低值")

    async def test_exhaustion_below_three_rolls_once(self):
        state = make_state(exhaustion=2)
        with patch("backend.engine.combat_save_damage.random.randint", side_effect=[4]) as rnd:
            await dm.execute_tool(
                "save_damage",
                {"targets": ["岚"], "dc": 15, "damage": 10, "damage_type": "火焰",
                 "ability": "dex", "reason": "火球术"}, state)
        self.assertEqual(rnd.call_count, 1, "力竭 2 级不该多掷一次")
        self.assertNotIn("advantage", last_roll(state))

    async def test_exhaustion_cancels_magic_resistance(self):
        """力竭 3 级（劣势）与魔法抗性（优势）同时存在时应抵消，只掷一次。"""
        state = make_state(exhaustion=3)
        state.character_info["race_traits"] = ["魔法抗性"]
        with patch("backend.engine.combat_save_damage.random.randint", side_effect=[7]) as rnd:
            await dm.execute_tool(
                "save_damage",
                {"targets": ["岚"], "dc": 15, "damage": 10, "damage_type": "火焰",
                 "ability": "dex", "magic": True, "reason": "火球术"}, state)
        self.assertEqual(rnd.call_count, 1, "优势与劣势抵消后只掷一次")
        event = last_roll(state)
        self.assertIn("抵消", event["advantage_note"])


if __name__ == "__main__":
    unittest.main()
