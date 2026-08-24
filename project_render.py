import base64
import json
import os
import re
import unicodedata
from pathlib import Path
from urllib import error, request


_DINGBAT_DIGITS = str.maketrans({
    "❶": "1", "❷": "2", "❸": "3", "❹": "4", "❺": "5",
    "❻": "6", "❼": "7", "❽": "8", "❾": "9", "❿": "10",
    "➀": "1", "➁": "2", "➂": "3", "➃": "4", "➄": "5",
    "➅": "6", "➆": "7", "➇": "8", "➈": "9", "➉": "10",
})
_HYPHENS = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-", "ー": "-"})
_ALPHA_NUMERIC = re.compile(r"^(?:[A-Z]{1,4}[-/]?\d{1,4}(?:[-/][A-Z0-9]{1,4})?|\d{1,4}[-/]?[A-Z]{1,3})$")
_LETTER_PART = re.compile(r"^[A-Z]{1,4}[-/]?$")
_DIGIT_PART = re.compile(r"^\d{1,4}$")


def render_cached(pdf_path: Path, cache_path: Path, page_number: int, long_edge: int, image_format: str):
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path, True

    import pypdfium2 as pdfium

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    document = page = bitmap = None
    try:
        document = pdfium.PdfDocument(str(pdf_path))
        if page_number > len(document):
            raise ValueError("指定ページがPDFのページ数を超えています。")
        page = document[page_number - 1]
        width, height = page.get_size()
        bitmap = page.render(scale=long_edge / max(width, height))
        image = bitmap.to_pil()
        temp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        if image_format == "jpeg":
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(temp_path, format="JPEG", quality=90, optimize=False)
        else:
            image.save(temp_path, format="PNG", optimize=False)
        temp_path.replace(cache_path)
        return cache_path, False
    finally:
        if bitmap is not None:
            bitmap.close()
        if page is not None:
            page.close()
        if document is not None:
            document.close()


def normalize_label(value):
    text = unicodedata.normalize("NFKC", str(value or "")).translate(_DINGBAT_DIGITS).translate(_HYPHENS)
    text = re.sub(r"\s+", "", text).upper()
    pairs = (("(", ")"), ("[", "]"), ("{", "}"), ("<", ">"))
    changed = True
    while changed and len(text) >= 2:
        changed = False
        for left, right in pairs:
            if text.startswith(left) and text.endswith(right):
                text = text[1:-1]
                changed = True
                break
    text = text.strip(".,:;・")
    if not text or len(text) > 12:
        return None
    if text.isdigit():
        number = int(text)
        return str(number) if 1 <= number <= 999 else None
    if _ALPHA_NUMERIC.fullmatch(text):
        return text
    return None


def _token_text(value):
    return unicodedata.normalize("NFKC", str(value or "")).translate(_DINGBAT_DIGITS).translate(_HYPHENS).strip().upper()


def _bbox(vertices):
    if not vertices:
        return None
    xs = [int(v.get("x", 0)) for v in vertices]
    ys = [int(v.get("y", 0)) for v in vertices]
    if not xs or not ys:
        return None
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    return {"x": x1, "y": y1, "w": max(1, x2 - x1), "h": max(1, y2 - y1)}


def _union_bbox(a, b):
    x1, y1 = min(a["x"], b["x"]), min(a["y"], b["y"])
    x2 = max(a["x"] + a["w"], b["x"] + b["w"])
    y2 = max(a["y"] + a["h"], b["y"] + b["h"])
    return {"x": x1, "y": y1, "w": max(1, x2 - x1), "h": max(1, y2 - y1)}


def _vertical_overlap(a, b):
    top = max(a["y"], b["y"])
    bottom = min(a["y"] + a["h"], b["y"] + b["h"])
    return max(0, bottom - top) / max(1, min(a["h"], b["h"]))


