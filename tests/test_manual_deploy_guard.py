import importlib.util
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / ".github" / "scripts" / "manual_deploy_guard.py"
spec = importlib.util.spec_from_file_location("manual_deploy_guard", GUARD_PATH)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def expect_gate_failure(callback, label):
    try:
        callback()
    except SystemExit as exc:
        require(exc.code == 1, f"{label}: unexpected exit code {exc.code}")
    else:
        raise AssertionError(f"{label}: gate unexpectedly passed")


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


def test_metadata_gate():
    main_sha = "a" * 40
    head_sha = "b" * 40
    original_api_get = guard.api_get
    original_write_output = guard.write_output
    original_repo = os.environ.get("GITHUB_REPOSITORY")

    def fake_api_get(path):
        if path.endswith("/branches/main"):
            return {"commit": {"sha": main_sha}}
        if path.endswith("/pulls/77"):
            return {
                "state": "open",
                "base": {"ref": "main"},
                "head": {"ref": "fix/header-disabled-thumbnail-nav", "sha": head_sha},
            }
        if "/check-runs" in path:
            return {
                "check_runs": [
                    {"name": "qa-regression", "status": "completed", "conclusion": "success"}
                ]
            }
        raise AssertionError(f"unexpected API path: {path}")

    try:
        os.environ["GITHUB_REPOSITORY"] = "nakagawach/piping-weld-tracker"
        guard.api_get = fake_api_get
        guard.write_output = lambda _name, _value: None
        good = SimpleNamespace(
            operation="pr_deploy",
            pr_number=77,
            target_branch="fix/header-disabled-thumbnail-nav",
            expected_sha=head_sha,
            qa_sha=head_sha,
            qa_confirmation="QA_PASS",
        )
        guard.metadata_gate(good)

        wrong_branch = SimpleNamespace(**{**vars(good), "target_branch": "fix/wrong"})
        expect_gate_failure(lambda: guard.metadata_gate(wrong_branch), "PR head branch gate")

        wrong_qa = SimpleNamespace(**{**vars(good), "qa_sha": main_sha})
        expect_gate_failure(lambda: guard.metadata_gate(wrong_qa), "QA SHA gate")

        rollback = SimpleNamespace(
            operation="rollback_main",
            pr_number=0,
            target_branch="main",
            expected_sha=main_sha,
            qa_sha=main_sha,
            qa_confirmation="QA_PASS",
        )
        guard.metadata_gate(rollback)
    finally:
        guard.api_get = original_api_get
        guard.write_output = original_write_output
        if original_repo is None:
            os.environ.pop("GITHUB_REPOSITORY", None)
        else:
            os.environ["GITHUB_REPOSITORY"] = original_repo


def test_rollback_local_dry_run():
    sha = "c" * 40
    original_git = guard.git
    original_write_output = guard.write_output
    try:
        guard.git = lambda *args: sha if args == ("rev-parse", "HEAD") else ""
        guard.write_output = lambda _name, _value: None
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "runtime-manifest.txt"
            args = SimpleNamespace(
                operation="rollback_main",
                main_sha=sha,
                expected_sha=sha,
                manifest=str(manifest),
            )
            guard.local_gate(args)
            lines = manifest.read_text(encoding="utf-8").splitlines()
            for runtime_file in guard.RUNTIME_ROOT_FILES:
                require(runtime_file in lines, f"rollback manifest missing {runtime_file}")
            require("requirements.txt" not in lines, "rollback manifest must not include requirements")
            require(not any(line.startswith("data/") for line in lines), "rollback manifest includes data")
    finally:
        guard.git = original_git
        guard.write_output = original_write_output


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
    test_metadata_gate()
    test_rollback_local_dry_run()
    test_workflow_structure()
    print("Manual deploy guard tests: PASS")


if __name__ == "__main__":
    main()
