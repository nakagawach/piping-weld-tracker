from progress import normalize_drawing_memo


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

for bad in [
    {"pageNumber": 0, "strokes": []},
    {"pageNumber": 1, "strokes": "bad"},
    {"pageNumber": 1, "strokes": [{"color": "#ffffff", "width": 24, "points": [[1, 2]]}]},
    {"pageNumber": 1, "strokes": [{"color": "#d93025", "width": 99, "points": [[1, 2]]}]},
    {"pageNumber": 1, "strokes": [{"color": "#d93025", "width": 24, "points": [[-1, 2]]}]},
]:
    try:
        normalize_drawing_memo(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(f"expected ValueError: {bad}")

print("drawing memo validation tests: PASS")
