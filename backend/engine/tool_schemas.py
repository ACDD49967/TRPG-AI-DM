"""AI 跑团主持工具集——OpenAI/DeepSeek function-calling 格式。"""

def _tool(name, desc, props, required=None):
    return {
        "type": "function",
        "function": {
            "name": name, "description": desc,
            "parameters": {"type": "object", "properties": props,
                           "required": required or list(props.keys())},
        },
    }
