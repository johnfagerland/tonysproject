#!/usr/bin/env python3
"""Story assembly assistant — transcripts + brief in, selects report out.

Reads the per-clip .json transcripts produced by the transcribe tool plus a
short text file with the client's narrative goal, asks Claude for selects and
a story order, verifies every returned timecode against the source transcripts,
and writes:

    selects_report.md  the full report (selects, story order, alternates, gaps)
    selects.csv        clip, in, out, quote, note — opens in Excel

Only transcript TEXT is sent to the API. Never media files.

Usage:
    python story_assist.py <transcripts_folder> <brief.txt> [--out <folder>]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from check_timecodes import check_selects, load_transcripts

# Pricing for the cost estimate printed after each run (USD per 1M tokens).
MODEL = os.environ.get("STORY_ASSIST_MODEL", "claude-opus-4-8")
PRICE_PER_MTOK = {"input": 5.00, "output": 25.00}  # claude-opus-4-8

# A full interview day can exceed what fits comfortably in one request, so the
# script works map-reduce style: one "find candidate selects" pass per clip
# (chunked if a clip is very long), then one combining pass that builds the
# narrative from the candidates only.
MAX_CHARS_PER_CHUNK = 60_000

SELECTS_SCHEMA = {
    "type": "object",
    "properties": {
        "selects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number", "description": "Start time in seconds, copied from a segment 'start' in the transcript"},
                    "end": {"type": "number", "description": "End time in seconds"},
                    "quote": {"type": "string", "description": "The statement, verbatim from the transcript"},
                    "reason": {"type": "string", "description": "Why this serves the narrative goal"},
                    "delivery": {"type": "integer", "description": "Delivery quality 1-5: complete sentence, no false starts, energy"},
                    "topic": {"type": "string", "description": "Short topic tag, e.g. 'dallas facility'"},
                },
                "required": ["start", "end", "quote", "reason", "delivery", "topic"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["selects"],
    "additionalProperties": False,
}


def get_client():
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent / ".env")
    except ImportError:
        pass
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(
            "ERROR: No API key found.\n"
            "Fix: copy '.env.example' to '.env' in the story-assist folder and put the\n"
            "key John gave you on the ANTHROPIC_API_KEY line. (Ask John if you lost it.)"
        )
    try:
        import anthropic
    except ImportError:
        sys.exit(
            "ERROR: The 'anthropic' package is not installed.\n"
            "Fix: open a terminal in this folder and run: pip install -r requirements.txt"
        )
    return anthropic.Anthropic()


class Usage:
    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0

    def add(self, usage) -> None:
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens

    @property
    def cost(self) -> float:
        return (
            self.input_tokens / 1e6 * PRICE_PER_MTOK["input"]
            + self.output_tokens / 1e6 * PRICE_PER_MTOK["output"]
        )


def chunk_segments(segments: list[dict]) -> list[list[dict]]:
    chunks, current, size = [], [], 0
    for seg in segments:
        line_len = len(seg["text"]) + 20
        if current and size + line_len > MAX_CHARS_PER_CHUNK:
            chunks.append(current)
            current, size = [], 0
        current.append(seg)
        size += line_len
    if current:
        chunks.append(current)
    return chunks


def render_transcript(segments: list[dict]) -> str:
    return "\n".join(f"[{seg['start']:.1f}s] {seg['text']}" for seg in segments)


def map_pass_clip(client, usage: Usage, clip: str, segments: list[dict], brief: str) -> list[dict]:
    """Find candidate selects in one clip (possibly in chunks)."""
    all_selects: list[dict] = []
    for chunk in chunk_segments(segments):
        prompt = (
            "You are helping a corporate video editor pull selects for a 2:30-4:00 piece.\n\n"
            f"CLIENT NARRATIVE GOAL:\n{brief}\n\n"
            f"Below is the transcript of one interview clip. The speaker is '{clip}' "
            "(clips are named after the interviewee).\n"
            "Find every statement that could serve the narrative goal.\n\n"
            "STRICT RULES:\n"
            "- 'quote' must be VERBATIM text from the transcript. Never paraphrase.\n"
            "- 'start' and 'end' must be copied from the [Ns] markers around the quote.\n"
            "- Prefer complete sentences with clean delivery (no false starts). Score "
            "delivery 1-5 accordingly.\n"
            "- If nothing in this clip serves the goal, return an empty list.\n\n"
            f"TRANSCRIPT OF '{clip}':\n{render_transcript(chunk)}"
        )
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            output_config={"format": {"type": "json_schema", "schema": SELECTS_SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
        )
        usage.add(response.usage)
        text = next(b.text for b in response.content if b.type == "text")
        for sel in json.loads(text)["selects"]:
            sel["clip"] = clip
            all_selects.append(sel)
    return all_selects


def reduce_pass(client, usage: Usage, brief: str, candidates: list[dict]) -> str:
    """Combine per-clip candidates into the narrative report (markdown)."""
    prompt = (
        "You are helping a corporate video editor assemble a 2:30-4:00 piece.\n\n"
        f"CLIENT NARRATIVE GOAL:\n{brief}\n\n"
        "Below are candidate selects already pulled from the interview transcripts "
        "(quote, clip, start/end in seconds, delivery score 1-5, topic).\n\n"
        "Write a markdown report with exactly these four sections:\n\n"
        "## 1. Selected statements\n"
        "A table: | # | Speaker/Clip | In | Out | Quote | Why |\n"
        "Choose the 10-20 best candidates. Format In/Out as HH:MM:SS. COPY quotes and "
        "times exactly from the candidates - never alter or invent them.\n\n"
        "## 2. Suggested story order\n"
        "Hook (0:00-0:20) / Context (0:20-0:50) / Substance (0:50-2:45, 2-3 mini-topics, "
        "mix speakers where possible) / Close. One-line rationale per act, and an "
        "estimated total running time vs the 2:30-4:00 target.\n\n"
        "## 3. Alternate takes\n"
        "Where the same idea appears more than once, rank the alternatives by the "
        "delivery score and say which to try first.\n\n"
        "## 4. Gaps\n"
        "What the narrative goal needs that is NOT in the candidates - suggest B-roll+VO, "
        "graphics, or pickup questions.\n\n"
        f"CANDIDATE SELECTS (JSON):\n{json.dumps(candidates, ensure_ascii=False)}"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    usage.add(response.usage)
    return next(b.text for b in response.content if b.type == "text")


def seconds_to_tc(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def write_csv(path: Path, selects: list[dict]) -> None:
    # utf-8-sig so Excel opens it with correct characters, no import wizard.
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["clip", "in", "out", "quote", "note"])
        for sel in selects:
            writer.writerow([
                sel["clip"],
                seconds_to_tc(sel["start"]),
                seconds_to_tc(sel["end"]),
                sel["quote"],
                f"delivery {sel['delivery']}/5 - {sel['reason']}",
            ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transcripts + brief -> selects report.")
    parser.add_argument("transcripts", help="The 'transcripts' folder created by the transcribe tool")
    parser.add_argument("brief", help="A .txt file with the client's narrative goal")
    parser.add_argument("--out", default=None, help="Output folder (default: next to the brief)")
    args = parser.parse_args(argv)

    transcripts_dir = Path(args.transcripts).expanduser()
    brief_path = Path(args.brief).expanduser()
    if not brief_path.is_file():
        sys.exit(f"ERROR: brief file not found: {brief_path}")
    brief = brief_path.read_text(encoding="utf-8").strip()
    if not brief:
        sys.exit(f"ERROR: the brief file is empty: {brief_path}")

    clips = load_transcripts(transcripts_dir)
    if not clips:
        sys.exit(
            f"ERROR: no transcript .json files found in '{transcripts_dir}'.\n"
            "Run the transcribe tool first - it creates them."
        )

    out_dir = Path(args.out) if args.out else brief_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    client = get_client()
    usage = Usage()

    print(f"Found {len(clips)} transcript(s). Finding candidate selects per clip...")
    candidates: list[dict] = []
    for clip, data in clips.items():
        found = map_pass_clip(client, usage, clip, data["segments"], brief)
        print(f"  {clip}: {len(found)} candidate(s)")
        candidates.extend(found)

    if not candidates:
        sys.exit(
            "No usable statements were found for this brief. Double-check that the "
            "brief describes what the video is about, or loosen it."
        )

    # Verify BEFORE building the report so hallucinated quotes never reach it.
    problems = check_selects(transcripts_dir, candidates)
    if problems:
        print(f"\nDropped {len(problems)} candidate(s) that failed verification:")
        for p in problems:
            print(f"  - {p}")
        bad_indexes = {int(p.split("#")[1].split(":")[0]) - 1 for p in problems if "#" in p}
        candidates = [c for i, c in enumerate(candidates) if i not in bad_indexes]
    if not candidates:
        sys.exit("ERROR: every candidate failed verification. Nothing trustworthy to report.")

    print("\nBuilding the narrative report...")
    report = reduce_pass(client, usage, brief, candidates)

    report_path = out_dir / "selects_report.md"
    csv_path = out_dir / "selects.csv"
    report_path.write_text(report, encoding="utf-8")
    write_csv(csv_path, sorted(candidates, key=lambda c: (-c["delivery"], c["clip"], c["start"])))

    print("\n" + "=" * 50)
    print(f"Report:   {report_path}")
    print(f"CSV:      {csv_path}  (all {len(candidates)} verified candidates)")
    print(f"API cost: ~${usage.cost:.2f} "
          f"({usage.input_tokens:,} in / {usage.output_tokens:,} out tokens on {MODEL})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
