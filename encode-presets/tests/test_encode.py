"""Validation-loop tests for the encoder.

Generates a synthetic 59.94fps source with ffmpeg, encodes it with real
presets, and verifies with ffprobe/ffmpeg that:
- output dimensions exactly match the preset (pad, crop, and stretch)
- a 59.94 -> 29.97 conversion produces true CFR at 29.97 (no judder settings)

Run from the encode-presets/ folder:  python -m pytest tests/ -v
(Needs `pip install -r requirements.txt` first; skips if ffmpeg is unavailable.)
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import encode  # noqa: E402


@pytest.fixture(scope="module")
def ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        pytest.skip("imageio-ffmpeg not installed")


@pytest.fixture(scope="module")
def source_5994(ffmpeg, tmp_path_factory):
    """A 4-second 1280x720 59.94fps test clip with audio."""
    path = tmp_path_factory.mktemp("src") / "master 59.94 #test.mov"
    subprocess.run([
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=60000/1001:duration=4",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(path),
    ], check=True)
    return path


def probe(ffmpeg: str, path: Path) -> dict:
    """Read stream info. imageio-ffmpeg ships ffmpeg but not ffprobe, so try
    ffprobe from PATH first and fall back to parsing ffmpeg -i output."""
    import shutil as _shutil
    ffprobe = _shutil.which("ffprobe")
    if ffprobe:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0", "-count_frames",
             "-show_entries",
             "stream=width,height,r_frame_rate,avg_frame_rate,nb_read_frames",
             "-of", "json", str(path)],
            capture_output=True, text=True, check=True).stdout
        return json.loads(out)["streams"][0]
    # Fallback: parse "1920x1080" and "29.97 fps" from ffmpeg's banner.
    result = subprocess.run([ffmpeg, "-i", str(path)], capture_output=True, text=True)
    import re
    m = re.search(r"(\d{3,5})x(\d{3,5})", result.stderr)
    fps = re.search(r"(\d+(?:\.\d+)?) fps", result.stderr)
    return {
        "width": int(m.group(1)), "height": int(m.group(2)),
        "avg_frame_rate": fps.group(1) if fps else "?",
        "r_frame_rate": fps.group(1) if fps else "?",
    }


def fps_value(rate: str) -> float:
    if "/" in str(rate):
        num, den = str(rate).split("/")
        return float(num) / float(den)
    return float(rate)


def run_preset(ffmpeg, src, name, preset):
    return encode.encode_one(ffmpeg, src, name, preset)


BASE = dict(fps=29.97, video_bitrate="2M", max_bitrate="3M", audio_bitrate="128k")


def test_pad_output_dimensions_exact(ffmpeg, source_5994):
    preset = dict(BASE, width=4480, height=1080, fit="pad", pad_color="black")
    out = run_preset(ffmpeg, source_5994, "stage-4480x1080", preset)
    info = probe(ffmpeg, out)
    assert (info["width"], info["height"]) == (4480, 1080)


def test_crop_output_dimensions_exact(ffmpeg, source_5994):
    preset = dict(BASE, width=1080, height=1080, fit="crop")
    out = run_preset(ffmpeg, source_5994, "square-crop", preset)
    info = probe(ffmpeg, out)
    assert (info["width"], info["height"]) == (1080, 1080)


def test_stretch_output_dimensions_exact(ffmpeg, source_5994):
    preset = dict(BASE, width=1920, height=1080, fit="stretch")
    out = run_preset(ffmpeg, source_5994, "stretched", preset)
    info = probe(ffmpeg, out)
    assert (info["width"], info["height"]) == (1920, 1080)


def test_5994_to_2997_is_true_cfr(ffmpeg, source_5994):
    """The judder check: output must be constant 29.97 (30000/1001), with the
    frame count matching duration x rate, not a VFR mongrel."""
    preset = dict(BASE, width=1920, height=1080, fit="pad", pad_color="black")
    out = run_preset(ffmpeg, source_5994, "standard-1080", preset)
    info = probe(ffmpeg, out)
    assert abs(fps_value(info["avg_frame_rate"]) - 29.97) < 0.01
    assert abs(fps_value(info["r_frame_rate"]) - 29.97) < 0.01
    if "nb_read_frames" in info:  # only when real ffprobe is available
        # 4 seconds at 29.97 -> ~120 frames (allow one frame of slack at EOF)
        assert abs(int(info["nb_read_frames"]) - 120) <= 1


def test_presets_yaml_is_valid():
    presets = encode.load_presets()
    assert "standard-1080" in presets
    assert presets["standard-1080"]["width"] == 1920
    assert presets["stage-4480x1080"]["fit"] == "pad"


def test_unknown_preset_fails_loudly(source_5994):
    with pytest.raises(SystemExit) as exc:
        encode.main([str(source_5994), "no-such-preset"])
    assert "no preset called" in str(exc.value)
