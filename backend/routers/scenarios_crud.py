"""剧本的列表 / 详情 / 游玩计数 / 改名 / 删除。

从 `backend/routers/scenarios.py` 拆出；导入（含切分与建世界）在 scenarios_import。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/api/scenarios")
async def list_scenarios(username: str = "default"):
    """列出当前用户可见的剧本（按用户名隔离）。"""
    from backend.scenario_store import list_scenarios as ls
    return {"scenarios": ls(username)}



@router.get("/api/classic-scenarios")
async def classic_scenarios():
    """列出公开/免费的经典剧本参考（仅名称与简介，不包含受版权保护的完整正文）。"""
    from backend.classic_scenarios import list_classic_scenarios
    return {"scenarios": list_classic_scenarios()}


@router.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str, username: str = "default"):
    """加载一个已保存的剧本（按用户名隔离）。"""
    from backend.scenario_store import Scenario
    s = Scenario.load(scenario_id, username)
    if s is None:
        raise HTTPException(status_code=404, detail="剧本不存在")
    return {
        "id": s.id,
        "meta": s.meta.to_dict(),
        "world_outline": s.world_outline,
        "world_state_json": s.world_state_json,
        "reference_script": s.reference_script,
        "source_chunks": s.source_chunks,
        "custom_rules": s.custom_rules,
        "custom_classes": s.custom_classes,
        "custom_skills": s.custom_skills,
        "extra_attributes": s.extra_attributes,
        "summary": s.meta.summary,
        "system": s.meta.system,
        "notes": s.notes,
    }



@router.post("/api/scenarios/{scenario_id}/play")
async def record_scenario_play(scenario_id: str, username: str = "default"):
    """记录剧本被游玩一次（按用户名隔离）。"""
    from backend.scenario_store import Scenario
    s = Scenario.load(scenario_id, username)
    if s is None:
        raise HTTPException(status_code=404, detail="剧本不存在")
    s.record_play()
    return {"total_sessions": s.meta.total_sessions}



@router.delete("/api/scenarios/{scenario_id}")
async def delete_scenario_endpoint(scenario_id: str, username: str = "default"):
    """删除一个剧本（按用户名隔离）。"""
    from backend.scenario_store import delete_scenario
    if not delete_scenario(scenario_id, username):
        raise HTTPException(status_code=404, detail="剧本不存在")
    return {"deleted": True}



@router.put("/api/scenarios/{scenario_id}")
async def update_scenario_endpoint(scenario_id: str, payload: dict, username: str = "default"):
    """编辑剧本：更新标题/描述/总结/备注/大纲/自定义内容（按用户名隔离）。"""
    from backend.scenario_store import Scenario
    s = Scenario.load(scenario_id, username)
    if s is None:
        raise HTTPException(status_code=404, detail="剧本不存在")
    if payload.get("title") is not None:
        s.meta.title = str(payload["title"])[:120]
    if payload.get("description") is not None:
        s.meta.description = str(payload["description"])[:500]
    if payload.get("summary") is not None:
        s.meta.summary = str(payload["summary"])
    if payload.get("notes") is not None:
        s.notes = str(payload["notes"])
    if payload.get("world_outline") is not None:
        s.world_outline = str(payload["world_outline"])
    if payload.get("custom_rules") is not None:
        s.custom_rules = str(payload["custom_rules"])
    if payload.get("custom_classes") is not None:
        s.custom_classes = list(payload["custom_classes"]) or []
    if payload.get("custom_skills") is not None:
        s.custom_skills = list(payload["custom_skills"]) or []
    if payload.get("extra_attributes") is not None:
        s.extra_attributes = dict(payload["extra_attributes"]) or {}
    s.save()
    return {"updated": True, "id": s.id}
