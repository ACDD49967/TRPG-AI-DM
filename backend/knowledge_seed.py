"""内置规则种子：把各系统的规则备注写入知识库（幂等，按 doc id 去重）。

从 `knowledge_retrieval` 拆出；`KnowledgeRetrievalMixin` 继承本 mixin，
调用方（`routers/knowledge.py`、`knowledge_base`）的 `seed_builtin_rules()` 不变。
"""
from __future__ import annotations

from datetime import datetime

from backend.engine.game_systems import build_stat_glossary, build_system_rule_block
from backend.scenario_importer import split_text


class KnowledgeSeedMixin:
    def seed_builtin_rules(self):
        """将内置规则备注写入知识库（幂等，按 doc id 去重）。"""
        self.load()
        existing_ids = {d["id"] for d in self.documents}
        seeds = [
            {
                "id": "builtin-rules-dnd5e",
                "title": "D&D 5e 规则备注",
                "content": build_system_rule_block("dnd5e") + "\n\n" + build_stat_glossary("dnd5e"),
                "source": "builtin",
                "system": "dnd5e",
                "tags": ["规则书", "DND5e"],
            },
            {
                "id": "builtin-rules-dnd4e",
                "title": "D&D 4e 规则备注",
                "content": build_system_rule_block("dnd4e") + "\n\n" + build_stat_glossary("dnd4e"),
                "source": "builtin",
                "system": "dnd4e",
                "tags": ["规则书", "DND4e"],
            },
            {
                "id": "builtin-rules-coc",
                "title": "COC 7e 规则备注",
                "content": build_system_rule_block("coc") + "\n\n" + build_stat_glossary("coc"),
                "source": "builtin",
                "system": "coc",
                "tags": ["规则书", "COC7e"],
            },
            {
                "id": "builtin-rules-custom",
                "title": "自定义规则通用备注",
                "content": build_system_rule_block("custom"),
                "source": "builtin",
                "system": "custom",
                "tags": ["规则书", "自定义"],
            },
        ]
        for seed in seeds:
            doc = {
                "id": seed["id"],
                "title": seed["title"],
                "content": seed["content"],
                "chunks": split_text(seed["content"], mode="naive", chunk_size=900),
                "source": seed["source"],
                "system": seed["system"],
                "tags": seed["tags"],
                "owner": "builtin",
                "created_at": datetime.now().isoformat(),
            }
            if seed["id"] in existing_ids:
                # 内置规则随版本更新，覆盖旧内容（例如修正 COC 衍生公式）
                for i, d in enumerate(self.documents):
                    if d["id"] == seed["id"]:
                        self.documents[i] = doc
                        break
            else:
                self.documents.append(doc)
                existing_ids.add(seed["id"])
        self.save()
