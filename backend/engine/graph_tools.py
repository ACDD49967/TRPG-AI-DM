"""知识图谱工具：实体关系查询、路径查询与图谱增量维护。

从 backend.engine.world_tools 拆出；dm_agent 反向再导出，保持既有调用方不变。
"""
from __future__ import annotations

import asyncio
import json
import re

from backend.engine.session import GameSessionState
from backend.engine.tool_shims import _safe_error_text, _client, _model


async def _exec_get_entity_graph(args: dict, state: GameSessionState) -> str:
    """局部子图查询工具：返回某实体周围的关系网络（含亲密度/置信度）。"""
    ws = getattr(state, "world_state", None)
    if ws is None:
        return "无世界状态"
    name = str(args.get("name", "") or "").strip()
    if not name:
        return "⚠ 需要 name"
    try:
        depth = max(1, min(2, int(args.get("depth", 1) or 1)))
    except (TypeError, ValueError):
        depth = 1
    from backend.engine.knowledge_graph import get_local_subgraph
    sub = get_local_subgraph(ws, name, depth=depth)
    if not sub["nodes"]:
        return f"⚠ 未找到实体: {name}"
    lines = [f"## 局部知识图谱: {name}"]
    for n in sub["nodes"]:
        extra = f" ({n.get('extra')})" if n.get("extra") else ""
        lines.append(f"- [{n.get('type')}] {n.get('label')}{extra}")
    if sub["edges"]:
        lines.append("### 关系")
        for e in sub["edges"]:
            extra = ""
            if e.get("strength") is not None:
                extra += f" 亲密度{e['strength']}"
            if e.get("confidence") is not None:
                extra += f" 置信度{e['confidence']}"
            if e.get("notes"):
                extra += f" 备注:{e['notes']}"
            lines.append(f"- {e['source']} --{e['relation']}--> {e['target']}{extra}")
    return "\n".join(lines)


# ── 知识图谱子AGENT（文本识别 + 关系更新） ─────────────────────

KG_AGENT_SYSTEM_PROMPT = """你是TRPG知识图谱维护专家。你的任务是从文本中识别实体与关系变化，并输出结构化JSON。

规则：
1. 只提取文本中明确出现或强烈暗示的关系，不要凭空编造。
2. 实体名必须尽量使用输入提供的“已知实体”，否则可创建新实体名。
3. relation 使用简洁英文或中文短语（如 ally/enemy/trust/betray/location/thread_link/co_involved）。
4. strength 为亲密度 0-100（越大关系越强），confidence 为置信度 0-1。
5. 只输出一个 JSON 对象，不要 Markdown、解释或多余文字。

输出格式：
{{"relations":[{{"source":"实体A","target":"实体B","relation":"ally","strength":70,"confidence":0.8,"notes":"一句话依据"}}]}}
"""


KG_AGENT_USER_PROMPT = """## 已知实体
{entities}

## 变化文本
{text}

## 提示
{hint}

请识别本次应新增/更新的关系，并输出JSON。"""


def _kg_extract_json(text: str) -> dict:
    """从子AGENT输出中稳健提取JSON对象。"""
    if not text:
        return {}
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if fence:
        t = fence.group(1).strip()
    start = t.find("{")
    end = t.rfind("}")
    if start >= 0 and end > start:
        t = t[start:end + 1]
    try:
        data = json.loads(t)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


async def _call_knowledge_graph_agent(state: GameSessionState, text: str, hint: str) -> dict:
    """调用知识图谱子AGENT进行文本识别，返回解析后的JSON或抛出异常。"""
    ws = getattr(state, "world_state", None)
    entity_names: list[str] = []
    if ws is not None:
        entity_names += [n.name for n in ws.npcs]
        entity_names += [l.name for l in ws.locations]
        entity_names += [str(c.get("name", "")) for c in ws.creatures if isinstance(c, dict)]
        entity_names += [f.key for f in ws.plot_flags]
    user_prompt = KG_AGENT_USER_PROMPT.format(
        entities="、".join(entity_names[:40]) or "（暂无）",
        text=text[:3000],
        hint=hint or "无",
    )
    client = _client(state)
    model = _model(state)
    resp = await asyncio.wait_for(
        client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": KG_AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
            temperature=0.2,
        ),
        timeout=40,
    )
    content = (resp.choices[0].message.content or "").strip()
    data = _kg_extract_json(content)
    if not data:
        raise ValueError("知识图谱子AGENT返回内容无法解析为JSON")
    return data


