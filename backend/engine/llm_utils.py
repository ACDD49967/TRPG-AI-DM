"""LLM 输出清理工具——拒绝文本剥离等通用逻辑（无第三方依赖）。"""

_REFUSAL_MARKERS = [
    "很抱歉，我无法", "抱歉，我无法", "我不能参与创作", "无法提供所请求",
    "涉及未成年", "不能参与", "绝对禁止生成", "这是我不能参与创作的",
]
_CONTINUATION_MARKERS = [
    "好的。以下", "好的，以下", "以下是我为你搭建", "在调整后的设定下继续",
    "以下是我为你", "好的。", "好的，",
]


def strip_refusal(text: str) -> str:
    """去掉模型输出的拒绝对话前缀，保留其后可能出现的实际内容。

    如果只有拒绝而没有实际内容，返回空字符串，由上层触发重试/降级。
    """
    if not text:
        return ""
    for marker in _REFUSAL_MARKERS:
        idx = text.find(marker)
        if idx >= 0:
            best = None
            for cont in _CONTINUATION_MARKERS:
                j = text.find(cont, idx)
                if j != -1 and (best is None or j < best):
                    best = j
            if best is not None:
                return text[best:].strip()
            return ""
    return text.strip()
