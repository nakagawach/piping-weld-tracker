#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib import request

ALLOWED_CHECK_CONCLUSIONS = {"success", "neutral", "skipped"}
RUNTIME_ROOT_FILES = [
    "app.py",
    "global_favorites.py",
    "progress.py",
    "project_render.py",
    "projects.py",
    "thumbnail_grid.py",
    "ui_polish.py",
    "ui_shell.py",
    "viewer_mode.py",
]
PROTECTED_PATH_PATTERNS = [
    re.compile(r"^data/"),
    re.compile(r"(^|/)\.env(?:\.|$)"),
    re.compile(r"\.sqlite3?$", re.I),
    re.compile(r"\.pdf$", re.I),
    re.compile(r"(^|/)(?:render_)?cache(?:/|$)", re.I),
    re.compile(r"(^|/).*wsgi.*\.py$", re.I),
    re.compile(r"(^|/)mysite(?:/|$)", re.I),
    re.compile(r"^tests/.*(?:seed|fixture)", re.I),
]
DB_ADDED_LINE_PATTERNS = [
    re.compile(r"\bALTER\s+TABLE\b", re.I),
    re.compile(r"\bDROP\s+TABLE\b", re.I),
    re.compile(r"\bCREATE\s+TABLE\b", re.I),
    re.compile(r"\bPRAGMA\s+user_version\b", re.I),
    re.compile(r"\bDB_PATH\s*=", re.I),
    re.compile(r"weld_tracker\.sqlite3", re.I),
]


def fail(message):
    print(f"GATE FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def api_get(path):
    token = os.environ.get("GITHUB_TOKEN", "")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    if not token:
        fail("GITHUB_TOKEN is unavailable")
    req = request.Request(
        f"{api_url}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "piping-weld-tracker-manual-deploy-guard",
        },
    )
    with request.urlopen(req, timeout=30) as response:
        return json.load(response)


def write_output(name, value):
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def validate_sha(value, label):
    if not re.fullmatch(r"[0-9a-f]{40}", value or ""):
        fail(f"{label} must be a full 40-character lowercase commit SHA")


def is_protected_path(path):
    return any(pattern.search(path) for pattern in PROTECTED_PATH_PATTERNS)


def added_diff_has_db_change(diff_text):
    for line in diff_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        payload = line[1:]
        if any(pattern.search(payload) for pattern in DB_ADDED_LINE_PATTERNS):
            return payload.strip()
    return None


