"""Aggregate raw.jsonl + judged.jsonl + spot_check.jsonl → report.md."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from runner.prompts import load_prompts


@dataclass
class Aggregate:
    totals: Counter = field(default_factory=Counter)              # with-plugin / vanilla / tie counts
    by_category: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    by_difficulty: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    no_command_rate: Counter = field(default_factory=Counter)     # config -> count of no_command
    top_plugin_losses: list[dict] = field(default_factory=list)
    spot_check_disagreement_count: int = 0
    spot_check_total: int = 0
    judged_count: int = 0


def aggregate(*, judged_path: Path, raw_path: Path, spot_path: Path, prompts_path: Path | None = None) -> Aggregate:
    agg = Aggregate()

    judged: list[dict] = []
    with judged_path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if "verdict_resolved" not in r:
                continue
            judged.append(r)
            agg.totals[r["verdict_resolved"]] += 1
    agg.judged_count = len(judged)

    # no_command per config
    with raw_path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("no_command"):
                agg.no_command_rate[r["config"]] += 1

    # category / difficulty slicing requires prompts file
    if prompts_path is not None and prompts_path.exists():
        prompts_by_id = {p.id: p for p in load_prompts(prompts_path)}
        for r in judged:
            p = prompts_by_id.get(r["prompt_id"])
            if p is None:
                continue
            for cat in p.category:
                agg.by_category[cat][r["verdict_resolved"]] += 1
            agg.by_difficulty[p.difficulty][r["verdict_resolved"]] += 1

    # plugin losses (sorted by score gap if present, else just by appearance)
    losses = [r for r in judged if r["verdict_resolved"] == "vanilla"]
    agg.top_plugin_losses = losses[:10]

    # spot-check vs judge agreement
    if spot_path.exists():
        # Build a map (prompt_id, config) -> all_passed
        spot_results: dict[tuple[str, str], bool] = {}
        with spot_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("ran") and "all_passed" in r:
                    spot_results[(r["prompt_id"], r["config"])] = r["all_passed"]

        for j in judged:
            plugin_pass = spot_results.get((j["prompt_id"], "with-plugin"))
            vanilla_pass = spot_results.get((j["prompt_id"], "vanilla"))
            if plugin_pass is None and vanilla_pass is None:
                continue
            agg.spot_check_total += 1
            verdict = j["verdict_resolved"]
            # Disagreement: judge said plugin won but its command actually failed.
            if verdict == "with-plugin" and plugin_pass is False:
                agg.spot_check_disagreement_count += 1
            if verdict == "vanilla" and vanilla_pass is False:
                agg.spot_check_disagreement_count += 1

    return agg


def _winrate(c: Counter) -> str:
    total = sum(c.values())
    if total == 0:
        return "(no data)"
    plugin = c.get("with-plugin", 0)
    vanilla = c.get("vanilla", 0)
    tie = c.get("tie", 0)
    return f"plugin {plugin}/{total} ({plugin / total:.0%}) | vanilla {vanilla}/{total} ({vanilla / total:.0%}) | tie {tie}/{total}"


def format_report(agg: Aggregate) -> str:
    lines = ["# claude-ffmpeg evaluation", ""]
    lines.append(f"Judged prompts: **{agg.judged_count}**")
    lines.append("")
    lines.append("## Headline win rate")
    lines.append("")
    lines.append(_winrate(agg.totals))
    lines.append("")

    if agg.by_category:
        lines.append("## Win rate by category")
        lines.append("")
        lines.append("| Category | Result |")
        lines.append("|---|---|")
        for cat, counter in sorted(agg.by_category.items()):
            lines.append(f"| {cat} | {_winrate(counter)} |")
        lines.append("")

    if agg.by_difficulty:
        lines.append("## Win rate by difficulty")
        lines.append("")
        lines.append("| Difficulty | Result |")
        lines.append("|---|---|")
        for diff in ("easy", "medium", "hard"):
            if diff in agg.by_difficulty:
                lines.append(f"| {diff} | {_winrate(agg.by_difficulty[diff])} |")
        lines.append("")

    lines.append("## `no_command` rate per config")
    lines.append("")
    lines.append(f"- with-plugin: **{agg.no_command_rate.get('with-plugin', 0)}**")
    lines.append(f"- vanilla:     **{agg.no_command_rate.get('vanilla', 0)}**")
    lines.append("")
    lines.append("> Asking too many clarifying questions when the user wants a quick command is itself a UX failure.")
    lines.append("")

    lines.append("## Spot-check vs judge agreement")
    lines.append("")
    if agg.spot_check_total == 0:
        lines.append("(no spot-check data)")
    else:
        rate = agg.spot_check_disagreement_count / agg.spot_check_total
        lines.append(f"Disagreement: **{agg.spot_check_disagreement_count} / {agg.spot_check_total} ({rate:.0%})**")
        if rate > 0.15:
            lines.append("")
            lines.append("> **WARNING:** disagreement >15%. Judge calls may not be reliable. Expand spot-check coverage.")
    lines.append("")

    lines.append("## Top plugin losses (most actionable section)")
    lines.append("")
    if not agg.top_plugin_losses:
        lines.append("(no losses recorded)")
    else:
        for loss in agg.top_plugin_losses:
            reasoning = loss.get("scores", {}).get("reasoning", "(no reasoning)")
            lines.append(f"- **{loss['prompt_id']}** — {reasoning}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--prompts", required=True, type=Path)
    args = parser.parse_args(argv)

    agg = aggregate(
        judged_path=args.run_dir / "judged.jsonl",
        raw_path=args.run_dir / "raw.jsonl",
        spot_path=args.run_dir / "spot_check.jsonl",
        prompts_path=args.prompts,
    )
    md = format_report(agg)
    out = args.run_dir / "report.md"
    out.write_text(md, encoding="utf-8")
    print(f"Wrote {out}")
    print()
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
