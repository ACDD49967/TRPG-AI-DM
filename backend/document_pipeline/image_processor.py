"""图片提取、去重、上下文标注、存储与生物图谱自动识别。"""
from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path
from typing import Any

from backend.document_pipeline.optional_imports import get_pymupdf
from backend.document_pipeline.types import ImageBlock

_MIN_WIDTH = 180
_MIN_HEIGHT = 180
_MAX_IMAGES_PER_PAGE = 12
_BESTIARY_KEYWORDS = re.compile(
    r"怪物库|生物图鉴|图鉴|怪物|生物|怪兽|Monster|Creature|Bestiary", re.I
)
_IMAGE_EXT = {1: "png", 2: "jpeg", 3: "jpeg", 4: "gif", 5: "png", 6: "bmp"}


def _context_from_page(page_text: str, limit: int = 500) -> str:
    """保留换行地提取页面上下文，便于识别实体名称与属性。"""
    lines = []
    for line in (page_text or "").split("\n"):
        s = re.sub(r"\s+", " ", line).strip()
        if s:
            lines.append(s)
    return "\n".join(lines)[:limit]


def _is_header_line(line: str) -> bool:
    if re.search(r"怪物库|生物图鉴|图鉴|目录|Contents|目\s*录|第\s*\d+\s*页/共|页面", line, re.I):
        return True
    if re.match(r"^\s*[0-9]+\s*$", line):
        return True
    return False


def _clean_entity_name(raw: str) -> str:
    s = re.sub(r"\s+", " ", raw or "").strip()
    # 去掉常见上下文尾缀
    s = re.split(r"(?:图片|图片来源|出自|来自|图鉴|怪物库|，|,|；|;)", s)[0]
    s = s.strip(" :：·.-—")
    if len(s) > 40:
        s = s[:40]
    return s


def _extract_entity_name(context: str, caption: str, page_no: int, kind: str = "bestiary") -> str:
    """从页面上下文/图注中提取更准确的实体名。"""
    lines = [re.sub(r"\s+", " ", x).strip() for x in (context or "").split("\n") if x.strip()]
    candidates = []
    if caption:
        candidates.append(caption)
    candidates.extend(lines)

    for cand in candidates:
        s = re.sub(r"\s+", " ", cand or "").strip()
        if not s or _is_header_line(s):
            continue
        # “名字 LVxx 角色” 形式
        m = re.match(r"^(.+?)\s+LV\s*\d+", s, re.I)
        if m:
            name = _clean_entity_name(m.group(1))
            if name:
                return name
        # “名字（英文/别名/类型）” 形式
        m = re.match(r"^(.+?)[（(]", s)
        if m:
            name = _clean_entity_name(m.group(1))
            if name:
                return name
        # 去掉常见前缀后第一段
        name = _clean_entity_name(s)
        if name and not _is_header_line(name):
            return name
    return f"{'怪物' if kind == 'bestiary' else '地图'}图谱第{page_no}页"


def _extract_stats_from_context(context: str) -> dict[str, str]:
    """从页面文本中尽力提取生物属性，供图谱/图鉴使用。"""
    text = re.sub(r"\s+", " ", context or "")
    lines = [re.sub(r"\s+", " ", x).strip() for x in (context or "").split("\n") if x.strip()]
    stats: dict[str, str] = {}
    hp = re.search(r"HP\s*[:：]?\s*(\d+)", text, re.I)
    if hp:
        stats["HP"] = hp.group(1)
    ac = re.search(r"AC\s*[:：]?\s*(\d+)", text, re.I)
    if ac:
        stats["AC"] = ac.group(1)
    speed = re.search(r"速度\s*[:：]?\s*(\d+)", text)
    if speed:
        stats["速度"] = speed.group(1)
    level = re.search(r"LV\s*(\d+)", text, re.I)
    if level:
        stats["等级"] = level.group(1)
    # 角色类型只取同一行中 LV 之后的短片段，避免把后续属性吸进 name/role
    for line in lines:
        m = re.search(r"LV\s*\d+\s*([^\n]*)", line, re.I)
        if m:
            role = m.group(1).strip()
            role = re.split(r"\s+(?:HP|AC|速度|力量|敏捷|感知|体质|智力|魅力|XP|等级)\s*[:：]?", role, flags=re.I)[0]
            role = role.strip(" :：·.-—")
            if role:
                stats["角色类型"] = role[:40]
            break
    # 六维属性（D&D 4e 怪物卡常见排列）
    attrs = re.search(
        r"力量\s*(\d+).*?敏捷\s*(\d+).*?感知\s*(\d+).*?体质\s*(\d+).*?智力\s*(\d+).*?魅力\s*(\d+)",
        text, re.S,
    )
    if attrs:
        stats["力量"] = attrs.group(1)
        stats["敏捷"] = attrs.group(2)
        stats["感知"] = attrs.group(3)
        stats["体质"] = attrs.group(4)
        stats["智力"] = attrs.group(5)
        stats["魅力"] = attrs.group(6)
    return stats


