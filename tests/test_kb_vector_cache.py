"""知识库索引/向量缓存回归：分词缓存与批量取向量不改变检索结果。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.engine.rag_utils as rag
import backend.knowledge_base as kb_module
import backend.knowledge_retrieval as kb_retrieval
import backend.local_vector_store as vector_store
from backend.knowledge_base import KnowledgeBase, _tokenize


class TestTokenCache(unittest.TestCase):
    def test_repeated_tokenize_reuses_cached_result(self):
        text = "灰石村外的地精斥候正在巡逻。"
        first = _tokenize(text)
        second = _tokenize(text)
        self.assertIs(first, second)
        self.assertEqual(first, kb_module._tokenize_uncached(text))


class TestVectorBatchLoad(unittest.TestCase):
    def test_retrieve_builds_and_reuses_persisted_vectors(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            kb_path = root / "documents.json"
            provider_before = rag.get_provider()
            rag.set_provider("local")
            try:
                with patch.object(vector_store, "VECTOR_DB", root / "vectors.sqlite3"), \
                     patch.object(kb_retrieval, "rag_rerank_or_none", return_value=None):
                    kb = KnowledgeBase(path=kb_path)
                    kb.add_document(
                        title="灰石村资料",
                        content="灰石村外的小径上有一名地精斥候，手持生锈短刀，黄昏时常在村口巡逻。",
                        source="test", system="custom", username="alice",
                    )
                    first = kb.retrieve("地精斥候", system="custom", top_k=3, username="alice")
                    self.assertTrue(first)
                    self.assertIn("地精", first[0]["text"])

                    stats = vector_store.vector_stats()
                    self.assertGreater(stats["count"], 0)

                    # 新实例（模拟重启）应能从持久化向量批量取回，结果保持一致
                    fresh = KnowledgeBase(path=kb_path)
                    second = fresh.retrieve("地精斥候", system="custom", top_k=3, username="alice")
                    self.assertEqual([s["text"] for s in first], [s["text"] for s in second])
            finally:
                rag.set_provider(provider_before)

    def test_load_vectors_by_hashes_returns_each_hash_once(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(vector_store, "VECTOR_DB", Path(td) / "vectors.sqlite3"):
                vector_store.save_vectors_batch("local", [
                    {"doc_id": "d1", "chunk_index": 0, "content_md5": "h1", "dense": [1.0, 0.0], "sparse": None},
                    {"doc_id": "d2", "chunk_index": 0, "content_md5": "h1", "dense": [1.0, 0.0], "sparse": None},
                    {"doc_id": "d2", "chunk_index": 1, "content_md5": "h2", "dense": None, "sparse": {"a": 0.5}},
                ])
                found = vector_store.load_vectors_by_hashes("local", ["h1", "h2", "missing"])
        self.assertEqual(set(found), {"h1", "h2"})
        self.assertEqual(found["h1"][0], [1.0, 0.0])
        self.assertEqual(found["h2"][1], {"a": 0.5})


if __name__ == "__main__":
    unittest.main()
