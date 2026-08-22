import json
import os
from pathlib import Path
from urllib import error, request

from flask import Flask, jsonify, render_template, request as flask_request

app = Flask(__name__)


def get_openai_api_key():
    key = os.getenv("OPENAI_API_KEY")
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
        if name.strip() == "OPENAI_API_KEY":
            return value.strip().strip('"').strip("'")
    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/analyze")
def analyze():
    api_key = get_openai_api_key()
    if not api_key:
        return jsonify({"error": "OPENAI_API_KEY が設定されていません。"}), 503

    body = flask_request.get_json(silent=True) or {}
    image_data_url = body.get("imageDataUrl", "")
    page_number = body.get("pageNumber")

    if not isinstance(image_data_url, str) or not image_data_url.startswith("data:image/"):
        return jsonify({"error": "解析画像が不正です。"}), 400
    if len(image_data_url) > 12_000_000:
        return jsonify({"error": "解析画像が大きすぎます。"}), 413

    schema = {
        "type": "object",
        "properties": {
            "markers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "integer"},
                        "x": {"type": "integer", "minimum": 0, "maximum": 1000},
                        "y": {"type": "integer", "minimum": 0, "maximum": 1000},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["number", "x", "y", "confidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["markers"],
        "additionalProperties": False,
    }

    prompt = (
        "This is one page of an engineering/piping drawing. Detect only integer labels that are "
        "visibly enclosed by a circle and appear to be item/weld identifiers. Ignore dimensions, "
        "page numbers, table values, connector pin numbers, and ordinary text numbers unless they "
        "are clearly inside a circular callout. Return the center position of each detected circular "
        "label using x and y normalized from 0 to 1000, where (0,0) is the top-left of the image. "
        f"The source PDF page number is {page_number}."
    )

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-5.6"),
        "store": False,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_data_url, "detail": "high"},
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "weld_marker_detection",
                "strict": True,
                "schema": schema,
            }
        },
    }

    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=90) as response:
            openai_response = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return jsonify({"error": "OpenAI APIエラー", "detail": detail[:1000]}), 502
    except Exception as exc:
        return jsonify({"error": "OpenAI APIへの接続に失敗しました。", "detail": str(exc)}), 502

    output_text = None
    for output_item in openai_response.get("output", []):
        if output_item.get("type") != "message":
            continue
        for content in output_item.get("content", []):
            if content.get("type") == "output_text":
                output_text = content.get("text")
                break
        if output_text:
            break

    if not output_text:
        return jsonify({"error": "OpenAI APIから解析結果を取得できませんでした。"}), 502

    try:
        result = json.loads(output_text)
    except json.JSONDecodeError:
        return jsonify({"error": "OpenAI APIの解析結果をJSONとして解釈できませんでした。"}), 502

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
