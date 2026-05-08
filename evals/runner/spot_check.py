"""Evaluate assertions from a prompt's spot_check block against an output file.

Used both as a library (for tests) and as a CLI (`python -m runner.spot_check ...`).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from random import Random

from runner.prompts import (
    Assertion,
    DurationAssertion,
    FFprobeFieldAssertion,
    FileExistsAssertion,
    NoBlackFramesAtStartAssertion,
    Prompt,
    load_prompts,
)


@dataclass
class AssertionResult:
    passed: bool
    detail: str


def _ffprobe_json(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path),
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return json.loads(result.stdout)


def _eval_file_exists(path: Path) -> AssertionResult:
    return AssertionResult(passed=path.exists(), detail="exists" if path.exists() else "missing")


def _eval_duration(path: Path, a: DurationAssertion) -> AssertionResult:
    info = _ffprobe_json(path)
    actual = float(info["format"]["duration"])
    if a.op == "approx":
        passed = abs(actual - a.value) <= a.tolerance
    elif a.op == "exact":
        passed = actual == a.value
    elif a.op == "less_than":
        passed = actual < a.value
    elif a.op == "greater_than":
        passed = actual > a.value
    else:
        raise ValueError(f"unknown duration op: {a.op}")
    return AssertionResult(passed=passed, detail=f"actual={actual:.3f}s expected {a.op} {a.value}±{a.tolerance}")


def _eval_ffprobe_field(path: Path, a: FFprobeFieldAssertion) -> AssertionResult:
    info = _ffprobe_json(path)
    streams = info.get("streams", [])
    if a.stream >= len(streams):
        return AssertionResult(passed=False, detail=f"stream {a.stream} not present")
    actual = streams[a.stream].get(a.key)
    if a.equals is not None:
        passed = actual == a.equals
        return AssertionResult(passed=passed, detail=f"{a.key}={actual!r} expected={a.equals!r}")
    if a.contains is not None:
        passed = a.contains in str(actual or "")
        return AssertionResult(passed=passed, detail=f"{a.key}={actual!r} contains={a.contains!r}")
    return AssertionResult(passed=actual is not None, detail=f"{a.key}={actual!r}")


def _eval_no_black_frames_at_start(path: Path, a: NoBlackFramesAtStartAssertion) -> AssertionResult:
    """Use ffmpeg's blackdetect filter on the first 2s — fail if any black detected."""
    result = subprocess.run(
        [
            "ffmpeg", "-v", "info", "-t", "2", "-i", str(path),
            "-vf", f"blackdetect=d=0.05:pic_th={1 - a.threshold}",
            "-f", "null", "-",
        ],
        capture_output=True, text=True, timeout=30,
    )
    has_black = "black_start" in result.stderr
    return AssertionResult(passed=not has_black, detail="no black detected" if not has_black else "black detected at start")


def evaluate_assertions(path: Path, assertions: list[Assertion]) -> list[AssertionResult]:
    out: list[AssertionResult] = []
    for a in assertions:
        if isinstance(a, FileExistsAssertion):
            out.append(_eval_file_exists(path))
        elif isinstance(a, DurationAssertion):
            out.append(_eval_duration(path, a))
        elif isinstance(a, FFprobeFieldAssertion):
            out.append(_eval_ffprobe_field(path, a))
        elif isinstance(a, NoBlackFramesAtStartAssertion):
            out.append(_eval_no_black_frames_at_start(path, a))
        else:
            raise TypeError(f"unhandled assertion type: {type(a).__name__}")
    return out


# ----------------------- CLI -----------------------

_FIXTURE_TOKEN = re.compile(r"\b(?:input\w*\.\w+|sample[\w-]*\.\w+)\b", re.IGNORECASE)


def _substitute_fixture(command: str, fixture_path: Path, output_path: Path) -> str:
    """Rewrite the command to point at our fixture for input and a tempfile for output.

    Heuristic: replace the FIRST input-looking filename with the fixture path, and the
    LAST filename token with the output path. Commands that fall outside this shape
    are flagged in spot_check.jsonl as `unrewritable=true` and skipped.
    """
    tokens = command.split()
    # Find the -i argument and replace what follows
    rewritten: list[str] = []
    i = 0
    found_i = False
    while i < len(tokens):
        tok = tokens[i]
        if tok == "-i" and i + 1 < len(tokens):
            rewritten.append(tok)
            rewritten.append(str(fixture_path))
            i += 2
            found_i = True
            continue
        rewritten.append(tok)
        i += 1
    if not found_i:
        raise ValueError("no -i found")
    # Replace last token (assumed output path) with our output_path
    if not rewritten[-1].startswith("-"):
        rewritten[-1] = str(output_path)
    else:
        rewritten.append(str(output_path))
    return " ".join(rewritten)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--prompts", required=True, type=Path)
    parser.add_argument("--fixtures", default=Path("fixtures"), type=Path)
    parser.add_argument("--fraction", type=float, default=0.15, help="fraction of spot_check-having prompts to execute")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("ERROR: ffmpeg/ffprobe not on PATH", file=sys.stderr)
        return 1

    prompts = {p.id: p for p in load_prompts(args.prompts)}
    raw_path = args.run_dir / "raw.jsonl"
    out_path = args.run_dir / "spot_check.jsonl"

    spot_eligible = [p for p in prompts.values() if p.spot_check is not None]
    rng = Random(args.seed)
    n = max(1, int(round(len(spot_eligible) * args.fraction)))
    sampled_ids = {p.id for p in rng.sample(spot_eligible, k=min(n, len(spot_eligible)))}
    print(f"Spot-checking {len(sampled_ids)} of {len(spot_eligible)} eligible prompts")

    with raw_path.open(encoding="utf-8") as f_in, out_path.open("w", encoding="utf-8") as f_out:
        for line in f_in:
            rec = json.loads(line)
            if rec["prompt_id"] not in sampled_ids:
                continue
            if rec["no_command"] or rec["command"] is None:
                continue
            prompt = prompts[rec["prompt_id"]]
            assert prompt.spot_check is not None
            fixture = args.fixtures / prompt.spot_check.fixture
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "out.mp4"
                try:
                    rewritten = _substitute_fixture(rec["command"], fixture, output)
                except ValueError as e:
                    f_out.write(json.dumps({**_meta(rec), "unrewritable": True, "error": str(e)}) + "\n")
                    continue
                exec_result = subprocess.run(
                    rewritten, shell=True, capture_output=True, text=True, timeout=120
                )
                if exec_result.returncode != 0:
                    f_out.write(
                        json.dumps(
                            {**_meta(rec), "ran": False, "stderr": exec_result.stderr[-2000:]}
                        )
                        + "\n"
                    )
                    continue
                results = evaluate_assertions(output, prompt.spot_check.assertions)
                f_out.write(
                    json.dumps(
                        {
                            **_meta(rec),
                            "ran": True,
                            "results": [asdict(r) for r in results],
                            "all_passed": all(r.passed for r in results),
                        }
                    )
                    + "\n"
                )

    print(f"Wrote {out_path}")
    return 0


def _meta(rec: dict) -> dict:
    return {"prompt_id": rec["prompt_id"], "config": rec["config"], "command": rec["command"]}


if __name__ == "__main__":
    raise SystemExit(main())
