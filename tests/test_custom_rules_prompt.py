"""自定义规则系统：玩家的规则文本必须在所有模块都到得了模型。

此前 `custom_rules` 只在 rules/combat 模块的规则块里注入，叙事/社交/场景等模块
（以及子 Agent 的 rules_ctx）完全看不到它——而它是自定义局唯一的规则来源。
"""
import unittest

from backend.engine.dm_prompts import build_character_info, build_system_prompt
from backend.engine.session import GameSessionState

RULE = "本世界判定用 2d10，目标值 12；没有职业，只有道途；法术不存在。"


def _state(system: str = "custom", rules: str = RULE) -> GameSessionState:
    return GameSessionState(
        "custom-rules", "char", "岚",
        {"game_system": system, "level": 1, "custom_rules": rules,
         "hp": 30, "max_hp": 30, "ac": 15,
         "attributes": {"str": 12, "dex": 12, "con": 12, "int": 12, "wis": 12, "cha": 12}},
        username="custom-user",
    )


class TestCustomRulesReachPrompt(unittest.TestCase):
    def test_every_module_prompt_carries_the_custom_rules(self):
        state = _state()
        for module in ("narrative", "social", "scene", "rules", "combat", "memory", "graph"):
            with self.subTest(module=module):
                prompt = build_system_prompt(state, dispatch_plan={"module": module})
                self.assertIn(RULE, prompt, f"{module} 模块看不到自定义规则")

    def test_subagent_context_carries_the_custom_rules(self):
        """子 Agent 的 rules_ctx 取 char_info[:1600]，规则必须落在这个预算内。"""
        info = build_character_info(_state())
        self.assertIn(RULE, info[:1600])

    def test_long_rules_are_truncated_with_a_pointer(self):
        long_rules = "规则条目。" * 400  # 2000 字
        info = build_character_info(_state(rules=long_rules))
        self.assertIn("本局自定义规则", info)
        self.assertIn("完整规则见规则模块", info, "被截断时要说明完整规则在哪")
        self.assertLess(len(info), 4000, "截断后不能把角色信息撑爆")

    def test_other_systems_do_not_get_a_custom_rules_line(self):
        for system in ("dnd5e", "dnd4e", "coc"):
            with self.subTest(system=system):
                info = build_character_info(_state(system=system))
                self.assertNotIn("本局自定义规则", info,
                                 f"{system} 有自己的系统提示词，不该混入自定义规则块")

    def test_empty_custom_rules_add_no_line(self):
        info = build_character_info(_state(rules="   "))
        self.assertNotIn("本局自定义规则", info)

    def test_braces_in_custom_rules_do_not_break_prompt_assembly(self):
        """规则文本里带花括号也必须能出提示词（历史上被 str.format 的 KeyError 坑过一次）。"""
        rule = '使用 {dice} 记法，例如 {"str": 2}；DC={12}，勿写成 {0}。'
        prompt = build_system_prompt(_state(rules=rule), dispatch_plan={"module": "rules"})
        self.assertIn(rule, prompt)


if __name__ == "__main__":
    unittest.main()
