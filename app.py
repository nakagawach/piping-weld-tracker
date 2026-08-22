from app_legacy import DATA_DIR, DB_PATH, app
from project_routes import register_project_routes

# Keep the verified OCR / number-map / weld-progress implementation in app_legacy.py
# unchanged, and add the new project/PDF registration routes alongside it.
register_project_routes(app, DB_PATH, DATA_DIR)


if __name__ == "__main__":
    app.run(debug=True)
