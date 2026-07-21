# Archiver — verified project transfers you don't have to babysit

Replaces the half-day of watching progress bars. Kick it off at end of day;
overnight it copies the project to your external drive, **verifies every file
with a checksum**, and writes an index entry so you can always answer *"which
drive is the Henderson project on?"* without plugging anything in.

**It never deletes your source files.** Ever. Deleting is a separate command
that re-verifies the archive first and makes you type DELETE.

## One-time setup

Open a terminal in this folder and run:

```
pip install -r requirements.txt
```

## Archiving a project

**Windows:** drag the finished project folder onto
**`Archive - Drop Project Folder Here.bat`**, then type the drive letter
(e.g. `E:\`) when asked.

**Mac:** double-click **`archive.command`** and follow the prompts.

**Terminal:**

```
python archiver.py archive "D:\Projects\Henderson_2026" "E:\"
```

What happens:

1. First time it sees a drive it asks you for a nickname ("gray 8TB #2") and
   remembers it.
2. It checks the drive has enough free space, then copies every file,
   checksumming the source and the copy. Any mismatch is retried once, then
   reported.
3. When 100% of files verify you get a clear **"VERIFIED — safe to delete
   source"** message, a manifest saved on the drive *and* on your computer,
   an entry in the master index, a log file, and a desktop notification.

**Interrupted?** (power cut, drive unplugged, you closed the window) — just run
the exact same command again. Already-verified files are skipped; it picks up
where it left off.

**Unattended overnight runs:** add `--yes` so it never stops to ask anything:

```
python archiver.py archive "D:\Projects\Henderson_2026" "E:\" --yes
```

**Health-check an old archive:** re-run the archive command with `--verify` to
re-checksum every already-archived file against the manifest (slower — it
re-reads the whole archive — but catches a drive going bad, and repairs any
damaged file from the source).

## Finding a project later

```
python archiver.py find "henderson"
```

```
Henderson_2026
  drive:    gray 8TB #2 (label 'ARCHIVE_02')
  location: E:\Henderson_2026
  archived: 2026-07-20  (1842 files, 412.55 GB)
```

The index lives at `~/EditorToolsArchive/archive_index.csv` — it also opens in
Excel if you prefer browsing it.

## Deleting the source (only after archiving)

```
python archiver.py cleanup "D:\Projects\Henderson_2026" "E:\"
```

This re-checksums every archived file against the manifest. Only if everything
is present and intact does it ask you to type `DELETE`. If anything is missing
or corrupt it stops and tells you exactly what — the source is untouched.

## When it breaks

| Message | Fix |
|---|---|
| `destination not found` | The drive isn't plugged in / mounted, or you typed the wrong letter. |
| `not enough space on the drive` | It checks before starting so it can't die at 90%. Use another drive. |
| `NOT COMPLETE — N file(s) failed` | Usually a flaky cable or a dying drive. Re-run the same command (verified files skip). If the same files keep failing, try another cable/port, then another drive. |
| `archive copy is CORRUPT` during cleanup | The drive copy went bad after archiving. Do NOT delete the source; re-run the archive command to repair it. |
| Nickname is wrong | Edit `~/EditorToolsArchive/drives.json` in any text editor. |
