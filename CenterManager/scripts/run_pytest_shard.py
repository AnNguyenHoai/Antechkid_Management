"""Run a deterministic subset of the Windows pytest suite.

Sharding only changes scheduling; all test files are still executed exactly once
across the matrix. Tests within a file remain in their original order.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pytest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    args = parser.parse_args()
    if args.count < 1 or not (0 <= args.shard < args.count):
        parser.error("Invalid shard")
    files = sorted(Path("tests").rglob("test_*.py"))
    chosen = [str(path) for index, path in enumerate(files) if index % args.count == args.shard]
    if not chosen:
        parser.error("Empty shard")
    print(f"Pytest shard {args.shard + 1}/{args.count}: {len(chosen)} of {len(files)} files", flush=True)
    return pytest.main([
        *chosen, "--tb=short", "--durations=25", "--timeout=120",
        "--timeout-method=thread", f"--junitxml=pytest-report-shard-{args.shard}.xml",
    ])


if __name__ == "__main__":
    sys.exit(main())
