"""Drive `claude -p` for every prompt × config and capture raw.jsonl.

Usage:
    python -m runner.run --prompts prompts/smoke.yaml \
                         --model claude-sonnet-4-6 \
                         --out results/2026-05-08-sonnet46-smoke
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from runner.claude_invoke import invoke
from runner.extract import extract_command
from runner.prompts import Prompt, load_prompts


def _record(prompt: Prompt, config: str, model: str, plugin_dir: Path | None) -> dict:
    result = invoke(model=model, plugin_dir=plugin_dir, prompt=prompt.prompt)
    extracted = extract_command(result.stdout)
    return {
        "prompt_id": prompt.id,
        "config": config,
        "model": model,
        "command": extracted.command,
        "no_command": extracted.no_command,
        "all_blocks": extracted.all_blocks,
        "raw_response": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set (check evals/.env)", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Path passed to claude --plugin-dir for the with-plugin config.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N prompts (smoke debugging).",
    )
    args = parser.parse_args(argv)

    prompts = load_prompts(args.prompts)
    if args.limit is not None:
        prompts = prompts[: args.limit]

    args.out.mkdir(parents=True, exist_ok=True)
    raw_path = args.out / "raw.jsonl"

    with raw_path.open("w", encoding="utf-8") as f:
        for i, prompt in enumerate(prompts, start=1):
            print(f"[{i}/{len(prompts)}] {prompt.id} ...", flush=True)
            for config, plugin_dir in (
                ("vanilla", None),
                ("with-plugin", args.repo_root),
            ):
                rec = _record(prompt, config, args.model, plugin_dir)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                status = "no-cmd" if rec["no_command"] else "ok"
                print(f"   {config}: {status}")

    print(f"\nWrote {raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
