"""角色属性与背景故事生成（三种模式：推断属性 / 生成背景 / 两者都生成）。

从 `backend/routers/generate.py` 搬出——那边原来一个 277 行的路由函数同时负责
校验、提示词拼装、重试与降级兜底。HTTP 语义保持不变：校验失败仍抛 HTTPException。
"""
from __future__ import annotations

from fastapi import HTTPException
from openai import AsyncOpenAI

from backend.config import ensure_valid_api_key, settings
from backend.engine.prompt_guard import extract_json_object, sanitize_user_text
from backend.schemas import GenerateAttributesRequest


async def generate_character_payload(request: GenerateAttributesRequest) -> dict:
    """AI生成角色属性与背景故事。

    三种模式：
    1. 提供背景故事、无属性 → AI推断属性+润色背景
    2. 提供属性、无背景故事 → AI根据种族/职业/属性生成生动背景
    3. 都不提供 → AI自动生成属性+背景

    返回值含 attributes 和 backstory。
    """
    api_key = request.api_key or settings.LLM_API_KEY
    base_url = request.base_url or settings.LLM_BASE_URL
    model = request.model_name or settings.LLM_MODEL_NAME
    if not model:
        raise HTTPException(status_code=400, detail="请先选择或填写模型名称")
    try:
        api_key = ensure_valid_api_key(request.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    has_backstory = bool(request.backstory.strip())
    has_attrs = bool(request.attributes and len(request.attributes) >= 6)
    system = request.game_system or "dnd5e"
    scenario_summary = request.scenario_summary or ""
    custom_rules = request.custom_rules or ""

    from backend.engine.game_systems import (
        get_style_directive,
        roll_coc_characteristics,
    )
    style_block = get_style_directive(system)
    scenario_block = f"\n\n## 已选剧本总结（必须自然融入角色背景）\n{scenario_summary[:1200]}" if scenario_summary else ""
    custom_block = f"\n\n## 自定义规则（背景须符合）\n{custom_rules[:1500]}" if custom_rules and system == "custom" else ""

    # COC 的数值必须由程序随机生成，不允许 LLM 编造属性
    if system == "coc" and not has_attrs:
        request.attributes = roll_coc_characteristics()
        has_attrs = True

    gender = request.gender or "未指定"
    # 归一化性别值（支持中英文）
    gender_normalized = gender
    if gender.lower() in ("男", "m", "male", "man"):
        gender_normalized = "男"
    elif gender.lower() in ("女", "f", "female", "woman"):
        gender_normalized = "女"
    gender_hint = ""
    gender_pronoun = "ta"
    if gender_normalized == "男":
        gender_hint = "性别: 男\n"
        gender_pronoun = "他"
    elif gender_normalized == "女":
        gender_hint = "性别: 女\n"
        gender_pronoun = "她"

    if has_backstory and not has_attrs:
        # 模式1：有背景故事 → 推断属性（仅 D&D 系）
        user_prompt = f"""请根据以下角色背景故事推断{ 'D&D 六维' if system != 'coc' else 'COC 八维' }属性值。

角色名: {request.character_name}
{gender_hint}种族: {request.race}
职业: {request.char_class}
背景故事: {request.backstory}
{scenario_block}

根据故事中描述的角色特点分配属性。D&D 使用标准数组[15,14,13,12,10,8]范围3-18；COC 使用1-99百分比。
{style_block}

润色后的背景必须保留原故事核心，分段（2-3段，段间空行），结尾留一个未解决的钩子。

只返回JSON：
{{"str": 数字, "dex": 数字, "con": 数字, "int": 数字, "wis": 数字, "cha": 数字, "backstory": "润色后的背景(150-250字)"}}"""
    elif system == "coc" and has_backstory and has_attrs:
        # COC 模式：已有背景故事，但属性必须由程序随机生成（不允许 LLM 编造）
        attrs = request.attributes or {}
        attr_names = [("str","力量"),("con","体质"),("dex","敏捷"),("int","智力"),("pow","意志"),("cha","魅力"),("siz","体型"),("edu","教育")]
        attr_line = " | ".join(f"{label}:{attrs.get(key, 50)}" for key, label in attr_names)
        user_prompt = f"""你是克苏鲁式调查员背景作者。

角色名: {request.character_name}
{gender_hint}职业/身份: {request.char_class}
调查员属性: {attr_line}
已有背景故事（请保留其核心设定，润色扩写为完整人物小传）: {request.backstory}
{scenario_block}

写一段200-350字的人物小传。要求:
1. 保留原背景故事中的关键经历与秘密，并补足具体伤疤、坏习惯、不愿提及的往事
2. 从调查员日常或某个具体时刻切入，不要模板开头
3. 必须与剧本总结中的世界观自然衔接
4. 角色性别是{gender_normalized}，使用"{gender_pronoun}"作为人称代词
5. 分段，2-3个自然段，段间空行；第一段写具体场景，第二段写关键往事，结尾留一个未解决的钩子
6. 文风要求：{style_block}

只返回JSON: {{"backstory": "..."}}"""
    elif has_attrs and not has_backstory:
        # 模式2：有属性 → 根据属性+剧本总结生成沉浸式背景
        attrs = request.attributes or {}
        if system == "coc":
            attr_names = [("str","力量"),("con","体质"),("dex","敏捷"),("int","智力"),("pow","意志"),("cha","魅力"),("siz","体型"),("edu","教育")]
            attr_line = " | ".join(f"{label}:{attrs.get(key, 50)}" for key, label in attr_names)
            role_hint = "调查员"
        else:
            str_val = attrs.get('str', 12)
            dex_val = attrs.get('dex', 12)
            int_val = attrs.get('int', 12)
            cha_val = attrs.get('cha', 12)
            wis_val = attrs.get('wis', 12)
            con_val = attrs.get('con', 12)
            attr_line = f"力{str_val} 敏{dex_val} 体{con_val} 智{int_val} 感{wis_val} 魅{cha_val}"
            role_hint = "冒险者"

        user_prompt = f"""你是沉浸式角色背景作者。这个角色不是填表格——ta是一个活过的人，身上有伤疤、有执念、有不为人知的秘密。

角色名: {request.character_name}
{gender_hint}种族: {request.race}
职业/身份: {request.char_class}
{role_hint}属性: {attr_line}
{scenario_block}
{custom_block}

写一段200-350字的人物小传。必须遵循:
1. 不要写"ta从小就"、"命运的齿轮"、"踏上冒险之路"等模板开头
2. 从一个具体时刻切入——ta正在做什么？手上沾着什么？闻到什么味道？
3. 属性值只是骨架。最重要的数字是ta在哪个时刻做了什么选择——那个选择的后果至今未消
4. 给出一个具体伤疤、一个坏习惯、一个ta对别人撒过的谎（或者别人对ta撒的谎）
5. **必须与已选剧本总结的世界观自然衔接**，让角色看起来属于这个世界
6. 角色的性别是{gender_normalized}，使用"{gender_pronoun}"作为人称代词。性别必须体现在故事中
7. **格式要求**：必须分段。2-3个自然段，段与段之间用空行分隔。不要写成一大坨连在一起的文字
8. **段落结构**：第一段写一个正在进行的具体场景；第二段写导致现状的关键往事/选择；第三段（如有）写一个未解决的钩子或执念
9. **导语钩子**：结尾必须留一个让玩家想知道“接下来会怎样”的悬念或邀请，不要写成总结性结尾
10. 文风要求：{style_block}

只返回JSON: {{"backstory": "..."}}"""
    else:
        # 模式3：自动生成属性+背景（COC 属性已由程序随机生成）
        attrs = request.attributes or {}
        if system == "coc":
            attr_names = [("str","力量"),("con","体质"),("dex","敏捷"),("int","智力"),("pow","意志"),("cha","魅力"),("siz","体型"),("edu","教育")]
            attr_line = " | ".join(f"{label}:{attrs.get(key, 50)}" for key, label in attr_names)
            role_hint = "调查员"
            user_prompt = f"""你是克苏鲁式调查员背景作者。

角色名: {request.character_name}
{gender_hint}职业/身份: {request.char_class}
调查员属性: {attr_line}
{scenario_block}

写一段200-350字的人物小传。要求:
1. 从调查员日常或某个具体时刻切入，不要模板开头
2. 给出一个具体伤疤、一个坏习惯、一个不愿提及的往事
3. 必须与剧本总结中的世界观自然衔接
4. 角色性别是{gender_normalized}，使用"{gender_pronoun}"作为人称代词
5. 分段，2-3个自然段，段间空行；第一段写具体场景，第二段写关键往事，结尾留一个未解决的钩子
6. 文风要求：{style_block}

只返回JSON: {{"backstory": "..."}}"""
        else:
            str_val = attrs.get('str', 12)
            dex_val = attrs.get('dex', 12)
            int_val = attrs.get('int', 12)
            cha_val = attrs.get('cha', 12)
            wis_val = attrs.get('wis', 12)
            con_val = attrs.get('con', 12)
            attr_line = f"力{str_val} 敏{dex_val} 体{con_val} 智{int_val} 感{wis_val} 魅{cha_val}"
            user_prompt = f"""你是一位小说家，正在为你的新主角写人物小传。这个角色不是在填表格——ta是一个活过的人，身上有伤疤、有执念、有不为人知的秘密。

角色名: {request.character_name}
{gender_hint}种族: {request.race}
职业: {request.char_class}
六维: {attr_line}
{scenario_block}
{custom_block}

第一步：根据种族特点和职业需求，分配六维属性（3-18范围）。
第二步：基于这组属性，写一段200-350字的人物小传。要求:
1. 不要写"ta从小就"、"命运的齿轮"、"踏上冒险之路"等模板开头
2. 从一个具体时刻切入——ta正在做什么？手上沾着什么？闻到什么味道？
3. 给出一个具体伤疤、一个坏习惯、一个ta对别人撒过的谎
4. 避免奇幻人物传记高频元素。写一个像《巫师》杰洛特或者《博德之门3》影心的角色——有缺陷，有灰色地带
5. 属性值只是骨架。最重要的数字是ta在哪个时刻做了什么选择
6. 角色的性别是{gender_normalized}，使用"{gender_pronoun}"作为人称代词。性别必须体现在故事中
7. **格式要求**：必须分段。2-3个自然段，段与段之间用空行分隔
8. **段落结构**：第一段写一个正在进行的具体场景；第二段写导致现状的关键往事/选择；结尾留一个未解决的钩子或执念
9. **导语钩子**：结尾必须留一个让玩家想知道“接下来会怎样”的悬念或邀请，不要写成总结性结尾
10. 文风要求：{style_block}

只返回JSON: {{"str":数字,"dex":数字,"con":数字,"int":数字,"wis":数字,"cha":数字,"backstory":"..."}}"""

    user_prompt = sanitize_user_text(user_prompt)
    try:
        import asyncio as _asyncio
        last_err = None
        text = ""
        # 推理模型下 reasoning_content 与正文共享 max_tokens：推理吃满预算时正文为空。
        # 因此第 2 次重试显式禁用思考并放大预算；网关不支持 thinking 参数时去掉该参数保底。
        plans = [
            {"disabled": False, "grow": False},
            {"disabled": True, "grow": True},
            {"disabled": False, "grow": True},
        ]
        for plan in plans:
            base_max_tokens = 4000 if request.thinking_strength == "low" else (6000 if request.thinking_strength == "medium" else 10000)
            current_max_tokens = int(base_max_tokens * (2 if plan["grow"] else 1))
            kwargs: dict = dict(
                model=model,
                messages=[
                    {"role": "system", "content": (
                        f"你是一位沉浸式角色背景设计师。只返回合法JSON，不要Markdown代码块，不要其他文本。"
                        f"角色性别是{gender_normalized}，使用'{gender_pronoun}'作为人称代词。"
                        f"背景故事要有具体伤疤、坏习惯和灰色地带，避免模板化叙事。\n\n{style_block}"
                    )},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=current_max_tokens,
                temperature=0.9,
            )
            if plan["disabled"]:
                kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
            try:
                resp = await client.chat.completions.create(**kwargs)
                text = (resp.choices[0].message.content or "").strip()
                if text:
                    break
                finish = resp.choices[0].finish_reason
                reasoning = getattr(resp.choices[0].message, "reasoning_content", None)
                print(f"[CharacterGen] 空响应 (finish={finish}, reasoning_len={len(reasoning or '')}, "
                      f"max_tokens={current_max_tokens}, thinking_disabled={plan['disabled']})")
                last_err = RuntimeError("空响应")
            except Exception as e:
                last_err = e
                print(f"[CharacterGen] 调用失败: {e}")
            await _asyncio.sleep(1)
        if not text:
            raise last_err or RuntimeError("背景生成失败")

        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        try:
            result = extract_json_object(text)
        except Exception:
            raise HTTPException(status_code=502, detail="角色生成返回的不是合法JSON")

        # 验证属性
        required = ["str", "dex", "con", "int", "wis", "cha"]
        attrs: dict[str, int] = {}
        if has_attrs:
            attrs = dict(request.attributes)
        else:
            for key in required:
                attrs[key] = max(3, min(18, int(result.get(key, 12))))

        backstory = result.get("backstory", "")
        if not backstory:
            backstory = f"{request.character_name}，一位{request.race}{request.char_class}，踏上了冒险之路。"

        return {"attributes": attrs, "backstory": backstory}

    except Exception as e:
        print(f"[CharacterGen] 背景生成最终失败: {e}")
        default_attrs = {
            "战士": {"str": 16, "dex": 13, "con": 15, "int": 10, "wis": 12, "cha": 8},
            "法师": {"str": 8, "dex": 13, "con": 12, "int": 16, "wis": 14, "cha": 10},
            "游荡者": {"str": 10, "dex": 16, "con": 12, "int": 13, "wis": 10, "cha": 14},
            "牧师": {"str": 13, "dex": 10, "con": 14, "int": 10, "wis": 16, "cha": 12},
            "游侠": {"str": 12, "dex": 16, "con": 13, "int": 10, "wis": 14, "cha": 8},
            "吟游诗人": {"str": 8, "dex": 14, "con": 10, "int": 12, "wis": 10, "cha": 16},
        }.get(request.char_class, {"str": 12, "dex": 12, "con": 12, "int": 12, "wis": 12, "cha": 12})
        return {
            "attributes": request.attributes or default_attrs,
            "backstory": f"{request.character_name}，一位{request.race}{request.char_class}，命运的齿轮开始转动…",
            "fallback": True,
        }
