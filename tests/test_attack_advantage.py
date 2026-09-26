"""攻击优势/劣势的后端裁定：状态、俯卧、长射程与特长抵消。"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import combat, dm_agent as dm
from backend.engine.combat_advantage import infer_attack_kind, resolve_attack_advantage
from backend.engine.rules import AdvantageMode
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


def _roll(total: int = 18):
    return SimpleNamespace(roll=15, total=total, result=SimpleNamespace(value="成功"))


class TestAttackAdvantageRules(unittest.TestCase):
    def test_attacker_and_target_conditions_are_structured(self):
        poisoned = resolve_attack_advantage(attacker_text="中毒")
        self.assertEqual(poisoned.mode, AdvantageMode.DISADVANTAGE)
        self.assertIn("攻击者中毒", poisoned.summary())

        blinded_target = resolve_attack_advantage(target_text="目盲")
        self.assertEqual(blinded_target.mode, AdvantageMode.ADVANTAGE)
        self.assertIn("无法有效防御", blinded_target.summary())

    def test_advantage_and_disadvantage_cancel(self):
        decision = resolve_attack_advantage(attacker_text="中毒", target_text="束缚")
        self.assertEqual(decision.mode, AdvantageMode.NORMAL)
        self.assertTrue(decision.cancelled)
        self.assertIn("抵消", decision.summary())

    def test_prone_target_changes_by_attack_kind(self):
        melee = resolve_attack_advantage(target_text="俯卧", attack_kind="melee")
        ranged = resolve_attack_advantage(target_text="俯卧", attack_kind="ranged")
        self.assertEqual(melee.mode, AdvantageMode.ADVANTAGE)
        self.assertEqual(ranged.mode, AdvantageMode.DISADVANTAGE)

    def test_long_range_disadvantage_can_be_cancelled_by_sharpshooter(self):
        without_feat = resolve_attack_advantage(attack_kind="ranged", long_range=True)
        self.assertEqual(without_feat.mode, AdvantageMode.DISADVANTAGE)
        self.assertIn("长射程", without_feat.summary())

        with_feat = resolve_attack_advantage(
            attack_kind="ranged", long_range=True,
            has_feat_effect=lambda key: key == "long_range_no_disadvantage")
        self.assertEqual(with_feat.mode, AdvantageMode.NORMAL)
        self.assertIn("神射手", with_feat.summary())

    def test_backend_state_beats_a_bare_model_declaration(self):
        decision = resolve_attack_advantage(attacker_text="中毒", declared="advantage")
        self.assertEqual(decision.mode, AdvantageMode.DISADVANTAGE,
                         "模型不能用一个 advantage 参数覆盖后端的目盲/中毒硬状态")

    def test_unmodelled_declared_source_still_works(self):
        decision = resolve_attack_advantage(
            declared="advantage", declared_reason="高台俯射")
        self.assertEqual(decision.mode, AdvantageMode.ADVANTAGE)
        self.assertIn("高台俯射", decision.summary())

    def test_attack_kind_inference_prefers_explicit_then_text(self):
        self.assertEqual(infer_attack_kind(explicit="ranged"), "ranged")
        self.assertEqual(infer_attack_kind("我用长剑劈砍"), "melee")
        self.assertEqual(infer_attack_kind("用长弓射击"), "ranged")


class TestAttackAdvantageIntegration(unittest.IsolatedAsyncioTestCase):
    def make_state(self, conditions: list[dict] | None = None,
                   feats: list[dict] | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "adv", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 5, "xp": 0,
             "game_system": "dnd5e", "char_class": "战士",
             "attributes": {"str": 16, "dex": 14, "con": 14},
             "conditions": list(conditions or []),
             "feats": list(feats or []),
             "inventory": {"items": [{"name": "长剑", "type": "weapon", "equipped": True}]}},
        )
        state.world_state = WorldState(session_id="adv", _storage_dir=tmp.name)
        state.world_state.npcs = [
            NpcEntry(name="地精斥候", attitude="敌对", hp=7, max_hp=7, ac=13,
                     level=1, alive=True)]
        state.turn_action_ledger = {}
        return state

    async def test_player_poisoned_forces_disadvantage_on_combat_round(self):
        state = self.make_state([{"name": "中毒", "description": "攻击检定劣势"}])
        seen = []

        def fake(attacker, ac, mod, dice, **kwargs):
            seen.append(kwargs.get("advantage"))
            return _roll(), 3

        with patch.object(combat, "combat_attack_roll", side_effect=fake):
            line = await dm.execute_tool(
                "combat_round",
                {"enemy_name": "地精斥候", "player_action": "挥剑", "enemy_can_act": False},
                state,
            )
        self.assertEqual(seen, [AdvantageMode.DISADVANTAGE])
        self.assertIn("劣势", line)
        self.assertIn("攻击者中毒", line)

    async def test_enemy_attack_gets_advantage_against_restrained_player(self):
        state = self.make_state([{"name": "束缚", "remaining_rounds": 2}])
        seen = []

        def fake(attacker, ac, mod, dice, **kwargs):
            seen.append(kwargs.get("advantage"))
            return _roll(), 4

        with patch.object(combat, "combat_attack_roll", side_effect=fake):
            line = await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)
        self.assertEqual(seen, [AdvantageMode.ADVANTAGE])
        self.assertIn("优势", line)
        self.assertIn("无法有效防御", line)

    async def test_prone_enemy_targets_and_counterattacks_with_correct_modes(self):
        state = self.make_state()
        seen: list[tuple[str, object]] = []

        def fake(attacker, ac, mod, dice, **kwargs):
            seen.append((attacker, kwargs.get("advantage")))
            return _roll(), 3 if attacker == "你" else 2

        with patch.object(combat, "combat_attack_roll", side_effect=fake):
            await dm.execute_tool(
                "combat_round",
                {"enemy_name": "地精斥候", "player_action": "挥剑劈下",
                 "enemy_condition": "俯卧"},
                state,
            )
        self.assertEqual(seen[0], ("你", AdvantageMode.ADVANTAGE),
                         "近战攻击俯卧目标应有优势")
        self.assertEqual(seen[1], ("地精斥候", AdvantageMode.DISADVANTAGE),
                         "俯卧敌人反击时攻击检定应有劣势")

    async def test_pack_tactics_uses_structured_battlefield_ally(self):
        from backend.engine import battlefield

        state = self.make_state()
        state.world_state.npcs[0].traits = ["Pack Tactics: advantage if an ally is within 5 ft."]
        state.world_state.npcs.append(
            NpcEntry(name="地精弓手", attitude="敌对", hp=6, max_hp=6, ac=14, alive=True))
        battlefield.set_placement(state, "你", "engaged", "none")
        battlefield.set_placement(state, "地精斥候", "engaged", "none")
        battlefield.set_placement(state, "地精弓手", "engaged", "none")
        seen = []

        def fake(attacker, ac, mod, dice, **kwargs):
            seen.append(kwargs.get("advantage"))
            return _roll(), 3

        with patch.object(combat, "combat_attack_roll", side_effect=fake):
            line = await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)
        self.assertEqual(seen, [AdvantageMode.ADVANTAGE])
        self.assertIn("群体战术", line)

    async def test_pack_tactics_needs_an_engaged_ally(self):
        state = self.make_state()
        state.world_state.npcs[0].traits = ["Pack Tactics: advantage if an ally is within 5 ft."]
        from backend.engine import battlefield
        battlefield.set_placement(state, "你", "engaged", "none")
        battlefield.set_placement(state, "地精斥候", "engaged", "none")
        seen = []

        def fake(attacker, ac, mod, dice, **kwargs):
            seen.append(kwargs.get("advantage"))
            return _roll(), 3

        with patch.object(combat, "combat_attack_roll", side_effect=fake):
            await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)
        self.assertEqual(seen, [None], "没有另一名缠斗盟友时不应凭空给群体战术优势")

    async def test_sunlight_sensitivity_uses_scene_time_and_weather(self):
        state = self.make_state()
        state.world_state.npcs[0].traits = [
            "Sunlight Sensitivity: disadvantage on attack rolls in sunlight."
        ]
        state.world_state.scene.current_time = "正午"
        state.world_state.scene.weather = "晴空万里"
        seen = []

        def fake(attacker, ac, mod, dice, **kwargs):
            seen.append(kwargs.get("advantage"))
            return _roll(), 3

        with patch.object(combat, "combat_attack_roll", side_effect=fake):
            line = await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)
        self.assertEqual(seen, [AdvantageMode.DISADVANTAGE])
        self.assertIn("阳光敏感", line)

    async def test_sunlight_sensitivity_is_quiet_at_dusk(self):
        state = self.make_state()
        state.world_state.npcs[0].traits = [
            "Sunlight Sensitivity: disadvantage on attack rolls in sunlight."
        ]
        state.world_state.scene.current_time = "黄昏"
        state.world_state.scene.weather = "晴"
        seen = []

        def fake(attacker, ac, mod, dice, **kwargs):
            seen.append(kwargs.get("advantage"))
            return _roll(), 3

        with patch.object(combat, "combat_attack_roll", side_effect=fake):
            line = await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)
        self.assertEqual(seen, [None], "黄昏不属于阳光环境")
        self.assertNotIn("阳光敏感", line)


if __name__ == "__main__":
    unittest.main()
