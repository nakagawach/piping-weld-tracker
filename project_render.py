import base64
import json
import os
from pathlib import Path
from urllib import error, request


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
    return {"pageNumber": page_number, "wordCount": len(words), "words": words}
