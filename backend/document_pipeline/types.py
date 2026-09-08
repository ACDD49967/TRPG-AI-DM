"""统一文档处理数据结构。

所有文档格式（txt/md/docx/doc/pdf/扫描件）最终都转化为：
- DocumentPage：页级信息
- TextBlock / TableBlock / ImageBlock：结构块
- DocumentResult：父块/子块/图片/元数据
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class DocumentPipelineCancelled(Exception):
    """文档管线被外部取消（例如前端点击取消）。"""


@dataclass
class TextBlock:
    text: str
    page_no: int = 1
    bbox: tuple[float, float, float, float] | None = None
    kind: str = "text"  # text | heading | paragraph | note | footer | header
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class TableBlock:
    rows: list[list[str]]
    headers: list[str] = field(default_factory=list)
    page_start: int = 1
    page_end: int = 1
    bboxes: dict[int, tuple[float, float, float, float]] = field(default_factory=dict)
    source: str = "pdfplumber"
    meta: dict[str, Any] = field(default_factory=dict)
    header_tree: list[dict] = field(default_factory=list)
    merged_cells: list[dict] = field(default_factory=list)
    markdown: str = ""
    json_data: dict[str, Any] = field(default_factory=dict)

    def to_text(self) -> str:
        lines = []
        if self.headers:
            lines.append(" | ".join(self.headers))
        for row in self.rows:
            lines.append(" | ".join(str(c or "") for c in row))
        return "\n".join(lines)


@dataclass
class ImageBlock:
    image_path: str
    url: str
    page_no: int = 1
    width: int = 0
    height: int = 0
    context_text: str = ""
    caption: str = ""
    ocr_text: str = ""
    auto_type: str = ""           # bestiary / map / item / other
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentPage:
    page_no: int = 1
    text: str = ""
    page_type: str = "text"       # text | table | scanned | mixed
    tables: list[TableBlock] = field(default_factory=list)
    images: list[ImageBlock] = field(default_factory=list)
    blocks: list[TextBlock] = field(default_factory=list)
    raw_text: str = ""
    ocr_used: bool = False
    meta: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParentChunk:
    id: str
    doc_id: str
    role: str = "parent"          # parent
    content: str = ""
    type: str = "text"            # text | table | image | heading
    page_no: int = 1
    table_id: str | None = None
    image_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChildChunk:
    id: str
    doc_id: str
    parent_id: str
    role: str = "child"
    content: str = ""
    context: str = ""             # 15% overlap context
    type: str = "text"
    page_no: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentResult:
    source: str = ""
    title: str = ""
    doc_type: str = ""
    cleaned_text: str = ""
    pages: list[DocumentPage] = field(default_factory=list)
    tables: list[TableBlock] = field(default_factory=list)
    images: list[ImageBlock] = field(default_factory=list)
    parent_chunks: list[ParentChunk] = field(default_factory=list)
    child_chunks: list[ChildChunk] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
