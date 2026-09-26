"""特长被动效果：图鉴里的 effect 要真的落到数值上。

feats.py 声明了 51 个 effect key，此前只有 3 个被代码读取——玩家在 4/8 级用属性提升
换来的「警觉」「健壮」「运动员」，除了角色卡多一行文字什么也没发生。
这里盯住本轮接上的六项：先攻加值、每级生命、属性加值、双持 AC、生命骰最低治疗、移动力。
"""
import unittest
from unittest.mock import AsyncMock, patch

from backend.engine import feat_effects, initiative
from backend.engine.character_state import _exec_update_state
from backend.engine.rules import short_rest
from backend.engine.session import GameSessionState


def hero(feats=None, level: int = 3, system: str = "dnd5e") -> GameSessionState:
    return GameSessionState(
        "feat", "char", "岚",
        {"game_system": system, "char_class": "战士", "level": level,
         "hp": 30, "max_hp": 30, "ac": 16, "xp": 0,
         "attributes": {"str": 14, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
         "feats": list(feats or []), "inventory": {"items": []}},
        username="feat-user",
    )


def add_feat(state: GameSessionState, payload, **extra):
    """走真实写回路径（update_state）加特长。"""
    return _exec_update_state(
        {"changes": {"feats_add": payload, **extra}, "reason": "升级选专长"}, state)


class TestFeatEffects(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.event = patch("backend.engine.character_state.push_event", new=AsyncMock())
        self.event.start()
        self.addCleanup(self.event.stop)
        self.damage_event = patch("backend.engine.player_damage.push_event", new=AsyncMock())
        self.damage_event.start()
        self.addCleanup(self.damage_event.stop)

    async def test_alert_adds_initiative_bonus(self):
        state = hero()
        await add_feat(state, {"id": "alert", "name": "警觉"})
        self.assertEqual(feat_effects.initiative_bonus(state), 5)
        roster = initiative.build_roster(state)
        self.assertEqual(roster[0].initiative_bonus, 5)

        seen: list[int] = []

        def fake_roll(dex_mod, rng=None):
            seen.append(dex_mod)
            return 10

        with patch.object(initiative, "roll_initiative", side_effect=fake_roll):
            initiative.start(state, roster=roster)
        # 12 敏捷 = +1，叠加「警觉」+5 后应掷 d20+6
        self.assertEqual(seen, [6])

    async def test_tough_raises_hp_now_and_on_level_up(self):
        state = hero(level=3)
        await add_feat(state, {"id": "tough", "name": "健壮"})
        self.assertEqual(state.character_info["max_hp"], 30 + 6, "健壮 = 每级 +2 生命")
        self.assertEqual(state.character_info["hp"], 36)
        # 重复同步不叠加（幂等）
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"gold": 1}, "reason": "无关变更"}, state)
        self.assertEqual(state.character_info["max_hp"], 36)

    async def test_tough_keeps_growing_after_level_up(self):
        from backend.engine.game_systems import DND5_CLASS_HD

        state = hero(level=3)
        await add_feat(state, {"id": "tough", "name": "健壮"})
        before = state.character_info["max_hp"]
        await _exec_update_state({"changes": {"xp": 2700}, "reason": "升级"}, state)
        gained_levels = state.character_info["level"] - 3
        self.assertGreater(gained_levels, 0)
        con_mod = (state.character_info["attributes"]["con"] - 10) // 2
        per_level_hp = max(1, (DND5_CLASS_HD["战士"] + 1) // 2 + con_mod)
        self.assertEqual(state.character_info["max_hp"] - before,
                         gained_levels * per_level_hp + gained_levels * 2,
                         "升级既有职业生命骰收益，也有健壮的每级 +2")

    async def test_removing_tough_reverts_the_bonus(self):
        state = hero(level=3)
        await add_feat(state, {"id": "tough", "name": "健壮"})
        await _exec_update_state({"changes": {"feats_remove": "健壮"}, "reason": "修正"}, state)
        self.assertEqual(state.character_info["max_hp"], 30)
        self.assertEqual(state.character_info["hp"], 30)

    async def test_athlete_applies_the_chosen_attribute(self):
        state = hero()
        await add_feat(state, {"name": "运动员", "attr_choice": "dex"})
        self.assertEqual(state.character_info["attributes"]["dex"], 13)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"gold": 5}, "reason": "无关变更"}, state)
        self.assertEqual(state.character_info["attributes"]["dex"], 13, "属性加值不能重复叠加")

    async def test_athlete_defaults_to_the_first_option(self):
        state = hero()
        await add_feat(state, {"name": "运动员"})
        self.assertEqual(state.character_info["attributes"]["str"], 15, "未指定时取图鉴第一项")

    async def test_dual_wielder_gets_ac_only_with_two_weapons(self):
        state = hero()
        await add_feat(state, {"name": "双持客"})
        state.character_info["inventory"]["items"] = [
            {"name": "长剑", "type": "weapon", "equipped": True},
            {"name": "短剑", "type": "weapon", "equipped": True},
        ]
        self.assertEqual(feat_effects.dual_wield_ac_bonus(state.character_info), 1)
        state.character_info["inventory"]["items"][1]["equipped"] = False
        self.assertEqual(feat_effects.dual_wield_ac_bonus(state.character_info), 0)

    async def test_dual_wielder_bonus_shows_up_in_recalculated_ac(self):
        from backend.engine.character_equipment import _recalc_equipment_effects

        state = hero()
        await add_feat(state, {"name": "双持客"})
        state.character_info["base_ac"] = 15
        state.character_info["inventory"]["items"] = [
            {"name": "长剑", "type": "weapon", "equipped": True},
            {"name": "匕首", "type": "weapon", "equipped": True},
        ]
        applied: dict = {}
        _recalc_equipment_effects(state, applied)
        self.assertEqual(state.character_info["ac"], 16, "双持客在 AC 重算里 +1")

    async def test_durable_raises_the_minimum_hit_die_heal(self):
        state = hero()
        await add_feat(state, {"name": "坚毅", "attr_choice": "con"})
        self.assertEqual(state.character_info["attributes"]["con"], 15, "坚毅同时 +1 CON")
        self.assertEqual(feat_effects.min_hit_die_heal(state), 4, "2×CON 调整值(+2) = 4")
        with patch("backend.engine.rules.random.randint", return_value=1):
            result = short_rest(10, 30, 3, 2, 3, hit_dice_type=10, dice_to_use=2, min_per_die=4)
        self.assertEqual(result["hp_restored"], 8, "每颗骰子至少回 4 点")

    async def test_mobile_reports_speed_bonus(self):
        state = hero()
        await add_feat(state, {"name": "轻灵移动"})
        self.assertEqual(feat_effects.speed_bonus(state), 10)
        from backend.engine.dm_prompts import build_character_info
        text = build_character_info(state)
        self.assertIn("移动力", text)
        self.assertIn("40", text)

    async def test_non_5e_systems_do_not_apply_the_catalog(self):
        state = hero(feats=[{"name": "警觉"}], system="coc")
        self.assertEqual(feat_effects.initiative_bonus(state), 0)
        self.assertEqual(feat_effects.hp_bonus_total(state), 0)

    async def test_mechanic_hints_reach_the_dm_info(self):
        """后端不强结算的特长（不受突袭/陷阱优势…）要结构化地提醒主 DM。"""
        from backend.engine.dm_prompts import build_character_info

        state = hero()
        self.assertEqual(feat_effects.mechanic_hints(state), [])
        await add_feat(state, {"name": "警觉"})
        await add_feat(state, {"name": "地城探索者"})
        hints = feat_effects.mechanic_hints(state)
        self.assertTrue(any("不受突袭" in h for h in hints))
        self.assertTrue(any("陷阱" in h for h in hints))
        text = build_character_info(state)
        self.assertIn("特长机制", text)
        self.assertIn("不受突袭", text)
        # 后端已自动结算的部分不在这里重复（避免 token 浪费）
        self.assertNotIn("先攻+5", text)
        # 关键：这段要真的进到模型看到的 system prompt 里，而不只是躺在角色信息函数里
        from backend.engine.dm_prompts import build_system_prompt
        sp = build_system_prompt(state, dispatch_plan={"module": "combat"})
        self.assertIn("不受突袭", sp)

    async def test_mechanic_hints_are_capped_and_compact(self):
        """这段会进每一轮 prompt：必须截断且足够短。"""
        state = hero(feats=[
            {"name": "警觉"}, {"name": "地城探索者"}, {"name": "双持客"},
            {"name": "强弩专家"}, {"name": "地脉探索者"} if False else {"name": "巨武器大师"},
            {"name": "重甲大师"}, {"name": "运动员"},
        ])
        hints = feat_effects.mechanic_hints(state)
        self.assertLessEqual(len(hints), feat_effects.MAX_MECHANIC_HINTS)
        self.assertLessEqual(sum(len(h) for h in hints), 400, "提示总量要控住 token")

    async def test_heavy_armor_master_reduces_only_physical_damage_in_heavy_armor(self):
        from backend.engine.player_damage import apply as apply_damage

        state = hero()
        await add_feat(state, {"name": "重甲大师", "attr_choice": "str"})
        state.character_info["inventory"]["items"] = [
            {"name": "板甲", "type": "armor", "equipped": True}]
        slashing = await apply_damage(state, 10, "挥砍", reason="地精砍你")
        self.assertEqual(slashing["hp_damage"], 7, "重甲大师：钝击/穿刺/挥砍 -3")
        fire = await apply_damage(state, 10, "火焰", reason="火球")
        self.assertEqual(fire["hp_damage"], 10, "非物理伤害不减")
        state.character_info["inventory"]["items"] = [
            {"name": "皮甲", "type": "armor", "equipped": True}]
        pierce = await apply_damage(state, 10, "穿刺", reason="箭矢")
        self.assertEqual(pierce["hp_damage"], 10, "换成轻甲就不再有减免")

    async def test_medium_armor_does_not_trigger_the_feat(self):
        from backend.engine.player_damage import apply as apply_damage

        state = hero()
        await add_feat(state, {"name": "重甲大师", "attr_choice": "str"})
        state.character_info["inventory"]["items"] = [
            {"name": "链甲衫", "type": "armor", "equipped": True}]
        result = await apply_damage(state, 10, "挥砍", reason="地精砍你")
        self.assertEqual(result["hp_damage"], 10, "链甲衫是中型甲，不算重甲")


if __name__ == "__main__":
    unittest.main()
