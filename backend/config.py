"""应用配置，从环境变量中加载。"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """TRPG AI 跑团主持应用的全局配置。"""

    # ── LLM 配置（默认 OpenAI 兼容格式，不预设具体模型）──
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv(
        "LLM_BASE_URL",
        "https://api.openai.com/v1",
    )
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "")
    MAX_OUTPUT_TOKENS: int = int(os.getenv("MAX_OUTPUT_TOKENS", "4096"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.9"))

    # 兼容旧配置
    @property
    def ANTHROPIC_API_KEY(self) -> str:
        return self.LLM_API_KEY

    @property
    def MODEL_NAME(self) -> str:
        return self.LLM_MODEL_NAME

    # ── 数据库 ──
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite+aiosqlite:///./dndgame.db"
    )

    # ── 服务器 ──
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")

    # ── 游戏设置 ──
    MAX_ACTIVE_CONTEXT_ROUNDS: int = int(os.getenv("MAX_ACTIVE_CONTEXT_ROUNDS", "10"))
    SUMMARY_TRIGGER_ROUNDS: int = int(os.getenv("SUMMARY_TRIGGER_ROUNDS", "8"))
    MEMORY_RETRIEVAL_COUNT: int = int(os.getenv("MEMORY_RETRIEVAL_COUNT", "5"))
    RATE_LIMIT_SECONDS: float = float(os.getenv("RATE_LIMIT_SECONDS", "2.0"))


settings = Settings()