def detect_image_type(context: str) -> str:
    if _BESTIARY_KEYWORDS.search(context):
        return "bestiary"
    if re.search(r"地图|Map|区域图|地形图", context, re.I):
        return "map"
    if re.search(r"物品|道具|Item", context, re.I):
        return "item"
    return "other"


def auto_register_bestiary_images(
    username: str,
    scenario_id: str,
    images: list[ImageBlock],
    system: str = "dnd4e",
) -> int:
    """将识别为生物图谱的图片自动写入图鉴，返回新增数量。

    修复：
    - 名称只取实体名，不再把整段上下文塞进名称；
    - 尽可能从页面上下文提取 HP/AC/等级/六维等属性。
    """
    try:
        from backend.media_manager import add_bestiary, _load_meta
    except Exception:
        return 0
    count = 0
    try:
        existing = _load_meta(username, "bestiary")
    except Exception:
        existing = []
    # 幂等：只和同作用域（当前剧本或通用）比较，避免通用图鉴同名图片阻止剧本副本。
    sid = str(scenario_id or "")
    scoped_existing = [i for i in existing if str(i.get("scenario_id") or "") == sid]
    existing_paths = {str(i.get("image_path") or "") for i in scoped_existing}
    existing_auto_pages = {
        ((i.get("details") or {}).get("source_page", ""), str(i.get("image_path") or ""))
        for i in scoped_existing if (i.get("details") or {}).get("auto")
    }
    for img in images or []:
        if img.auto_type != "bestiary":
            continue
        name = _extract_entity_name(img.context_text, img.caption, img.page_no, "bestiary")
        # 幂等：同一图片 URL 或同一页同图不重复写入
        if img.url in existing_paths or (img.page_no, img.url) in existing_auto_pages:
            continue
        stats = _extract_stats_from_context(img.context_text)
        add_bestiary(
            username=username,
            name=name,
            system=system,
            description=(img.context_text or "")[:300],
            stats=stats,
            image_path=img.url,
            tags=["自动识别", "怪物库", "图谱"],
            details={"source_page": img.page_no, "auto": True,
                     "source_text": (img.context_text or "")[:500]},
            scenario_id=scenario_id,
        )
        existing_paths.add(img.url)
        existing_auto_pages.add((img.page_no, img.url))
        count += 1
    return count


def auto_register_map_images(
    username: str,
    scenario_id: str,
    images: list[ImageBlock],
) -> int:
    """将识别为地图的图片自动写入地图图鉴，返回新增数量。"""
    try:
        from backend.media_manager import add_map, _load_meta
    except Exception:
        return 0
    count = 0
    try:
        existing = _load_meta(username, "maps")
    except Exception:
        existing = []
    # 幂等：只和同作用域（当前剧本或通用）比较。
    sid = str(scenario_id or "")
    existing_paths = {
        str(i.get("image_path") or "")
        for i in existing if str(i.get("scenario_id") or "") == sid
    }
    for img in images or []:
        if img.auto_type != "map":
            continue
        if img.url in existing_paths:
            continue
        name = _extract_entity_name(img.context_text, img.caption, img.page_no, "map")
        add_map(
            username=username,
            name=name,
            description=(img.context_text or "")[:300],
            image_path=img.url,
            locations=[],
            system="custom",
            details={"source_page": img.page_no, "auto": True,
                     "source_text": (img.context_text or "")[:500]},
            scenario_id=scenario_id,
        )
        existing_paths.add(img.url)
        count += 1
    return count


