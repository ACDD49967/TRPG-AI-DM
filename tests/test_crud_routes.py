"""增删改查接口：世界状态 / 角色状态 / 图鉴 / 地图 / 法术 / 知识库 / 存档 / 扩展包。

这些接口此前只有"读"或"删"：创建与编辑只能靠主 DM 工具。这里验证补上的写入通道
与 DM 走同一批处理器（世界状态、角色状态直接复用 _exec_* 工具处理器）。
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from backend.engine.session import GameSessionState, session_manager
from backend.engine.world_state import WorldState


class CrudRoutesBase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from backend.main import app

        self.app = app
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)

        from backend import extension_manager, media_store, save_manager
        self.stack = __import__("contextlib").ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(media_store, "MEDIA_ROOT", root / "media"))
        self.stack.enter_context(patch.object(save_manager, "SAVE_ROOT", root / "saves"))
        self.stack.enter_context(patch.object(extension_manager, "EXT_ROOT", root / "extensions"))

        from backend.knowledge_base import KnowledgeBase
        self.kb = KnowledgeBase(root / "kb.json")
        self.stack.enter_context(patch("backend.knowledge_base.get_knowledge_base",
                                       return_value=self.kb))

        self.state = GameSessionState(
            "crud-api", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 3, "xp": 900, "gold": 10,
             "game_system": "dnd5e", "char_class": "战士",
             "attributes": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10}},
            username="cruduser",
        )
        self.state.world_state = WorldState(session_id="crud-api", _storage_dir=self.tmp.name)
        session_manager._sessions["crud-api"] = self.state

    async def asyncTearDown(self):
        session_manager._sessions.pop("crud-api", None)

    def client(self):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                                 base_url="http://test")


class TestWorldStateCrud(CrudRoutesBase):
    async def test_world_snapshot_shape(self):
        async with self.client() as client:
            response = await client.get("/api/game/crud-api/world?username=cruduser")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        for key in ("scene", "npcs", "locations", "plot_flags", "battlefield", "initiative"):
            self.assertIn(key, body)

    async def test_add_update_remove_npc(self):
        async with self.client() as client:
            added = await client.post("/api/game/crud-api/world?username=cruduser", json={
                "action": "add_npc", "target": "铁匠柯尔",
                "changes": {"role": "铁匠", "location": "灰石村", "attitude": "中立",
                            "hp": 12, "max_hp": 12, "ac": 12}})
            updated = await client.post("/api/game/crud-api/world?username=cruduser", json={
                "action": "update_npc", "target": "铁匠柯尔",
                "changes": {"attitude": "友好", "personality": "话少但热心"}})
            removed = await client.post("/api/game/crud-api/world?username=cruduser", json={
                "action": "remove_npc", "target": "铁匠柯尔"})

        self.assertEqual(added.status_code, 200)
        npcs = {n["name"]: n for n in added.json()["world"]["npcs"]}
        self.assertIn("铁匠柯尔", npcs)
        self.assertEqual(npcs["铁匠柯尔"]["role"], "铁匠")
        after = {n["name"]: n for n in updated.json()["world"]["npcs"]}
        self.assertEqual(after["铁匠柯尔"]["attitude"], "友好")
        self.assertEqual(after["铁匠柯尔"]["personality"], "话少但热心")
        self.assertEqual(removed.status_code, 200)
        self.assertNotIn("铁匠柯尔", {n["name"] for n in removed.json()["world"]["npcs"]})

    async def test_update_scene_via_route(self):
        async with self.client() as client:
            response = await client.post("/api/game/crud-api/world?username=cruduser", json={
                "action": "update_scene",
                "changes": {"current_location": "灰石村", "weather": "小雨"}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["world"]["scene"]["location"], "灰石村")

    async def test_missing_action_is_400(self):
        async with self.client() as client:
            response = await client.post("/api/game/crud-api/world?username=cruduser", json={})
        self.assertEqual(response.status_code, 400)

    async def test_world_rule_keeps_world_snapshot_readable(self):
        """世界规则是纯文本：写入后 /world 仍必须能读（dict(字符串) 会直接 500）。"""
        async with self.client() as client:
            written = await client.post("/api/game/crud-api/world?username=cruduser", json={
                "action": "set_world_rule", "target": "本世界没有神祇，魔法稀少。"})
            read = await client.get("/api/game/crud-api/world?username=cruduser")

        self.assertEqual(written.status_code, 200)
        self.assertEqual(read.status_code, 200, "设置世界规则后快照不能打不开")
        self.assertIn("魔法稀少", str(read.json()["world_rules"]))

    async def test_character_note_crud_and_player_visibility(self):
        """角色笔记是玩家可见内容，此前只有 DM 能写：补增/改/删与可见性。"""
        base = "/api/game/crud-api/world?username=cruduser"
        journal_url = "/api/game/crud-api/journal?username=cruduser"
        async with self.client() as client:
            added = await client.post(base, json={
                "action": "add_note", "target": "铁匠柯尔",
                "changes": {"target_type": "npc", "comment": "他右手有旧伤",
                            "clue": "像是矿难留下的"}})
            snapshot = await client.get(base)
            journal = await client.get(journal_url)
            hidden = await client.post(base, json={
                "action": "update_note", "target": "铁匠柯尔",
                "changes": {"target_type": "npc", "comment": "他在隐瞒矿难的真相",
                            "visible": False}})
            journal_hidden = await client.get(journal_url)
            removed = await client.post(base, json={
                "action": "remove_character_note", "target": "铁匠柯尔",
                "changes": {"target_type": "npc"}})
            after = await client.get(base)

        self.assertEqual(added.status_code, 200)
        notes = {n["target"]: n for n in snapshot.json()["notes"]}
        self.assertIn("铁匠柯尔", notes)
        self.assertEqual(notes["铁匠柯尔"]["clue"], "像是矿难留下的")
        self.assertTrue(notes["铁匠柯尔"]["visible"])
        self.assertEqual([n["target"] for n in journal.json()["character_notes"]["npc_notes"]],
                         ["铁匠柯尔"])
        self.assertEqual(hidden.status_code, 200)
        hidden_note = {n["target"]: n for n in hidden.json()["world"]["notes"]}["铁匠柯尔"]
        self.assertEqual(hidden_note["comment"], "他在隐瞒矿难的真相")
        self.assertFalse(hidden_note["visible"])
        self.assertEqual(journal_hidden.json()["character_notes"]["npc_notes"], [],
                         "visible=False 的笔记不该出现在玩家笔记里")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(after.json()["notes"], [])

    async def test_unknown_session_is_404(self):
        async with self.client() as client:
            response = await client.get("/api/game/nope/world?username=cruduser")
        self.assertEqual(response.status_code, 404)

    async def test_delete_session_clears_memory_and_world_state_file(self):
        """会话删除：既是 CRUD 的"删"，也顺带解决临时会话清理。"""
        self.state.world_state.save()
        path = Path(self.tmp.name) / "crud-api.json"
        self.assertTrue(path.exists(), "前置条件：世界状态已落盘")
        async with self.client() as client:
            deleted = await client.delete("/api/game/crud-api?username=cruduser")
            after = await client.get("/api/game/crud-api/world?username=cruduser")
            someone_else = await client.delete("/api/game/crud-api?username=other")

        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json()["deleted"])
        self.assertFalse(path.exists(), "删会话要连世界状态文件一起清掉")
        self.assertEqual(after.status_code, 404)
        self.assertEqual(someone_else.status_code, 404, "别人的用户名不能删掉你的会话")


class TestCharacterStateCrud(CrudRoutesBase):
    async def test_session_settings_patch(self):
        async with self.client() as client:
            before = await client.get("/api/game/crud-api/settings?username=cruduser")
            response = await client.patch("/api/game/crud-api/settings?username=cruduser", json={
                "model_name": "deepseek-chat", "play_mode": "lite",
                "thinking_strength": "low", "api_key": "sk-test-not-echoed"})
            bad = await client.patch("/api/game/crud-api/settings?username=cruduser",
                                     json={"play_mode": "turbo"})
            empty = await client.patch("/api/game/crud-api/settings?username=cruduser", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(before.status_code, 200)
        self.assertNotIn("api_key", before.json(), "读取设置不回显 API Key")
        body = response.json()
        self.assertEqual(body["settings"]["model_name"], "deepseek-chat")
        self.assertEqual(body["settings"]["play_mode"], "lite")
        self.assertEqual(body["settings"]["thinking_strength"], "low")
        self.assertNotIn("sk-test", str(body), "API Key 不能在响应里回显")
        self.assertEqual(self.state.api_key, "sk-test-not-echoed", "但确实写入了会话")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(empty.status_code, 400)

    async def test_state_snapshot_and_updates(self):
        async with self.client() as client:
            before = await client.get("/api/game/crud-api/state?username=cruduser")
            changed = await client.post("/api/game/crud-api/state?username=cruduser", json={
                "changes": {"hp": -8, "conditions_add": ["中毒"], "exhaustion": 1,
                            "damage_resistances_add": ["火焰"]},
                "reason": "毒云陷阱"})
            after = await client.get("/api/game/crud-api/state?username=cruduser")

        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.json()["character_info"]["hp"], 30)
        self.assertEqual(changed.status_code, 200)
        info = after.json()["character_info"]
        self.assertEqual(info["hp"], 22)
        self.assertEqual(info["exhaustion"], 1)
        self.assertEqual(info["damage_resistances"], ["火焰"])
        self.assertTrue(any("中毒" in str(c) for c in after.json()["conditions"]))

    async def test_state_update_requires_changes(self):
        async with self.client() as client:
            response = await client.post("/api/game/crud-api/state?username=cruduser",
                                         json={"reason": "什么都没改"})
        self.assertEqual(response.status_code, 400)

    async def test_inventory_add_update_equip_remove(self):
        """背包物品的增删改查：add 只在不存在时追加，改描述/数量靠 update。"""
        def items(response):
            raw = response.json()["state"]["character_info"]["inventory"]
            return raw.get("items", []) if isinstance(raw, dict) else raw

        base = "/api/game/crud-api/state?username=cruduser"
        async with self.client() as client:
            added = await client.post(base, json={"changes": {"inventory_add": {
                "name": "治疗药水", "description": "恢复 2d4+2", "quantity": 2}}})
            updated = await client.post(base, json={"changes": {"inventory_update": {
                "name": "治疗药水", "description": "恢复 2d4+2；也可解一种毒", "quantity": 3}}})
            equipped = await client.post(base, json={"changes": {
                "inventory_equip": "治疗药水"}})
            renamed = await client.post(base, json={"changes": {"inventory_update": {
                "name": "治疗药水", "new_name": "高级治疗药水"}}})
            removed = await client.post(base, json={"changes": {
                "inventory_remove": "高级治疗药水"}})

        self.assertEqual(added.status_code, 200)
        self.assertEqual([i["name"] for i in items(added)], ["治疗药水"])
        self.assertEqual(items(updated)[0]["quantity"], 3)
        self.assertIn("解一种毒", items(updated)[0]["description"])
        self.assertTrue(items(equipped)[0]["equipped"])
        self.assertEqual([i["name"] for i in items(renamed)], ["高级治疗药水"])
        self.assertTrue(items(renamed)[0]["equipped"], "改名要保留装备状态")
        self.assertEqual(items(removed), [])

    async def test_levelup_and_state_share_the_same_sheet(self):
        async with self.client() as client:
            await client.post("/api/game/crud-api/state?username=cruduser", json={
                "changes": {"xp": 6000}, "reason": "通关奖励"})
            snapshot = await client.get("/api/game/crud-api/state?username=cruduser")
        self.assertGreaterEqual(snapshot.json()["character_info"]["level"], 4, "经验应触发升级")


class TestContentCrud(CrudRoutesBase):
    async def test_bestiary_update(self):
        from backend.media_manager import add_bestiary, list_bestiary
        item = add_bestiary("cruduser", "测试地精", "dnd5e", "矮小狡诈", {"HP": "7", "AC": "15"})
        async with self.client() as client:
            response = await client.put(f"/api/bestiary/{item['id']}?username=cruduser",
                                        json={"name": "测试地精·改", "stats": {"HP": "9", "AC": "16"},
                                              "tags": ["测试"]})
        self.assertEqual(response.status_code, 200)
        names = {b["name"] for b in list_bestiary("cruduser")}
        self.assertIn("测试地精·改", names)

    async def test_map_update(self):
        from backend.media_manager import add_map, list_maps
        item = add_map("cruduser", "测试城", "老城", "", locations=[], system="dnd5e")
        async with self.client() as client:
            response = await client.put(f"/api/maps/{item['id']}?username=cruduser",
                                        json={"description": "新城墙已修好"})
        self.assertEqual(response.status_code, 200)
        maps = {m["name"]: m for m in list_maps("cruduser")}
        self.assertIn("测试城", maps)
        self.assertIn("新城墙", str(maps["测试城"].get("description", "")))

    async def test_spell_update(self):
        from backend.media_manager import add_spell, list_spells
        item = add_spell("cruduser", "测试火球", "dnd5e", "丢一团火", level="3",
                         school="塑能", classes=["法师"])
        async with self.client() as client:
            response = await client.put(f"/api/spells/{item['id']}?username=cruduser",
                                        json={"description": "丢一团更大的火", "level": "3"})
        self.assertEqual(response.status_code, 200)
        spells = {s["name"]: s for s in list_spells("cruduser")}
        self.assertIn("测试火球", spells)
        self.assertIn("更大", str(spells["测试火球"].get("description", "")))

    async def test_knowledge_update_regenerates_chunks(self):
        doc = self.kb.add_note("旧标题", "旧内容" * 40, username="cruduser")
        async with self.client() as client:
            response = await client.put(f"/api/knowledge/{doc['id']}?username=cruduser",
                                        json={"title": "新标题", "content": "新内容" * 80,
                                              "tags": ["改过"]})
        self.assertEqual(response.status_code, 200)
        body = self.kb.get_document(doc["id"], "cruduser")
        self.assertEqual(body["title"], "新标题")
        self.assertIn("新内容", body["content"])
        self.assertGreater(len(body["chunks"]), 0, "正文改了要重新切块")

    async def test_knowledge_update_unknown_doc_is_404(self):
        async with self.client() as client:
            response = await client.put("/api/knowledge/nope?username=cruduser",
                                        json={"title": "x"})
        self.assertEqual(response.status_code, 404)

    async def test_extension_update(self):
        from backend.extension_manager import add_extension, list_extensions
        ext = add_extension("cruduser", "旧扩展", "描述", "内容" * 60)
        async with self.client() as client:
            response = await client.put(f"/api/extensions/{ext['id']}?username=cruduser",
                                        json={"name": "新扩展", "content": "新正文" * 120})
        self.assertEqual(response.status_code, 200)
        names = {e["name"] for e in list_extensions("cruduser")}
        self.assertIn("新扩展", names)


class TestSaveCrud(CrudRoutesBase):
    async def test_scenario_update_and_delete(self):
        """剧本编辑走 PUT（ScenarioStep 的「选择/编辑」路径），删除走 DELETE。"""
        from backend.scenario_store import create_scenario
        with patch("backend.scenario_store.SCENARIO_DIR", str(Path(self.tmp.name) / "scenarios")):
            scenario = create_scenario(
                world_outline="# 旧大纲\n开局在灰石村。", world_state_json="{}",
                reference_script="", custom_rules="", custom_classes=[], custom_skills=[],
                extra_attributes={}, notes="", title="旧标题", description="旧描述",
                summary="旧总结", system="dnd5e", tone="剑与魔法",
                character_name="岚", race="人类", char_class="战士", level=1, score=80,
                username="cruduser")
            async with self.client() as client:
                updated = await client.put(
                    f"/api/scenarios/{scenario.id}?username=cruduser",
                    json={"title": "新标题", "world_outline": "# 新大纲\n开局在港口。"})
                fetched = await client.get(f"/api/scenarios/{scenario.id}?username=cruduser")
                removed = await client.delete(f"/api/scenarios/{scenario.id}?username=cruduser")
                missing = await client.get(f"/api/scenarios/{scenario.id}?username=cruduser")

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["meta"]["title"], "新标题")
        self.assertIn("港口", fetched.json()["world_outline"])
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(missing.status_code, 404)

    async def test_rename_save(self):
        from backend.save_manager import create_save, list_saves
        save = create_save(self.state, label="自动存档", auto=True)
        async with self.client() as client:
            response = await client.put(f"/api/saves/{save['id']}?username=cruduser",
                                        json={"label": "打龙之前"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["save"]["label"], "打龙之前")
        labels = {s["id"]: s.get("label") for s in list_saves("cruduser")}
        self.assertEqual(labels.get(save["id"]), "打龙之前")

    async def test_rename_missing_save_is_404(self):
        async with self.client() as client:
            response = await client.put("/api/saves/nope?username=cruduser", json={"label": "x"})
        self.assertEqual(response.status_code, 404)

    async def test_rename_requires_label(self):
        from backend.save_manager import create_save
        save = create_save(self.state, label="存档", auto=True)
        async with self.client() as client:
            response = await client.put(f"/api/saves/{save['id']}?username=cruduser", json={})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
