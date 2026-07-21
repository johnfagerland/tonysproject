#!/usr/bin/env python3
"""Verify that selects (quotes + timecodes) actually exist in the source transcripts.

Hallucinated timecodes are the failure mode that destroys trust in the whole
workflow, so every scripted run is checked automatically. Can also be run by
hand against a CSV:

    python check_timecodes.py transcripts/ selects.csv
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

# A select's In point may sit a few seconds off the segment boundary (quotes can
# start mid-segment); allow that much slack when matching.
TIME_TOLERANCE_SECONDS = 5.0


def normalize(text: str) -> str:
    """Lowercase, strip punctuation and collapse whitespace for fuzzy matching."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_timecode(tc: str | float | int) -> float:
    """Accept seconds (numeric) or 'HH:MM:SS' / 'MM:SS' strings."""
    if isinstance(tc, (int, float)):
        return float(tc)
    parts = [p for p in str(tc).strip().split(":") if p != ""]
    if not parts or not all(re.fullmatch(r"\d+(\.\d+)?", p) for p in parts):
        raise ValueError(f"unreadable timecode: {tc!r}")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def load_transcripts(transcripts_dir: Path) -> dict[str, dict]:
    """Load every per-clip .json written by the transcribe tool, keyed by clip stem."""
    clips = {}
    for path in sorted(transcripts_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "segments" in data:
            clips[path.stem] = data
    return clips


def verify_select(clips: dict[str, dict], clip: str, start: float, quote: str) -> str | None:
    """Return None if the select checks out, else a human-readable problem."""
    clip_key = Path(clip).stem  # tolerate 'clip.mp4' vs 'clip'
    data = clips.get(clip_key)
    if data is None:
        return f"clip '{clip}' not found among the transcripts"

    segments = data["segments"]
    if not segments:
        return f"clip '{clip}' has an empty transcript"

    # 1. The quote must actually appear in the clip's transcript text.
    full_text = normalize(" ".join(seg["text"] for seg in segments))
    probe = normalize(quote)
    # Long quotes may span segment boundaries with tiny transcription drift;
    # require the first ~12 words to match verbatim.
    probe_head = " ".join(probe.split()[:12])
    if not probe_head or probe_head not in full_text:
        return f"quote not found in '{clip}': \"{quote[:60]}...\""

    # 2. The In timecode must land on/near a segment that contains the quote head.
    for seg in segments:
        seg_window = normalize(" ".join(
            s["text"] for s in segments
            if seg["start"] - 1 <= s["start"] <= seg["end"] + 30
        ))
        if probe_head in seg_window and abs(seg["start"] - start) <= TIME_TOLERANCE_SECONDS:
            return None
    return (
        f"timecode {start:.0f}s doesn't match where the quote appears in '{clip}'"
    )


def check_selects(transcripts_dir: Path, selects: list[dict]) -> list[str]:
    """Check a list of {clip, start, quote} dicts. Returns a list of problems."""
    clips = load_transcripts(transcripts_dir)
    if not clips:
        return [f"no transcript .json files found in {transcripts_dir}"]
    problems = []
    for i, sel in enumerate(selects, start=1):
        try:
            start = parse_timecode(sel["start"])
        except (ValueError, KeyError) as exc:
            problems.append(f"select #{i}: {exc}")
            continue
        issue = verify_select(clips, str(sel.get("clip", "")), start, str(sel.get("quote", "")))
        if issue:
            problems.append(f"select #{i}: {issue}")
    return problems


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python check_timecodes.py <transcripts_folder> <selects.csv>")
        return 2
    transcripts_dir = Path(sys.argv[1])
    csv_path = Path(sys.argv[2])
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    selects = [{"clip": r["clip"], "start": r["in"], "quote": r["quote"]} for r in rows]
    problems = check_selects(transcripts_dir, selects)
    if problems:
        print(f"{len(problems)} problem(s) found:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"All {len(selects)} selects verified against the transcripts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
