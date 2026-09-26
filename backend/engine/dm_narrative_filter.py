"""DM 叙事过滤：反八股清洗、重复片段去重、工具回声/元信息泄露剔除。

从 `backend/engine/dm_runtime.py` 拆出（那边只留流式循环与工具子集），
由 dm_runtime 再导出，既有 import 不变。
"""
from __future__ import annotations

import re


# ═══════════════════════════════════════════════════════════════
# 反八股正则——AI叙事输出后自动过滤
# ═══════════════════════════════════════════════════════════════

CLICHE_PATTERNS = [
    # P1-5修复：排除战斗动词，避免误杀"不是劈——是砸"等战斗动作描述
    (r'不是(?!劈|砍|刺|砸|扫|挡|闪|撞|压|缴|射|挥|捅|斩|削|挑|格|拉|推|踹|踢|抓|咬|撕|掐)[^，。；,!.\n]{2,30}，而是', ''),
    (r'不是(?!劈|砍|刺|砸|扫|挡|闪|撞|压|缴|射|挥|捅|斩|削|挑|格|拉|推|踹|踢|抓|咬|撕|掐)[^，。；,!.\n]{2,30}，是', ''),
    (r'不是(?!劈|砍|刺|砸|扫|挡|闪|撞|压|缴|射|挥|捅|斩|削|挑|格|拉|推|踹|踢|抓|咬|撕|掐)[^，。；,!.\n]{2,30}\.而是', ''),
    (r'殊不知[^，。]{2,30}[，。]', ''),
    (r'然而[^，。]{0,5}他[^，。]{0,5}并不知道', ''),
    (r'一个[^，。]{0,10}从未[^，。]{0,10}过的', ''),
    (r'命运的齿轮[^，。]{0,15}转动', ''),
    (r'他[^，。]{0,10}永远[^，。]{0,10}不会[^，。]{0,10}知道', ''),
    (r'仿佛[^，。]{5,30}一般', ''),
    (r'宛如[^，。]{5,30}一般', ''),
    (r'空气中[^，。]{0,10}弥漫着[^，。]{0,10}的气息', ''),
    (r'一股[^，。]{2,10}的气息[^，。]{0,10}扑面而来', ''),
    (r'在[^，。]{3,20}的深处', ''),
    # P2-6: 编辑评审新增——高频滥调
    (r'血红的[^，。；]{0,15}', ''),          # "血红的XX"
    (r'划破了寂静', ''),                       # 常见声音描写滥调
    (r'如同一[只个条头匹缕片][^，。]{3,25}', ''),  # "...如同一只..."比喻标志词
    (r'一股[^，。]{1,12}寒意', ''),
    (r'不知为何', ''),
    (r'内心深处', ''),
    (r'突然之间|突然，|忽然，', ''),
    (r'神秘的力量', ''),
    (r'命运的齿轮[^，。]{0,12}转动', ''),
    (r'空气中[^，。]{0,12}安静', ''),
    (r'他?她?[^，。]{0,6}感到一股[^，。]{1,12}', ''),
]



def sanitize_narrative(text: str) -> str:
    """过滤掉八股文套路句式，但保留原意。P0-2: 增加连贯性检查。"""
    for pattern, _ in CLICHE_PATTERNS:
        text = re.sub(pattern, '', text)
    # 清理多余标点
    text = re.sub(r'，{2,}', '，', text)
    text = re.sub(r'。{2,}', '。', text)
    text = re.sub(r'\s{3,}', '\n\n', text)
    # P0-2修复：检测并移除SSE拼接导致的重复片段
    text = _dedupe_fragments(text)
    # 过滤主DM偶尔输出的幕后/工具元台词
    text = re.sub(r'[^。！？\n]*系统(?:检定)?工具[^。！？\n]*[。！？]?', '', text)
    text = re.sub(r'[^。！？\n]*(?:需要额外参数|正在调用工具|我来结算|我先确认)[^。！？\n]*[。！？]?', '', text)
    text = re.sub(r'[^。！？\n]*(?:让我为你|为你进行.{0,8}检定|我来为你|进行一次.{0,8}检定)[^。！？\n]*[。！？]?', '', text)
    # 剥离决策建议块——决策应通过suggest_choices工具推送，不应出现在叙事正文中
    text = re.sub(r'\n*[-—]+\s*\n\*\*决策建议\*\*[\s\S]*$', '', text)
    text = re.sub(r'\n\*\*决策建议\*\*[\s\S]*$', '', text)
    # 检测"三"过度使用——在单次回复中超过3个独立"三"时记录警告
    three_count = len(re.findall(r'(?<!\d)三(?!\d|十|百|千|万)', text))
    if three_count > 3:
        print(f"[sanitize] 警告：本回复中出现{three_count}次'三'——可能是AI惯性填充数字")
    return text.strip()




