"""CRUD 覆盖守护：每个"内容资源"都必须能增删改查（用户明确要求的能力）。

做法是读 FastAPI 的 OpenAPI：集合端点要有 GET+POST（查/增），
单项端点要有 PUT+DELETE（改/删）。

两个有意的例外，写在测试里当作"设计决策"而不是漏项：
- `tasks`：长任务用 `POST /api/tasks/{id}/cancel` 取消，不做物理删除；
- `media`：只有上传（`POST /api/media/character`），图片归属角色/NPC，
  删除走它们的 PUT（清空图片字段）或角色删除。
"""
import unittest
from collections import defaultdict

ROOT_RESOURCES = {
    # 资源名: (集合前缀, 单项前缀)
    "characters": ("/api/characters", "/api/characters/{card_id}"),
    "bestiary": ("/api/bestiary", "/api/bestiary/{beast_id}"),
    "extensions": ("/api/extensions", "/api/extensions/{ext_id}"),
    "knowledge": ("/api/knowledge", "/api/knowledge/{doc_id}"),
    "maps": ("/api/maps", "/api/maps/{map_id}"),
    "saves": ("/api/saves", "/api/saves/{save_id}"),
    "scenarios": ("/api/scenarios", "/api/scenarios/{scenario_id}"),
    "spells": ("/api/spells", "/api/spells/{spell_id}"),
    # 长期记忆：以前只能创建与检索，删改没有任何入口（玩家看不见系统记住了什么）
    "memories": ("/api/memories", "/api/memories/{mem_id}"),
}


class TestCrudCoverage(unittest.TestCase):
    def setUp(self):
        from backend.main import app

        self.paths = app.openapi().get("paths", {})

    def _verbs(self, prefix: str) -> set:
        out: set = set()
        for path, ops in self.paths.items():
            if path == prefix or path.startswith(prefix + "/"):
                out |= {m.upper() for m in ops}
        return out

    def test_each_content_resource_supports_crud(self):
        missing: list[str] = []
        for name, (collection, item) in ROOT_RESOURCES.items():
            with self.subTest(resource=name):
                collection_verbs = self._verbs(collection)
                item_verbs = self._verbs(item)
                for need in ("GET", "POST"):
                    if need not in collection_verbs:
                        missing.append(f"{name}: 集合端点缺 {need}（现有 {sorted(collection_verbs)}）")
                for need in ("PUT", "DELETE"):
                    if need not in item_verbs:
                        missing.append(f"{name}: 单项端点缺 {need}（现有 {sorted(item_verbs)}）")
        self.assertEqual(missing, [], "内容资源的增删改查不完整：\n" + "\n".join(missing))

    def test_documented_exceptions_stay_intentional(self):
        """任务用 cancel、媒体只上传——这两条是设计决策，别被"补 DELETE"顺手改掉。"""
        tasks = self._verbs("/api/tasks")
        self.assertIn("POST", tasks)
        self.assertTrue(any(p.endswith("/cancel") for p in self.paths
                            if p.startswith("/api/tasks/")),
                        "任务取消端点必须在")
        media = self._verbs("/api/media")
        self.assertEqual(media, {"POST"}, "媒体域目前只提供上传；若新增动词请同步更新本测试的说明")


if __name__ == "__main__":
    unittest.main()
