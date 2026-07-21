"""Tests for the story-assist script — chunking, CSV output, and the timecode
verifier that guards against hallucinated quotes/timecodes.

Run from the story-assist/ folder:  python -m pytest tests/ -v
(No API key needed; nothing here calls the network.)
"""

import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_timecodes import check_selects, load_transcripts, parse_timecode  # noqa: E402
from story_assist import chunk_segments, seconds_to_tc, write_csv  # noqa: E402

random.seed(42)

WORDS = ("platform team growth Dallas facility launch quarter customers proud "
         "results change leadership process production support systems future").split()


def make_transcript(path: Path, clip: str, n_segments: int, planted: dict[int, str] | None = None):
    """Write a synthetic transcript json; optionally plant known sentences at
    given segment indexes."""
    segments = []
    t = 0.0
    for i in range(n_segments):
        text = " ".join(random.choices(WORDS, k=14)) + "."
        if planted and i in planted:
            text = planted[i]
        dur = 4.0 + random.random() * 3
        segments.append({"start": round(t, 3), "end": round(t + dur, 3), "text": text})
        t += dur + 0.5
    path.write_text(json.dumps({
        "schema_version": 1, "clip": clip,
        "duration_seconds": round(t, 3), "segments": segments,
    }), encoding="utf-8")
    return segments


def build_corpus(tmp_path: Path):
    """3 transcripts totaling well over 30k words, with known planted quotes."""
    tdir = tmp_path / "transcripts"
    tdir.mkdir()
    planted_quote = "The biggest change this year was the new Dallas facility opening ahead of schedule."
    segs_a = make_transcript(tdir / "Sarah_Henderson.json", "Sarah_Henderson", 900,
                             planted={450: planted_quote})
    make_transcript(tdir / "Mike_Ops.json", "Mike_Ops", 800)
    make_transcript(tdir / "Priya_CEO.json", "Priya_CEO", 700)
    return tdir, planted_quote, segs_a[450]


def test_corpus_is_over_30k_words(tmp_path):
    tdir, _, _ = build_corpus(tmp_path)
    total = sum(
        len(seg["text"].split())
        for clip in load_transcripts(tdir).values()
        for seg in clip["segments"]
    )
    assert total > 30_000


def test_valid_select_passes(tmp_path):
    tdir, quote, seg = build_corpus(tmp_path)
    ok = check_selects(tdir, [{"clip": "Sarah_Henderson", "start": seg["start"], "quote": quote}])
    assert ok == []


def test_hallucinated_quote_is_caught(tmp_path):
    tdir, _, seg = build_corpus(tmp_path)
    problems = check_selects(tdir, [{
        "clip": "Sarah_Henderson", "start": seg["start"],
        "quote": "We tripled revenue thanks to our incredible synergy initiatives.",
    }])
    assert len(problems) == 1
    assert "quote not found" in problems[0]


def test_hallucinated_timecode_is_caught(tmp_path):
    tdir, quote, seg = build_corpus(tmp_path)
    problems = check_selects(tdir, [{
        "clip": "Sarah_Henderson",
        "start": seg["start"] + 600,  # way off
        "quote": quote,
    }])
    assert len(problems) == 1
    assert "timecode" in problems[0]


def test_unknown_clip_is_caught(tmp_path):
    tdir, quote, seg = build_corpus(tmp_path)
    problems = check_selects(tdir, [{"clip": "NoSuchPerson", "start": seg["start"], "quote": quote}])
    assert "not found among the transcripts" in problems[0]


def test_parse_timecode_formats():
    assert parse_timecode(75) == 75.0
    assert parse_timecode("01:15") == 75.0
    assert parse_timecode("00:01:15") == 75.0
    assert parse_timecode("1:01:15") == 3675.0


def test_chunking_splits_long_clips_and_keeps_order():
    segments = [{"start": float(i), "end": float(i) + 4, "text": "word " * 400} for i in range(60)]
    chunks = chunk_segments(segments)
    assert len(chunks) > 1
    flat = [seg for chunk in chunks for seg in chunk]
    assert flat == segments  # nothing lost, order preserved


def test_csv_opens_cleanly_for_excel(tmp_path):
    selects = [{
        "clip": "Sarah_Henderson", "start": 65.2, "end": 71.9,
        "quote": 'She said "it\'s huge", with commas, too',
        "reason": "hook candidate", "delivery": 5,
    }]
    out = tmp_path / "selects.csv"
    write_csv(out, selects)
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM so Excel auto-detects encoding
    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["clip"] == "Sarah_Henderson"
    assert rows[0]["in"] == "00:01:05"
    assert rows[0]["out"] == "00:01:12"
    assert rows[0]["quote"] == 'She said "it\'s huge", with commas, too'
    assert seconds_to_tc(3661) == "01:01:01"
