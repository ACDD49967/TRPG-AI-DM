"""装备 AC：首次装上护甲/盾牌时，加值不能被"基准 AC 取在变更之后"吞掉。

实测发现：5e 战士 AC 16、背包里一把未装备的盾牌，装上后 AC 仍是 16（应为 18）。
原因是 `base_ac` 只在 `_recalc_equipment_effects` 里首次计算，而那一刻装备**已经**换好了，
于是 `base_ac = 当前AC - 新加成`，把这次的加成抹平。卸下方向反而是对的（-2），两头不对称。
"""
import unittest

from backend.engine.character_state import _exec_update_state
from backend.engine.session import GameSessionState


def fighter(ac: int = 16, items: list | None = None) -> GameSessionState:
    return GameSessionState(
        "equip-ac", "char", "岚",
        {"game_system": "dnd5e", "level": 1, "hp": 12, "max_hp": 12, "ac": ac,
         "attributes": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10},
         "inventory": {"items": items or [
             {"name": "盾牌", "equipped": False, "type": "armor"},
             {"name": "鳞甲", "equipped": False, "type": "armor"},
         ]}},
        username="equip-user",
    )


class TestEquipmentAc(unittest.IsolatedAsyncioTestCase):
    async def test_equipping_shield_raises_ac(self):
        state = fighter()
        await _exec_update_state({"changes": {"inventory_equip": "盾牌"}}, state)
        self.assertEqual(state.character_info.get("base_ac"), 16,
                         "基准 AC 应记成没穿盾牌时的 16")
        self.assertEqual(state.character_info["ac"], 18, "装盾牌应该 +2")

    async def test_unequip_takes_the_bonus_back(self):
        state = fighter()
        await _exec_update_state({"changes": {"inventory_equip": "盾牌"}}, state)
        await _exec_update_state({"changes": {"inventory_unequip": "盾牌"}}, state)
        self.assertEqual(state.character_info["ac"], 16, "卸下后应回到 16")

    async def test_two_armor_pieces_stack_and_unstack_stably(self):
        state = fighter()
        await _exec_update_state({"changes": {"inventory_equip": "盾牌"}}, state)
        await _exec_update_state({"changes": {"inventory_equip": "鳞甲"}}, state)
        self.assertEqual(state.character_info["ac"], 22, "盾牌+2 与鳞甲+4 都要算上")
        await _exec_update_state({"changes": {"inventory_unequip": "鳞甲"}}, state)
        self.assertEqual(state.character_info["ac"], 18)
        await _exec_update_state({"changes": {"inventory_unequip": "盾牌"}}, state)
        self.assertEqual(state.character_info["ac"], 16)

    async def test_non_armor_system_is_untouched(self):
        """COC 没有 D&D 的护甲 AC 概念，换装不该改 AC。"""
        state = fighter(ac=12)
        state.character_info["game_system"] = "coc"
        await _exec_update_state({"changes": {"inventory_equip": "盾牌"}}, state)
        self.assertEqual(state.character_info["ac"], 12)


if __name__ == "__main__":
    unittest.main()
