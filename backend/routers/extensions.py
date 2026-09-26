"""扩展包管理。"""
from __future__ import annotations


from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI

from backend.config import ensure_valid_api_key, settings
from backend.engine.prompt_guard import extract_json_object, sanitize_user_text
from backend.engine.session import (
    get_session_for_user,
)

# 兼容搬移前的调用写法：归属校验直接复用 session 层实现
_get_session_for_user = get_session_for_user

# 装配仍在 backend.main：这里只提供本域路由
router = APIRouter(tags=["extensions"])



@router.get("/api/extensions")
async def list_extensions_api(username: str = "default"):
    from backend.extension_manager import list_extensions
    return {"extensions": list_extensions(username)}



@router.post("/api/extensions")
async def add_extension_api(payload: dict):
    from backend.extension_manager import add_extension
    username = str(payload.get("username") or "default")
    ext = add_extension(
        username=username,
        name=str(payload.get("name") or "未命名扩展包"),
        description=str(payload.get("description") or ""),
        content=str(payload.get("content") or ""),
        system=str(payload.get("system") or "custom"),
        tags=payload.get("tags") or [],
        source=str(payload.get("source") or "user"),
    )
    return {"extension": ext}



@router.post("/api/extensions/generate")
async def generate_extension_api(payload: dict):
    """由 LLM 生成扩展包 JSON。"""
    from backend.extension_manager import add_extension
    username = str(payload.get("username") or "default")
    description = str(payload.get("description") or "")
    system = str(payload.get("system") or "custom")
    api_key = payload.get("api_key") or settings.LLM_API_KEY
    model = payload.get("model_name") or settings.LLM_MODEL_NAME
    base_url = payload.get("base_url") or settings.LLM_BASE_URL
    if not model:
        raise HTTPException(status_code=400, detail="请先选择模型")
    try:
        api_key = ensure_valid_api_key(api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not description.strip():
        raise HTTPException(status_code=400, detail="请描述你想生成的扩展包")

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    prompt = f"""请为一个 TRPG 游戏生成一个扩展包，必须返回合法 JSON，不要 Markdown 代码块，不要其他文本。

规则系统：{system}
扩展包需求：{description}

JSON 格式：
{{
  "name": "扩展包名称",
  "description": "一句话简介",
  "content": "扩展包具体内容：新增规则、职业/调查员能力、物品、NPC、事件、特殊机制等，Markdown 格式，300-800字",
  "tags": ["标签1", "标签2"]
}}"""
    prompt = sanitize_user_text(prompt)
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一位TRPG扩展包设计者。只返回合法JSON。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
            temperature=0.8,
        )
        text = (resp.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        try:
            data = extract_json_object(text)
        except Exception:
            raise HTTPException(status_code=502, detail="扩展包生成返回的不是合法JSON")
        ext = add_extension(
            username=username,
            name=str(data.get("name") or "LLM生成扩展包"),
            description=str(data.get("description") or ""),
            content=str(data.get("content") or ""),
            system=system,
            tags=data.get("tags") or ["LLM生成"],
            source="llm",
        )
        return {"extension": ext}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扩展包生成失败: {e}") from e



@router.delete("/api/extensions/{ext_id}")
async def delete_extension_api(ext_id: str, username: str = "default"):
    from backend.extension_manager import delete_extension
    if not delete_extension(username, ext_id):
        raise HTTPException(status_code=404, detail="扩展包不存在")
    return {"deleted": True}


@router.put("/api/extensions/{ext_id}")
async def update_extension_api(ext_id: str, payload: dict, username: str = "default"):
    """编辑扩展包（名称/描述/正文/规则系统/标签）；正文变了会重新切块。"""
    from backend.extension_manager import update_extension
    ext = update_extension(
        username, ext_id,
        name=payload.get("name"),
        description=payload.get("description"),
        content=payload.get("content"),
        system=payload.get("system"),
        tags=payload.get("tags"),
    )
    if ext is None:
        raise HTTPException(status_code=404, detail="扩展包不存在")
    return {"extension": {"id": ext.get("id"), "name": ext.get("name"),
                          "description": ext.get("description"),
                          "chunks": len(ext.get("chunks") or [])}}
