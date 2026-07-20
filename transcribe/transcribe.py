#!/usr/bin/env python3
"""Local transcription pipeline for interview footage.

Point it at a folder of video files and it writes, next to a `transcripts/`
subfolder:

    transcripts/{clipname}.txt   readable transcript, [HH:MM:SS] per segment
    transcripts/{clipname}.srt   subtitle file (imports into Premiere Pro)
    transcripts/{clipname}.json  segments with start/end times (for story-assist)
    transcripts/_ALL_TRANSCRIPTS.txt  everything combined, ready to paste into Claude

Everything runs on this machine. No audio or video ever leaves it.

Usage:
    python transcribe.py <folder> [--model small|medium|large-v3] [--device auto|cpu|cuda]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import subprocess
from dataclasses import dataclass
from pathlib import Path

MEDIA_EXTENSIONS = {".mp4", ".mov", ".mxf", ".m4v", ".avi", ".mts", ".wav", ".mp3", ".m4a", ".aif", ".aiff"}

# Segments come from faster-whisper as (start_seconds, end_seconds, text).


@dataclass
class Segment:
    start: float
    end: float
    text: str


def find_media_files(folder: Path) -> tuple[list[Path], list[Path]]:
    """Return (media_files, skipped_files) for the top level of *folder*."""
    media, skipped = [], []
    for path in sorted(folder.iterdir()):
        if path.is_dir() or path.name.startswith("."):
            continue
        if path.suffix.lower() in MEDIA_EXTENSIONS:
            media.append(path)
        else:
            skipped.append(path)
    return media, skipped


def format_timestamp(seconds: float) -> str:
    """1234.5 -> '00:20:34' (for the readable .txt transcript)."""
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_srt_timestamp(seconds: float) -> str:
    """1234.567 -> '00:20:34,567' (SRT format uses a comma for milliseconds)."""
    seconds = max(0.0, seconds)
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_txt(segments: list[Segment]) -> str:
    lines = [f"[{format_timestamp(seg.start)}] {seg.text.strip()}" for seg in segments]
    return "\n".join(lines) + "\n"


def segments_to_srt(segments: list[Segment]) -> str:
    blocks = []
    for i, seg in enumerate(segments, start=1):
        blocks.append(
            f"{i}\n"
            f"{format_srt_timestamp(seg.start)} --> {format_srt_timestamp(seg.end)}\n"
            f"{seg.text.strip()}\n"
        )
    return "\n".join(blocks)


def segments_to_json(clip_name: str, duration: float, segments: list[Segment]) -> str:
    payload = {
        "schema_version": 1,
        "clip": clip_name,
        "duration_seconds": round(duration, 3),
        "segments": [
            {"start": round(seg.start, 3), "end": round(seg.end, 3), "text": seg.text.strip()}
            for seg in segments
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def speaker_label_from_filename(path: Path) -> str:
    """His bins are organized per person, so the filename identifies the speaker."""
    return path.stem


def get_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        sys.exit(
            "ERROR: Could not find the bundled ffmpeg.\n"
            "Fix: open a terminal in this folder and run:\n"
            "    pip install -r requirements.txt\n"
            f"(technical detail: {exc})"
        )


def extract_audio(media_path: Path, wav_path: Path) -> None:
    """Extract 16 kHz mono WAV — the format whisper models expect."""
    ffmpeg = get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(media_path),
        "-vn", "-ac", "1", "-ar", "16000", "-f", "wav",
        str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg could not read the audio from '{media_path.name}'.\n"
            f"The file may be corrupt, or it may have no audio track.\n"
            f"ffmpeg said: {result.stderr.strip()[:500]}"
        )


def load_model(model_size: str, device: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit(
            "ERROR: The transcription engine (faster-whisper) is not installed.\n"
            "Fix: open a terminal in this folder and run:\n"
            "    pip install -r requirements.txt"
        )

    if device == "auto":
        # Try the GPU first; fall back to CPU if there is no NVIDIA card / CUDA.
        try:
            model = WhisperModel(model_size, device="cuda", compute_type="float16")
            print("Using NVIDIA GPU (much faster).")
            return model
        except Exception:  # noqa: BLE001
            print("No usable NVIDIA GPU found — using CPU. This works fine, just slower.")
            return WhisperModel(model_size, device="cpu", compute_type="int8")
    compute = "float16" if device == "cuda" else "int8"
    return WhisperModel(model_size, device=device, compute_type=compute)


def transcribe_file(model, media_path: Path) -> tuple[list[Segment], float]:
    """Transcribe one file, showing a progress bar. Returns (segments, duration)."""
    from tqdm import tqdm

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "audio.wav"
        extract_audio(media_path, wav_path)

        seg_iter, info = model.transcribe(str(wav_path), vad_filter=True)
        duration = float(info.duration or 0.0)

        segments: list[Segment] = []
        # faster-whisper yields segments lazily; drive a progress bar off the
        # audio position so long interviews don't look frozen.
        with tqdm(
            total=round(duration, 1),
            unit="sec",
            desc=f"  {media_path.name[:40]}",
            bar_format="{l_bar}{bar}| {n:.0f}/{total:.0f}s [{elapsed}<{remaining}]",
        ) as bar:
            for seg in seg_iter:
                text = seg.text.strip()
                if text:
                    segments.append(Segment(start=seg.start, end=seg.end, text=text))
                bar.n = min(round(seg.end, 1), bar.total or seg.end)
                bar.refresh()
            bar.n = bar.total
            bar.refresh()
    return segments, duration


def write_outputs(out_dir: Path, media_path: Path, segments: list[Segment], duration: float) -> None:
    stem = media_path.stem
    (out_dir / f"{stem}.txt").write_text(segments_to_txt(segments), encoding="utf-8")
    (out_dir / f"{stem}.srt").write_text(segments_to_srt(segments), encoding="utf-8")
    (out_dir / f"{stem}.json").write_text(
        segments_to_json(stem, duration, segments), encoding="utf-8"
    )


def build_combined_transcript(out_dir: Path, transcribed: list[Path]) -> None:
    """One big text file, clearly headed per clip, formatted for pasting into an LLM."""
    parts = [
        "COMBINED INTERVIEW TRANSCRIPTS\n"
        "Each section below is one clip. The speaker is identified by the clip's filename.\n"
        "Timestamps are [HH:MM:SS] from the start of that clip.\n"
    ]
    for media_path in transcribed:
        stem = media_path.stem
        txt = (out_dir / f"{stem}.txt").read_text(encoding="utf-8")
        parts.append(
            "=" * 70 + "\n"
            f"CLIP: {media_path.name}\n"
            f"SPEAKER: {speaker_label_from_filename(media_path)}\n"
            + "=" * 70 + "\n"
            + txt
        )
    (out_dir / "_ALL_TRANSCRIPTS.txt").write_text("\n".join(parts), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transcribe a folder of interview footage — locally.")
    parser.add_argument("folder", help="Folder containing the video files")
    parser.add_argument(
        "--model", default="medium",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Model size. medium = best accuracy/speed balance (default). "
             "small = ~2x faster, slightly less accurate. large-v3 = most accurate, slowest.",
    )
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"],
                        help="auto (default) uses the GPU if you have one.")
    args = parser.parse_args(argv)

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        sys.exit(f"ERROR: '{folder}' is not a folder. Drop a FOLDER of clips, not a single file.")

    media, skipped = find_media_files(folder)
    for path in skipped:
        print(f"WARNING: skipping '{path.name}' — not a video/audio file.")
    if not media:
        sys.exit(
            f"ERROR: No video or audio files found in '{folder}'.\n"
            f"Looked for: {', '.join(sorted(MEDIA_EXTENSIONS))}"
        )

    print(f"Found {len(media)} file(s) to transcribe.")
    print(f"Loading '{args.model}' model (first run downloads it — a few GB, one time only)...")
    model = load_model(args.model, args.device)

    out_dir = folder / "transcripts"
    out_dir.mkdir(exist_ok=True)

    done: list[Path] = []
    failed: list[tuple[Path, str]] = []
    for i, media_path in enumerate(media, start=1):
        print(f"\n[{i}/{len(media)}] {media_path.name}")
        try:
            segments, duration = transcribe_file(model, media_path)
            if not segments:
                print(f"  NOTE: no speech detected in '{media_path.name}'. Wrote empty transcript.")
            write_outputs(out_dir, media_path, segments, duration)
            done.append(media_path)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED: {exc}")
            failed.append((media_path, str(exc)))

    if done:
        build_combined_transcript(out_dir, done)

    print("\n" + "=" * 50)
    print(f"Done. {len(done)} transcribed, {len(failed)} failed.")
    print(f"Transcripts are in: {out_dir}")
    if failed:
        print("\nThese files could not be transcribed:")
        for path, err in failed:
            print(f"  - {path.name}: {err.splitlines()[0]}")
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled. Already-finished transcripts were kept.")
        raise SystemExit(130)
