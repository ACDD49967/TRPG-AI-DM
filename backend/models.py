"""AI地下城主的 SQLAlchemy ORM 数据模型。"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def _gen_id() -> str:
    """生成一个短唯一ID。"""
    return uuid.uuid4().hex[:12]


class User(Base):
    """用户表——一个用户可以创建多个角色。"""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_id)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    characters: Mapped[list["Character"]] = relationship(back_populates="user")


class Character(Base):
    """角色表——D&D 角色数据（属性、背包、状态等）。"""
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    gender: Mapped[str] = mapped_column(String(16), default="未指定")  # 男/女/未指定
    race: Mapped[str] = mapped_column(String(32), default="人类")
    char_class: Mapped[str] = mapped_column(String(32), default="战士")
    level: Mapped[int] = mapped_column(Integer, default=1)
    hp: Mapped[int] = mapped_column(Integer, default=30)
    max_hp: Mapped[int] = mapped_column(Integer, default=30)
    mp: Mapped[int] = mapped_column(Integer, default=10)
    max_mp: Mapped[int] = mapped_column(Integer, default=10)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    gold: Mapped[int] = mapped_column(Integer, default=10)
    # 六维属性：力量、敏捷、体质、智力、感知、魅力
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=lambda: {
        "str": 12, "dex": 12, "con": 12, "int": 12, "wis": 12, "cha": 12,
    })
    # 背包物品
    inventory: Mapped[dict[str, Any]] = mapped_column(JSON, default=lambda: {
        "items": [],
    })
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="characters")
    sessions: Mapped[list["GameSession"]] = relationship(back_populates="character")


class GameSession(Base):
    """游戏会话表——一次冒险的所有状态。"""
    __tablename__ = "game_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | paused | ended
    current_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    world_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    character: Mapped["Character"] = relationship(back_populates="sessions")
    event_logs: Mapped[list["GameEventLog"]] = relationship(back_populates="session")
    memories: Mapped[list["Memory"]] = relationship(back_populates="session")


class GameEventLog(Base):
    """事件日志表——记录每次 SSE 事件，用于断线重连时补发。"""
    __tablename__ = "game_events_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["GameSession"] = relationship(back_populates="event_logs")


class Memory(Base):
    """长期记忆表——关键剧情事实（为向量检索预留 embedding 字段）。"""
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["GameSession"] = relationship(back_populates="memories")
