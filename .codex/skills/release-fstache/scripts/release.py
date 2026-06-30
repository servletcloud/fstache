#!/usr/bin/env python3
import argparse
import json
import re
import shlex
import subprocess
import sys
import time
import tomllib
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
PYPROJECT = REPO_ROOT / "pyproject.toml"
LOCKFILE = REPO_ROOT / "uv.lock"
PUBLISH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish.yml"
VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
POLL_INTERVAL_SECONDS = 5
RUN_POLL_ATTEMPTS = 48
PYPI_POLL_ATTEMPTS = 60


def main() -> int:
    args = parse_args()
    require_release_checkout()

    project_name, current_version = read_project_metadata()
    target_version = choose_target_version(current_version, args)
    tag = f"v{target_version}"
    require_tag_absent(tag)

    run(["uv", "version", target_version, "--no-sync"])
    changed_version = read_project_metadata()[1]
    if changed_version != target_version:
        fail(f"uv version wrote {changed_version}, expected {target_version}")

    run(["make", "post-ai-change"], capture=False)
    run(["uv", "build"], capture=False)

    run(
        [
            "git",
            "add",
            str(PYPROJECT.relative_to(REPO_ROOT)),
            str(LOCKFILE.relative_to(REPO_ROOT)),
        ]
    )
    staged = run_output(["git", "diff", "--cached", "--name-only"])
    if sorted(staged.splitlines()) != ["pyproject.toml", "uv.lock"]:
        fail(f"unexpected staged files:\n{staged}")

    commit_message = f"Release {target_version}"
    run(["git", "commit", "-m", commit_message], capture=False)
    commit_sha = run_output(["git", "rev-parse", "HEAD"])

    run(["git", "push", "origin", "main"], capture=False)
    run(["git", "tag", tag])
    run(["git", "push", "origin", tag], capture=False)

    run_id, run_url = wait_for_publish_run(tag, commit_sha)
    run(["gh", "run", "watch", run_id, "--exit-status"], capture=False)
    run_details = load_run_details(run_id)
    if run_details["conclusion"] != "success":
        fail(f"publish workflow failed: {run_details['url']}")

    pypi_summary = wait_for_pypi(project_name, target_version)
    install_summary = verify_install(project_name, target_version)

    print()
    print("Release complete")
    print(f"Project: {project_name}")
    print(f"Previous version: {current_version}")
    print(f"Released version: {target_version}")
    print(f"Commit: {commit_sha}")
    print(f"Tag: {tag}")
    print(f"GitHub Actions: {run_url}")
    print(f"PyPI summary: {pypi_summary}")
    print(f"Install check: {install_summary}")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Release fstache to PyPI.")
    parser.add_argument("version", nargs="?", help="Exact X.Y.Z version to release.")
    parser.add_argument(
        "--bump",
        choices=("patch", "minor", "major"),
        default="patch",
        help="Version component to bump when no exact version is supplied.",
    )
    args = parser.parse_args()
    if args.version and not VERSION_PATTERN.fullmatch(args.version):
        fail("exact version must use X.Y.Z numeric form, for example 2.0.0")

    return args


def require_release_checkout() -> None:
    if not PYPROJECT.exists():
        fail(f"pyproject.toml not found at {PYPROJECT}")
    if not PUBLISH_WORKFLOW.exists():
        fail(".github/workflows/publish.yml is required for tag-triggered publishing")

    branch = run_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if branch != "main":
        fail(f"release must start on main, currently on {branch}")

    status = run_output(["git", "status", "--porcelain"])
    if status:
        fail(f"release must start from a clean working tree:\n{status}")

    run(["git", "fetch", "origin", "main", "--tags"], capture=False)
    local_main = run_output(["git", "rev-parse", "HEAD"])
    remote_main = run_output(["git", "rev-parse", "origin/main"])
    if local_main != remote_main:
        fail("local main must match origin/main before releasing")

    run(["gh", "auth", "status"], capture=False)


def read_project_metadata() -> tuple[str, str]:
    with PYPROJECT.open("rb") as file:
        project = tomllib.load(file)["project"]

    return project["name"], project["version"]


