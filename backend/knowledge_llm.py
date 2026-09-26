"""知识库 → 图鉴注入：用 LLM 从文档里提取地点/生物/法术并补全字段。

从 `backend/routers/knowledge.py` 的 `knowledge_llm_process` 搬出：
路由只做参数校验，流水线（含每个条目的补全调用）在这里。
"""
from __future__ import annotations

import json

from openai import AsyncOpenAI

from backend.engine.prompt_guard import extract_json_object, sanitize_user_text


async def extract_media_entries(*, username: str, doc_id: str = "", scenario_id: str = "",
                                api_key: str, base_url: str, model: str) -> dict:
    from backend.knowledge_base import get_knowledge_base
    from backend.media_manager import add_bestiary, add_map, add_spell

    kb = get_knowledge_base()
    docs = kb.list_documents(username)
    if doc_id:
        docs = [d for d in docs if d["id"] == doc_id]
    if not docs:
        return {"locations": 0, "creatures": 0, "spells": 0, "message": "没有可处理的知识库文档"}

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    counts = {"locations": 0, "creatures": 0, "spells": 0}

    async def _complete_media_entry(kind: str, item: dict) -> dict:
        """对缺失字段的图鉴条目调用 LLM 补全，保证完整性。"""
        if kind == "locations":
            required = ["name", "description", "type", "status", "culture", "notable_figures", "dangers"]
        elif kind == "creatures":
            required = ["name", "description", "stats"]
            if all(item.get(k) for k in required):
                stats = item.get("stats") or {}
                if all(k in stats for k in ("力量", "敏捷", "体质", "智力", "感知", "魅力", "技能", "特性", "动作")):
                    return item
        else:
            required = ["name", "level", "school", "description", "casting_time", "range", "components", "duration", "classes"]
        if all(item.get(k) for k in required):
            return item
        kind_label = {"locations": "地点", "creatures": "生物", "spells": "法术"}.get(kind, kind)
        prompt = (
            f"你是 TRPG {kind_label}图鉴补全器。下面是一个不完整的 {kind_label} JSON，请补全缺失字段并输出完整 JSON。"
            "地点需要 name/description/type/status/culture/notable_figures/dangers/related_locations/related_npcs/related_creatures；"
            "生物需要 name/description/stats(含 HP/AC/速度/六维/技能/特性/动作)/tags/related_locations/related_npcs；"
            "法术需要 name/level/school/description/casting_time/range/components/duration/classes。不要解释，只输出 JSON。\n"
            + json.dumps(item, ensure_ascii=False)
        )
        try:
            resp = await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}],
                temperature=0.2, max_tokens=2000,
            )
            text = (resp.choices[0].message.content or "").strip().replace("```json", "").replace("```", "").strip()
            try:
                completed = extract_json_object(text)
            except Exception:
                completed = {}
            if isinstance(completed, dict):
                merged = {**item, **completed}
                if kind == "creatures":
                    stats = {**item.get("stats", {}), **(completed.get("stats") or {})}
                    merged["stats"] = stats
                return merged
        except Exception:
            pass
        return item

    for doc in docs:
        full = kb.get_document(doc["id"], username)
        content = sanitize_user_text((full or {}).get("content", "") or "")
        if len(content) < 200:
            continue
        prompt = (
            "你是 TRPG 图鉴注入器。从以下知识文档中提取可作为图鉴条目的结构化数据，并建立实体关联。"
            "只输出 JSON 对象：{\"locations\":[{\"name\":\"\",\"description\":\"\",\"type\":\"\",\"status\":\"\",\"culture\":\"\",\"notable_figures\":\"\",\"dangers\":\"\",\"related_locations\":[],\"related_npcs\":[],\"related_creatures\":[]}],"
            "\"creatures\":[{\"name\":\"\",\"description\":\"\",\"stats\":{\"HP\":\"\",\"AC\":\"\",\"速度\":\"\",\"力量\":\"\",\"敏捷\":\"\",\"体质\":\"\",\"智力\":\"\",\"感知\":\"\",\"魅力\":\"\",\"技能\":\"\",\"特性\":\"\",\"动作\":\"\"},\"tags\":[],\"related_locations\":[],\"related_npcs\":[]}],"
            "\"spells\":[{\"name\":\"\",\"level\":\"\",\"school\":\"\",\"description\":\"\",\"casting_time\":\"\",\"range\":\"\",\"components\":\"\",\"duration\":\"\",\"classes\":[]}]}。"
            "没有的数组输出空数组，不要解释。\n\n文档：\n" + content[:12000]
        )
        try:
            resp = await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}],
                temperature=0.2, max_tokens=4000,
            )
            text = (resp.choices[0].message.content or "").strip().replace("```json", "").replace("```", "").strip()
            try:
                data = extract_json_object(text)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for loc in data.get("locations") or []:
                if not isinstance(loc, dict) or not str(loc.get("name", "")).strip():
                    continue
                loc = await _complete_media_entry("locations", loc)
                add_map(username, str(loc["name"]).strip(), str(loc.get("description", "") or "")[:500], "",
                        [], doc.get("system", "custom"),
                        details={"type": loc.get("type", ""), "status": loc.get("status", ""), "source": "知识库·LLM"},
                        scenario_id=scenario_id)
                counts["locations"] += 1
            for cr in data.get("creatures") or []:
                if not isinstance(cr, dict) or not str(cr.get("name", "")).strip():
                    continue
                cr = await _complete_media_entry("creatures", cr)
                add_bestiary(username, str(cr["name"]).strip(), doc.get("system", "custom"),
                             str(cr.get("description", "") or ""), cr.get("stats") or {},
                             tags=(cr.get("tags") or []) + ["知识库", "LLM"],
                             details={"source": "知识库·LLM"}, scenario_id=scenario_id)
                counts["creatures"] += 1
            for sp in data.get("spells") or []:
                if not isinstance(sp, dict) or not str(sp.get("name", "")).strip():
                    continue
                sp = await _complete_media_entry("spells", sp)
                add_spell(username, str(sp["name"]).strip(), doc.get("system", "custom"),
                          str(sp.get("description", "") or ""), level=str(sp.get("level", "0")),
                          school=str(sp.get("school", "") or ""), casting_time=str(sp.get("casting_time", "") or ""),
                          range_=str(sp.get("range", "") or ""), components=str(sp.get("components", "") or ""),
                          duration=str(sp.get("duration", "") or ""), classes=sp.get("classes") or [],
                          scenario_id=scenario_id, tags=["知识库", "LLM", "法术"])
                counts["spells"] += 1
        except Exception:
            continue

    return {"locations": counts["locations"], "creatures": counts["creatures"], "spells": counts["spells"]}