def _horizontal_gap(a, b):
    if a["x"] <= b["x"]:
        return b["x"] - (a["x"] + a["w"])
    return a["x"] - (b["x"] + b["w"])


def extract_label_candidates(words):
    prepared = []
    candidates = []
    seen = set()

    def add(label, box):
        key = (label, round(box["x"] / 3), round(box["y"] / 3), round(box["w"] / 3), round(box["h"] / 3))
        if key in seen:
            return
        seen.add(key)
        candidates.append({"number": label, "source": "ocr", "bbox": box})

    for word in words:
        box = _bbox(word.get("vertices", []))
        if box is None:
            continue
        raw = _token_text(word.get("text", ""))
        prepared.append({"raw": raw, "bbox": box})
        label = normalize_label(raw)
        if label:
            add(label, box)

    # Vision sometimes separates labels such as F1 or S2 into adjacent tokens.
    # Only combine a short letter token and a numeric token that are on the same line and close together.
    for index, item in enumerate(prepared):
        raw = item["raw"]
        if not (_LETTER_PART.fullmatch(raw) or _DIGIT_PART.fullmatch(raw)):
            continue
        best = None
        best_gap = None
        for other_index, other in enumerate(prepared):
            if index == other_index:
                continue
            other_raw = other["raw"]
            complementary = (
                (_LETTER_PART.fullmatch(raw) and _DIGIT_PART.fullmatch(other_raw))
                or (_DIGIT_PART.fullmatch(raw) and _LETTER_PART.fullmatch(other_raw))
            )
            if not complementary or _vertical_overlap(item["bbox"], other["bbox"]) < 0.55:
                continue
            gap = _horizontal_gap(item["bbox"], other["bbox"])
            max_gap = max(item["bbox"]["h"], other["bbox"]["h"]) * 0.9
            if gap < -max_gap * 0.25 or gap > max_gap:
                continue
            if best_gap is None or gap < best_gap:
                best = other
                best_gap = gap
        if best is None:
            continue
        left, right = (item, best) if item["bbox"]["x"] <= best["bbox"]["x"] else (best, item)
        label = normalize_label(left["raw"] + right["raw"])
        if label:
            add(label, _union_bbox(left["bbox"], right["bbox"]))

    return candidates


def _vision_key(app_dir: Path):
    key = os.getenv("GOOGLE_VISION_API_KEY")
    if key:
        return key
    env_path = app_dir / ".env"
    if not env_path.exists():
        return None
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "GOOGLE_VISION_API_KEY":
            return value.strip().strip('"').strip("'")
    return None


def vision_ocr(image_path: Path, page_number: int, app_dir: Path):
    api_key = _vision_key(app_dir)
    if not api_key:
        raise RuntimeError("GOOGLE_VISION_API_KEY が設定されていません。")

    image_base64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {"requests": [{"image": {"content": image_base64}, "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]}]}
    req = request.Request(
        f"https://vision.googleapis.com/v1/images:annotate?key={api_key}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=90) as response:
            vision_response = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google Vision APIエラー: {detail[:1200]}") from exc
    except Exception as exc:
        raise RuntimeError(f"Google Vision APIへの接続に失敗しました: {exc}") from exc

    responses = vision_response.get("responses", [])
    if not responses:
        raise RuntimeError("Google Vision APIから結果を取得できませんでした。")
    first = responses[0]
    if first.get("error"):
        raise RuntimeError(f"Google Vision APIエラー: {first['error']}")

    words = []
    for annotation in first.get("textAnnotations", [])[1:]:
        text = annotation.get("description", "")
        vertices = annotation.get("boundingPoly", {}).get("vertices", [])
        points = [{"x": int(v.get("x", 0)), "y": int(v.get("y", 0))} for v in vertices]
        if text and points:
            words.append({"text": text, "vertices": points})
    return {
        "pageNumber": page_number,
        "wordCount": len(words),
        "words": words,
        "candidates": extract_label_candidates(words),
    }
