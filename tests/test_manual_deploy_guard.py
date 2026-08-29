import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / ".github" / "scripts" / "manual_deploy_guard.py"
spec = importlib.util.spec_from_file_location("manual_deploy_guard", GUARD_PATH)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def test_guard_functions():
    protected = [
        "data/weld_tracker.sqlite3",
        "data/pdfs/user.pdf",
        ".env",
        ".env.production",
        "cache/page.png",
        "tests/seed_fixture.py",
        "production_wsgi.py",
        "mysite/app.py",
    ]
    for path in protected:
        require(guard.is_protected_path(path), f"protected path missed: {path}")

    allowed = [
        "app.py",
        "templates/project_progress.html",
        "static/app.css",
        "tests/ui_shell_e2e.py",
    ]
    for path in allowed:
        require(not guard.is_protected_path(path), f"safe path rejected: {path}")

    require(
        guard.added_diff_has_db_change("+connection.execute('ALTER TABLE x ADD y TEXT')"),
        "ALTER TABLE was not detected",
    )
    require(
        guard.added_diff_has_db_change("+DB_PATH = Path('/tmp/test.sqlite3')"),
        "DB path change was not detected",
    )
    require(
        guard.added_diff_has_db_change(" context\n-old\n+button:disabled{cursor:not-allowed}") is None,
        "ordinary UI diff was incorrectly treated as DB change",
    )

    expected_runtime = {
        "app.py",
        "global_favorites.py",
        "progress.py",
        "project_render.py",
        "projects.py",
        "thumbnail_grid.py",
        "ui_polish.py",
        "ui_shell.py",
        "viewer_mode.py",
    }
    require(set(guard.RUNTIME_ROOT_FILES) == expected_runtime, "runtime allowlist drifted")


def test_workflow_structure():
    legacy = [
        ROOT / ".github" / "workflows" / "deploy-pythonanywhere.yml",
        ROOT / ".github" / "workflows" / "deploy-ui-shell-v3.yml",
        ROOT / ".github" / "workflows" / "deploy-rotation-stability-test.yml",
    ]
    for path in legacy:
        text = path.read_text(encoding="utf-8")
        require("\n  push:" not in text, f"legacy push deploy still enabled: {path.name}")
        require("workflow_dispatch:" in text, f"legacy workflow unexpectedly lost manual trigger: {path.name}")

    ci_text = (ROOT / ".github" / "workflows" / "ui-shell-v3.yml").read_text(encoding="utf-8")
    require("UI Shell V3 Browser Regression" in ci_text, "non-deploy browser CI missing")

    manual = (ROOT / ".github" / "workflows" / "deploy-pythonanywhere-dev.yml").read_text(encoding="utf-8")
    require("workflow_dispatch:" in manual, "manual deploy workflow lacks workflow_dispatch")
    require("\n  push:" not in manual, "manual deploy workflow must never deploy on push")
    require("\n  pull_request:" not in manual, "manual deploy workflow must never deploy on PR event")
    require("qa_confirmation" in manual and "qa_sha" in manual, "QA gates are missing")
    require("checks: read" in manual, "GitHub Checks read permission missing")
    require("pythonanywhere-runtime-manifest.txt" in manual, "full runtime manifest is not used")
    require("upload_file \"requirements.txt\"" not in manual, "requirements must not be uploaded")
    require("upload_file \".env\"" not in manual and "upload_file .env" not in manual, ".env must not be uploaded")
    require("All allowlisted runtime files uploaded successfully. Reload is now permitted." in manual, "partial upload reload gate marker missing")
    require(
        manual.index("Upload complete allowlisted runtime snapshot") < manual.index("Reload shared PythonAnywhere web app"),
        "reload step appears before complete upload step",
    )
    require("${PUBLIC_ORIGIN}/" in manual, "mysite root smoke check missing")
    require("/weld/projects-screen" in manual, "weld smoke check missing")


def main():
    test_guard_functions()
    test_workflow_structure()
    print("Manual deploy guard tests: PASS")


if __name__ == "__main__":
    main()
