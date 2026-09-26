"""先攻模型：固定加值、Combatant 与 InitiativeTracker（顺序与回合余额的唯一来源）。

从 `backend/engine/initiative.py` 拆出；那边保留 `tracker_for` / `start` / `consume` / `sync_*`
这些会话级门面，并再导出本模块的名字（既有 import 与测试打桩语义不变）。
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any, Iterable


HINT_PREFIX = "[系统-先攻]"

# 生物特性里表示"一轮多个回合"的关键词；时间暂停是法术，由 grant_turns 显式授予
_MULTI_TURN_PATTERN = re.compile(r"时间暂停|time\s*stop|多重回合|多次行动|multi[- ]?turn", re.I)

# 先攻使用独立随机源：不干扰主流程的骰子序列（测试里 dm.random.randint 常被打桩为
# 固定骰点流，若先攻也走同一个源会把后续伤害骰的桩值吃掉）。
_RNG = random.Random()


def normalize_key(name: Any) -> str:
    """行动者归一：去掉括号注解与空白并小写，让「地精斥候（受伤）」与「地精斥候」同键。"""
    text = re.sub(r"[（(][^）)]*[)）]", "", str(name or ""))
    return re.sub(r"\s+", "", text).lower()


def dex_modifier(attrs: Any) -> int:
    try:
        dex = int((attrs or {}).get("dex", 10) or 10)
    except (TypeError, ValueError):
        dex = 10
    return (dex - 10) // 2


def roll_initiative(dex_mod: int = 0, rng: Any = None) -> int:
    return int((rng or _RNG).randint(1, 20)) + int(dex_mod or 0)


def turns_per_round_from_traits(traits: Iterable[Any] | str | None) -> int:
    """从特性描述里推断一轮几个回合；默认 1，命中关键词给 2（保守取值）。"""
    if not traits:
        return 1
    text = " ".join(str(t) for t in traits) if not isinstance(traits, str) else traits
    return 2 if _MULTI_TURN_PATTERN.search(text) else 1


def _sort_key(combatant: "Combatant") -> tuple:
    """先攻高者先；同值时玩家优先（5e 常见裁定习惯），再按名字稳定排序。"""
    return (-int(combatant.initiative), 0 if combatant.is_player else 1, combatant.name)


@dataclass
class Combatant:
    name: str
    side: str = "enemy"          # player | enemy | ally
    initiative: int = 0
    dex_mod: int = 0
    hp: int = 0
    max_hp: int = 0
    alive: bool = True
    turns_per_round: int = 1
    turns_used: int = 0
    extra_used: dict[str, int] = field(default_factory=dict)
    initiative_bonus: int = 0     # 特长等固定加值（如「警觉」+5），掷先攻时叠加
    note: str = ""
    surprised: bool = False       # 突袭轮：该单位本轮不能行动/反应
    surprise_immune: bool = False # 「警觉」等特性：不会被突袭

    @property
    def is_player(self) -> bool:
        return self.side == "player"

    @property
    def turns_left(self) -> int:
        if not self.alive:
            return 0
        return max(0, int(self.turns_per_round or 1) - int(self.turns_used or 0))

    def acted_this_round(self) -> bool:
        return self.turns_used > 0

    def to_dict(self) -> dict:
        return {
            "name": self.name, "side": self.side, "initiative": self.initiative,
            "dex_mod": self.dex_mod, "hp": self.hp, "max_hp": self.max_hp,
            "alive": self.alive, "turns_per_round": self.turns_per_round,
            "turns_used": self.turns_used, "extra_used": dict(self.extra_used),
            "initiative_bonus": self.initiative_bonus,
            "note": self.note,
            "surprised": self.surprised,
            "surprise_immune": self.surprise_immune,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Combatant":
        return cls(
            name=str(data.get("name") or ""),
            side=str(data.get("side") or "enemy"),
            initiative=int(data.get("initiative", 0) or 0),
            dex_mod=int(data.get("dex_mod", 0) or 0),
            hp=int(data.get("hp", 0) or 0),
            max_hp=int(data.get("max_hp", 0) or 0),
            alive=bool(data.get("alive", True)),
            turns_per_round=max(1, int(data.get("turns_per_round", 1) or 1)),
            turns_used=max(0, int(data.get("turns_used", 0) or 0)),
            extra_used={str(k): int(v) for k, v in (data.get("extra_used") or {}).items()},
            initiative_bonus=int(data.get("initiative_bonus", 0) or 0),
            note=str(data.get("note") or ""),
            surprised=bool(data.get("surprised", False)),
            surprise_immune=bool(data.get("surprise_immune", False)),
        )


@dataclass
class InitiativeTracker:
    """一轮内的先攻顺序与回合余额。"""

    round: int = 1
    order: list[Combatant] = field(default_factory=list)

    # ── 查询 ────────────────────────────────────────────────
    def find(self, name: Any) -> Combatant | None:
        key = normalize_key(name)
        if not key:
            return None
        for c in self.order:
            if normalize_key(c.name) == key:
                return c
        return None

    def knows(self, name: Any) -> bool:
        return self.find(name) is not None

    def alive(self) -> list[Combatant]:
        return [c for c in self.order if c.alive]

    def pending(self) -> list[Combatant]:
        """本轮还没行动（还有回合余额）的存活单位，按先攻顺序。"""
        return [c for c in self.order if c.alive and c.turns_left > 0]

    def current(self) -> Combatant | None:
        pending = self.pending()
        return pending[0] if pending else None

    def order_line(self) -> str:
        parts = []
        for c in self.order:
            mark = "" if c.alive else "✝"
            parts.append(f"{c.name}({c.initiative}){mark}")
        return " > ".join(parts) if parts else "（空）"

    def summary(self) -> str:
        """给主 DM 的系统提示：顺序、当前该谁、谁还没动。"""
        pending = [c.name for c in self.pending()]
        acted = [c.name for c in self.alive() if c.turns_left == 0]
        lines = [f"{HINT_PREFIX} 第{self.round}轮先攻顺序：{self.order_line()}"]
        cur = self.current()
        if cur is not None:
            lines.append(f"当前该行动的是：{cur.name}（剩余回合 {cur.turns_left}）。")
        if pending:
            lines.append("本轮尚未行动：" + "、".join(pending) + "。")
        if acted:
            lines.append("本轮已行动：" + "、".join(acted) + "。")
        surprised = [c.name for c in self.order if c.alive and c.surprised]
        if surprised:
            lines.append("突袭回合：" + "、".join(surprised) + " 本轮不能行动或反应。")
        lines.append(
            "敌人回合请用 enemy_attack 逐个结算（同一敌人本轮回合用尽后不得再动）；"
            "若局势确实需要额外行动（多段攻击/动作如潮/传奇动作/时间暂停/多重回合），"
            "请用 action_source 声明来源，不要直接叙述多打一次。"
        )
        return "\n".join(lines)

    def payload(self) -> dict:
        """前端展示用（不含 DM 提示文本）。"""
        current = self.current()
        return {
            "round": self.round,
            "current": current.name if current else "",
            "order": [
                {
                    "name": c.name, "side": c.side, "initiative": c.initiative,
                    "hp": c.hp, "max_hp": c.max_hp, "alive": c.alive,
                    "turns_left": c.turns_left, "is_player": c.is_player,
                    "is_current": bool(current and c is current),
                    "surprised": c.surprised,
                }
                for c in self.order
            ],
        }

    # ── 变更 ────────────────────────────────────────────────
    def begin_round(self) -> None:
        """新的战斗轮：轮数 +1，重置所有单位的回合消耗与额外行动计数。"""
        self.round = int(self.round or 1) + 1
        for c in self.order:
            c.turns_used = 0
            c.extra_used.clear()
            c.surprised = False

    def mark_surprised(self, side: str) -> list[str]:
        """标记某一方在突袭轮中不能行动；免疫单位跳过。返回被标记的名字。"""
        side = str(side or "").strip().lower()
        marked: list[str] = []
        for c in self.order:
            if c.side != side or not c.alive or c.surprise_immune:
                continue
            c.surprised = True
            marked.append(c.name)
        return marked

    def consume(self, name: Any, source: str = "", requested: int = 0):
        """消耗一个回合（或登记一次额外行动）。

        返回 (是否允许, 拒绝原因, 是否开启新回合)。
        `source` 非空表示额外行动，交给行动经济账本判配额；这里只登记计数。
        """
        c = self.find(name)
        if c is None or not c.alive:
            return True, "", False
        if c.surprised:
            return (
                False,
                f"{c.name} 处于突袭回合，本轮不能行动或反应；等下一轮再动。",
                False,
            )
        if source:
            c.extra_used[source] = int(c.extra_used.get(source, 0)) + 1
            return True, "", False
        if c.turns_left <= 0:
            reason = (
                f"{c.name} 本轮（第{self.round}轮）的主行动已经结算过"
                f"（每轮 {c.turns_per_round} 个回合，已用完）。"
                f"请等到下一轮；若这是合法的额外行动（多段攻击/动作如潮/传奇动作/"
                f"加速术/时间暂停等），请用 action_source 声明来源后重新调用，"
                f"不要为了重掷失败的结果而声明额外行动。"
            )
            return False, reason, False
        c.turns_used += 1
        return True, "", True

    def sync(self, roster: list[Combatant]) -> None:
        """把最新名单并进来：新单位补投先攻，已知单位只更新血量/存活/回合额度。"""
        for incoming in roster:
            existing = self.find(incoming.name)
            if existing is None:
                self.order.append(incoming)
                continue
            existing.hp = incoming.hp
            existing.max_hp = incoming.max_hp or existing.max_hp
            existing.alive = incoming.alive
            existing.turns_per_round = max(existing.turns_per_round, incoming.turns_per_round)
            existing.note = incoming.note or existing.note
            existing.surprise_immune = bool(existing.surprise_immune or incoming.surprise_immune)
        self.order.sort(key=_sort_key)

    def mark_defeated(self, name: Any) -> None:
        c = self.find(name)
        if c is not None:
            c.alive = False
            c.hp = 0
            c.turns_used = c.turns_per_round  # 不再占用本轮提示

    def update_hp(self, name: Any, hp: int, max_hp: int = 0) -> None:
        c = self.find(name)
        if c is None:
            return
        c.hp = max(0, int(hp))
        if max_hp:
            c.max_hp = max(int(max_hp), c.max_hp)
        if c.hp <= 0:
            c.alive = False

    def grant_turns(self, name: Any, turns: int, note: str = "") -> int:
        """给某个单位追加本轮的回合（时间暂停等明确的多回合效果）。返回新的回合额度。"""
        c = self.find(name)
        if c is None:
            return 0
        extra = max(0, int(turns))
        c.turns_per_round = max(1, int(c.turns_per_round or 1) + extra)
        if note:
            c.note = note
        return c.turns_per_round

    def to_dict(self) -> dict:
        return {"round": self.round, "order": [c.to_dict() for c in self.order]}

    @classmethod
    def from_dict(cls, data: dict) -> "InitiativeTracker":
        tracker = cls(round=max(1, int(data.get("round", 1) or 1)))
        tracker.order = [Combatant.from_dict(d) for d in (data.get("order") or [])]
        return tracker


# ── 与 GameSessionState 的对接 ─────────────────────────────
