"""Platform admin CLI for moderation actions."""
from __future__ import annotations

import argparse
import json
from urllib import request


def _api_request(method: str, url: str, payload: dict | None, api_key: str) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json", "X-PhiLab-API-Key": api_key}
    req = request.Request(url, data=body, headers=headers, method=method)
    with request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-url", required=True, help="Platform base URL.")
    parser.add_argument("--api-key", required=True, help="Admin API key.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ban = subparsers.add_parser("ban", help="Ban a contributor.")
    ban.add_argument("--contributor-id", required=True)
    ban.add_argument("--reason", default=None)

    unban = subparsers.add_parser("unban", help="Unban a contributor.")
    unban.add_argument("--contributor-id", required=True)

    role = subparsers.add_parser("role", help="Set admin role.")
    role.add_argument("--contributor-id", required=True)
    role.add_argument("--is-admin", choices=["true", "false"], required=True)

    invalidate = subparsers.add_parser("invalidate", help="Invalidate a result.")
    invalidate.add_argument("--result-id", required=True)
    invalidate.add_argument("--reason", default=None)

    restore = subparsers.add_parser("restore", help="Restore a result.")
    restore.add_argument("--result-id", required=True)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    base = args.platform_url.rstrip("/")
    if args.command == "ban":
        url = f"{base}/api/platform/admin/contributors/{args.contributor_id}/ban"
        payload = {"reason": args.reason} if args.reason else None
        resp = _api_request("POST", url, payload, args.api_key)
    elif args.command == "unban":
        url = f"{base}/api/platform/admin/contributors/{args.contributor_id}/unban"
        resp = _api_request("POST", url, None, args.api_key)
    elif args.command == "role":
        url = f"{base}/api/platform/admin/contributors/{args.contributor_id}/role?is_admin={args.is_admin}"
        resp = _api_request("POST", url, None, args.api_key)
    elif args.command == "invalidate":
        url = f"{base}/api/platform/admin/results/{args.result_id}/invalidate"
        payload = {"reason": args.reason} if args.reason else None
        resp = _api_request("POST", url, payload, args.api_key)
    elif args.command == "restore":
        url = f"{base}/api/platform/admin/results/{args.result_id}/restore"
        resp = _api_request("POST", url, None, args.api_key)
    else:
        raise SystemExit("Unknown command.")
    print(json.dumps(resp, indent=2))


if __name__ == "__main__":
    main()
