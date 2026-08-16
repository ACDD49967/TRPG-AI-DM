"""经典剧本参考库——仅收录公开/免费可用的经典剧本名称与格式化简介，便于快速参考。

不包含受版权保护的完整正文；用户可据此在网络上合法获取原版。
"""

CLASSIC_SCENARIOS = [
    {
        "name": "The Haunting",
        "system": "coc",
        "tone": "克苏鲁恐怖",
        "summary": "1920年代波士顿，调查员受托调查一座闹鬼宅邸，最终发现地下邪教仪式与旧日支配者的痕迹。",
        "source": "Call of Cthulhu 7th Edition Quick-Start Rules（官方免费快速规则）",
        "outline": [
            "开端：委托人 Corbitt 宅邸的怪异事件，调查员从房东/亲属处收集线索。",
            "发展：宅邸中的灵异现象逐步升级，地下室的祭坛与 Corbitt 的真相浮现。",
            "高潮：阻止邪教徒仪式，面对 Corbitt 的亡灵或逃离宅邸。",
        ],
    },
    {
        "name": "The Delian Tomb",
        "system": "dnd5e",
        "tone": "史诗奇幻",
        "summary": "一座被遗忘的古老墓穴，哥布林掳走了铁匠的女儿，冒险者必须深入墓穴营救。",
        "source": "Matt Colville - Running the Game（免费示例冒险）",
        "outline": [
            "开端：村庄求助，铁匠女儿被哥布林掳走。",
            "发展：追踪至 Delian 古墓，墓穴内机关与哥布林伏击。",
            "高潮：击败哥布林首领，救出人质，发现墓穴历史。",
        ],
    },
    {
        "name": "A Most Potent Brew",
        "system": "dnd5e",
        "tone": "轻松幽默",
        "summary": "酒馆老板的配方被盗，冒险者进入地下酒窖追查一只巨大的老鼠与隐藏的炼金实验室。",
        "source": "Winghorn Press（免费入门冒险）",
        "outline": [
            "开端：酒馆老板请求找回失窃的酿酒配方。",
            "发展：酒窖中的巨型老鼠与炼金装置。",
            "高潮：击败鼠王，取回配方。",
        ],
    },
    {
        "name": "The Mad Manor of Astabar",
        "system": "dnd5e",
        "tone": "黑暗奇幻",
        "summary": "一位疯癫法师的庄园被魔法扭曲，冒险者进入寻找失踪的商队。",
        "source": "D&D Adventurers League（免费公开冒险）",
        "outline": [
            "开端：商队在 Astabar 庄园附近失踪。",
            "发展：庄园内魔法陷阱与扭曲空间。",
            "高潮：面对疯法师 Astabar 的幻象与真相。",
        ],
    },
]


def list_classic_scenarios():
    return CLASSIC_SCENARIOS
