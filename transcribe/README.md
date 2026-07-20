# Transcribe — interview footage → timecoded transcripts, 100% local

Drop a folder of interview clips on a script and get, for every clip:

- **`.txt`** — readable transcript with `[HH:MM:SS]` timestamps
- **`.srt`** — subtitle file you can import straight into Premiere
- **`.json`** — machine-readable version (used by the story-assist tool)
- **`_ALL_TRANSCRIPTS.txt`** — every clip combined into one file, formatted to
  paste into Claude along with your story brief

Nothing is uploaded anywhere. The transcription model runs on your computer.

## One-time setup

1. Install Python 3.11+ (see the main README one folder up).
2. Open a terminal **in this folder** and run:

   ```
   pip install -r requirements.txt
   ```

   Windows shortcut: click the address bar in this folder's Explorer window,
   type `cmd`, press Enter, then paste the line above.

The first time you transcribe, the speech model downloads automatically
(~1.5 GB, one time only). After that it works fully offline.

## How to use it

**Windows:** drag your folder of clips onto **`Transcribe - Drop Folder Here.bat`**.

**Mac:** double-click **`transcribe.command`**, then drag the folder into the
Terminal window and press Return.
(First time only: if Mac blocks it, right-click → Open → Open. If it says
"permission denied", run `chmod +x transcribe.command` once in Terminal.)

**Terminal (either OS):**

```
python transcribe.py "D:\Projects\Henderson\Interviews"
```

A `transcripts` folder appears inside the folder you dropped.

### Options

| What you want | Command |
|---|---|
| Faster, slightly less accurate | `python transcribe.py <folder> --model small` |
| Most accurate, slowest | `python transcribe.py <folder> --model large-v3` |
| Force CPU (if GPU acts up) | `python transcribe.py <folder> --device cpu` |

**Accuracy vs speed:** the default `medium` model is the sweet spot — near-
perfect on clean interview audio. `small` is roughly 2× faster and fine for
rough select pulls. `large-v3` squeezes out a little more accuracy on heavy
accents or bad audio but takes noticeably longer. On a modern CPU expect
roughly real-time to 3× real-time with `medium`; with an NVIDIA GPU it's many
times faster (the tool finds the GPU automatically).

### Tips

- **Name clips after the person** (e.g. `Sarah_Henderson_01.mp4`). The combined
  transcript uses the filename as the speaker label, which is what makes the
  story-assist step work well.
- Non-video files in the folder are skipped with a warning — a stray `.psd` or
  `.xml` won't break anything.
- You can cancel any time (Ctrl+C / close the window). Finished transcripts
  are kept; just run it again and re-do the rest.

## When it breaks

| Message | What it means / fix |
|---|---|
| `'python' is not recognized` | Python isn't installed or wasn't added to PATH. Reinstall Python and check "Add Python to PATH". On Mac, use `python3`. |
| `faster-whisper is not installed` | Run the setup step: `pip install -r requirements.txt` |
| `ffmpeg could not read the audio` | That one clip is corrupt or has no audio track. The other clips still finish. |
| It looks stuck on "Loading model" the first time | It's downloading the model (~1.5 GB). Let it finish once; it never downloads again. |
| Transcripts have wrong words | Try `--model large-v3`, and check the audio isn't clipped/distorted at the source. |