def metadata_gate(args):
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo or "/" not in repo:
        fail("GITHUB_REPOSITORY is unavailable")

    validate_sha(args.expected_sha, "expected_sha")
    validate_sha(args.qa_sha, "qa_sha")
    if args.qa_confirmation != "QA_PASS":
        fail("qa_confirmation must exactly equal QA_PASS")
    if args.qa_sha != args.expected_sha:
        fail("QA-approved SHA does not match expected SHA")

    main = api_get(f"/repos/{repo}/branches/main")
    main_sha = main["commit"]["sha"]
    validate_sha(main_sha, "main SHA")

    if args.operation == "pr_deploy":
        if args.pr_number <= 0:
            fail("pr_number must be positive for pr_deploy")
        if not args.target_branch or args.target_branch == "main":
            fail("target_branch must be a non-main PR branch")
        pr = api_get(f"/repos/{repo}/pulls/{args.pr_number}")
        if pr.get("state") != "open":
            fail("target PR is not open")
        if pr.get("base", {}).get("ref") != "main":
            fail("target PR base is not main")
        if pr.get("head", {}).get("ref") != args.target_branch:
            fail("target PR head branch does not match target_branch")
        if pr.get("head", {}).get("sha") != args.expected_sha:
            fail("target PR head SHA does not match expected_sha")
    elif args.operation == "rollback_main":
        if args.target_branch != "main":
            fail("rollback_main requires target_branch=main")
        if args.expected_sha != main_sha:
            fail("rollback_main expected_sha must equal current main HEAD")
    else:
        fail("unsupported operation")

    checks = api_get(f"/repos/{repo}/commits/{args.expected_sha}/check-runs?per_page=100")
    check_runs = checks.get("check_runs", [])
    bad_checks = []
    for check in check_runs:
        status = check.get("status")
        conclusion = check.get("conclusion")
        if status != "completed" or conclusion not in ALLOWED_CHECK_CONCLUSIONS:
            bad_checks.append(f"{check.get('name')}:{status}/{conclusion}")
    if bad_checks:
        fail("non-passing or incomplete GitHub Checks: " + ", ".join(bad_checks))

    print(f"PR number: {args.pr_number if args.operation == 'pr_deploy' else 'rollback-main'}")
    print(f"Target branch: {args.target_branch}")
    print(f"Expected SHA: {args.expected_sha}")
    print(f"QA SHA: {args.qa_sha}")
    print(f"Current main SHA: {main_sha}")
    print(f"GitHub Checks found: {len(check_runs)}")
    if not check_runs:
        print("No GitHub Checks found for target SHA; exact QA_PASS + QA SHA remain mandatory gates.")

    write_output("main_sha", main_sha)
    write_output("target_sha", args.expected_sha)


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def local_gate(args):
    actual_sha = git("rev-parse", "HEAD")
    if actual_sha != args.expected_sha:
        fail(f"checkout HEAD {actual_sha} does not match expected SHA {args.expected_sha}")

    if args.operation == "pr_deploy":
        diff_range = f"{args.main_sha}...HEAD"
        name_status = git("diff", "--name-status", diff_range)
        changed = []
        deleted = []
        for raw in name_status.splitlines():
            if not raw:
                continue
            parts = raw.split("\t")
            status = parts[0]
            path = parts[-1]
            changed.append(path)
            if status.startswith("D"):
                deleted.append(path)

        if "requirements.txt" in changed:
            fail("requirements.txt changed; dependency changes require a separate gate")
        protected = [path for path in changed if is_protected_path(path)]
        if protected:
            fail("protected paths changed: " + ", ".join(protected))
        runtime_deleted = [
            path for path in deleted
            if path in RUNTIME_ROOT_FILES or path.startswith("templates/") or path.startswith("static/")
        ]
        if runtime_deleted:
            fail("runtime file deletion detected: " + ", ".join(runtime_deleted))

        patch = git("diff", "--unified=0", diff_range, "--", "*.py")
        db_change = added_diff_has_db_change(patch)
        if db_change:
            fail("database/schema/path change detected in added Python line: " + db_change)

        print("Changed files relative to current main:")
        for path in changed:
            print(f"  {path}")
    else:
        if actual_sha != args.main_sha:
            fail("rollback checkout is not current main SHA")
        print("Rollback mode: current main runtime will be re-uploaded without DB/data changes.")

    manifest = []
    for file_name in RUNTIME_ROOT_FILES:
        path = Path(file_name)
        if not path.is_file() or path.is_symlink():
            fail(f"required runtime file missing or unsafe: {file_name}")
        manifest.append(file_name)

    for directory in ("templates", "static"):
        root = Path(directory)
        if not root.exists():
            if directory == "static":
                continue
            fail("templates directory is missing")
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                fail(f"symlink is not allowed in runtime manifest: {path}")
            if path.is_file():
                rel = path.as_posix()
                if is_protected_path(rel):
                    fail(f"protected file would enter runtime manifest: {rel}")
                manifest.append(rel)

    if not manifest:
        fail("runtime manifest is empty")

    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(f"Runtime manifest files: {len(manifest)}")
    for path in manifest:
        print(f"  upload: {path}")
    write_output("actual_sha", actual_sha)
    write_output("manifest", manifest_path.as_posix())


def build_parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    metadata = sub.add_parser("metadata")
    metadata.add_argument("--operation", required=True, choices=["pr_deploy", "rollback_main"])
    metadata.add_argument("--pr-number", required=True, type=int)
    metadata.add_argument("--target-branch", required=True)
    metadata.add_argument("--expected-sha", required=True)
    metadata.add_argument("--qa-sha", required=True)
    metadata.add_argument("--qa-confirmation", required=True)

    local = sub.add_parser("local")
    local.add_argument("--operation", required=True, choices=["pr_deploy", "rollback_main"])
    local.add_argument("--main-sha", required=True)
    local.add_argument("--expected-sha", required=True)
    local.add_argument("--manifest", required=True)
    return parser


def main():
    args = build_parser().parse_args()
    if args.command == "metadata":
        metadata_gate(args)
    else:
        local_gate(args)


if __name__ == "__main__":
    main()
