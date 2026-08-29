"""应用配置，从环境变量中加载。"""

import os
from dotenv import load_dotenv

load_dotenv()


def ensure_valid_api_key(api_key: str | None = None) -> str:
    """校验 API Key，拒绝空值或 .env.example 中的示例占位 Key。"""
    key = (api_key or settings.LLM_API_KEY or "").strip()
    lowered = key.lower()
    if not key or "your-api-key" in lowered or lowered.startswith("sk-your"):
        raise ValueError("未配置有效 API Key（当前为示例占位 Key），请在前端填写真实 Key")
    return key


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

    # ── 可选 RAG 向量/重排模型（默认关闭，不会自动下载）──
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "local")  # local | bge
    BGE_MODEL_PATH: str = os.getenv("BGE_MODEL_PATH", "models/bge-m3-q4_k_m.gguf")
    BGE_M3_DIR: str = os.getenv("BGE_M3_DIR", "models/bge-m3")
    BGE_M3_REPO: str = os.getenv("BGE_M3_REPO", "BAAI/bge-m3")
    BGE_RERANKER_PATH: str = os.getenv("BGE_RERANKER_PATH", "models/bge-reranker-base")
    BGE_MODEL_DOWNLOAD_URL: str = os.getenv(
        "BGE_MODEL_DOWNLOAD_URL",
        "https://huggingface.co/Infini-Model/BGE-M3-GGUF/resolve/main/bge-m3-q4_k_m.gguf",
    )
    BGE_RERANKER_REPO: str = os.getenv("BGE_RERANKER_REPO", "BAAI/bge-reranker-base")
    RAG_RERANK_TOP_K: int = int(os.getenv("RAG_RERANK_TOP_K", "20"))
    RAG_QUERY_CLASSIFY: bool = os.getenv("RAG_QUERY_CLASSIFY", "true").lower() in ("1", "true", "yes")

    # ── 可选 PostgreSQL / pgvector ──
    ENABLE_PGVECTOR: bool = os.getenv("ENABLE_PGVECTOR", "false").lower() in ("1", "true", "yes")

    # ── 游戏设置 ──
    MAX_ACTIVE_CONTEXT_ROUNDS: int = int(os.getenv("MAX_ACTIVE_CONTEXT_ROUNDS", "10"))
    SUMMARY_TRIGGER_ROUNDS: int = int(os.getenv("SUMMARY_TRIGGER_ROUNDS", "8"))
    MEMORY_RETRIEVAL_COUNT: int = int(os.getenv("MEMORY_RETRIEVAL_COUNT", "5"))
    RATE_LIMIT_SECONDS: float = float(os.getenv("RATE_LIMIT_SECONDS", "2.0"))


settings = Settings()
