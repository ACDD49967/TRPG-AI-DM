"""地图、生物图鉴、角色图片等媒体资源管理（租户隔离）。"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.default_content import CLASSIC_BESTIARY, COMMON_CITIES

MEDIA_ROOT = Path("media")


def _user_media_dir(username: str) -> Path:
    safe = "".join(c for c in (username or "default") if c.isalnum() or c in "._-") or "default"
    return MEDIA_ROOT / safe


def _images_dir(username: str) -> Path:
    d = _user_media_dir(username) / "images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meta_path(username: str, kind: str) -> Path:
    return _user_media_dir(username) / f"{kind}.json"


def _load_meta(username: str, kind: str) -> list[dict]:
    p = _meta_path(username, kind)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_meta(username: str, kind: str, items: list[dict]):
    p = _meta_path(username, kind)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_seeded(username: str):
    """为指定用户写入一次内置经典生物与城市背景（幂等）。"""
    user_dir = _user_media_dir(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    marker = user_dir / "seeded.json"
    if marker.exists():
        return
    for beast in CLASSIC_BESTIARY:
        add_bestiary(
            username=username,
            name=beast["name"],
            system=beast["system"],
            description=beast["description"],
            stats=beast.get("stats", {}),
            image_path="",
            tags=beast.get("tags", []),
        )
    for city in COMMON_CITIES:
        add_map(
            username=username,
            name=city["name"],
            description=city["description"],
            image_path="",
            locations=city.get("locations", []),
            system=city.get("system", "custom"),
        )
    marker.write_text("1", encoding="utf-8")


def save_image(username: str, data: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        ext = ".png"
    img_id = uuid.uuid4().hex[:16]
    path = _images_dir(username) / f"{img_id}{ext}"
    path.write_bytes(data)
    return f"/media/{_user_media_dir(username).name}/images/{img_id}{ext}"


def add_map(username: str, name: str, description: str, image_path: str,
            locations: list[dict] | None = None, system: str = "custom") -> dict:
    items = _load_meta(username, "maps")
    item = {
        "id": uuid.uuid4().hex[:16],
        "name": name or "未命名地图",
        "description": description or "",
        "image_path": image_path,
        "locations": locations or [],
        "system": system,
        "created_at": datetime.now().isoformat(),
    }
    items.append(item)
    _save_meta(username, "maps", items)
    return item


def list_maps(username: str) -> list[dict]:
    ensure_seeded(username)
    return _load_meta(username, "maps")


def delete_map(username: str, map_id: str) -> bool:
    items = _load_meta(username, "maps")
    new = [i for i in items if i["id"] != map_id]
    if len(new) == len(items):
        return False
    _save_meta(username, "maps", new)
    return True


def add_bestiary(username: str, name: str, system: str, description: str,
                 stats: dict | None = None, image_path: str = "", tags: list[str] | None = None) -> dict:
    items = _load_meta(username, "bestiary")
    item = {
        "id": uuid.uuid4().hex[:16],
        "name": name or "未命名生物",
        "system": system,
        "description": description or "",
        "stats": stats or {},
        "image_path": image_path,
        "tags": tags or [],
        "created_at": datetime.now().isoformat(),
    }
    items.append(item)
    _save_meta(username, "bestiary", items)
    return item


def list_bestiary(username: str) -> list[dict]:
    ensure_seeded(username)
    return _load_meta(username, "bestiary")


def delete_bestiary(username: str, beast_id: str) -> bool:
    items = _load_meta(username, "bestiary")
    new = [i for i in items if i["id"] != beast_id]
    if len(new) == len(items):
        return False
    _save_meta(username, "bestiary", new)
    return True
