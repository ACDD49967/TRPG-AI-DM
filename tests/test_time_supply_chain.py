"""时间/补给到机械后果的整链：跨天扣口粮 → 缺补给累积力竭 → 检定/豁免劣势
→ 长休（有食物）减 1 级 → 夜间赶路消耗火把。

分段规则已有测试（`test_time_rules`），但"补给 → 力竭 → 掷骰后果"这条链
此前没有人连着走一遍，最容易出现的漏就是中间某一环没接上。
"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import dice_tools
from backend.engine import dm_agent as dm
from backend.engine import time_rules
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState

_TEMP_DIRS: list = []


def make_state(*, rations: int = 2, water: int = 2, torches: int = 4,
               exhaustion: int = 0) -> GameSessionState:
    tmp = tempfile.TemporaryDirectory()
    _TEMP_DIRS.append(tmp)
    items = []
    if rations:
        items.append({"name": "口粮", "quantity": rations})
    if water:
        items.append({"name": "水袋", "quantity": water})
    if torches:
        items.append({"name": "火把", "quantity": torches})
    state = GameSessionState(
        "supply-chain", "char", "岚",
        {"hp": 20, "max_hp": 30, "ac": 15, "level": 3, "game_system": "dnd5e",
         "char_class": "战士", "exhaustion": exhaustion,
         "attributes": {"str": 16, "dex": 14, "con": 14},
         "inventory": {"items": items}},
    )
    state.world_state = WorldState(session_id="supply-chain", _storage_dir=tmp.name)
    state.world_state.scene.current_location = "商道"
    state.world_state.scene.visible_npcs_here = ["地精"]
    state.world_state.npcs = [NpcEntry(name="地精", attitude="敌对", hp=20, max_hp=20,
                                       ac=13, alive=True, location="商道")]
    return state


def item_qty(state: GameSessionState, name: str) -> int:
    return time_rules._item_qty_left(state, name)


class TestTimeSupplyChain(unittest.IsolatedAsyncioTestCase):
    async def test_one_day_with_supplies_costs_one_ration_and_water(self):
        state = make_state(rations=2, water=2)
        out = await dm.execute_tool(
            "advance_time", {"hours": 24, "reason": "沿商道赶路"}, state)
        self.assertEqual(item_qty(state, "口粮"), 1)
        self.assertEqual(item_qty(state, "水袋"), 1)
        self.assertEqual(time_rules.exhaustion_level(state), 0, "有补给不该力竭")
        self.assertIn("消耗 1 份口粮", out)

    async def test_missing_supplies_then_check_disadvantage(self):
        state = make_state(rations=0, water=0)
        out = await dm.execute_tool("advance_time", {"hours": 24, "reason": "断粮赶路"}, state)
        self.assertEqual(time_rules.exhaustion_level(state), 1)
        self.assertIn("力竭", out)
        # 力竭 1 级 → 检定劣势（后端强制，不靠 AI）
        with patch.object(dice_tools.random, "randint", side_effect=[2, 19]):
            roll_out = await dm.execute_tool(
                "dice_roll", {"skill_name": "求生", "dc": 12, "reason": "找食物"}, state)
        event = [d for _, t, d in state.event_history if t == "dice_roll"][-1]
        self.assertEqual(event["advantage"], "disadvantage")
        self.assertIn("力竭1级", event["advantage_note"])
        self.assertEqual(event["roll"], 2, "劣势取低值")
        self.assertIn("力竭", roll_out)

    async def test_three_days_without_food_blocks_saves(self):
        state = make_state(rations=0, water=0)
        for _ in range(3):
            await dm.execute_tool("advance_time", {"hours": 24, "reason": "继续赶路"}, state)
        self.assertEqual(time_rules.exhaustion_level(state), 3)
        with patch("backend.engine.combat_save_damage.random.randint", side_effect=[18, 5]):
            await dm.execute_tool(
                "save_damage",
                {"targets": ["岚"], "dc": 15, "damage": 8, "damage_type": "火焰",
                 "ability": "dex", "reason": "滚落的火盆"}, state)
        event = [d for _, t, d in state.event_history if t == "dice_roll"][-1]
        self.assertEqual(event["advantage"], "disadvantage")
        self.assertEqual(event["roll"], 5, "力竭 3 级豁免取低值")

    async def test_long_rest_with_food_reduces_exhaustion(self):
        state = make_state(rations=1, water=1, exhaustion=3)
        out = await dm.execute_tool(
            "take_rest", {"rest_type": "long", "reason": "在村口长休"}, state)
        self.assertEqual(time_rules.exhaustion_level(state), 2, "有食物的长休减 1 级力竭")
        self.assertEqual(state.character_info["hp"], 30, "长休应该回满血")
        self.assertIn("力竭", out)

    async def test_night_travel_consumes_torches_per_hour(self):
        state = make_state(torches=4)
        out = await dm.execute_tool(
            "advance_time",
            {"hours": 3, "reason": "夜间赶路", "light_source": "火把"}, state)
        self.assertEqual(item_qty(state, "火把"), 1, "1 支/小时，3 小时吃掉 3 支")
        self.assertIn("照明", out)

    async def test_night_travel_without_light_warns(self):
        state = make_state(torches=0)
        out = await dm.execute_tool(
            "advance_time",
            {"hours": 2, "reason": "摸黑前进", "light_source": "火把"}, state)
        self.assertIn("没有可用的照明", out)


if __name__ == "__main__":
    unittest.main()