async def _exec_get_graph_path(args: dict, state: GameSessionState) -> str:
    """查询两个实体之间的最短关系路径。"""
    ws = getattr(state, "world_state", None)
    if ws is None:
        return "无世界状态"
    source = str(args.get("source", "") or "").strip()
    target = str(args.get("target", "") or "").strip()
    if not source or not target:
        return "⚠ 需要 source 与 target"
    try:
        max_depth = max(1, min(6, int(args.get("max_depth", 4) or 4)))
    except (TypeError, ValueError):
        max_depth = 4
    from backend.engine.knowledge_graph import get_graph_path
    path = get_graph_path(ws, source, target, max_depth=max_depth)
    if not path:
        return f"⚠ 未找到 {source} -> {target} 的路径（深度≤{max_depth}）"
    lines = [f"## 关系路径: {source} -> {target}"]
    for i, e in enumerate(path):
        extra = ""
        if e.get("strength") is not None:
            extra += f" 亲密度{e['strength']}"
        if e.get("confidence") is not None:
            extra += f" 置信度{e['confidence']}"
        lines.append(f"{i + 1}. {e['source']} --{e['relation']}--> {e['target']}{extra}")
    return "\n".join(lines)


async def _exec_update_knowledge_graph(args: dict, state: GameSessionState) -> str:
    """DM识别到图谱应变化时调用：子AGENT识别并更新关系，结果/错误回传给DM。"""
    ws = getattr(state, "world_state", None)
    if ws is None:
        return "无世界状态"
    text = str(args.get("text", "") or "").strip()
    hint = str(args.get("hint", "") or "").strip()
    if not text:
        return "未提供变化文本（text）"

    try:
        data = await _call_knowledge_graph_agent(state, text, hint)
    except Exception as e:
        return f"❌ 知识图谱子AGENT失败: {_safe_error_text(e)}。请修正描述后重试或改用其他方式。"

    relations = data.get("relations")
    if not isinstance(relations, list) or not relations:
        return "⚠ 子AGENT未识别出任何关系变化。请提供更明确的文本或调整hint后重试。"

    applied: list[str] = []
    errors: list[str] = []
    for i, rel in enumerate(relations):
        if not isinstance(rel, dict):
            errors.append(f"relations[{i}] 不是对象")
            continue
        src = str(rel.get("source", "") or "").strip()
        dst = str(rel.get("target", "") or "").strip()
        relation = str(rel.get("relation", "") or "").strip()
        if not src or not dst or not relation:
            errors.append(f"relations[{i}] 缺少 source/target/relation")
            continue
        if src == dst:
            errors.append(f"relations[{i}] source 与 target 相同: {src}")
            continue
        strength = rel.get("strength")
        confidence = rel.get("confidence")
        try:
            strength = None if strength is None else max(0.0, min(100.0, float(strength)))
        except (TypeError, ValueError):
            errors.append(f"relations[{i}].strength 非法: {strength}")
            continue
        try:
            confidence = None if confidence is None else max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            errors.append(f"relations[{i}].confidence 非法: {confidence}")
            continue
        notes = str(rel.get("notes", "") or "")[:200]
        ws.add_or_update_relation(src, dst, relation=relation,
                                  strength=strength, confidence=confidence, notes=notes)
        applied.append(f"{src} --{relation}--> {dst} (亲密度{strength if strength is not None else 50}, 置信度{confidence if confidence is not None else 0.5})")

    if errors and not applied:
        return "❌ 知识图谱更新失败，全部条目校验未通过:\n- " + "\n- ".join(errors) + "\n请修正后重新调用。"
    result_lines = [f"✅ 更新 {len(applied)} 条关系"]
    result_lines += [f"- {a}" for a in applied[:10]]
    if errors:
        result_lines.append(f"⚠ 有 {len(errors)} 条被跳过:")
        result_lines += [f"  - {e}" for e in errors[:5]]
    return "\n".join(result_lines)
