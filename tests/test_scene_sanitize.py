"""场景字段规范化：防止散文与注解污染顶栏、笔记和 NPC 名单。"""
import tempfile
import unittest

from backend.engine.world_state import LocationEntry, NpcEntry, WorldState


class TestSceneSanitize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = WorldState(session_id="scene_test", _storage_dir=self.tmp.name)
        self.ws.npcs = [
            NpcEntry(name="地精斥候", attitude="敌对", hp=7, max_hp=7),
            NpcEntry(name="铁匠柯尔", attitude="中立", hp=14, max_hp=14),
        ]
        self.addCleanup(self.tmp.cleanup)

    def test_location_and_time_drop_annotations(self):
        self.ws.update_scene(
            current_location="村外小径（地精斥候交战处）",
            current_time="黄昏（短休进行中）",
            weather="阴云低垂（雨腥）",
        )
        self.assertEqual(self.ws.scene.current_location, "村外小径")
        self.assertEqual(self.ws.scene.current_time, "黄昏")
        self.assertEqual(self.ws.scene.weather, "阴云低垂")

    def test_long_prose_is_clamped(self):
        self.ws.update_scene(weather="山风渐起，带着未干的水光和血腥味一路卷过整片林地" * 2)
        self.assertLessEqual(len(self.ws.scene.weather), 24)
        self.assertNotIn("\n", self.ws.scene.weather)

    def test_annotated_npc_names_do_not_create_duplicates(self):
        before = {n.name for n in self.ws.npcs}
        self.ws.update_scene(visible_npcs_here=[
            "地精斥候（已倒地）",
            "两个地精斥候（约60尺外，老榆树下）",
            "铁匠柯尔",
            "无",
        ])
        self.assertEqual(self.ws.scene.visible_npcs_here, ["地精斥候", "铁匠柯尔"])
        self.assertEqual({n.name for n in self.ws.npcs}, before)

    def test_unknown_annotated_npc_is_registered_with_clean_name(self):
        self.ws.update_scene(visible_npcs_here=["神秘商人（披斗篷）"])
        names = [n.name for n in self.ws.npcs]
        self.assertIn("神秘商人", names)
        self.assertNotIn("神秘商人（披斗篷）", names)

    def test_visible_npc_list_is_deduped_and_capped(self):
        self.ws.update_scene(visible_npcs_here=[f"路人{i}" for i in range(12)])
        self.assertLessEqual(len(self.ws.scene.visible_npcs_here), 8)
        self.assertEqual(len(set(self.ws.scene.visible_npcs_here)), len(self.ws.scene.visible_npcs_here))

    def test_new_location_is_registered_once(self):
        self.ws.update_scene(current_location="旧商道旁货车残骸处（老榆树下）")
        self.ws.update_scene(current_location="旧商道旁货车残骸处（再经过）")
        matches = [l.name for l in self.ws.locations if l.name.startswith("旧商道")]
        self.assertEqual(matches, ["旧商道旁货车残骸处"])


class TestNpcNameCanonicalisation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = WorldState(session_id="npc_test", _storage_dir=self.tmp.name)
        self.ws.npcs = [NpcEntry(name="地精斥候", attitude="敌对", hp=7, max_hp=7)]

    def test_annotated_names_resolve_to_existing_npc(self):
        self.assertEqual(self.ws.canonical_npc_name("地精斥候（已倒地）"), "地精斥候")
        self.assertEqual(self.ws.canonical_npc_name("两只地精斥候"), "地精斥候")
        self.assertIsNotNone(self.ws.get_npc("地精斥候（灌木丛后）"))

    def test_add_npc_merges_instead_of_duplicating(self):
        self.ws.add_npc(NpcEntry(name="地精斥候（灌木丛后未现身）", role="侦察兵", notes="在等接应"))
        self.assertEqual(len(self.ws.npcs), 1)
        self.assertEqual(self.ws.npcs[0].name, "地精斥候")
        self.assertEqual(self.ws.npcs[0].role, "侦察兵")

    def test_unknown_annotated_name_is_cleaned_and_added(self):
        self.ws.add_npc(NpcEntry(name="神秘商人（披斗篷）", role="商人"))
        names = [n.name for n in self.ws.npcs]
        self.assertIn("神秘商人", names)
        self.assertNotIn("神秘商人（披斗篷）", names)

    def test_update_npc_accepts_annotated_name(self):
        self.assertTrue(self.ws.update_npc("地精斥候（已倒地）", hp=0, alive=False))
        self.assertEqual(self.ws.npcs[0].hp, 0)


if __name__ == "__main__":
    unittest.main()
