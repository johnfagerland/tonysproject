# Changelog

## v1.0.0 — 2026-07-20

Initial release.

- **transcribe/** — local timecoded transcription (faster-whisper). Outputs
  .txt / .srt / .json per clip plus a combined `_ALL_TRANSCRIPTS.txt` for
  pasting into Claude. Drag-and-drop wrappers for Windows and Mac.
- **story-assist/** — battle-tested prompt template (paste-into-Claude
  workflow) plus a scripted version that reads transcript JSON + a brief and
  writes a selects report (Markdown) and a timecode CSV. Includes an automated
  timecode checker that verifies every quote against the source transcripts.
- **archiver/** — verified (xxhash) copy to external drives, resumable,
  never deletes source automatically, per-project manifest, master
  `archive_index.csv` with drive nicknames, and `find` search.
- **feedback-parser/** — single-file web page that turns pasted client
  feedback into a categorized, timecoded revision checklist with a
  "needs clarification" section. Works from a local file or hosted with a
  Vercel proxy.
- **encode-presets/** — `presets.yaml` + `encode.py` for one-command H.264
  delivery encodes, including custom stage-wall resolutions with pad/crop/
  stretch strategies. Batch mode included.
