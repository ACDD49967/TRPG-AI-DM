# -*- coding: utf-8 -*-
"""一键拉取 BGE-M3 / BGE-reranker 模型。

优先使用 ModelScope（国内镜像快，且支持忽略非必要文件）。
如网络可直连 HuggingFace，也可由 backend/model_setup.py 自动下载。
"""
from modelscope import snapshot_download

IGNORE = [
    "*.onnx", "*.onnx_data", "*.jpg", "*.jpeg", "*.png", "*.webp", "*.gif",
    "*.md", "imgs/*", "images/*", "*.DS_Store",
]

if __name__ == "__main__":
    print("downloading BAAI/bge-m3 ...")
    p1 = snapshot_download("BAAI/bge-m3", local_dir="models/bge-m3", ignore_patterns=IGNORE)
    print("bge-m3 ->", p1)

    print("downloading BAAI/bge-reranker-base ...")
    p2 = snapshot_download("BAAI/bge-reranker-base", local_dir="models/bge-reranker-base", ignore_patterns=IGNORE)
    print("bge-reranker-base ->", p2)
