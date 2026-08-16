"""全流程冒烟测试：覆盖健康检查、知识库、扩展包、媒体、游戏创建、存档/读档。"""

from fastapi.testclient import TestClient

from backend.main import app


def main():
    with TestClient(app) as c:
        # 1. 健康检查
        r = c.get("/api/health")
        assert r.status_code == 200, r.text
        print("[OK] health", r.json())

        # 2. 知识库
        r = c.get("/api/knowledge")
        assert r.status_code == 200
        print("[OK] knowledge list", len(r.json().get("documents", [])))
        r = c.post("/api/knowledge", json={"title": "冒烟测试知识", "content": "这是用于测试的知识内容。", "system": "custom"})
        assert r.status_code == 200, r.text
        doc_id = r.json()["doc"]["id"]
        r = c.post("/api/knowledge/retrieve", json={"query": "测试知识", "system": "custom", "top_k": 3})
        assert r.status_code == 200 and r.json().get("results")
        print("[OK] knowledge retrieve")
        r = c.delete(f"/api/knowledge/{doc_id}")
        assert r.status_code == 200

        # 3. 扩展包
        r = c.post("/api/extensions", json={"username": "__smoke__", "name": "测试扩展", "content": "测试扩展内容", "system": "dnd5e"})
        assert r.status_code == 200, r.text
        ext_id = r.json()["extension"]["id"]
        r = c.get("/api/extensions?username=__smoke__")
        assert r.status_code == 200 and any(x["id"] == ext_id for x in r.json()["extensions"])
        r = c.delete(f"/api/extensions/{ext_id}?username=__smoke__")
        assert r.status_code == 200
        print("[OK] extension add/list/delete")

        # 4. 地图/图鉴（触发内置 seed）
        r = c.get("/api/maps?username=__smoke__")
        assert r.status_code == 200 and r.json()["maps"]
        r = c.get("/api/bestiary?username=__smoke__")
        assert r.status_code == 200 and r.json()["bestiary"]
        print("[OK] maps/bestiary seed", len(r.json()["bestiary"]))

        # 5. 创建游戏（不调用 LLM）
        r = c.post("/api/game/new", json={
            "username": "__smoke__",
            "character_name": "测试角色",
            "race": "人类",
            "char_class": "战士",
            "attributes": {"str": 14, "dex": 12, "con": 14, "int": 10, "wis": 12, "cha": 8},
            "game_system": "dnd5e",
            "play_mode": "lite",
            "extension_ids": [],
        })
        assert r.status_code == 200, r.text
        session_id = r.json()["session_id"]
        print("[OK] game create", session_id)

        # 6. 手动存档
        r = c.post(f"/api/game/{session_id}/save", json={"label": "冒烟存档"})
        assert r.status_code == 200, r.text
        r = c.get("/api/saves?username=__smoke__")
        assert r.status_code == 200 and r.json()["saves"]
        save_id = r.json()["saves"][0]["id"]
        print("[OK] save", save_id)

        # 7. 载入存档
        r = c.post("/api/saves/load", json={"username": "__smoke__", "save_id": save_id})
        assert r.status_code == 200 and r.json()["session_id"]
        print("[OK] load save")

        # 8. 场景列表
        r = c.get("/api/scenarios")
        assert r.status_code == 200
        print("[OK] scenarios", len(r.json().get("scenarios", [])))

        print("\nAll smoke tests passed.")


if __name__ == "__main__":
    main()
