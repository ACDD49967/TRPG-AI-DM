"""媒体条目机翻：SRD 法术与地点/生物描述的批量中文翻译。

从 `backend/routers/media.py` 搬出——那边两个路由各 74-78 行，都是
"取会话 LLM 配置 → 分批调用 → 解析 JSON → 落盘 → 推事件"的流水线。
路由只保留归属校验与参数检查；HTTP 语义不变（校验失败仍抛 HTTPException）。
"""
from __future__ import annotations

import json

from fastapi import HTTPException
from openai import AsyncOpenAI

from backend.config import ensure_valid_api_key, settings
from backend.engine.prompt_guard import extract_json_array, extract_json_object, sanitize_user_text
from backend.engine.session import push_event


async def translate_srd_spells(state, payload: dict) -> dict:
    """把带 SRD 标签且尚无中文描述的法术批量翻译（名称 + 描述）。"""
    try:
        api_key = ensure_valid_api_key(state.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from backend.media_manager import _load_meta, _save_meta, list_spells

    list_spells(state.username or "default", None)  # 确保已导入
    items = _load_meta(state.username or "default", "spells")
    spell_ids = payload.get("spell_ids") or []
    targets = [
        s for s in items
        if "SRD" in (s.get("tags") or []) and not s.get("description_zh")
        and (not spell_ids or s.get("id") in spell_ids)
    ]
    if not targets:
        return {"translated": 0, "remaining": 0, "message": "没有需要翻译的 SRD 法术"}

    client = AsyncOpenAI(api_key=api_key, base_url=getattr(state, "base_url", None) or settings.LLM_BASE_URL)
    model = state.model_name or settings.LLM_MODEL_NAME
    if not model:
        raise HTTPException(status_code=400, detail="当前会话没有可用模型")

    items_by_id = {s["id"]: s for s in items}
    translated = 0
    batch_size = 15
    for start in range(0, len(targets), batch_size):
        batch = targets[start:start + batch_size]
        prompt = (
            "你是 D&D 5e 法术简体中文翻译器。将下面的 JSON 数组中每个法术的 name 与 description 翻译成简体中文。"
            "保留 D&D 规则术语：豁免、施法距离、法术成分(V/S/M)、专注、动作、反应、环位、学派等。"
            "description 保持完整并符合中文 TRPG 表达。只输出 JSON 数组，不要解释。\n"
            + json.dumps([
                {"name": s["name"], "description": s.get("description", "")} for s in batch
            ], ensure_ascii=False)
        )
        prompt = sanitize_user_text(prompt)
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4000,
            )
            text = (resp.choices[0].message.content or "").strip()
            text = text.replace("```json", "").replace("```", "").strip()
            try:
                data = extract_json_array(text)
            except Exception:
                try:
                    data = extract_json_object(text).get("spells") or extract_json_object(text).get("translations") or []
                except Exception:
                    continue
            if not isinstance(data, list):
                continue
            for i, spell in enumerate(batch):
                if i >= len(data):
                    break
                item = items_by_id.get(spell["id"])
                if item is None:
                    continue
                item["name_zh"] = str(data[i].get("name") or spell["name"])
                item["description_zh"] = str(data[i].get("description") or spell.get("description", ""))
                translated += 1
        except Exception:
            continue

    if translated:
        _save_meta(state.username or "default", "spells", items)
        try:
            await push_event(state, "spells_updated", {})
        except Exception:
            pass

    remaining = len(targets) - translated
    return {"translated": translated, "remaining": remaining}

async def translate_media(state, payload: dict, kind: str) -> dict:
    """批量翻译地点（maps）或生物（bestiary）的 description。"""
    try:
        api_key = ensure_valid_api_key(state.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from backend.media_manager import list_bestiary, list_maps, _load_meta, _save_meta

    if kind == "locations":
        list_maps(state.username or "default", None)
        items = _load_meta(state.username or "default", "maps")
    else:
        list_bestiary(state.username or "default", None)
        items = _load_meta(state.username or "default", "bestiary")
    ids = payload.get("item_ids") or []
    targets = [
        item for item in items
        if not item.get("description_zh") and (not ids or item.get("id") in ids)
    ]
    if not targets:
        return {"translated": 0, "remaining": 0, "message": "没有需要翻译的条目"}

    client = AsyncOpenAI(api_key=api_key, base_url=getattr(state, "base_url", None) or settings.LLM_BASE_URL)
    model = state.model_name or settings.LLM_MODEL_NAME
    if not model:
        raise HTTPException(status_code=400, detail="当前会话没有可用模型")

    items_by_id = {i["id"]: i for i in items}
    translated = 0
    batch_size = 15
    for start in range(0, len(targets), batch_size):
        batch = targets[start:start + batch_size]
        prompt = (
            "你是 TRPG 简体中文翻译器。把下面的 JSON 数组中每个条目的 description 翻译成简体中文。"
            "保留专有名词（可音译），不要改变结构。只输出 JSON 数组：[{\"description\":\"中文\"}]。\n"
            + json.dumps([{"name": i.get("name", ""), "description": i.get("description", "")} for i in batch], ensure_ascii=False)
        )
        prompt = sanitize_user_text(prompt)
        try:
            resp = await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}],
                temperature=0.2, max_tokens=3000,
            )
            text = (resp.choices[0].message.content or "").strip().replace("```json", "").replace("```", "").strip()
            try:
                data = extract_json_array(text)
            except Exception:
                continue
            if not isinstance(data, list):
                continue
            for i, item in enumerate(batch):
                if i >= len(data):
                    break
                target = items_by_id.get(item["id"])
                if target is None:
                    continue
                target["description_zh"] = str(data[i].get("description") or target.get("description", ""))
                translated += 1
        except Exception:
            continue

    if translated:
        _save_meta(state.username or "default", "maps" if kind == "locations" else "bestiary", items)
        try:
            await push_event(state, "maps_updated" if kind == "locations" else "bestiary_updated", {})
        except Exception:
            pass

    remaining = len(targets) - translated
    return {"translated": translated, "remaining": remaining}
