"""强力攻击（-5 命中 / +10 伤害）：只有对应特长才允许声明。

`combat.py` 里原本只算了 `has_gwm` 打一行提示，-5/+10 从来没有真正参与结算；
这条测试盯住"有没有特长"、"近战还是远程"、"拒绝时不能结算"三件事。
"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import combat, dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


def _roll(total: int = 18):
    return SimpleNamespace(roll=15, total=total, result=SimpleNamespace(value="成功"))


class TestPowerAttack(unittest.IsolatedAsyncioTestCase):
    def make_state(self, feats: list[dict] | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "power", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 5, "xp": 0,
             "game_system": "dnd5e", "char_class": "战士",
             "attributes": {"str": 18, "dex": 14, "con": 14},
             "feats": list(feats or []),
             "inventory": {"items": [{"name": "巨剑", "type": "weapon", "equipped": True}]}},
        )
        state.world_state = WorldState(session_id="power", _storage_dir=tmp.name)
        state.world_state.npcs = [
            NpcEntry(name="石魔像", attitude="敌对", hp=80, max_hp=80, ac=17, level=5, alive=True)]
        return state

    def _patched_roll(self, damage: int = 9):
        """记录传进来的攻击修正，返回固定骰面与伤害。"""
        seen: list[int] = []

        def fake(attacker, ac, mod, dice):
            seen.append(mod)
            return _roll(), damage

        return patch.object(combat, "combat_attack_roll", side_effect=fake), seen

    async def test_without_the_feat_it_is_refused(self):
        state = self.make_state()
        patcher, seen = self._patched_roll()
        with patcher:
            result = await dm.execute_tool(
                "combat_round",
                {"enemy_name": "石魔像", "player_action": "挥剑", "power_attack": True}, state)
        self.assertIn("没有对应特长", result)
        self.assertEqual(seen, [], "被拒绝时不应掷骰")
        self.assertEqual(state.world_state.npcs[0].hp, 80, "被拒绝时不应结算伤害")

    async def test_great_weapon_master_gets_minus_five_plus_ten(self):
        state = self.make_state([{"id": "great_weapon_master", "name": "巨武器大师"}])
        patcher, seen = self._patched_roll(damage=9)
        with patcher:
            result = await dm.execute_tool(
                "combat_round",
                {"enemy_name": "石魔像", "player_action": "挥剑猛砍",
                 "power_attack": True, "enemy_can_act": False}, state)
        self.assertEqual(state.world_state.npcs[0].hp, 80 - 19, "9 点伤害 +10 = 19")
        self.assertIn("强力攻击（巨武器大师）", result)
        base_mod = seen[0]

        # 同样条件下不声明强力攻击：修正应高出 5，伤害不加 10
        state2 = self.make_state([{"id": "great_weapon_master", "name": "巨武器大师"}])
        patcher2, seen2 = self._patched_roll(damage=9)
        with patcher2:
            await dm.execute_tool(
                "combat_round",
                {"enemy_name": "石魔像", "player_action": "挥剑猛砍", "enemy_can_act": False}, state2)
        self.assertEqual(seen2[0] - base_mod, 5, "强力攻击的命中修正应为 -5")
        self.assertEqual(state2.world_state.npcs[0].hp, 80 - 9)

    async def test_sharpshooter_is_required_for_ranged_attacks(self):
        # 只有巨武器大师 + 远程动作 → 拒绝
        state = self.make_state([{"id": "great_weapon_master", "name": "巨武器大师"}])
        patcher, seen = self._patched_roll()
        with patcher:
            refused = await dm.execute_tool(
                "combat_round",
                {"enemy_name": "石魔像", "player_action": "用长弓射击", "power_attack": True}, state)
        self.assertIn("没有对应特长", refused)
        self.assertEqual(seen, [])

        # 有神射手 → 远程可用
        state = self.make_state([{"id": "sharpshooter", "name": "神射手"}])
        patcher, seen = self._patched_roll(damage=9)
        with patcher:
            result = await dm.execute_tool(
                "combat_round",
                {"enemy_name": "石魔像", "player_action": "用长弓射击",
                 "power_attack": True, "enemy_can_act": False}, state)
        self.assertIn("强力攻击（神射手）", result)
        self.assertEqual(state.world_state.npcs[0].hp, 80 - 19)

    async def test_hint_lists_available_power_feats(self):
        state = self.make_state([{"id": "great_weapon_master", "name": "巨武器大师"}])
        patcher, _ = self._patched_roll()
        with patcher:
            result = await dm.execute_tool(
                "combat_round",
                {"enemy_name": "石魔像", "player_action": "挥剑", "enemy_can_act": False}, state)
        self.assertIn("power_attack=true", result, "结算行要提示 DM 可以声明强力攻击")

    async def test_non_5e_systems_never_allow_it(self):
        state = self.make_state([{"id": "great_weapon_master", "name": "巨武器大师"}])
        state.character_info["game_system"] = "custom"
        patcher, seen = self._patched_roll()
        with patcher:
            result = await dm.execute_tool(
                "combat_round",
                {"enemy_name": "石魔像", "player_action": "挥剑", "power_attack": True}, state)
        self.assertIn("没有对应特长", result)
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
