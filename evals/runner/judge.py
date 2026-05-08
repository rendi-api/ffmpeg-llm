"""Blinded LLM-as-judge over raw.jsonl. Writes judged.jsonl.

Per row: shuffles A/B labels (per-row blinding), sends both responses to a fresh
Claude Opus session with the rubric, parses scores + verdict + reasoning.

Uses prompt caching on the system prompt (rubric) — same rubric for every call.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from runner.budget import PRICING, Budget, BudgetExceeded

JUDGE_MODEL = "claude-opus-4-7"

RUBRIC_SYSTEM = """You are a senior FFmpeg expert grading two AI-generated responses to the same user request.

You will be shown:
- The user's request.
- Response A and Response B (one is from a baseline, one is from a tool under test — but you do NOT know which).

For each response, score on these axes. If the response contains a command, use these axes:

- correctness (0-3): would this command run without error and produce the requested output? 0 = wrong/broken; 1 = runs but mostly misses the goal; 2 = runs and mostly correct with minor issues; 3 = correct and complete.
- pitfall_coverage (0-3): does it apply the relevant playback-compat / faststart / yuv420p / setsar=1:1 / setpts-after-trim / hvc1 / similar defaults the situation calls for? 0 = ignores all relevant ones; 3 = nails them.
- efficiency_idiom (0-2): is it doing the work the cheap, standard way (e.g. -c copy when remuxing, single filter graph instead of multiple passes)? 0 = clearly wasteful or non-idiomatic; 2 = clean and idiomatic.

If the response contains NO command and is just clarifying questions, use this axis instead:

- clarification_quality (0-3): did it identify the RIGHT ambiguities (codec, target device, container, bitrate)? 0 = generic hedging or wrong questions; 3 = exactly what an expert would ask.

Then a verdict: which response is better? "A", "B", or "tie".

Penalize unsafe guesses (e.g., assuming H264 when the user said "make it work everywhere") more than neutral guesses (defaulting to MP4 container when unspecified).

Output STRICT JSON only, no prose, matching this schema:

{
  "a": {"correctness": int|null, "pitfall_coverage": int|null, "efficiency_idiom": int|null, "clarification_quality": int|null},
  "b": {"correctness": int|null, "pitfall_coverage": int|null, "efficiency_idiom": int|null, "clarification_quality": int|null},
  "verdict": "A" | "B" | "tie",
  "reasoning": "1-3 sentences explaining the verdict, naming specific flags or pitfalls."
}

Use null for axes that don't apply (e.g. `clarification_quality` is null when a command was given).
"""


def _build_user_message(prompt_text: str, response_a: str, response_b: str) -> str:
    return f"""User request:
---
{prompt_text}
---

Response A:
---
{response_a}
---

Response B:
---
{response_b}
---

Output the JSON now."""


def _extract_json(text: str) -> dict:
    """Tolerant JSON extractor — handles models wrapping JSON in ```json ... ```."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    if obj_match:
        return json.loads(obj_match.group(0))
    raise ValueError(f"no JSON found in: {text!r}")


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--prompts", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--budget-usd", type=float, default=float(os.environ.get("EVAL_BUDGET_USD", 30.0)))
    args = parser.parse_args(argv)

    raw_path = args.run_dir / "raw.jsonl"
    judged_path = args.run_dir / "judged.jsonl"

    # Group raw rows by prompt_id
    by_prompt: dict[str, dict[str, dict]] = defaultdict(dict)
    with raw_path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            by_prompt[r["prompt_id"]][r["config"]] = r

    # Need prompt text — load it
    from runner.prompts import load_prompts
    prompts_by_id = {p.id: p for p in load_prompts(args.prompts)}

    rng = random.Random(args.seed)
    client = Anthropic()
    budget = Budget(cap_usd=args.budget_usd)
    pricing = PRICING[JUDGE_MODEL]

    with judged_path.open("w", encoding="utf-8") as out:
        for prompt_id, configs in by_prompt.items():
            if "vanilla" not in configs or "with-plugin" not in configs:
                print(f"   {prompt_id}: missing config; skipping", flush=True)
                continue
            # Per-row blinding
            swap = rng.random() < 0.5
            response_a_config = "with-plugin" if not swap else "vanilla"
            response_b_config = "vanilla" if not swap else "with-plugin"
            response_a = configs[response_a_config]["raw_response"]
            response_b = configs[response_b_config]["raw_response"]
            prompt_text = prompts_by_id[prompt_id].prompt

            # Pre-flight budget check (~2k input + 300 output as conservative estimate)
            if budget.would_exceed(input_tokens=2000, output_tokens=300, pricing=pricing):
                print(f"BUDGET CAP REACHED at prompt {prompt_id}; stopping.", file=sys.stderr)
                break

            try:
                msg = client.messages.create(
                    model=JUDGE_MODEL,
                    max_tokens=600,
                    system=[
                        {
                            "type": "text",
                            "text": RUBRIC_SYSTEM,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[
                        {
                            "role": "user",
                            "content": _build_user_message(prompt_text, response_a, response_b),
                        }
                    ],
                )
            except Exception as e:
                out.write(json.dumps({"prompt_id": prompt_id, "error": str(e)}) + "\n")
                continue

            try:
                budget.charge(
                    f"judge:{prompt_id}",
                    input_tokens=msg.usage.input_tokens,
                    output_tokens=msg.usage.output_tokens,
                    pricing=pricing,
                )
            except BudgetExceeded as e:
                print(str(e), file=sys.stderr)
                break

            text = msg.content[0].text  # type: ignore[union-attr]
            try:
                parsed = _extract_json(text)
            except Exception as e:
                out.write(
                    json.dumps(
                        {"prompt_id": prompt_id, "error": f"unparseable: {e}", "raw": text}
                    )
                    + "\n"
                )
                continue

            # Translate verdict from A/B back to with-plugin/vanilla
            verdict_label_map = {"A": response_a_config, "B": response_b_config, "tie": "tie"}
            row = {
                "prompt_id": prompt_id,
                "blinding": {"A": response_a_config, "B": response_b_config},
                "scores": parsed,
                "verdict_resolved": verdict_label_map.get(parsed.get("verdict"), "tie"),
                "spent_usd": round(budget.spent_usd, 6),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            print(f"   {prompt_id}: {row['verdict_resolved']} (${budget.spent_usd:.4f})", flush=True)

    print(f"\nJudged. Total spent: ${budget.spent_usd:.4f}. Wrote {judged_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
