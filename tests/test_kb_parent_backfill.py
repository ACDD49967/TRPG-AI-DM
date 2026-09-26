"""父块回填回归：检索命中子块时必须带回 parent_id / parent_content。

这是 SKILL 第 6 条明令"任何检索改动都要保留"的不变量；5.203 把回填逻辑搬到
`knowledge_rank.parent_context` 后，这里固定住语义。
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.engine.rag_utils as rag
import backend.knowledge_retrieval as kb_retrieval
import backend.local_vector_store as vector_store
from backend.knowledge_base import KnowledgeBase
from backend.knowledge_rank import parent_context


class TestParentContextHelper(unittest.TestCase):
    def test_matching_child_returns_parent_content(self):
        doc = {
            "child_chunks": [{"content": "子块A", "parent_id": "p1"},
                             {"content": "子块B", "parent_id": "p2"}],
            "parent_chunks": [{"id": "p1", "content": "父块A"},
                              {"id": "p2", "content": "父块B"}],
        }
        self.assertEqual(parent_context(doc, "子块B"), ("p2", "父块B"))

    def test_unknown_chunk_or_missing_structure_returns_empty(self):
        self.assertEqual(parent_context({}, "任意"), ("", ""))
        self.assertEqual(
            parent_context({"child_chunks": [{"content": "子块A", "parent_id": "p9"}]}, "子块A"),
            ("p9", ""),
            "父块缺失时仍要回填 parent_id，内容为空",
        )


class TestRetrieveBackfillsParent(unittest.TestCase):
    def test_added_document_gets_parent_backfill(self):
        with tempfile.TemporaryDirectory() as td:
            provider_before = rag.get_provider()
            rag.set_provider("local")
            try:
                with patch.object(vector_store, "VECTOR_DB", Path(td) / "vectors.sqlite3"), \
                        patch.object(kb_retrieval, "rag_rerank_or_none", return_value=None):
                    kb = KnowledgeBase(path=Path(td) / "documents.json")
                    kb.add_document(
                        title="灰石村资料",
                        content="灰石村外的小径上有一名地精斥候，手持生锈短刀，黄昏时常在村口巡逻。",
                        source="test", system="custom", username="alice",
                    )
                    hits = kb.retrieve("地精斥候", system="custom", top_k=3, username="alice")
            finally:
                rag.set_provider(provider_before)

        self.assertTrue(hits, "应至少命中一个分块")
        top = hits[0]
        self.assertIn("地精", top["text"])
        self.assertTrue(top["parent_id"], "命中子块必须带上父块 id")
        self.assertTrue(top["parent_content"], "命中子块必须回填父块内容")
        self.assertIn(top["text"], top["parent_content"], "父块应包含该子块原文")


if __name__ == "__main__":
    unittest.main()
