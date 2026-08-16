"""切分功能测试：拉取/生成多种格式剧本，验证格式识别、文本提取与切分。"""

import json
import urllib.request
from pathlib import Path

from backend.engine.game_systems import detect_game_system
from backend.scenario_importer import extract_text, split_text, split_text_semantic

OUT_DIR = Path("eval_results/samples")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DELIAN_URL = "https://raw.githubusercontent.com/World-Smiths/the-delian-tomb/main/README.md"
COC_PDF_URL = "https://www.chaosium.com/content/FreePDFs/CoC/CHA23131%20Call%20of%20Cthulhu%207th%20Edition%20Quick-Start%20Rules.pdf"


def fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def make_docx(path: Path, text: str) -> None:
    from docx import Document
    doc = Document()
    for para in text.split("\n"):
        doc.add_paragraph(para)
    doc.save(str(path))


def make_doc_fallback(path: Path, text: str) -> None:
    # 使用 UTF-8 纯文本模拟 .doc 的 fallback 提取路径
    path.write_text(text, encoding="utf-8")


def run():
    report = {}
    sample_text = fetch(DELIAN_URL).decode("utf-8", errors="replace")

    # 1) .md（网络原文）
    md_path = OUT_DIR / "delian-tomb.md"
    md_path.write_text(sample_text, encoding="utf-8")
    # 2) .txt（同一份内容，验证纯文本读取）
    txt_path = OUT_DIR / "delian-tomb.txt"
    txt_path.write_text(sample_text, encoding="utf-8")
    # 3) .docx（用 python-docx 生成）
    docx_path = OUT_DIR / "delian-tomb.docx"
    make_docx(docx_path, sample_text)
    # 4) .doc（fallback 纯文本）
    doc_path = OUT_DIR / "delian-tomb.doc"
    make_doc_fallback(doc_path, sample_text)
    # 5) .pdf（COC Quick-Start 官方 PDF）
    pdf_path = OUT_DIR / "coc-quickstart.pdf"
    pdf_path.write_bytes(fetch(COC_PDF_URL))

    samples = [
        ("md", md_path),
        ("txt", txt_path),
        ("docx", docx_path),
        ("doc", doc_path),
        ("pdf", pdf_path),
    ]

    for label, path in samples:
        data = path.read_bytes()
        try:
            text = extract_text(path.name, data)
            chunks_naive = split_text(text, mode="naive", chunk_size=900)
            chunks_semantic = split_text_semantic(text, max_chunk_size=1200, min_chunk_size=400)
            system = detect_game_system(text, path.name)
            report[label] = {
                "file": path.name,
                "size_bytes": len(data),
                "extracted_chars": len(text),
                "naive_chunks": len(chunks_naive),
                "semantic_chunks": len(chunks_semantic),
                "detected_system": system,
                "first_chunk_preview": text[:120].replace("\n", " "),
                "naive_first_chunk_preview": chunks_naive[0][:120].replace("\n", " ") if chunks_naive else "",
                "semantic_first_chunk_preview": chunks_semantic[0][:120].replace("\n", " ") if chunks_semantic else "",
                "ok": True,
            }
            print(f"[OK] {label:5s} chars={len(text):6d} naive={len(chunks_naive):3d} semantic={len(chunks_semantic):3d} system={system}")
        except Exception as e:
            report[label] = {"file": path.name, "ok": False, "error": str(e)}
            print(f"[FAIL] {label}: {e}")

    report_path = Path("eval_results/split_test_report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告已写入 {report_path}")


if __name__ == "__main__":
    run()
