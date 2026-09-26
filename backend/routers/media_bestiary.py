"""生物图鉴接口：列表/新增/上传/删除/改名。

从 `backend/routers/media.py` 拆出；那边只做装配（`main.py` 仍只 include media 一个路由，
OpenAPI 路径与 `media` 标签都不变）。
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter()


@router.get("/api/bestiary")
async def list_bestiary_api(username: str = "default", scenario_id: str | None = None):
    from backend.media_manager import list_bestiary
    return {"bestiary": list_bestiary(username, scenario_id)}



@router.post("/api/bestiary")
async def add_bestiary_api(payload: dict):
    from backend.media_manager import add_bestiary, find_bestiary_exact, update_bestiary
    username = str(payload.get("username") or "default")
    name = str(payload.get("name") or "未命名生物")
    scenario_id = str(payload.get("scenario_id") or "")
    # 只更新同作用域条目；剧本内同名通用图鉴不会被改写。
    existing = find_bestiary_exact(username, scenario_id or None, name)
    if existing:
        item = update_bestiary(username, existing["id"], {
            "system": str(payload.get("system") or "custom"),
            "description": str(payload.get("description") or ""),
            "stats": payload.get("stats") or {},
            # 前端通常先上传图片再 JSON 补充字段；这里必须保留已有图片，不能被空值覆盖。
            "image_path": str(payload.get("image_path") or existing.get("image_path") or ""),
            "tags": payload.get("tags") or [],
            "details": payload.get("details") or {},
            "scenario_id": scenario_id,
        })
    else:
        item = add_bestiary(
            username=username,
            name=name,
            system=str(payload.get("system") or "custom"),
            description=str(payload.get("description") or ""),
            stats=payload.get("stats") or {},
            image_path=str(payload.get("image_path") or ""),
            tags=payload.get("tags") or [],
            details=payload.get("details") or {},
            scenario_id=scenario_id,
        )
    return {"bestiary": item}



@router.post("/api/bestiary/upload")
async def upload_bestiary_api(
    file: UploadFile = File(...),
    username: str = Form("default"),
    name: str = Form("未命名生物"),
    system: str = Form("custom"),
    description: str = Form(""),
    stats: str = Form("{}"),
    tags: str = Form(""),
    scenario_id: str = Form(""),
):
    from backend.media_manager import add_bestiary, find_bestiary_exact, save_image, update_bestiary
    import json as _json
    data = await file.read()
    image_path = save_image(username, data, file.filename or "creature.png")
    try:
        stats_data = _json.loads(stats) if stats.strip() else {}
    except Exception:
        stats_data = {}
    tags_list = [t.strip() for t in tags.split(",") if t.strip()]
    # 只更新同作用域条目；剧本内同名通用图鉴不会被覆盖。
    existing = find_bestiary_exact(username, scenario_id or None, name)
    if existing:
        item = update_bestiary(username, existing["id"], {
            "system": system,
            "description": description, "stats": stats_data, "image_path": image_path,
            "tags": tags_list, "scenario_id": scenario_id,
        })
    else:
        item = add_bestiary(username, name, system, description, stats_data, image_path,
                            tags_list, scenario_id=scenario_id)
    return {"bestiary": item}



@router.delete("/api/bestiary/{beast_id}")
async def delete_bestiary_api(beast_id: str, username: str = "default"):
    from backend.media_manager import delete_bestiary
    if not delete_bestiary(username, beast_id):
        raise HTTPException(status_code=404, detail="生物不存在")
    return {"deleted": True}


@router.put("/api/bestiary/{beast_id}")
async def update_bestiary_api(beast_id: str, payload: dict, username: str = "default"):
    """编辑图鉴条目（数值 stats / 详情 details / 标签 / 描述 / 所属剧本）。"""
    from backend.media_manager import update_bestiary
    changes = {k: v for k, v in payload.items() if k not in ("username",)}
    result = update_bestiary(username, beast_id, changes)
    if result is None:
        raise HTTPException(status_code=404, detail="生物不存在")
    return {"beast": result}
