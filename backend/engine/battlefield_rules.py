"""战场规则模型：距离档位、掩体加值与 Placement/Battlefield 数据结构。

从 `backend/engine/battlefield.py` 拆出；那边保留会话状态门面与攻击预检。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


BAND_HINT = "[系统-态势]"

# 档位 → (中文名, 约略距离) —— 只用于提示与射程判断，不做精确格子
BANDS: dict[str, tuple[str, str]] = {
    "engaged": ("缠斗", "0 尺"),
    "near": ("近距离", "约 30 尺"),
    "far": ("远距离", "约 120 尺"),
    "out": ("脱离交战", "超出交战距离"),
}
_BAND_ALIASES = {
    "engaged": "engaged", "缠斗": "engaged", "近战": "engaged", "贴身": "engaged", "melee": "engaged",
    "near": "near", "近": "near", "近距离": "near", "close": "near",
    "far": "far", "远": "far", "远距离": "far", "ranged": "far", "distant": "far",
    "out": "out", "脱离": "out", "离开": "out", "逃": "out", "fled": "out",
}

COVERS: dict[str, tuple[str, int]] = {
    "none": ("无掩体", 0),
    "half": ("半掩体", 2),
    "three_quarters": ("四分之三掩体", 5),
    "full": ("全掩体", 99),
}
_COVER_ALIASES = {
    "none": "none", "无": "none", "无掩体": "none", "没有": "none", "暴露": "none",
    "half": "half", "半": "half", "半掩体": "half", "半个": "half", "部分": "half",
    "three_quarters": "three_quarters", "3/4": "three_quarters", "三分之四": "three_quarters",
    "四分之三": "three_quarters", "大量": "three_quarters", "¾": "three_quarters",
    "full": "full", "全": "full", "全掩体": "full", "完全": "full", "躲好": "full",
}

# 近战能打到的档位（远距离需要先接近）
MELEE_BANDS = ("engaged", "near")


def normalize_band(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if text in _BAND_ALIASES:
        return _BAND_ALIASES[text]
    for key, band in _BAND_ALIASES.items():
        if key and key in text:
            return band
    return ""


def normalize_cover(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if text in _COVER_ALIASES:
        return _COVER_ALIASES[text]
    for key, cover in _COVER_ALIASES.items():
        if key and key in text:
            return cover
    return ""


def normalize_name(state: Any, name: Any) -> str:
    """行动者归一（与 initiative 一致：去注解、忽略大小写）。"""
    text = re.sub(r"[（(][^）)]*[)）]", "", str(name or ""))
    text = re.sub(r"\s+", "", text)
    if not text:
        return ""
    char = re.sub(r"\s+", "", str(getattr(state, "character_name", "") or ""))
    if text.lower() in ("你", "玩家", "pc", "player", "自己", "主角") and char:
        return char
    return text


def cover_ac_bonus(cover: Any) -> int:
    """5e 掩体：半掩体 +2 AC、四分之三掩体 +5 AC。"""
    canonical = normalize_cover(cover)
    if canonical in ("none", ""):
        return 0
    if canonical == "full":
        return 0          # 全掩体不能被打到，由 can_be_targeted 判定
    return COVERS[canonical][1]


def cover_dex_bonus(cover: Any) -> int:
    """5e：掩体同样给敏捷豁免加值（+2 / +5）。"""
    return cover_ac_bonus(cover)


def melee_reachable(band: Any) -> bool:
    """近战能否够到：缠斗/近距离可以，远距离与脱离都要先移动。"""
    canonical = normalize_band(band)
    if not canonical:
        return True       # 没记录档位时不拦，交给 DM
    return canonical in MELEE_BANDS


def can_be_targeted(cover: Any, attacker_ignores_cover: bool = False) -> bool:
    """全掩体无法被直接攻击（神射手的 ignore_cover 也不越过全掩体）。"""
    return normalize_cover(cover) != "full"


def provokes_opportunity(old_band: Any, new_band: Any) -> bool:
    """从缠斗脱离（改为近距离/远距离/脱离）会引发借机攻击。"""
    return normalize_band(old_band) == "engaged" and normalize_band(new_band) in ("near", "far", "out")


def hp_ratio(hp: int, max_hp: int) -> float:
    return (hp / max_hp) if max_hp else 1.0


@dataclass
class Placement:
    band: str = ""
    cover: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        return {"band": self.band, "cover": self.cover, "note": self.note}

    @classmethod
    def from_dict(cls, data: dict) -> "Placement":
        return cls(band=str(data.get("band") or ""), cover=str(data.get("cover") or ""),
                   note=str(data.get("note") or ""))


@dataclass
class Battlefield:
    """当前战斗的场景态势：谁在哪一档、谁有什么掩体。"""

    places: dict[str, Placement] = field(default_factory=dict)

    def get(self, state: Any, name: Any) -> Placement | None:
        key = normalize_name(state, name).lower()
        return self.places.get(key) if key else None

    def set(self, state: Any, name: Any, band: str = "", cover: str = "",
            note: str = "") -> Placement | None:
        key = normalize_name(state, name)
        if not key:
            return None
        place = self.places.setdefault(key.lower(), Placement())
        if band:
            place.band = band
        if cover:
            place.cover = cover
        if note:
            place.note = note
        return place

    def remove(self, state: Any, name: Any) -> bool:
        key = normalize_name(state, name).lower()
        return bool(key and self.places.pop(key, None) is not None)

    def alive_places(self) -> list[tuple[str, Placement]]:
        return [(name, place) for name, place in self.places.items() if place.band or place.cover]

    def summary(self) -> str:
        if not self.places:
            return "战场态势：尚未记录（默认双方可近战、无掩体）。"
        parts = []
        for name, place in self.places.items():
            band = BANDS.get(place.band, ("", ""))[0] or "档位未记录"
            cover = COVERS.get(place.cover, ("", 0))[0] or "掩体未记录"
            text = f"{name}：{band} / {cover}"
            if place.note:
                text += f"（{place.note}）"
            parts.append(text)
        return "战场态势：" + "；".join(parts) + "。"

    def to_dict(self) -> dict:
        return {"places": {name: place.to_dict() for name, place in self.places.items()}}

    @classmethod
    def from_dict(cls, data: dict) -> "Battlefield":
        places = {str(k): Placement.from_dict(v or {})
                  for k, v in (data.get("places") or {}).items()}
        return cls(places=places)


# ── 与 GameSessionState 的对接 ─────────────────────────────
