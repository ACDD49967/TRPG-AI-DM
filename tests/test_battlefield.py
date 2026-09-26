"""战场态势：掩体加 AC/敏捷豁免、近战够不到要先接近、脱离缠斗引发借机攻击。"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import battlefield as bf
from backend.engine import combat
from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


def _roll(value: str = "成功", total: int = 18):
    return SimpleNamespace(roll=15, total=total, result=SimpleNamespace(value=value))


class TestBattlefieldRules(unittest.TestCase):
    def test_band_and_cover_normalisation(self):
        self.assertEqual(bf.normalize_band("缠斗"), "engaged")
        self.assertEqual(bf.normalize_band("远距离"), "far")
        self.assertEqual(bf.normalize_band("fled"), "out")
        self.assertEqual(bf.normalize_band(""), "")
        self.assertEqual(bf.normalize_cover("半掩体"), "half")
        self.assertEqual(bf.normalize_cover("¾"), "three_quarters")
        self.assertEqual(bf.normalize_cover("全掩体"), "full")

    def test_cover_bonuses_follow_5e(self):
        self.assertEqual(bf.cover_ac_bonus("none"), 0)
        self.assertEqual(bf.cover_ac_bonus("half"), 2)
        self.assertEqual(bf.cover_ac_bonus("three_quarters"), 5)
        self.assertEqual(bf.cover_dex_bonus("half"), 2)
        self.assertEqual(bf.cover_dex_bonus("three_quarters"), 5)

    def test_melee_reach_and_full_cover(self):
        self.assertTrue(bf.melee_reachable("engaged"))
        self.assertTrue(bf.melee_reachable("near"))
        self.assertFalse(bf.melee_reachable("far"))
        self.assertFalse(bf.melee_reachable("out"))
        self.assertTrue(bf.melee_reachable(""), "未登记档位时不拦")
        self.assertFalse(bf.can_be_targeted("full"))
        self.assertTrue(bf.can_be_targeted("three_quarters"))

    def test_disengage_provokes_opportunity_attack(self):
        self.assertTrue(bf.provokes_opportunity("engaged", "near"))
        self.assertTrue(bf.provokes_opportunity("engaged", "out"))
        self.assertFalse(bf.provokes_opportunity("near", "far"), "本来就不在缠斗，不算脱离")
        self.assertFalse(bf.provokes_opportunity("engaged", "engaged"))


class TestBattlefieldState(unittest.TestCase):
    def make_state(self) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "bf", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14}},
        )
        state.world_state = WorldState(session_id="bf", _storage_dir=tmp.name)
        return state

    def test_set_and_read_placement(self):
        state = self.make_state()
        place, warning = bf.set_placement(state, "你", "engaged", "half", "躲在货车后")
        self.assertEqual(place.band, "engaged")
        self.assertEqual(bf.band_of(state, "岚"), "engaged", "玩家别名应归一到角色名")
        self.assertEqual(bf.cover_ac_bonus(bf.cover_of(state, "岚")), 2)
        self.assertEqual(warning, "", "进入缠斗不触发借机攻击")
        self.assertIn("岚", bf.summary(state))

    def test_disengage_warns_and_queues_hint(self):
        state = self.make_state()
        bf.set_placement(state, "岚", "engaged", "none")
        _, warning = bf.set_placement(state, "岚", "far", "")
        self.assertIn("借机攻击", warning)
        bf.replace_hint(state, bf.BAND_HINT + " " + warning)
        self.assertTrue(any(str(h).startswith(bf.BAND_HINT) for h in state.pending_system_hints))

    def test_serialisation_round_trip(self):
        state = self.make_state()
        bf.set_placement(state, "岚", "near", "three_quarters")
        bf.set_placement(state, "地精", "engaged", "half")
        data = bf.field_for(state).to_dict()
        restored = bf.Battlefield.from_dict(data)
        self.assertEqual(restored.get(state, "岚").band, "near")
        self.assertEqual(restored.get(state, "地精").cover, "half")

    def test_save_manager_persists_battlefield(self):
        from backend.save_manager import _serialize_dynamic
        state = self.make_state()
        bf.set_placement(state, "岚", "far", "half")
        dyn = _serialize_dynamic(state)
        self.assertIsNotNone(dyn["battlefield"])
        restored = bf.Battlefield.from_dict(dyn["battlefield"])
        self.assertEqual(restored.get(state, "岚").band, "far")

    def test_clear_empties_state(self):
        state = self.make_state()
        bf.set_placement(state, "岚", "engaged", "half")
        bf.clear(state)
        self.assertEqual(bf.summary(state), "战场态势：尚未记录（默认双方可近战、无掩体）。")


class TestBattlefieldInCombat(unittest.IsolatedAsyncioTestCase):
    def make_state(self, traits: list[str] | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "bfc", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14},
             "inventory": {"items": [{"name": "长剑", "equipped": True}]}},
        )
        state.world_state = WorldState(session_id="bfc", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "碎石坡"
        state.world_state.scene.visible_npcs_here = ["地精弓手"]
        state.world_state.npcs = [NpcEntry(
            name="地精弓手", attitude="敌对", hp=20, max_hp=20, ac=13, level=1, alive=True,
            location="碎石坡", attributes={"str": 10, "dex": 14}, traits=traits or [])]
        state.turn_tool_results = {}
        state.turn_action_ledger = {}
        return state

    def _patch_dice(self, player_damage: int = 3, enemy_damage: int = 4):
        def fake(attacker, ac, mod, dice):
            return _roll(), (player_damage if attacker == "你" else enemy_damage)
        return patch.object(combat, "combat_attack_roll", side_effect=fake)

    async def test_half_cover_raises_target_ac(self):
        state = self.make_state()
        bf.set_placement(state, "地精弓手", "near", "half")
        with patch.object(combat, "combat_attack_roll",
                          side_effect=lambda a, ac, m, d: (_roll(), 3)) as dice:
            line = await dm.execute_tool(
                "combat_round", {"enemy_name": "地精弓手", "player_action": "挥长剑劈砍",
                                 "enemy_can_act": False}, state)
        self.assertEqual(dice.call_args_list[0].args[1], 15, "AC13 + 半掩体2 = 15")
        self.assertIn("目标掩体 AC+2", line)

    async def test_sharpshooter_feat_ignores_cover(self):
        state = self.make_state()
        state.character_info["feats"] = [{"id": "sharpshooter", "name": "神射手",
                                          "description": "远程攻击无视半掩体和四分之三掩体"}]
        bf.set_placement(state, "地精弓手", "near", "three_quarters")
        with patch.object(combat, "combat_attack_roll",
                          side_effect=lambda a, ac, m, d: (_roll(), 3)) as dice:
            await dm.execute_tool(
                "combat_round", {"enemy_name": "地精弓手", "player_action": "我举弓射击它",
                                 "enemy_can_act": False}, state)
        self.assertEqual(dice.call_args_list[0].args[1], 13, "神射手无视掩体")

    async def test_far_target_requires_closing_distance(self):
        state = self.make_state()
        bf.set_placement(state, "地精弓手", "far", "none")
        with self._patch_dice():
            blocked = await dm.execute_tool(
                "combat_round", {"enemy_name": "地精弓手", "player_action": "挥长剑砍它"}, state)
            allowed = await dm.execute_tool(
                "combat_round", {"enemy_name": "地精弓手", "player_action": "冲上去挥剑",
                                 "close_distance": True}, state)
        self.assertIn("近战够不到", blocked)
        self.assertIn("战斗结算", allowed)
        self.assertEqual(bf.band_of(state, "岚"), "engaged", "接近后应更新玩家档位")

    async def test_full_cover_blocks_attack(self):
        state = self.make_state()
        bf.set_placement(state, "地精弓手", "near", "full")
        blocked = await dm.execute_tool(
            "combat_round", {"enemy_name": "地精弓手", "player_action": "挥长剑劈砍"}, state)
        self.assertIn("全掩体", blocked)
        self.assertEqual(state.world_state.npcs[0].hp, 20)

    async def test_player_cover_raises_ac_against_enemy_attack(self):
        state = self.make_state()
        bf.set_placement(state, "岚", "near", "three_quarters")
        with patch.object(combat, "combat_attack_roll",
                          side_effect=lambda a, ac, m, d: (_roll(), 0)) as dice:
            await dm.execute_tool("enemy_attack", {"enemy_name": "地精弓手"}, state)
        self.assertEqual(dice.call_args.args[1], 21, "AC16 + 四分之三掩体5 = 21")

    async def test_opportunity_attack_ignores_distance_rule(self):
        state = self.make_state()
        bf.set_placement(state, "岚", "out", "none")
        with self._patch_dice(enemy_damage=5):
            blocked = await dm.execute_tool("enemy_attack", {"enemy_name": "地精弓手"}, state)
            reaction = await dm.execute_tool(
                "enemy_attack", {"enemy_name": "地精弓手", "action_source": "opportunity_attack"},
                state)
        self.assertIn("近战够不到", blocked)
        self.assertIn("造成 5 点伤害", reaction, "借机攻击是反应，不受距离拦截")

    async def test_dex_save_gets_cover_bonus(self):
        state = self.make_state()
        bf.set_placement(state, "地精弓手", "near", "half")
        # d20=9 + 敏捷2 + 熟练2 = 13 < DC15（无掩体必失败）；加半掩体 +2 → 15 成功减半
        with patch.object(combat.random, "randint", return_value=9):
            out = await dm.execute_tool("save_damage", {
                "targets": ["地精弓手"], "dc": 15, "damage": 20, "damage_type": "火焰",
                "ability": "dex", "reason": "火球"}, state)
        self.assertIn("掩体 +2 敏捷豁免", out)
        self.assertIn("成功", out)
        self.assertEqual(state.world_state.npcs[0].hp, 10, "掩体让豁免成功，伤害减半")

    async def test_set_tactical_state_tool_registers_multiple(self):
        state = self.make_state()
        out = await dm.execute_tool("set_tactical_state", {
            "placements": [
                {"combatant": "地精弓手", "band": "near", "cover": "half", "note": "躲在石堆后"},
                {"combatant": "你", "band": "near", "cover": "none"},
            ]}, state)
        self.assertIn("地精弓手", out)
        self.assertEqual(bf.cover_of(state, "地精弓手"), "half")
        self.assertEqual(bf.band_of(state, "岚"), "near")
        events = [d for _, t, d in state.event_history
                  if t == "game_event" and d.get("type") == "battlefield"]
        self.assertEqual(len(events), 1, "态势更新要推一条可见事件")

    async def test_combat_end_clears_battlefield(self):
        state = self.make_state()
        bf.set_placement(state, "地精弓手", "near", "half")
        state.world_state.npcs[0].alive = False
        state.world_state.npcs[0].hp = 0
        combat._refresh_combat_state(state)
        self.assertIsNone(bf.placement_of(state, "地精弓手"), "战斗结束应清空态势")


if __name__ == "__main__":
    unittest.main()
