#!/usr/bin/env python3
"""One-command delivery encodes, including odd stage-wall resolutions.

    python encode.py <master.mov> <preset>          one file
    python encode.py <folder> <preset>              batch: every video in folder
    python encode.py --list                         show available presets

Presets live in presets.yaml — add a new stage spec by copying a block.

Why these ffmpeg settings (for when an AV lead asks):
- H.264 High profile / level auto: the most universally decodable codec for
  playback machines, media servers, and LED processors.
- Constant frame rate (-fps_mode cfr + -r): playback hardware and show-control
  software assume CFR; variable frame rate causes drift and judder.
- Closed GOP, 2-second keyframes (-g, -flags +cgop, -sc_threshold 0): lets
  operators scrub/loop cleanly and keeps seeking frame-accurate.
- yuv420p pixel format: anything fancier (4:2:2/10-bit) fails on hardware
  decoders; 4:2:0 8-bit plays everywhere.
- -movflags +faststart: moves the index to the front of the file so it starts
  instantly, including when streamed off a server.
- AAC 320k stereo 48kHz: transparent quality, universally supported.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mxf", ".m4v", ".avi", ".mts"}


def load_presets(path: Path | None = None) -> dict:
    try:
        import yaml
    except ImportError:
        sys.exit(
            "ERROR: PyYAML is not installed.\n"
            "Fix: open a terminal in this folder and run: pip install -r requirements.txt"
        )
    preset_path = path or Path(__file__).resolve().parent / "presets.yaml"
    if not preset_path.exists():
        sys.exit(f"ERROR: presets.yaml not found at {preset_path}")
    with open(preset_path, encoding="utf-8") as f:
        presets = yaml.safe_load(f)
    if not isinstance(presets, dict) or not presets:
        sys.exit("ERROR: presets.yaml is empty or malformed.")
    for name, p in presets.items():
        for field in ("width", "height", "fps", "fit", "video_bitrate"):
            if field not in p:
                sys.exit(f"ERROR: preset '{name}' is missing the '{field}' field in presets.yaml")
        if p["fit"] not in ("pad", "crop", "stretch"):
            sys.exit(f"ERROR: preset '{name}': fit must be pad, crop, or stretch (got '{p['fit']}')")
    return presets


def get_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        sys.exit(
            "ERROR: bundled ffmpeg not found.\n"
            "Fix: open a terminal in this folder and run: pip install -r requirements.txt"
        )


def scale_filter(preset: dict) -> str:
    w, h = preset["width"], preset["height"]
    fit = preset["fit"]
    if fit == "pad":
        color = preset.get("pad_color", "black")
        return (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color={color},setsar=1"
        )
    if fit == "crop":
        return (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},setsar=1"
        )
    return f"scale={w}:{h},setsar=1"  # stretch


def build_command(ffmpeg: str, src: Path, dest: Path, preset: dict) -> list[str]:
    fps = preset["fps"]
    # Keyframe every ~2 seconds, e.g. 60 at 29.97fps.
    gop = max(1, int(round(float(fps) * 2)))
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-stats",
        "-i", str(src),
        "-vf", scale_filter(preset),
        "-r", str(fps), "-fps_mode", "cfr",
        "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-b:v", str(preset["video_bitrate"]),
        "-maxrate", str(preset.get("max_bitrate", preset["video_bitrate"])),
        "-bufsize", str(preset.get("max_bitrate", preset["video_bitrate"])),
        "-g", str(gop), "-keyint_min", str(gop), "-flags", "+cgop", "-sc_threshold", "0",
        "-c:a", "aac", "-b:a", str(preset.get("audio_bitrate", "320k")), "-ac", "2", "-ar", "48000",
        "-movflags", "+faststart",
        str(dest),
    ]
    return cmd


def encode_one(ffmpeg: str, src: Path, preset_name: str, preset: dict) -> Path:
    dest = src.with_name(f"{src.stem}_{preset_name}.mp4")
    if dest == src:
        dest = src.with_name(f"{src.stem}_{preset_name}_encoded.mp4")
    print(f"  {src.name} -> {dest.name}")
    result = subprocess.run(build_command(ffmpeg, src, dest, preset))
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed on '{src.name}'. The file may be corrupt or an "
            "unsupported format. Scroll up for ffmpeg's own message."
        )
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Encode masters to delivery presets.")
    parser.add_argument("source", nargs="?", help="A video file, or a folder of them (batch)")
    parser.add_argument("preset", nargs="?", help="Preset name from presets.yaml")
    parser.add_argument("--list", action="store_true", help="List available presets")
    args = parser.parse_args(argv)

    presets = load_presets()
    if args.list or not args.source:
        print("Available presets:")
        for name, p in presets.items():
            print(f"  {name:<20} {p['width']}x{p['height']} @ {p['fps']}fps, "
                  f"{p['fit']}, {p['video_bitrate']} - {p.get('description', '')}")
        return 0

    if not args.preset:
        sys.exit("ERROR: no preset given. Run 'python encode.py --list' to see the options.")
    if args.preset not in presets:
        sys.exit(f"ERROR: no preset called '{args.preset}'.\n"
                 f"Available: {', '.join(presets)}")
    preset = presets[args.preset]

    source = Path(args.source).expanduser()
    if source.is_dir():
        files = [p for p in sorted(source.iterdir())
                 if p.suffix.lower() in VIDEO_EXTENSIONS]
        if not files:
            sys.exit(f"ERROR: no video files found in '{source}'.")
    elif source.is_file():
        files = [source]
    else:
        sys.exit(f"ERROR: '{source}' does not exist.")

    ffmpeg = get_ffmpeg_exe()
    print(f"Encoding {len(files)} file(s) with preset '{args.preset}' "
          f"({preset['width']}x{preset['height']} @ {preset['fps']}fps, {preset['fit']}).")
    failed = []
    for src in files:
        try:
            encode_one(ffmpeg, src, args.preset, preset)
        except RuntimeError as exc:
            print(f"  FAILED: {exc}")
            failed.append(src.name)

    print(f"\nDone: {len(files) - len(failed)} encoded, {len(failed)} failed.")
    if failed:
        for name in failed:
            print(f"  failed: {name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
