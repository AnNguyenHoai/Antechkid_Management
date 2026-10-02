#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a destination-bound CenterManager Git provisioning bundle.

The Git token is requested with getpass so it is not placed in shell history or
process arguments. The output can only be decrypted by the destination that
created the corresponding public provisioning request.
"""

import argparse
import getpass
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from centermanager.services.git_provisioning import create_bundle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path, help="Public request exported by the destination")
    parser.add_argument("output", type=Path, help="Encrypted bundle to send back")
    parser.add_argument("--repository-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--email", default="")
    args = parser.parse_args()

    token = getpass.getpass("Git access token (input hidden): ").strip()
    if not token:
        parser.error("Git access token is required")

    request = json.loads(args.request.read_text(encoding="utf-8"))
    payload = {
        "repository_url": args.repository_url,
        "username": args.username,
        "token": token,
        "branch": args.branch,
        "email": args.email,
        "allow_local_file_remote": False,
    }
    bundle = create_bundle(request, payload)
    args.output.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    print(f"Encrypted provisioning bundle written to: {args.output}")
    print("The bundle is destination-bound and does not contain a plaintext token.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
