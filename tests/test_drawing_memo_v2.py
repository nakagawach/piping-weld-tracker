import json
from pathlib import Path

from app import DB_PATH, app
from progress import normalize_drawing_memo
from tests.ui_shell_e2e import PROJECT_ID, seed_database


def memo_path(page_number):
    return DB_PATH.parent / "drawing_memos" / f"project-{PROJECT_ID}-page-{page_number}.json"


def cleanup(*pages):
    for page_number in pages:
        path = memo_path(page_number)
        if path.exists():
            path.unlink()


def main():
    seed_database()
    cleanup(1, 2, 3)

    valid = normalize_drawing_memo(
        {
            "pageNumber": 2,
            "strokes": [
                {"color": "#d93025", "width": 24, "points": [[10, 20], [30.123, 40.456]]},
                {"color": "#1967d2", "width": 12, "points": [[0, 0]]},
            ],
        }
    )
    assert valid["pageNumber"] == 2
    assert valid["strokes"][0]["points"][1] == [30.12, 40.46]

    bad_payloads = [
        {"pageNumber": 0, "strokes": []},
        {"pageNumber": 1, "strokes": "bad"},
        {"pageNumber": 1, "strokes": [{"color": "#ffffff", "width": 24, "points": [[1, 2]]}]},
        {"pageNumber": 1, "strokes": [{"color": "#d93025", "width": 99, "points": [[1, 2]]}]},
        {"pageNumber": 1, "strokes": [{"color": "#d93025", "width": 24, "points": [[-1, 2]]}]},
        {"pageNumber": 1, "strokes": [{"color": "#d93025", "width": 24, "points": []}]},
    ]
    for bad in bad_payloads:
        try:
            normalize_drawing_memo(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError: {bad}")

    client = app.test_client()
    response = client.get(f"/projects/{PROJECT_ID}/drawing-memo?page=1")
    assert response.status_code == 200
    assert response.get_json()["strokes"] == []

    payload = {
        "pageNumber": 1,
        "strokes": [
            {"color": "#d93025", "width": 24, "points": [[100, 200], [300, 400]]},
        ],
    }
    response = client.post(f"/projects/{PROJECT_ID}/drawing-memo", json=payload)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["count"] == 1
    path = memo_path(1)
    assert path.exists()
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["pageNumber"] == 1
    assert stored["strokes"][0]["points"] == [[100.0, 200.0], [300.0, 400.0]]

    response = client.get(f"/projects/{PROJECT_ID}/drawing-memo?page=1")
    assert response.status_code == 200
    loaded = response.get_json()
    assert loaded["strokes"] == stored["strokes"]
    assert loaded["updatedAt"]

    response = client.post(
        f"/projects/{PROJECT_ID}/drawing-memo",
        json={"pageNumber": 1, "strokes": []},
    )
    assert response.status_code == 200
    assert response.get_json()["count"] == 0
    assert memo_path(1).exists(), "explicit clear should persist an empty memo file, not delete user data"
    assert json.loads(memo_path(1).read_text(encoding="utf-8"))["strokes"] == []

    assert client.get(f"/projects/{PROJECT_ID}/drawing-memo?page=0").status_code == 400
    assert client.get("/projects/987654/drawing-memo?page=1").status_code == 404
    assert client.post(
        f"/projects/{PROJECT_ID}/drawing-memo",
        json={"pageNumber": 1, "strokes": [{"color": "#fff", "width": 24, "points": [[1, 2]]}]},
    ).status_code == 400

    cleanup(1, 2, 3)
    print("DRAWING_MEMO_API_VALIDATION: PASS")


if __name__ == "__main__":
    main()
