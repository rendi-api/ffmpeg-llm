import json
from pathlib import Path

from runner.report import aggregate, format_report


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_aggregate_counts_verdicts(tmp_path: Path):
    judged = tmp_path / "judged.jsonl"
    _write_jsonl(judged, [
        {"prompt_id": "p1", "verdict_resolved": "with-plugin", "scores": {"verdict": "A"}, "blinding": {}},
        {"prompt_id": "p2", "verdict_resolved": "vanilla", "scores": {"verdict": "B"}, "blinding": {}},
        {"prompt_id": "p3", "verdict_resolved": "with-plugin", "scores": {"verdict": "A"}, "blinding": {}},
        {"prompt_id": "p4", "verdict_resolved": "tie", "scores": {"verdict": "tie"}, "blinding": {}},
    ])
    raw = tmp_path / "raw.jsonl"
    _write_jsonl(raw, [
        {"prompt_id": "p1", "config": "with-plugin", "no_command": False},
        {"prompt_id": "p1", "config": "vanilla", "no_command": False},
        {"prompt_id": "p2", "config": "with-plugin", "no_command": True},
        {"prompt_id": "p2", "config": "vanilla", "no_command": False},
    ])
    spot = tmp_path / "spot_check.jsonl"
    _write_jsonl(spot, [
        {"prompt_id": "p1", "config": "with-plugin", "ran": True, "all_passed": True},
        {"prompt_id": "p1", "config": "vanilla", "ran": True, "all_passed": False},
    ])

    agg = aggregate(judged_path=judged, raw_path=raw, spot_path=spot)

    assert agg.totals["with-plugin"] == 2
    assert agg.totals["vanilla"] == 1
    assert agg.totals["tie"] == 1
    assert agg.no_command_rate["with-plugin"] == 1
    assert agg.no_command_rate["vanilla"] == 0
    assert agg.spot_check_disagreement_count == 0  # judged plugin won, spot agrees


def test_format_report_smoke(tmp_path: Path):
    judged = tmp_path / "judged.jsonl"
    _write_jsonl(judged, [
        {"prompt_id": "p1", "verdict_resolved": "with-plugin", "scores": {"verdict": "A"}, "blinding": {}},
    ])
    raw = tmp_path / "raw.jsonl"
    _write_jsonl(raw, [
        {"prompt_id": "p1", "config": "with-plugin", "no_command": False},
        {"prompt_id": "p1", "config": "vanilla", "no_command": False},
    ])
    spot = tmp_path / "spot_check.jsonl"
    _write_jsonl(spot, [])

    agg = aggregate(judged_path=judged, raw_path=raw, spot_path=spot)
    md = format_report(agg)
    assert "# claude-ffmpeg evaluation" in md
    assert "with-plugin" in md
