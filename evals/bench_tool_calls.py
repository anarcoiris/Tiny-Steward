"""Load provider parse fixtures and score profiles (fixture-only; no live LLM)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.providers.registry import list_providers, resolve_provider

EVALS_ROOT = Path(__file__).resolve().parent
PROVIDERS_ROOT = EVALS_ROOT / "providers"


@dataclass(frozen=True)
class FixtureCase:
    provider_id: str
    name: str
    text: str
    expected: list[dict[str, Any]]
    path: Path


def iter_fixtures(provider_id: str | None = None) -> list[FixtureCase]:
    """Yield ``*.txt`` + matching ``*.expected.json`` under evals/providers/."""
    cases: list[FixtureCase] = []
    ids = [provider_id] if provider_id else list_providers()
    for pid in ids:
        root = PROVIDERS_ROOT / pid
        if not root.is_dir():
            continue
        for txt_path in sorted(root.glob("*.txt")):
            expected_path = txt_path.with_suffix(".expected.json")
            if not expected_path.is_file():
                # Also accept stem.expected.json next to stem.txt
                expected_path = txt_path.parent / f"{txt_path.stem}.expected.json"
            if not expected_path.is_file():
                raise FileNotFoundError(f"Missing expected JSON for {txt_path}")
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
            cases.append(
                FixtureCase(
                    provider_id=pid,
                    name=txt_path.stem,
                    text=txt_path.read_text(encoding="utf-8"),
                    expected=expected,
                    path=txt_path,
                )
            )
    return cases


def score_fixtures(provider_id: str | None = None) -> dict[str, Any]:
    """Return per-provider pass counts for fixture extract_actions."""
    report: dict[str, Any] = {"providers": {}, "total": 0, "passed": 0}
    cases = iter_fixtures(provider_id)
    by_provider: dict[str, list[FixtureCase]] = {}
    for case in cases:
        by_provider.setdefault(case.provider_id, []).append(case)

    for pid, group in by_provider.items():
        profile = resolve_provider(pid, default=pid)
        passed = 0
        failures: list[dict[str, Any]] = []
        for case in group:
            got = profile.extract_actions(case.text)
            ok = got == case.expected
            if ok:
                passed += 1
            else:
                failures.append(
                    {
                        "name": case.name,
                        "expected": case.expected,
                        "got": got,
                    }
                )
        report["providers"][pid] = {
            "total": len(group),
            "passed": passed,
            "pass_rate": (passed / len(group)) if group else 1.0,
            "failures": failures,
        }
        report["total"] += len(group)
        report["passed"] += passed

    report["pass_rate"] = (report["passed"] / report["total"]) if report["total"] else 1.0
    return report


def print_scorecard(report: dict[str, Any] | None = None) -> int:
    """Print a compact scorecard; return exit code 0 if all pass."""
    report = report or score_fixtures()
    print("Provider tool-call fixture scorecard (no live LLM)")
    print("-" * 52)
    for pid, row in report["providers"].items():
        rate = row["pass_rate"] * 100
        print(f"  {pid:16s}  {row['passed']}/{row['total']}  ({rate:.0f}%)")
        for fail in row["failures"]:
            print(f"    FAIL {fail['name']}")
            print(f"      expected: {fail['expected']}")
            print(f"      got:      {fail['got']}")
    overall = report["pass_rate"] * 100
    print("-" * 52)
    print(f"  overall          {report['passed']}/{report['total']}  ({overall:.0f}%)")
    return 0 if report["passed"] == report["total"] else 1


def main() -> None:
    raise SystemExit(print_scorecard())


if __name__ == "__main__":
    main()
