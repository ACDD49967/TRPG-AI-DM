"""剧本导入门面：文件读取 / 切分 / LLM 切分 / 总结与建剧本。

实现已按职责拆到 scenario_text_io / scenario_split / scenario_llm_split /
scenario_generate；这里再导出，保证既有 import 不变。
"""

from backend.scenario_text_io import (  # noqa: E402
    SUPPORTED_EXTENSIONS,
    _extract_doc,
    _extract_docx,
    _extract_pdf,
    extract_text,
    normalize_text,
)
from backend.scenario_split import (  # noqa: E402
    _char_ngrams,
    _cosine,
    _join_chunk,
    _merge_vec,
    _vec,
    split_text,
    split_text_naive,
    split_text_recursive,
    split_text_semantic,
)
from backend.scenario_llm_split import (  # noqa: E402
    LLM_SPLIT_CHUNK_CHARS,
    LLM_SPLIT_MAX_CALLS,
    LLM_SPLIT_MAX_TOKENS,
    LLM_SPLIT_PROMPT,
    _llm_split_segment,
    _parse_split_payload,
    _split_for_llm,
    llm_split_text,
)
from backend.scenario_generate import (  # noqa: E402
    SUMMARY_PROMPT,
    _fallback_summary,
    generate_scenario_from_text,
    generate_summary,
)
# 规则系统识别属于 game_systems，但导入端点历来从本门面取；补上再导出，
# 否则 routers/scenarios_import 的懒加载 import 会在运行时抛 ImportError（端点 500）。
from backend.engine.game_systems import detect_game_system  # noqa: E402,F401

__all__ = [
    "detect_game_system",
    "SUPPORTED_EXTENSIONS",
    "_extract_doc",
    "_extract_docx",
    "_extract_pdf",
    "extract_text",
    "normalize_text",
    "_char_ngrams",
    "_cosine",
    "_join_chunk",
    "_merge_vec",
    "_vec",
    "split_text",
    "split_text_naive",
    "split_text_recursive",
    "split_text_semantic",
    "LLM_SPLIT_CHUNK_CHARS",
    "LLM_SPLIT_MAX_CALLS",
    "LLM_SPLIT_MAX_TOKENS",
    "LLM_SPLIT_PROMPT",
    "_llm_split_segment",
    "_parse_split_payload",
    "_split_for_llm",
    "llm_split_text",
    "SUMMARY_PROMPT",
    "_fallback_summary",
    "generate_scenario_from_text",
    "generate_summary",
]
