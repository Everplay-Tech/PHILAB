"""PHILAB Contribution CLI."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib import parse, request

CONFIG_PATH = Path.home() / ".philab" / "config.json"
DEFAULT_PLATFORM_URL = "https://api.philab.everplay.tech"


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def _save_config(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _api_request(method: str, url: str, payload: dict | None = None, api_key: str | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-PhiLab-API-Key"] = api_key
    req = request.Request(url, data=body, headers=headers, method=method)
    with request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def register(args: argparse.Namespace) -> None:
    url = args.platform_url.rstrip("/") + "/api/platform/register"
    payload = {"username": args.username, "email": args.email}
    resp = _api_request("POST", url, payload)
    config = _load_config()
    config.update({
        "platform_url": args.platform_url,
        "api_key": resp.get("api_key"),
        "contributor_id": resp.get("id"),
        "username": resp.get("username"),
    })
    _save_config(config)
    print(f"✓ Registered as {resp.get('username')}")
    print(f"  API Key: {resp.get('api_key')}")
    print(f"  Saved to {CONFIG_PATH}")


def list_tasks(args: argparse.Namespace) -> None:
    url = args.platform_url.rstrip("/") + "/api/platform/tasks"
    params = {}
    if args.status:
        params["status"] = args.status
    if args.priority is not None:
        params["priority"] = str(args.priority)
    if params:
        url += "?" + parse.urlencode(params)
    resp = _api_request("GET", url)
    for task in resp:
        print(f"{task['id']} | {task['name']} | {task['status']} | {task['runs_completed']}/{task['runs_needed']}")


def run_task(args: argparse.Namespace) -> None:
    config = _load_config()
    platform_url = args.platform_url or config.get("platform_url") or DEFAULT_PLATFORM_URL
    api_key = config.get("api_key")
    if not api_key:
        raise SystemExit("Missing API key. Run register first.")
    task_url = platform_url.rstrip("/") + f"/api/platform/tasks/{args.task_id}"
    task = _api_request("GET", task_url)
    spec_dir = Path.home() / ".philab" / "tasks"
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / f"{args.task_id}.yaml"
    spec_path.write_text(task["spec_yaml"], encoding="utf-8")

    command = [
        sys.executable,
        "phi2_lab/scripts/run_experiment.py",
        "--spec",
        str(spec_path),
        "--preset",
        args.preset,
        "--geometry-telemetry",
        "--submit-to",
        platform_url,
        "--api-key",
        api_key,
        "--task-id",
        args.task_id,
    ]
    subprocess.run(command, check=False)


def my_runs(args: argparse.Namespace) -> None:
    config = _load_config()
    platform_url = args.platform_url or config.get("platform_url") or DEFAULT_PLATFORM_URL
    api_key = config.get("api_key")
    contributor_id = config.get("contributor_id")
    if not api_key or not contributor_id:
        raise SystemExit("Missing API key or contributor id. Run register first.")
    url = platform_url.rstrip("/") + f"/api/platform/results?contributor_id={contributor_id}"
    resp = _api_request("GET", url, api_key=api_key)
    for result in resp:
        print(f"{result['id']} | task={result['task_id']} | {result['submitted_at']} | valid={result['is_valid']}")


def leaderboard(args: argparse.Namespace) -> None:
    url = args.platform_url.rstrip("/") + "/api/platform/contributors"
    params = {"sort_by": args.sort_by, "limit": str(args.limit)}
    url += "?" + parse.urlencode(params)
    resp = _api_request("GET", url)
    for idx, contributor in enumerate(resp, start=1):
        print(f"{idx}. {contributor['username']} | runs={contributor['runs_completed']} | compute={contributor['compute_donated_seconds']}s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-url", default=None, help="Override platform base URL.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_cmd = subparsers.add_parser("register", help="Register as a contributor.")
    register_cmd.add_argument("--username", required=True)
    register_cmd.add_argument("--email", default=None)
    register_cmd.set_defaults(func=register)

    tasks_cmd = subparsers.add_parser("list-tasks", help="List available tasks.")
    tasks_cmd.add_argument("--status", default=None)
    tasks_cmd.add_argument("--priority", type=int, default=None)
    tasks_cmd.set_defaults(func=list_tasks)

    run_cmd = subparsers.add_parser("run", help="Run a task locally and submit results.")
    run_cmd.add_argument("--task-id", required=True)
    run_cmd.add_argument("--preset", default="gpu_starter")
    run_cmd.set_defaults(func=run_task)

    runs_cmd = subparsers.add_parser("my-runs", help="List your submitted runs.")
    runs_cmd.set_defaults(func=my_runs)

    leaderboard_cmd = subparsers.add_parser("leaderboard", help="Show top contributors.")
    leaderboard_cmd.add_argument("--sort-by", default="runs")
    leaderboard_cmd.add_argument("--limit", type=int, default=20)
    leaderboard_cmd.set_defaults(func=leaderboard)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.platform_url is None:
        config = _load_config()
        args.platform_url = config.get("platform_url") or DEFAULT_PLATFORM_URL
    args.func(args)


if __name__ == "__main__":
    main()