def auto_register_media_images(
    username: str,
    scenario_id: str,
    images: list[ImageBlock],
    system: str = "dnd4e",
) -> dict[str, int]:
    """统一注册生物/地图图片到图鉴，返回 {bestiary, map} 新增数。"""
    return {
        "bestiary": auto_register_bestiary_images(username, scenario_id, images, system=system),
        "map": auto_register_map_images(username, scenario_id, images),
    }


def extract_and_process_single_image(
    data: bytes,
    filename: str,
    doc_id: str,
    username: str = "default",
    media_root: str = "media",
) -> ImageBlock | None:
    """处理单张图片（PNG/JPG 地图、展示材料等），生成 ImageBlock。"""
    if not data:
        return None
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        if (w or 0) < _MIN_WIDTH or (h or 0) < _MIN_HEIGHT:
            return None
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
        raw = img.tobytes()
        digest = hashlib.md5(raw).hexdigest()
        base = Path(media_root) / "documents" / (doc_id or "tmp") / "images"
        base.mkdir(parents=True, exist_ok=True)
        fname = f"page_1_1_{digest[:8]}.png"
        path = base / fname
        img.save(path, "PNG")
        url = f"/media/documents/{doc_id}/images/{fname}"
        stem = Path(filename or "图片").stem
        context = _context_from_page(stem, limit=200)
        auto_type = detect_image_type(stem)
        return ImageBlock(
            image_path=str(path),
            url=url,
            page_no=1,
            width=w,
            height=h,
            context_text=context,
            caption=stem,
            ocr_text="",
            auto_type=auto_type,
            meta={"doc_id": doc_id, "username": username, "md5": digest, "single_image": True},
        )
    except Exception:
        return None


def extract_and_process_images(
    pdf_data: bytes,
    pages_meta: list[Any],
    doc_id: str,
    username: str = "default",
    media_root: str = "media",
) -> list[ImageBlock]:
    """从 PDF 提取图片，写入 media/documents/{doc_id}/images，并返回 ImageBlock。"""
    fitz = get_pymupdf()
    if fitz is None:
        return []
    blocks: list[ImageBlock] = []
    seen: set[str] = set()
    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
    except Exception:
        return []
    base = Path(media_root) / "documents" / (doc_id or "tmp") / "images"
    base.mkdir(parents=True, exist_ok=True)

    page_texts = {p.page_no: p.text or "" for p in pages_meta if hasattr(p, "page_no")}

    for pno, page in enumerate(doc, start=1):
        if pno > len(pages_meta):
            break
        imgs = page.get_images(full=True) or []
        count = 0
        for img in imgs[: _MAX_IMAGES_PER_PAGE * 2]:
            if count >= _MAX_IMAGES_PER_PAGE:
                break
            try:
                xref = img[0]
                ext = _IMAGE_EXT.get(int(img[1] or 0), "png")
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                raw = pix.tobytes(ext if ext != "jpeg" else "png")
                w, h = pix.width, pix.height
                pix = None
            except Exception:
                continue
            if w < _MIN_WIDTH or h < _MIN_HEIGHT:
                continue
            digest = hashlib.md5(raw).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)

            fname = f"page_{pno}_{count + 1}_{digest[:8]}.png"
            path = base / fname
            path.write_bytes(raw)
            url = f"/media/documents/{doc_id}/images/{fname}"

            context = _context_from_page(page_texts.get(pno, ""))
            caption = ""
            m = re.search(r"(?:图|figure|FIG)[^。\n]{0,80}", context, re.I)
            if m:
                caption = m.group(0).strip()

            auto_type = detect_image_type(context)
            blocks.append(ImageBlock(
                image_path=str(path),
                url=url,
                page_no=pno,
                width=w,
                height=h,
                context_text=context,
                caption=caption,
                ocr_text="",
                auto_type=auto_type,
                meta={"doc_id": doc_id, "username": username, "md5": digest},
            ))
            count += 1
        # 超页保护
        if len(blocks) > 500:
            break
    try:
        doc.close()
    except Exception:
        pass
    return blocks
