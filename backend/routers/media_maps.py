"""地图接口：列表/新增/上传/删除/改名。

从 `backend/routers/media.py` 拆出；那边只做装配（`main.py` 仍只 include media 一个路由，
OpenAPI 路径与 `media` 标签都不变）。
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter()


@router.get("/api/maps")
async def list_maps_api(username: str = "default", scenario_id: str | None = None):
    from backend.media_manager import list_maps
    return {"maps": list_maps(username, scenario_id)}



@router.post("/api/maps")
async def add_map_api(payload: dict):
    from backend.media_manager import add_map, find_map_exact, update_map
    username = str(payload.get("username") or "default")
    name = str(payload.get("name") or "未命名地图")
    scenario_id = str(payload.get("scenario_id") or "")
    existing = find_map_exact(username, scenario_id or None, name)
    if existing:
        item = update_map(username, existing["id"], {
            "description": str(payload.get("description") or ""),
            # 前端通常先上传图片再 JSON 补充字段；这里必须保留已有图片，不能被空值覆盖。
            "image_path": str(payload.get("image_path") or existing.get("image_path") or ""),
            "locations": payload.get("locations") or [],
            "system": str(payload.get("system") or "custom"),
            "details": payload.get("details") or {},
            "scenario_id": scenario_id,
        })
    else:
        item = add_map(
            username=username,
            name=name,
            description=str(payload.get("description") or ""),
            image_path=str(payload.get("image_path") or ""),
            locations=payload.get("locations") or [],
            system=str(payload.get("system") or "custom"),
            details=payload.get("details") or {},
            scenario_id=scenario_id,
        )
    return {"map": item}



@router.post("/api/maps/upload")
async def upload_map_api(
    file: UploadFile = File(...),
    username: str = Form("default"),
    name: str = Form("未命名地图"),
    description: str = Form(""),
    system: str = Form("custom"),
    locations: str = Form("[]"),
    scenario_id: str = Form(""),
):
    from backend.media_manager import add_map, find_map_exact, save_image, update_map
    import json as _json
    data = await file.read()
    image_path = save_image(username, data, file.filename or "map.png")
    try:
        locs = _json.loads(locations) if locations.strip() else []
    except Exception:
        locs = []
    existing = find_map_exact(username, scenario_id or None, name)
    if existing:
        item = update_map(username, existing["id"], {
            "description": description, "image_path": image_path, "locations": locs,
            "system": system, "scenario_id": scenario_id,
        })
    else:
        item = add_map(username, name, description, image_path, locs, system, scenario_id=scenario_id)
    return {"map": item}



@router.delete("/api/maps/{map_id}")
async def delete_map_api(map_id: str, username: str = "default"):
    from backend.media_manager import delete_map
    if not delete_map(username, map_id):
        raise HTTPException(status_code=404, detail="地图不存在")
    return {"deleted": True}


@router.put("/api/maps/{map_id}")
async def update_map_api(map_id: str, payload: dict, username: str = "default"):
    """编辑地图/城市条目（名称/描述/地点/系统/备注）。"""
    from backend.media_manager import update_map
    changes = {k: v for k, v in payload.items() if k not in ("username",)}
    result = update_map(username, map_id, changes)
    if result is None:
        raise HTTPException(status_code=404, detail="地图不存在")
    return {"map": result}
