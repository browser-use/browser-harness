#!/usr/bin/env python3
"""Copy the canonical browser-harness skill into a package tree.

The repo keeps skills/browser-harness/SKILL.md as a symlink to avoid doc drift.
Some package builders and zip-based plugin installers do not preserve symlinks,
so packaging should call this script with an output directory and ship the
regular file it writes there.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil


def materialize(output_dir: Path) -> Path:
    repo = Path(__file__).resolve().parents[1]
    source = repo / "SKILL.md"
    target = output_dir / "skills" / "browser-harness" / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", help="package output directory")
    args = parser.parse_args(argv)
    print(materialize(Path(args.output_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
