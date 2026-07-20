"""Unit tests for the transcription pipeline's file handling and output formats.

These run without the whisper model. The full end-to-end check (real ≥10-minute
interview, timestamp accuracy ±1s) is a manual step documented at the bottom.

Run from the transcribe/ folder:  python -m pytest tests/ -v
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from transcribe import (  # noqa: E402
    Segment,
    build_combined_transcript,
    find_media_files,
    format_srt_timestamp,
    format_timestamp,
    segments_to_json,
    segments_to_srt,
    segments_to_txt,
    speaker_label_from_filename,
    write_outputs,
)

SEGMENTS = [
    Segment(0.0, 4.2, "My name is Sarah and I run the Henderson account."),
    Segment(5.1, 9.87, "The biggest change this year was the new platform."),
    Segment(65.5, 71.0, "Honestly, the team pulled it off."),
]


def test_timestamp_formats():
    assert format_timestamp(0) == "00:00:00"
    assert format_timestamp(65.5) == "00:01:05"
    assert format_timestamp(3661.9) == "01:01:01"
    assert format_srt_timestamp(0) == "00:00:00,000"
    assert format_srt_timestamp(65.5) == "00:01:05,500"
    assert format_srt_timestamp(3661.987) == "01:01:01,987"


def test_txt_output_has_timestamp_per_segment():
    txt = segments_to_txt(SEGMENTS)
    lines = txt.strip().splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("[00:00:00] ")
    assert lines[2].startswith("[00:01:05] ")


def test_srt_round_trips_through_pysrt():
    pysrt = pytest.importorskip("pysrt")
    srt_text = segments_to_srt(SEGMENTS)
    subs = pysrt.from_string(srt_text)
    assert len(subs) == 3
    assert subs[0].text == SEGMENTS[0].text
    # pysrt times are (h, m, s, ms); verify the third cue starts at 00:01:05,500
    assert subs[2].start.minutes == 1
    assert subs[2].start.seconds == 5
    assert subs[2].start.milliseconds == 500


def test_json_schema_is_stable():
    data = json.loads(segments_to_json("clip01", 71.0, SEGMENTS))
    assert data["schema_version"] == 1
    assert data["clip"] == "clip01"
    assert data["duration_seconds"] == 71.0
    assert data["segments"][0] == {
        "start": 0.0,
        "end": 4.2,
        "text": "My name is Sarah and I run the Henderson account.",
    }


def test_find_media_files_skips_non_media(tmp_path):
    (tmp_path / "interview.mp4").touch()
    (tmp_path / "b-roll.MOV").touch()
    (tmp_path / "notes.docx").touch()
    (tmp_path / "project.prproj").touch()
    (tmp_path / ".DS_Store").touch()
    (tmp_path / "subfolder").mkdir()
    media, skipped = find_media_files(tmp_path)
    assert [p.name for p in media] == ["b-roll.MOV", "interview.mp4"]
    assert [p.name for p in skipped] == ["notes.docx", "project.prproj"]


def test_filenames_with_spaces_and_special_characters(tmp_path):
    tricky = "Sarah O'Brien - Take #2 (final).mp4"
    (tmp_path / tricky).touch()
    media, _ = find_media_files(tmp_path)
    assert media[0].name == tricky
    assert speaker_label_from_filename(media[0]) == "Sarah O'Brien - Take #2 (final)"

    out_dir = tmp_path / "transcripts"
    out_dir.mkdir()
    write_outputs(out_dir, media[0], SEGMENTS, 71.0)
    build_combined_transcript(out_dir, media)
    combined = (out_dir / "_ALL_TRANSCRIPTS.txt").read_text(encoding="utf-8")
    assert f"CLIP: {tricky}" in combined
    assert "SPEAKER: Sarah O'Brien - Take #2 (final)" in combined
    assert "Henderson account" in combined


def test_empty_segments_produce_valid_files(tmp_path):
    clip = tmp_path / "silence.mp4"
    clip.touch()
    out_dir = tmp_path / "transcripts"
    out_dir.mkdir()
    write_outputs(out_dir, clip, [], 10.0)
    assert (out_dir / "silence.txt").read_text(encoding="utf-8") == "\n"
    assert json.loads((out_dir / "silence.json").read_text(encoding="utf-8"))["segments"] == []


# ---------------------------------------------------------------------------
# Manual end-to-end validation (needs a real interview file, run on your machine):
#   python transcribe.py /path/to/folder-with-10min-interview
# Check: timestamps in the .txt within ±1s of the actual video; .srt imports
# into Premiere (File > Import); .json opens and looks like the schema above.
# ---------------------------------------------------------------------------