def choose_target_version(current_version: str, args: argparse.Namespace) -> str:
    if not VERSION_PATTERN.fullmatch(current_version):
        fail(f"current version must use X.Y.Z numeric form, got {current_version}")
    if args.version:
        if version_tuple(args.version) <= version_tuple(current_version):
            fail(
                f"target version {args.version} must be greater than current {current_version}"
            )

        return args.version

    major, minor, patch = version_tuple(current_version)
    match args.bump:
        case "major":
            target = (major + 1, 0, 0)
        case "minor":
            target = (major, minor + 1, 0)
        case "patch":
            target = (major, minor, patch + 1)
        case _:
            fail(f"unsupported bump: {args.bump}")

    return ".".join(str(part) for part in target)


def version_tuple(version: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(version)
    if not match:
        fail(f"invalid version: {version}")

    return tuple(int(part) for part in match.groups())


def require_tag_absent(tag: str) -> None:
    local_tag = run_output(["git", "tag", "--list", tag])
    if local_tag:
        fail(f"local tag already exists: {tag}")

    remote_tag = run_output(
        ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}"]
    )
    if remote_tag:
        fail(f"remote tag already exists: {tag}")


def wait_for_publish_run(tag: str, commit_sha: str) -> tuple[str, str]:
    print(f"Waiting for publish workflow on {tag}...")
    for _ in range(RUN_POLL_ATTEMPTS):
        runs = json.loads(
            run_output(
                [
                    "gh",
                    "run",
                    "list",
                    "--workflow",
                    "publish.yml",
                    "--branch",
                    tag,
                    "--event",
                    "push",
                    "--json",
                    "databaseId,headSha,status,conclusion,url,displayTitle",
                    "--limit",
                    "10",
                ]
            )
        )
        for run_info in runs:
            if run_info["headSha"] == commit_sha:
                run_id = str(run_info["databaseId"])

                return run_id, run_info["url"]
        time.sleep(POLL_INTERVAL_SECONDS)

    fail(f"publish workflow run did not appear for {tag}")


def load_run_details(run_id: str) -> dict[str, str]:
    return json.loads(
        run_output(
            [
                "gh",
                "run",
                "view",
                run_id,
                "--json",
                "conclusion,status,url,headBranch,headSha,event,displayTitle",
            ]
        )
    )


def wait_for_pypi(project_name: str, version: str) -> str:
    print(f"Waiting for PyPI to expose {project_name}=={version}...")
    url = f"https://pypi.org/pypi/{project_name}/json"
    for attempt in range(PYPI_POLL_ATTEMPTS):
        request = urllib.request.Request(
            f"{url}?release_check={attempt}_{int(time.time())}",
            headers={"Cache-Control": "no-cache"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
        if payload["info"]["version"] == version and version in payload["releases"]:
            return payload["info"]["summary"]
        time.sleep(POLL_INTERVAL_SECONDS)

    fail(f"PyPI did not expose {project_name}=={version} in time")


def verify_install(project_name: str, version: str) -> str:
    code = (
        "import importlib.metadata as m; "
        f"name = {project_name!r}; "
        "print(m.version(name)); "
        "print(m.metadata(name)['Summary'])"
    )
    output = run_output(
        [
            "uv",
            "run",
            "--no-project",
            "--refresh",
            "--with",
            f"{project_name}=={version}",
            "python",
            "-c",
            code,
        ],
        cwd=Path("/tmp"),
    )
    lines = output.splitlines()
    if not lines or lines[0] != version:
        fail(f"install check returned unexpected output:\n{output}")

    return " | ".join(lines)


def run_output(command: list[str], *, cwd: Path = REPO_ROOT) -> str:
    completed = run(command, cwd=cwd)

    return completed.stdout.strip()


def run(
    command: list[str],
    *,
    cwd: Path = REPO_ROOT,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    print(f"+ {shlex.join(command)}")
    if capture:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    else:
        completed = subprocess.run(command, cwd=cwd, text=True, check=False)

    if completed.returncode != 0:
        if capture:
            if completed.stdout:
                print(completed.stdout, file=sys.stderr)
            if completed.stderr:
                print(completed.stderr, file=sys.stderr)
        fail(
            f"command failed with exit code {completed.returncode}: {shlex.join(command)}"
        )

    return completed


def fail(message: str) -> None:
    raise SystemExit(message)


if __name__ == "__main__":
    raise SystemExit(main())
