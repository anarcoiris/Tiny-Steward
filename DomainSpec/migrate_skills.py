#!/usr/bin/env python3
"""
Move skills out of the broken unclassified dump into topic folders
using DomainSpec/domainspec_mapping.csv.

Usage:
  python DomainSpec/migrate_skills.py --dry-run
  python DomainSpec/migrate_skills.py
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SKILLS = ROOT / "skills"
MAPPING = HERE / "domainspec_mapping.csv"
BROKEN_MIGRATE = SKILLS / "unclassified" / "migrate.py"

# Where non-skill node types land
TYPE_FOLDERS = {
    "domain": "_infra",
    "infra_or_meta_needs_triage": "_meta",
    "policy": "_policy",
}

SKIP_NAMES = {
    "unclassified",
    "_infra",
    "_meta",
    "_policy",
    ".git",
}


def load_mapping() -> dict[str, tuple[str, str]]:
    """skill_id -> (node_type, domain_or_bucket)"""
    out: dict[str, tuple[str, str]] = {}
    with MAPPING.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sid = row["skill_id"]
            ntype = row["node_type"]
            domain = row["domain"]
            if ntype == "skill":
                bucket = domain or "unclassified"
            else:
                bucket = TYPE_FOLDERS.get(ntype, "_meta")
            out[sid] = (ntype, bucket)
    return out


def find_skill_dir(skill_id: str) -> Path | None:
    """Locate a skill dir: top-level, under unclassified, or already in a topic."""
    candidates = [
        SKILLS / skill_id,
        SKILLS / "unclassified" / skill_id,
    ]
    for p in candidates:
        if p.is_dir():
            return p
    # Already under some topic?
    for child in SKILLS.iterdir():
        if not child.is_dir() or child.name in SKIP_NAMES:
            continue
        nested = child / skill_id
        if nested.is_dir():
            return nested
    return None


def destination_for(skill_id: str, bucket: str) -> Path:
    return SKILLS / bucket / skill_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not MAPPING.exists():
        print(f"Missing mapping: {MAPPING}", file=sys.stderr)
        return 1

    mapping = load_mapping()
    moves: list[tuple[Path, Path]] = []
    missing: list[str] = []
    already_ok: list[str] = []

    for skill_id, (_ntype, bucket) in sorted(mapping.items()):
        src = find_skill_dir(skill_id)
        dst = destination_for(skill_id, bucket)
        if src is None:
            missing.append(skill_id)
            continue
        if src.resolve() == dst.resolve():
            already_ok.append(skill_id)
            continue
        moves.append((src, dst))

    # Loose files currently stuck in unclassified/
    loose_files = []
    unclass = SKILLS / "unclassified"
    if unclass.is_dir():
        for f in unclass.iterdir():
            if f.is_file() and f.name != "migrate.py":
                loose_files.append(f)

    print(f"Mapped skills: {len(mapping)}")
    print(f"Already in place: {len(already_ok)}")
    print(f"To move: {len(moves)}")
    print(f"Missing on disk: {len(missing)}")
    print(f"Loose files to restore to skills/: {len(loose_files)}")
    if missing:
        print("Missing:", ", ".join(missing[:20]))

    # Preview by bucket
    by_bucket: dict[str, int] = {}
    for _src, dst in moves:
        by_bucket[dst.parent.name] = by_bucket.get(dst.parent.name, 0) + 1
    print("\nMoves by destination bucket:")
    for b, c in sorted(by_bucket.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {b}: {c}")

    if args.dry_run:
        print("\nDry run — no changes.")
        return 0

    # Execute moves
    for src, dst in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            print(f"SKIP (exists): {dst}")
            continue
        shutil.move(str(src), str(dst))

    for f in loose_files:
        target = SKILLS / f.name
        if not target.exists():
            shutil.move(str(f), str(target))
            print(f"Restored file: {f.name}")

    # Remove broken migrate script and empty junk
    if BROKEN_MIGRATE.exists():
        BROKEN_MIGRATE.unlink()
        print("Removed broken unclassified/migrate.py")

    stray = unclass / "abusing"
    if stray.is_dir() and not any(stray.iterdir()):
        stray.rmdir()
        print("Removed empty stray unclassified/abusing/")

    # Remove unclassified if empty (or only empty leftovers)
    if unclass.is_dir():
        leftovers = list(unclass.iterdir())
        if not leftovers:
            unclass.rmdir()
            print("Removed empty unclassified/")
        else:
            print(f"Note: unclassified/ still has {len(leftovers)} entries:")
            for p in leftovers[:20]:
                print(f"  {p.name}")

    # Recount
    topic_dirs = [p for p in SKILLS.iterdir() if p.is_dir() and not p.name.startswith(".")]
    skill_leaves = sum(
        1
        for topic in topic_dirs
        for child in topic.iterdir()
        if child.is_dir() and not child.name.startswith(".")
    )
    print(f"\nDone. Topic/bucket folders: {len(topic_dirs)}; skill leaves under them: {skill_leaves}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
