"""5e 仪式施法：不消耗法术位、额外 10 分钟，且必须有仪式施法能力与仪式版本。

此前 `cast_spell` 只有"扣法术位"一条路径——法术数据带 ritual 标记、专长里也有
「仪式施法者」，但代码里没有任何仪式结算，DM 只能自己编。
"""
import unittest
from unittest.mock import AsyncMock, patch

from backend.engine import spell_tools
from backend.engine.session import GameSessionState
from backend.engine.spell_tools import _exec_cast_spell


def caster(char_class: str = "法师", feats: list | None = None) -> GameSessionState:
    return GameSessionState(
        "ritual", "char", "岚",
        {"game_system": "dnd5e", "level": 3, "char_class": char_class,
         "hp": 20, "max_hp": 30, "ac": 12,
         "attributes": {"str": 10, "dex": 12, "con": 12, "int": 16, "wis": 12, "cha": 14},
         "feats": list(feats or []),
         "spell_slots": {"spell_slots": [3, 2, 0], "pact_slots": 0}},
        username="ritual-user",
    )


RITUAL_SPELL = {"name": "鉴定术", "level": "1", "school": "预言", "ritual": True,
                "description": "识别物品的魔法属性"}
PLAIN_SPELL = {"name": "魔法飞弹", "level": "1", "school": "塑能", "ritual": False,
               "description": "自动命中的力场飞弹"}


class TestRitualCasting(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for target in ("backend.engine.spell_tools.push_event",
                       "backend.engine.character_state.push_event"):
            patcher = patch(target, new=AsyncMock())
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_wizard_casts_ritual_without_spending_a_slot(self):
        state = caster("法师")
        with patch.object(spell_tools, "_search_spell_for_entity", return_value=RITUAL_SPELL), \
             patch.object(spell_tools, "_apply_time_stop", new=AsyncMock(return_value="")):
            line = await _exec_cast_spell({"name": "鉴定术", "level": 1, "ritual": True}, state)
        self.assertEqual(state.character_info["spell_slots"]["spell_slots"], [3, 2, 0],
                         "仪式施法不能扣法术位")
        self.assertIn("仪式", line)
        self.assertIn("10 分钟", line)
        self.assertGreaterEqual(int(getattr(state, "clock_minutes", 0) or 0), 10,
                                "仪式施法要推进 10 分钟游戏内时间")

    async def test_feat_grants_ritual_casting_to_other_classes(self):
        state = caster("战士", feats=[{"id": "ritual_caster", "name": "仪式施法者"}])
        with patch.object(spell_tools, "_search_spell_for_entity", return_value=RITUAL_SPELL), \
             patch.object(spell_tools, "_apply_time_stop", new=AsyncMock(return_value="")):
            line = await _exec_cast_spell({"name": "鉴定术", "level": 1, "ritual": True}, state)
        self.assertIn("仪式", line)
        self.assertEqual(state.character_info["spell_slots"]["spell_slots"], [3, 2, 0])

    async def test_without_the_ability_it_is_refused(self):
        state = caster("战士")
        with patch.object(spell_tools, "_search_spell_for_entity", return_value=RITUAL_SPELL):
            line = await _exec_cast_spell({"name": "鉴定术", "level": 1, "ritual": True}, state)
        self.assertIn("没有仪式施法能力", line)
        self.assertEqual(state.character_info["spell_slots"]["spell_slots"], [3, 2, 0])

    async def test_non_ritual_spell_cannot_be_cast_as_ritual(self):
        state = caster("法师")
        with patch.object(spell_tools, "_search_spell_for_entity", return_value=PLAIN_SPELL):
            line = await _exec_cast_spell({"name": "魔法飞弹", "level": 1, "ritual": True}, state)
        self.assertIn("没有仪式版本", line)
        self.assertEqual(state.character_info["spell_slots"]["spell_slots"], [3, 2, 0])

    async def test_normal_cast_still_spends_a_slot(self):
        state = caster("法师")
        with patch.object(spell_tools, "_search_spell_for_entity", return_value=RITUAL_SPELL), \
             patch.object(spell_tools, "_apply_time_stop", new=AsyncMock(return_value="")):
            line = await _exec_cast_spell({"name": "鉴定术", "level": 1}, state)
        self.assertIn("已消耗法术位", line)
        self.assertEqual(state.character_info["spell_slots"]["spell_slots"], [2, 2, 0])


if __name__ == "__main__":
    unittest.main()
