"""伤害类型规则：抗性/免疫/易伤解析与生物豁免加值。"""
import unittest

from backend.engine.damage_rules import (
    ability_modifier, canonical_damage_type, creature_save_modifier, damage_multiplier,
    infer_damage_type, weapon_damage_type,
)
from backend.engine.world_state import NpcEntry


class TestDamageMultiplier(unittest.TestCase):
    def test_infer_damage_type_picks_the_earliest_mention(self):
        self.assertEqual(infer_damage_type("弯刀 1d6 挥砍"), "挥砍")
        self.assertEqual(infer_damage_type("咬击 1d4 穿刺 + 1d6 毒素"), "穿刺")
        self.assertEqual(infer_damage_type("bite: 5 (1d6+2) piercing damage"), "穿刺")
        self.assertEqual(infer_damage_type("普通攻击 1d6"), "")
        self.assertEqual(infer_damage_type(None), "")

    def test_weapon_damage_type_keywords(self):
        self.assertEqual(weapon_damage_type("我挥长剑砍向地精"), "挥砍")
        self.assertEqual(weapon_damage_type("用匕首刺向咽喉"), "穿刺")
        self.assertEqual(weapon_damage_type("抡起战锤砸下"), "钝击")
        self.assertEqual(weapon_damage_type("我冲过去抱住它"), "")

    def test_english_text_from_srd_entries(self):
        text = ("Hit: 7 (1d8+3) piercing damage, and the target must make a DC 11 Constitution saving throw. "
                "The webbing can be destroyed (AC 10; hp 5; vulnerability to fire damage; "
                "immunity to bludgeoning, poison, and psychic damage).")
        self.assertEqual(damage_multiplier(text, "火焰")[0], 2.0)
        self.assertEqual(damage_multiplier(text, "钝击")[0], 0.0)
        self.assertEqual(damage_multiplier(text, "毒素")[0], 0.0)
        self.assertEqual(damage_multiplier(text, "心灵")[0], 0.0)
        self.assertEqual(damage_multiplier(text, "穿刺")[0], 1.0)

    def test_chinese_text_from_builtin_cards(self):
        text = "特性：黑暗视觉；免疫中毒；火焰抗性；对雷鸣易伤。"
        self.assertEqual(damage_multiplier(text, "毒素")[0], 0.0)
        self.assertEqual(damage_multiplier(text, "火焰")[0], 0.5)
        self.assertEqual(damage_multiplier(text, "雷鸣")[0], 2.0)
        self.assertEqual(damage_multiplier(text, "冷冻")[0], 1.0)

    def test_modifiers_bind_within_their_own_clause(self):
        """回归：跨子句串台会把"挥砍抗性"读成"免疫挥砍"（真实试玩探针发现）。"""
        text = "爪击 1d6+2 挥砍 挥砍抗性 免疫毒素"
        self.assertEqual(damage_multiplier(text, "挥砍")[0], 0.5, "对挥砍只有抗性")
        self.assertEqual(damage_multiplier(text, "毒素")[0], 0.0, "免疫属于毒素")
        self.assertEqual(damage_multiplier("免疫火焰，但对挥砍有抗性", "挥砍")[0], 0.5)
        self.assertEqual(damage_multiplier("免疫火焰，但对挥砍有抗性", "火焰")[0], 0.0)

    def test_condition_immunity_is_not_damage_immunity(self):
        """回归：'状态免疫：中毒' 说的是状态免疫，别把毒素伤害也算成免疫。"""
        self.assertEqual(damage_multiplier("状态免疫：中毒", "毒素")[0], 1.0)
        self.assertEqual(damage_multiplier("Condition Immunities: poisoned", "毒素")[0], 1.0)
        self.assertEqual(damage_multiplier("伤害免疫：毒素", "毒素")[0], 0.0)
        self.assertEqual(damage_multiplier("状态免疫：中毒；免疫毒素伤害", "毒素")[0], 0.0,
                         "同一张卡上两条都写时，伤害免疫仍然算数")

    def test_type_before_modifier_forms(self):
        self.assertEqual(damage_multiplier("穿戴者对冷冻伤害有抗性", "冷冻")[0], 0.5)
        self.assertEqual(damage_multiplier("龙裔血脉：火焰抗性", "火焰")[0], 0.5)
        self.assertEqual(damage_multiplier("抗性：火焰、冷冻", "冷冻")[0], 0.5)

    def test_resistance_and_vulnerability_cancel(self):
        text = "resistance to fire damage; vulnerability to fire damage"
        multiplier, note = damage_multiplier(text, "火焰")
        self.assertEqual(multiplier, 1.0)
        self.assertIn("抵消", note)

    def test_unknown_or_missing_type_is_neutral(self):
        self.assertEqual(damage_multiplier("immunity to fire damage", "")[0], 1.0)
        self.assertEqual(damage_multiplier("immunity to fire damage", "某种未知伤害")[0], 1.0)

    def test_npc_entry_traits_are_searched(self):
        npc = NpcEntry(name="火元素", traits=["免疫火焰", "冷冻易伤"])
        self.assertEqual(damage_multiplier(npc, "火焰")[0], 0.0)
        self.assertEqual(damage_multiplier(npc, "冷冻")[0], 2.0)

    def test_canonical_damage_type_aliases(self):
        self.assertEqual(canonical_damage_type("fire"), "火焰")
        self.assertEqual(canonical_damage_type("Fire "), "火焰")
        self.assertEqual(canonical_damage_type("暗蚀"), "黯蚀")
        self.assertEqual(canonical_damage_type("穿刺"), "穿刺")
        self.assertEqual(canonical_damage_type("bludgeoning"), "钝击")


class TestCreatureSaveModifier(unittest.TestCase):
    def test_explicit_save_on_card(self):
        mod, source = creature_save_modifier({"traits": ["敏捷豁免 +5"]}, {}, "dex")
        self.assertEqual(mod, 5)
        self.assertEqual(source, "卡面豁免")

    def test_four_e_defense(self):
        mod, source = creature_save_modifier({}, {"反射": "18"}, "dex")
        self.assertEqual(mod, 18)
        self.assertIn("4e", source)

    def test_derived_from_ability_score(self):
        npc = NpcEntry(name="石像鬼", level=4)
        mod, source = creature_save_modifier(npc, {"敏捷": "14"}, "dex")
        # 敏捷 14 → +2；4 级熟练 +2
        self.assertEqual(mod, 4)
        self.assertEqual(source, "属性推导")

    def test_ability_modifier_table(self):
        self.assertEqual(ability_modifier(8), -1)
        self.assertEqual(ability_modifier(10), 0)
        self.assertEqual(ability_modifier(20), 5)


if __name__ == "__main__":
    unittest.main()
