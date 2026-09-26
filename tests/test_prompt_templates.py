"""提示词模板回归：所有模块都必须能真实构建 system prompt。

背景：prompt 里写了未转义的花括号（如 {"feats_add": ...}）会让
SYSTEM_PROMPT.format() 抛 KeyError，导致整个叙事回合崩溃；
而回合级测试把 build_system_prompt mock 掉了，根本测不到。
"""
import tempfile
import unittest

from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestPromptTemplates(unittest.TestCase):
    def make_state(self) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "prompt", "char", "岚",
            {"hp": 20, "max_hp": 20, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "race": "人类", "play_mode": "deep",
             "attributes": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10},
             "world_outline": "旧商道上的地精伏击。", "backstory": "为寻找兄长而旅行。"},
        )
        state.world_state = WorldState(session_id="prompt", _storage_dir=tmp.name)
        state.world_state.npcs = [NpcEntry(name="地精斥候", attitude="敌对", hp=7, max_hp=7)]
        return state

    def test_every_module_builds_system_prompt(self):
        state = self.make_state()
        for module in ("narrative", "rules", "combat", "scene", "social", "memory", "graph"):
            with self.subTest(module=module):
                prompt = dm.build_system_prompt(
                    state,
                    retrieved_chunks=[],
                    dispatch_plan={"module": module, "focus_context": "", "tool_hint": ""},
                    subagent_brief="### 世界顾问\n事实",
                )
                self.assertIn("你是", prompt)
                self.assertGreater(len(prompt), 200)

    def test_lite_mode_and_other_systems_also_build(self):
        for system, mode in (("dnd5e", "lite"), ("coc", "deep"), ("dnd4e", "deep"), ("custom", "deep")):
            state = self.make_state()
            state.character_info["game_system"] = system
            state.character_info["play_mode"] = mode
            with self.subTest(system=system, mode=mode):
                prompt = dm.build_system_prompt(state, dispatch_plan={"module": "narrative"})
                self.assertGreater(len(prompt), 200)

    def test_mode_instructions_build_for_all_modes(self):
        state = self.make_state()
        for focused in (True, False):
            for mode in ("lite", "deep"):
                state.character_info["play_mode"] = mode
                self.assertGreater(len(dm._mode_instructions(state, focused)), 10)

    def test_decision_prompts_format_safely(self):
        """静态提示词里若含未转义花括号，.format() 会直接抛错。"""
        from backend.engine import dm_agent as agent

        for name in ("SYSTEM_PROMPT", "DM_DECISION_PROMPT", "COC_SYSTEM_PROMPT",
                     "COC_DECISION_PROMPT", "DND4E_SYSTEM_PROMPT", "DND4E_DECISION_PROMPT",
                     "CUSTOM_SYSTEM_PROMPT", "CUSTOM_DECISION_PROMPT"):
            template = getattr(agent, name, None)
            if not isinstance(template, str) or "{character_info" not in template:
                continue
            with self.subTest(template=name):
                template.format(character_info="", memory_context="",
                                world_context="", world_state_compact="")


if __name__ == "__main__":
    unittest.main()
