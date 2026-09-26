"""世界生成的 LLM 管道：思考参数、输出预算自适应、重试与知识库注入。

从 backend.engine.world_builder 拆出。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from openai import AsyncOpenAI

from backend.config import settings
from backend.engine.llm_utils import strip_refusal as _strip_refusal
from backend.knowledge_base import get_knowledge_base



def _thinking_extra_body(disabled: bool) -> dict:
    """构造 thinking 控制参数。

    推理模型下 content 与 reasoning_content **共享同一个 max_tokens 预算**：
    推理先吃满预算时正文会被挤空（finish_reason=length、content 为空），
    对外表现就是“LLM 空响应”。结构化/评审类任务禁用思考即可稳定拿到正文。
    """
    return {"thinking": {"type": "disabled"}} if disabled else {}



# 输出预算上限的状态放在 `world_builder`（编排模块，见那边的注释）：
# 本模块只做惰性读取/降级，保证"自适应上限"全局只有一份。
def _cap_state() -> tuple[int, int]:
    from backend.engine import world_builder as _wb
    return _wb._current_output_cap(), _wb._OUTPUT_CAP_FALLBACK


def _lower_cap_to_fallback(fallback: int) -> None:
    from backend.engine import world_builder as _wb
    _wb._output_cap = fallback


def _current_output_cap() -> int:
    return _cap_state()[0]



def _is_max_tokens_limit_error(err: Exception) -> bool:
    """判断异常是否为“max_tokens 超过网关允许上限”。"""
    msg = str(err).lower()
    if "max_tokens" not in msg and "max_new_tokens" not in msg and "max output" not in msg:
        return False
    return any(k in msg for k in (
        "too large", "exceed", "greater", "maximum", "at most", "less than",
        "must be", "invalid", "range", "limit",
    ))



async def _llm(client: AsyncOpenAI, model: str, system: str, user: str,
               max_tokens: int = 4000, temp: float = 0.85, timeout: float = 180.0,
               thinking_strength: str = "medium", token_callback=None, error_callback=None,
               disable_thinking: bool = False) -> str:
    """单次LLM调用，统一使用流式输出。

    流式模式下超时只作用于“等待首个响应头”，不会在模型长文本生成中途掐断，
    从而大幅减少长剧本/推理模型场景下的 Request timed out。

    空响应（content 为空）的三层防护：
    1. 逐 chunk 累计 reasoning_content，日志可直接区分“推理吃满预算”与“模型真的没输出”；
    2. 长 prompt 自动抬高正文预算下限，避免长上下文推理把正文挤掉（导入剧本时尤其明显）；
    3. 重试时改用非流式 + 显式禁用思考 + 放大预算——这是最能救回空响应的组合；
       若网关不支持 thinking 参数，再去掉该参数保底重试一次。

    disable_thinking=True 用于合并/评分/JSON 抽取等确定性任务：这类任务不需要长推理，
    首次调用即禁用思考可避免“推理吃满预算 → 正文为空 → 白跑一次重试”。

    输出预算由 settings.LLM_MAX_OUTPUT_TOKENS（默认 32768）封顶：剧本创作是长文本任务，
    充裕预算既能避免正文被推理挤空，也能避免长 JSON（NPC/地点/旗标）被中途截断。
    """
    from backend.engine.prompt_guard import with_json_instruction
    cap_now, cap_fallback = _cap_state()  # 网关输出上限自适应：被拒绝时下调并记住
    if "JSON" in system or "JSON" in user:
        system = with_json_instruction(system)
    import asyncio
    mult = 1.8 if thinking_strength == "high" else (0.6 if thinking_strength == "low" else 1.0)
    # 长上下文会显著拉长推理长度，给正文保留预算下限。
    # 实测创作步（Step3/4）的 reasoning 会随输入上下文增长到 3000-5300 token，
    # 预算过小会导致首次尝试正文为空（需靠重试救回，白等一轮）。
    prompt_chars = len(system) + len(user)
    min_budget = 8000 + min(8000, prompt_chars // 8)
    max_tokens = min(cap_now, max(int(max_tokens * mult), min_budget))

    fast_first = disable_thinking or thinking_strength == "low"
    # 三次尝试：流式 → 非流式+禁思考(放大预算) → 非流式+无 thinking 参数(兼容老旧网关)
    plans = [
        {"stream": True, "disabled": fast_first,
         "budget": max_tokens, "label": "流式" + ("+禁用思考" if fast_first else "")},
        {"stream": False, "disabled": True,
         "budget": min(cap_now, max(max_tokens * 2, cap_fallback)),
         "label": "非流式+禁用思考"},
        {"stream": False, "disabled": False,
         "budget": min(cap_now, cap_fallback * 2), "label": "非流式+默认思考"},
    ]
    last_err = None
    attempt = 1
    while attempt <= len(plans):
        plan = plans[attempt - 1]
        current_max_tokens = min(plan["budget"], _cap_state()[0])
        extra_body = _thinking_extra_body(plan["disabled"])
        try:
            if plan["stream"]:
                # 优先流式：避免长文本生成中途被掐断
                stream = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model,
                        messages=[{"role":"system","content":system},{"role":"user","content":user}],
                        max_tokens=current_max_tokens, temperature=temp, stream=True,
                        **({"extra_body": extra_body} if extra_body else {})),
                    timeout=timeout,
                )
                content = ""
                reasoning = ""
                finish = None
                last_usage = None
                while True:
                    try:
                        chunk = await asyncio.wait_for(stream.__anext__(), timeout=60)
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        print(f"[WorldBuilder] LLM流式调用第{attempt}次空闲超时(60s无新数据)")
                        raise RuntimeError("流式响应空闲超时")
                    if getattr(chunk, "usage", None) is not None:
                        last_usage = chunk.usage
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    if choice.finish_reason:
                        finish = choice.finish_reason
                    d = choice.delta
                    if d is None:
                        continue
                    if d.content:
                        content += d.content
                        if token_callback is not None:
                            token_callback(d.content)
                    # 推理内容逐 chunk 累计：只在最后一个 chunk 取会导致日志恒为 0，无法定位空响应
                    rc = getattr(d, "reasoning_content", None)
                    if rc:
                        reasoning += rc
            else:
                # 非流式：部分服务商流式返回空，非流式更稳；带思考时 reasoning 只能整段取回
                resp = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model,
                        messages=[{"role":"system","content":system},{"role":"user","content":user}],
                        max_tokens=current_max_tokens, temperature=temp,
                        **({"extra_body": extra_body} if extra_body else {})),
                    timeout=timeout,
                )
                choice = resp.choices[0]
                content = choice.message.content or ""
                reasoning = getattr(choice.message, "reasoning_content", None) or ""
                finish = choice.finish_reason
                last_usage = getattr(resp, "usage", None)
            content = _strip_refusal(content)
            if content:
                return content
            # 空响应：用 finish_reason 区分“被 token 上限截断”与“模型确实没给正文”
            if finish == "length":
                why = "输出被 max_tokens 截断(finish_reason=length，推理吃满预算)"
            else:
                why = f"finish_reason={finish}"
            reasoning_tokens = None
            try:
                reasoning_tokens = last_usage.completion_tokens_details.reasoning_tokens
            except Exception:
                pass
            print(f"[WorldBuilder] LLM第{attempt}次空响应[{plan['label']}] ({why}, "
                  f"reasoning≈{len(reasoning)}字/{reasoning_tokens}tok, max_tokens={current_max_tokens})"
                  + ("，将切换禁用思考重试" if attempt < len(plans) else ""))
            last_err = f"空响应({why})"
        except asyncio.TimeoutError:
            last_err = f"超时({timeout}s，等待首个响应)"
            print(f"[WorldBuilder] LLM调用第{attempt}次超时({timeout}s，等待首个响应)")
        except Exception as e:
            # 网关 max_tokens 上限低于本机配置：降到兼容值后立即用同一套策略重试，不消耗尝试次数
            cap_now, cap_fallback = _cap_state()
            if _is_max_tokens_limit_error(e) and cap_now > cap_fallback:
                _lower_cap_to_fallback(cap_fallback)
                print(f"[WorldBuilder] 网关拒绝 max_tokens={current_max_tokens}，"
                      f"已将输出上限降至 {cap_fallback} 并重试: {e}")
                continue
            last_err = str(e)
            print(f"[WorldBuilder] LLM调用第{attempt}次失败[{plan['label']}]: {e}")
        if attempt < len(plans):
            await asyncio.sleep(1)
        attempt += 1
    print(f"[WorldBuilder] LLM调用最终失败: {last_err}，降级处理")
    if error_callback is not None:
        error_callback(last_err or "未知错误")
    return ""



def _with_knowledge(prompt: str, query: str, system: str, top_k: int = 3,
                    username: str | None = None) -> str:
    """从本地知识库检索相关规则/设定片段并附加到 Prompt（按用户名隔离）。"""
    try:
        results = get_knowledge_base().retrieve(query, system=system, top_k=top_k, username=username)
        if results:
            block = "\n\n## 可用规则/设定参考（来自知识库，按需采用）\n"
            block += "\n".join(f"- [{r.get('title','')}] {r.get('text','')[:300]}" for r in results)
            return prompt + block
    except Exception:
        pass
    return prompt



async def _with_knowledge_async(prompt: str, query: str, system: str, top_k: int = 3,
                                username: str | None = None) -> str:
    """知识库检索的异步包装。

    检索是同步的重操作（首次还会加载嵌入模型），直接在当前协程里调用会阻塞事件循环，
    导致剧本生成期间 SSE 进度无法推送、前端看起来“卡住”。
    """
    import asyncio
    return await asyncio.to_thread(_with_knowledge, prompt, query, system, top_k, username)
