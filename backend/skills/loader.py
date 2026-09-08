"""AI 技能包加载器：解析 `SKILL.md` 的 YAML Frontmatter + Markdown 指令正文。

标准化约定：
- 每个技能包是一个目录，目录内必须有 `SKILL.md`；
- 文件顶部用 `---` 包裹 YAML 元数据，至少包含 `name`、`description`；
- `---` 之后是 Markdown 指令正文，供 AI Agent 按需加载后作为专业能力说明；
- 可选元数据：`role`、`version`、`tags`、`allowed-tools` 等，由调用方自行解释。
"""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SKILLS_DIR = Path(
    os.getenv("SKILL_PACKS_DIR", str(Path(__file__).with_name("packs")))
)
_FRONTMATTER_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*\r?\n(.*)\Z", re.S)

_CACHE: dict[str, "SkillPack"] | None = None
_LOCK = threading.RLock()


@dataclass(frozen=True)
class SkillPack:
    """一个标准化的 AI 技能包。"""

    name: str
    description: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    path: str = ""

    def meta(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)


def _parse_skill_file(skill_file: Path) -> SkillPack | None:
    """解析单个 SKILL.md；格式非法时返回 None 并打印警告。"""
    try:
        text = skill_file.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[Skills] 无法读取 {skill_file}: {e}")
        return None

    match = _FRONTMATTER_RE.match(text)
    if not match:
        print(f"[Skills] 跳过无 YAML Frontmatter 的技能包: {skill_file}")
        return None

    raw_meta, content = match.group(1), match.group(2).strip()
    try:
        import yaml
        meta = yaml.safe_load(raw_meta)
    except Exception as e:
        print(f"[Skills] Frontmatter YAML 解析失败 {skill_file}: {e}")
        return None

    if not isinstance(meta, dict):
        print(f"[Skills] Frontmatter 不是对象，已跳过: {skill_file}")
        return None

    name = str(meta.get("name") or "").strip()
    description = str(meta.get("description") or "").strip()
    if not name or not description:
        print(f"[Skills] 技能包缺少 name 或 description: {skill_file}")
        return None
    if not content:
        print(f"[Skills] 技能包缺少 Markdown 指令正文: {skill_file}")
        return None

    return SkillPack(
        name=name,
        description=description,
        content=content,
        metadata=meta,
        path=str(skill_file),
    )


def discover_skill_packs(force: bool = False) -> dict[str, SkillPack]:
    """扫描技能包目录，按 name 返回全部合法技能包。"""
    global _CACHE
    with _LOCK:
        if _CACHE is not None and not force:
            return _CACHE

        packs: dict[str, SkillPack] = {}
        if not _SKILLS_DIR.exists():
            print(f"[Skills] 技能包目录不存在: {_SKILLS_DIR}")
            _CACHE = packs
            return packs

        for skill_file in sorted(_SKILLS_DIR.glob("*/SKILL.md")):
            pack = _parse_skill_file(skill_file)
            if pack is None:
                continue
            if pack.name in packs:
                print(f"[Skills] 技能包名称重复，后加载覆盖前一个: {pack.name}")
            packs[pack.name] = pack

        _CACHE = packs
        return packs


def reload_skill_packs() -> dict[str, SkillPack]:
    """清空缓存并重新扫描，供开发/热更新使用。"""
    return discover_skill_packs(force=True)


def get_skill_pack(name: str) -> SkillPack | None:
    return discover_skill_packs().get(str(name or "").strip())


def list_skill_packs() -> list[dict[str, Any]]:
    """返回技能包元数据列表，供 API / 调试 / 前端展示。"""
    return [
        {
            "name": p.name,
            "description": p.description,
            "path": p.path,
            "role": p.meta("role", ""),
            "version": p.meta("version", 1),
            "tags": p.meta("tags", []),
            "allowed-tools": p.meta("allowed-tools", []),
        }
        for p in discover_skill_packs().values()
    ]
