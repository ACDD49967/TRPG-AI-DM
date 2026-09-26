"""法术位收支：施法扣位、位不足要拒绝、戏法免费、长休恢复、短休不恢复普通位。

此前只有 fixture 里出现过 spell_slots 字段，没有任何断言盯住"扣了多少、恢复多少"——
和刚修掉的 AC 问题同一类：接口返回成功，数值却可能不对。
"""
import unittest
from unittest.mock import AsyncMock, patch

from backend.engine.game_systems import get_dnd5_spell_slots
from backend.engine.character_state import _exec_update_state
from backend.engine.session import GameSessionState
from backend.engine.session_tools import _exec_rest
from backend.engine.spell_tools import _exec_cast_spell


def caster(char_class: str = "法师", level: int = 3, slots: list | None = None,
           pact: int = 0) -> GameSessionState:
    return GameSessionState(
        "slots", "char", "岚",
        {"game_system": "dnd5e", "level": level, "char_class": char_class,
         "hp": 20, "max_hp": 30, "ac": 12,
         "attributes": {"str": 10, "dex": 12, "con": 12, "int": 16, "wis": 12, "cha": 14},
         "spell_slots": {"spell_slots": slots if slots is not None else [3, 2, 0],
                         "pact_slots": pact, "pact_slot_level": 1},
         "class_resources": [{"key": "arcane_recovery", "name": "奥术回想",
                              "current": 0, "max": 1}]},
        username="slots-user",
    )


class TestSpellSlotAccounting(unittest.IsolatedAsyncioTestCase):
    async def test_casting_consumes_exactly_one_slot(self):
        state = caster(slots=[3, 2, 0])
        with patch("backend.engine.spell_tools.push_event", new=AsyncMock()) as event:
            line = await _exec_cast_spell({"name": "魔法飞弹", "level": 1}, state)
        self.assertEqual(state.character_info["spell_slots"]["spell_slots"], [2, 2, 0])
        self.assertIn("剩余 2", line)
        self.assertEqual(event.await_args.args[2]["spell_slots"]["spell_slots"], [2, 2, 0])

    async def test_casting_without_slots_is_refused_and_changes_nothing(self):
        state = caster(slots=[0, 0, 0])
        with patch("backend.engine.spell_tools.push_event", new=AsyncMock()):
            line = await _exec_cast_spell({"name": "火球术", "level": 3}, state)
        self.assertIn("不足", line)
        self.assertEqual(state.character_info["spell_slots"]["spell_slots"], [0, 0, 0])

    async def test_cantrip_costs_nothing(self):
        state = caster(slots=[3, 2, 0])
        with patch("backend.engine.spell_tools.push_event", new=AsyncMock()):
            line = await _exec_cast_spell({"name": "火焰箭", "level": 0}, state)
        self.assertIn("不消耗法术位", line)
        self.assertEqual(state.character_info["spell_slots"]["spell_slots"], [3, 2, 0])

    async def test_warlock_pact_slot_is_consumed(self):
        state = caster(char_class="邪术师", slots=[0, 0], pact=2)
        with patch("backend.engine.spell_tools.push_event", new=AsyncMock()):
            line = await _exec_cast_spell({"name": "邪术冲击", "level": 1, "pact": True}, state)
        self.assertEqual(state.character_info["spell_slots"]["pact_slots"], 1)
        self.assertIn("契约 1", line)

        with patch("backend.engine.spell_tools.push_event", new=AsyncMock()):
            await _exec_cast_spell({"name": "邪术冲击", "level": 1, "pact": True}, state)
            refused = await _exec_cast_spell({"name": "邪术冲击", "level": 1, "pact": True}, state)
        self.assertIn("不足", refused)

    async def test_long_rest_restores_all_slots(self):
        state = caster(char_class="法师", level=3, slots=[0, 0, 0])
        with patch("backend.engine.session_tools.push_event", new=AsyncMock()):
            await _exec_rest({"rest_type": "long"}, state)
        self.assertEqual(state.character_info["spell_slots"]["spell_slots"],
                         get_dnd5_spell_slots("法师", 3)["spell_slots"])

    async def test_long_rest_refills_class_resources(self):
        state = caster()
        with patch("backend.engine.session_tools.push_event", new=AsyncMock()):
            await _exec_rest({"rest_type": "long"}, state)
        recovery = state.character_info["class_resources"][0]
        self.assertEqual(recovery["current"], recovery["max"], "长休要把职业资源补满")

    async def test_short_rest_does_not_restore_normal_slots(self):
        """5e 规则：普通法术位只有长休恢复（邪术师的契约位才在短休回）。"""
        state = caster(char_class="法师", level=3, slots=[0, 0, 0])
        with patch("backend.engine.session_tools.push_event", new=AsyncMock()):
            await _exec_rest({"rest_type": "short"}, state)
        self.assertEqual(state.character_info["spell_slots"]["spell_slots"], [0, 0, 0])

    async def test_slots_are_capped_by_class_and_level(self):
        """写回是"剩余值"：3 级法师最多 4 个 1 环、2 个 2 环，写 9 也得收敛。"""
        state = caster(char_class="法师", level=3, slots=[9, 9, 9])
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state(
                {"changes": {"spell_slots": [9, 9, 9]}, "reason": "恢复"}, state)
        self.assertEqual(state.character_info["spell_slots"]["spell_slots"], [4, 2, 0],
                         "超上限的法术位要按官方表收敛")

    async def test_high_level_slots_are_zeroed_for_low_level_casters(self):
        """3 级法师不该有 4 环位：卡上多出来的等级位一律归 0。"""
        state = caster(char_class="法师", level=3, slots=[4, 2, 0, 1, 1])
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state(
                {"changes": {"spell_slots": [4, 2, 0, 1, 1]}, "reason": "导入角色卡"}, state)
        self.assertEqual(state.character_info["spell_slots"]["spell_slots"],
                         [4, 2, 0, 0, 0])

    async def test_warlock_pact_slots_are_capped_too(self):
        state = caster(char_class="邪术师", level=3, slots=[], pact=99)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state(
                {"changes": {"spell_slots": {"pact_slots": 99}}, "reason": "恢复"}, state)
        pact = state.character_info["spell_slots"]["pact_slots"]
        self.assertEqual(pact, get_dnd5_spell_slots("邪术师", 3)["pact_slots"])

    async def test_non_caster_slots_are_left_alone(self):
        """战士不在法术位表里：不封顶也不清空，避免误伤自定义/多职业卡。"""
        state = caster(char_class="战士", level=3, slots=[3, 0, 0])
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state(
                {"changes": {"spell_slots": [3, 0, 0]}, "reason": "无关字段"}, state)
        self.assertEqual(state.character_info["spell_slots"]["spell_slots"], [3, 0, 0])


if __name__ == "__main__":
    unittest.main()
