# Story Assist — transcripts + brief in, selects with timecodes out

This attacks the biggest time sink: listening through interview footage to
find usable statements. There are **two ways to use it** — start with the
first, it needs zero setup.

**Privacy:** only transcript *text* ever goes to the AI. Footage never leaves
your machine — that's what the transcribe tool being local is for.

## Way 1 — paste into Claude (no setup)

Open **`prompt-template.md`** and follow it. Short version: run the transcribe
tool, then paste the client's goal + `_ALL_TRANSCRIPTS.txt` into
[claude.ai](https://claude.ai) using the ready-made prompt. You get selects
with timecodes, a story order, ranked alternate takes, and a gaps list.

## Way 2 — the script (better for big interview days)

The script handles interview days too big to paste into a chat, and it
**automatically verifies every quote and timecode against the transcripts**
so nothing made-up ever reaches your selects list.

### One-time setup

1. Open a terminal in this folder and run:

   ```
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to a file named exactly `.env` (in this folder) and
   paste the API key John gave you on the `ANTHROPIC_API_KEY=` line.
   Costs run on John's account — pennies per project, and each run prints
   what it cost.

### How to use it

1. Save the client's narrative goal into a text file, e.g. `brief.txt`.
   A sentence or a paragraph — whatever you have from the client.
2. Run:

   ```
   python story_assist.py "D:\Projects\Henderson\Interviews\transcripts" brief.txt
   ```

You get two files next to the brief:

- **`selects_report.md`** — selects table, story order (hook → context →
  substance → close), alternate takes ranked by delivery, and gaps to cover
  with B-roll/VO. Opens in any Markdown viewer or plain-text editor.
- **`selects.csv`** — clip / in / out / quote / note. Opens in Excel; keep it
  on a second monitor while pulling selects in Premiere.

### Trust, but verify

Every candidate quote is checked against the transcript .json files before the
report is built; anything that doesn't verify is dropped and listed. You can
also re-check a CSV yourself any time:

```
python check_timecodes.py <transcripts_folder> selects.csv
```

## When it breaks

| Message | Fix |
|---|---|
| `No API key found` | Create the `.env` file as described in setup. The file must be named `.env` exactly (not `.env.txt`). |
| `no transcript .json files found` | Point it at the `transcripts` folder the transcribe tool created (the one containing the .json files). |
| `authentication_error` | The API key is wrong or was rotated — ask John for a fresh one. |
| `rate_limit_error` | Wait a minute and run it again. |
| Selects seem off-topic | Improve the brief — one concrete paragraph about what the video must say beats one vague sentence. |
