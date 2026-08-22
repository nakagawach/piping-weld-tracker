import json
import os
from pathlib import Path
from urllib import error, request

from flask import Flask, jsonify, render_template, request as flask_request

app = Flask(__name__)


def get_google_vision_api_key():
    key = os.getenv("GOOGLE_VISION_API_KEY")
    if key:
        return key

    env_path = Path(__file__).with_name(".env")
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


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/ocr")
def ocr():
    api_key = get_google_vision_api_key()
    if not api_key:
        return jsonify({"error": "GOOGLE_VISION_API_KEY が設定されていません。"}), 503

    body = flask_request.get_json(silent=True) or {}
    image_base64 = body.get("imageBase64", "")
    page_number = body.get("pageNumber")

    if not isinstance(image_base64, str) or not image_base64:
        return jsonify({"error": "解析画像がありません。"}), 400
    if len(image_base64) > 12_000_000:
        return jsonify({"error": "解析画像が大きすぎます。"}), 413

    payload = {
        "requests": [
            {
                "image": {"content": image_base64},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            }
        ]
    }

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
        return jsonify({"error": "Google Vision APIエラー", "detail": detail[:1200]}), 502
    except Exception as exc:
        return jsonify({"error": "Google Vision APIへの接続に失敗しました。", "detail": str(exc)}), 502

    responses = vision_response.get("responses", [])
    if not responses:
        return jsonify({"error": "Google Vision APIから結果を取得できませんでした。"}), 502

    first = responses[0]
    if first.get("error"):
        return jsonify({"error": "Google Vision APIエラー", "detail": first["error"]}), 502

    annotations = first.get("textAnnotations", [])
    words = []
    for annotation in annotations[1:]:
        text = annotation.get("description", "")
        vertices = annotation.get("boundingPoly", {}).get("vertices", [])
        points = [
            {"x": int(vertex.get("x", 0)), "y": int(vertex.get("y", 0))}
            for vertex in vertices
        ]
        if not text or not points:
            continue
        words.append({"text": text, "vertices": points})

    return jsonify({
        "pageNumber": page_number,
        "wordCount": len(words),
        "words": words,
    })


if __name__ == "__main__":
    app.run(debug=True)
