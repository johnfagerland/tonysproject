# Editor Tools

A set of five small tools that automate the boring parts of corporate video
editing: transcribing interviews, finding the good soundbites, archiving
finished projects, turning messy client feedback into a checklist, and
one-command encodes for stage playback.

**You do not need to be a programmer to use these.** Every tool can be run by
dragging a folder or file onto a script, or by double-clicking. Each folder has
its own README with step-by-step instructions and a "when it breaks" section.

## One-time setup (5 minutes)

1. Install Python 3.11 or newer from <https://www.python.org/downloads/>.
   **On Windows, check the box that says "Add Python to PATH" during install.**
2. Open the tool folder you want to use and follow its README's setup section
   (usually a single `pip install -r requirements.txt` — the README shows
   exactly what to type or double-click).

That's it. No accounts, no subscriptions, nothing goes to the cloud except
plain text in the two tools that explicitly say so.

## The tools

| Folder | What it does | Footage leaves your machine? |
|---|---|---|
| `transcribe/` | Drop a folder of interview clips → get timecoded transcripts (.txt, .srt, .json) for every clip. Runs entirely on your computer. | **No — 100% local** |
| `story-assist/` | Transcripts + the client's story brief in → recommended soundbites with timecodes and a suggested story order out. | Only transcript **text** (never video/audio) |
| `archiver/` | Verified, resumable copies of finished projects to your external drives, plus a searchable index of which drive every project is on. | **No — 100% local** |
| `feedback-parser/` | Paste messy client emails / Frame.io comments → clean, timecoded revision checklist grouped by category. | Only the feedback **text** you paste |
| `encode-presets/` | One-command H.264 encodes for delivery, including odd stage-wall resolutions (pad/crop/stretch). | **No — 100% local** |

## The rule about footage

RAW footage never goes to the cloud. The two AI-assisted tools (`story-assist`
and `feedback-parser`) send **only text** — transcripts and feedback notes — to
the Anthropic API. Video and audio files are never uploaded by anything in this
repo.

## Audio leveling (no tool needed — use what you already own)

Your most-hated task is already solved by software you have:

1. **Premiere Essential Sound panel:** select all your dialogue clips →
   Essential Sound → tag as *Dialogue* → **Loudness → Auto-Match**. This
   levels every clip to a broadcast-standard loudness in one click.
2. **Enhance Speech** (Premiere 2024+): in Essential Sound under *Dialogue*,
   toggle **Enhance Speech** for noisy or roomy recordings. Use the strength
   slider sparingly (30–50% usually sounds natural).
3. For genuinely rough recordings (phone audio, echoey conference rooms), run
   the file through **Adobe Podcast Enhance** (free with your Adobe login at
   <https://podcast.adobe.com/enhance>) and cut the cleaned file in instead.
4. Final check: keep your master mix around **-23 LUFS for broadcast** or
   **-16 LUFS for web/ballroom playback** (Premiere's Loudness Radar or the
   Essential Sound auto-match handles this for you).

## Getting updates

You'll receive new versions as a zip file with a dated changelog
(`CHANGELOG.md`). To update: delete the old folder, unzip the new one, done.
Your settings files (`.env`, `config.js`, archive index) live outside the
zip's replaced files or are listed in the changelog if you need to carry
anything over.
