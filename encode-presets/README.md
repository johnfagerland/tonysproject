# Encode Presets — one-command delivery encodes

Turns a master into a delivery file with the right settings every time,
including the weird stage-wall resolutions (4480×1080 and friends).

## One-time setup

```
pip install -r requirements.txt
```

## How to use it

**Windows:** drag your master file (or a folder of masters for a batch) onto
**`Encode - Drop Video Here.bat`**, then type the preset name it shows you.

**Mac:** double-click **`encode.command`** and follow the prompts.

**Terminal:**

```
python encode.py --list                          # see the presets
python encode.py "Master_v3.mov" standard-1080   # one file
python encode.py "D:\Masters\" stage-4480x1080   # every video in the folder
```

Output lands next to the source, named `Master_v3_standard-1080.mp4`.

## Adding a stage spec

Open `presets.yaml` in any text editor, copy an existing block, rename it, and
change `width`/`height`. Example for a 3840×1200 wall:

```yaml
stage-3840x1200:
  description: "Acme Corp 2026 main wall"
  width: 3840
  height: 1200
  fps: 29.97
  fit: pad          # pad = letterbox (safe) | crop = fill & trim | stretch = distort to fit
  pad_color: black  # or a hex like "0x101010" to match the show look
  video_bitrate: 35M
  max_bitrate: 45M
  audio_bitrate: 320k
```

**Which `fit` to pick:** `pad` is the safe default — your 16:9 content sits
centered with bars, nothing cropped or distorted. Use `crop` when the wall
should be edge-to-edge full and losing the edges is acceptable. Use `stretch`
only when the LED processor expects a pre-distorted feed (ask the vendor).

## Why these settings (for AV leads who ask)

- **H.264 High profile, yuv420p** — decodes on every playback machine, media
  server, and LED processor in the field. 4:2:2/10-bit files are what cause
  the "it won't play" call at 7am.
- **Constant frame rate** — playback and show-control software assume CFR;
  VFR causes audio drift and judder. A 59.94 master requested at 29.97 is
  converted properly (every other frame), not left variable.
- **Closed GOP, 2s keyframes** — clean looping, scrubbing, and frame-accurate
  cueing on playback rigs.
- **`+faststart`** — file starts playing instantly, even off a server.
- **High bitrate (20 Mb/s at 1080p, more for walls)** — playback is from local
  storage; there is no reason to starve the encode. Bump `video_bitrate` in
  the preset if you ever see banding in gradients.
- **AAC 320k stereo 48 kHz** — transparent and universal.

## When it breaks

| Message | Fix |
|---|---|
| `no preset called '...'` | Typo — run `python encode.py --list` and copy the exact name. |
| `ffmpeg failed on ...` | The master may be corrupt or a very odd format. Try re-exporting the master. |
| Output looks squeezed | The preset uses `stretch` — switch it to `pad` unless the vendor asked for stretched. |
| Bars on the sides/top | That's `pad` doing its job: the master's aspect ratio doesn't match the preset. Use `crop` if edge-to-edge matters more than keeping the edges. |