def _dedupe_fragments(text: str) -> str:
    """检测相邻句子中由于SSE拼接错误导致的重复文本片段并移除。"""
    sentences = re.split(r'(?<=[。！？\n])\s*', text)
    if len(sentences) < 2:
        return text
    cleaned = [sentences[0]]
    for i in range(1, len(sentences)):
        prev = sentences[i-1].strip()
        curr = sentences[i].strip()
        if not curr:
            continue
        # 如果当前句子是前一句的完整子串（说明被流式拼接重复推送了）
        if len(curr) >= 10 and curr in prev:
            continue
        # 如果当前句子的后半段与它前一句的后半段高度重叠（15字以上的共同子串）
        if len(prev) >= 20 and len(curr) >= 15:
            overlap_len = 0
            min_len = min(len(prev), len(curr))
            for j in range(1, min_len):
                if prev[-j:] == curr[:j]:
                    overlap_len = j
            if overlap_len >= 15:
                # 修剪掉重叠部分
                curr = curr[overlap_len:].strip()
                if not curr:
                    continue
        cleaned.append(curr)
    return '\n'.join(cleaned)


_META_LEAK_PATTERN = re.compile(
    r"系统(?:检定)?工具|工具参数错误|需要额外参数|正在调用工具|我来结算|我先确认|让我先看看|让我看看|先调出|调出战力|系统提示|系统提醒|后台分析|子Agent|专家简报|让我为你|为你进行.{0,8}检定|我来为你|进行一次.{0,8}检定|你的角色(?:回想|状态|卡)?|作为玩家|玩家视角|OOC|出戏"
)



# 工具自己会推送结算行（🎲 骰子 / ⚔️ 战斗 / 💀 死亡 / 🛌 休息），
# 提示词又要求 DM “简要说明工具结果”，于是玩家会把同一信息看两遍。
# 这里直接丢掉以工具标记开头的复述行，信息仍由工具行和骰子浮层给出。
_TOOL_ECHO_PATTERN = re.compile(r"^\s*(?:🎲|⚔️|⚔|💀|☠️|☠|🛌)\s*[^。！？\n]*")



# DM 有时会自己编一条骰子/战斗结算行（实测见过用 🚨 开头、且该系统回合根本没掷骰）。
# 只要文本里出现工具专属的数值签名，就说明这条是工具该给的内容。
_TOOL_ECHO_SIGNATURE = re.compile(
    r"(?:d20|d100)\s*=\s*\d+.*?(?:vs\s*DC|AC\s*\d+)|敌人HP\s*[:：]\s*\d+|"
    r"\[成功\s*\d/3\s*失败\s*\d/3\]|短休\s*:\s*\+\d+HP"
)




def _is_player_visible_segment(seg: str) -> bool:
    """幕后台词与工具结算复述都不应进入玩家可见叙事。"""
    if not seg.strip():
        return True
    if _META_LEAK_PATTERN.search(seg):
        return False
    if _TOOL_ECHO_PATTERN.match(seg):
        return False
    if _TOOL_ECHO_SIGNATURE.search(seg):
        return False
    return True
