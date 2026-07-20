#!/usr/bin/env python3
"""Archive automation — verified, resumable, indexed project transfers.

    python archiver.py archive <project_folder> <destination_drive_or_folder>
    python archiver.py cleanup <project_folder> <destination>
    python archiver.py find "henderson"

Safety rules baked in:
- The source is NEVER deleted automatically. After 100% verification you get a
  "verified - safe to delete source" report; actual deletion is the separate
  `cleanup` command, which re-verifies the archive first and asks again.
- Every file is hashed (xxhash) on the source, copied, then re-hashed on the
  destination. A mismatch is retried once, then reported loudly.
- Interrupted transfers resume: rerun the same command and already-verified
  files are skipped.

A master index lives in your home folder (~/EditorToolsArchive) so you can ask
"which drive is project X on?" without plugging anything in.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import datetime as dt
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

try:
    import xxhash
except ImportError:
    sys.exit(
        "ERROR: the 'xxhash' package is not installed.\n"
        "Fix: open a terminal in this folder and run: pip install -r requirements.txt"
    )

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB — streams files of any size with flat memory use
MANIFEST_FLUSH_INTERVAL = 25  # save progress every N files so a crash loses little
INDEX_DIR = Path(os.environ.get("ARCHIVER_INDEX_DIR", Path.home() / "EditorToolsArchive"))
INDEX_CSV = INDEX_DIR / "archive_index.csv"
DRIVES_JSON = INDEX_DIR / "drives.json"
MANIFESTS_DIR = INDEX_DIR / "manifests"
LOGS_DIR = INDEX_DIR / "logs"
INDEX_COLUMNS = ["date", "project", "drive_label", "drive_nickname",
                 "destination", "files", "total_gb", "manifest"]

# Files that should never be archived (OS litter).
SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}


# --------------------------------------------------------------------------- hashing / fs

def hash_file(path: Path) -> str:
    h = xxhash.xxh64()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def copy_and_hash(src: Path, dest: Path) -> str:
    """Copy src -> dest in one streaming pass, returning the source hash.
    Writes to a temp name first so an interrupted copy never leaves a
    plausible-looking half file at the real destination."""
    tmp = dest.with_name(dest.name + ".part")
    h = xxhash.xxh64()
    with open(src, "rb") as fin, open(tmp, "wb") as fout:
        while chunk := fin.read(CHUNK_SIZE):
            h.update(chunk)
            fout.write(chunk)
    os.replace(tmp, dest)
    # Preserve timestamps so the archive mirrors the source.
    stat = src.stat()
    os.utime(dest, (stat.st_atime, stat.st_mtime))
    return h.hexdigest()


def iter_project_files(project: Path):
    for path in sorted(project.rglob("*")):
        if path.is_file() and path.name not in SKIP_NAMES and not path.name.endswith(".part"):
            yield path


def get_drive_label(dest: Path) -> str:
    """Volume label of the drive holding *dest* (best effort per OS)."""
    dest = dest.resolve()
    if platform.system() == "Windows":
        try:
            root = Path(dest.anchor)
            buf = ctypes.create_unicode_buffer(261)
            ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
                ctypes.c_wchar_p(str(root)), buf, 261, None, None, None, None, 0)
            if buf.value:
                return buf.value
            return str(root).rstrip("\\/")
        except Exception:  # noqa: BLE001
            return str(dest.anchor).rstrip("\\/")
    # Mac/Linux: external drives mount under /Volumes/<Label> or /media/<user>/<Label>
    parts = dest.parts
    for marker in ("Volumes", "media", "mnt"):
        if marker in parts:
            idx = parts.index(marker)
            rest = parts[idx + 1:]
            if rest:
                # /media/<user>/<label> has one extra level
                return rest[1] if marker == "media" and len(rest) > 1 else rest[0]
    return dest.anchor or "unknown-drive"


# --------------------------------------------------------------------------- index / nicknames

def ensure_index() -> None:
    for d in (INDEX_DIR, MANIFESTS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def get_drive_nickname(label: str, assume_yes: bool = False) -> str:
    """Remember a human nickname per drive ('gray 8TB #2'). Prompt on first use."""
    ensure_index()
    drives = {}
    if DRIVES_JSON.exists():
        drives = json.loads(DRIVES_JSON.read_text(encoding="utf-8"))
    if label in drives:
        return drives[label]
    nickname = label
    if not assume_yes and sys.stdin.isatty():
        answer = input(
            f"\nNew drive detected (label: '{label}').\n"
            "Give it a nickname you'll recognize (e.g. 'gray 8TB #2'), or press "
            f"Enter to just use '{label}': "
        ).strip()
        if answer:
            nickname = answer
    drives[label] = nickname
    DRIVES_JSON.write_text(json.dumps(drives, indent=2, ensure_ascii=False), encoding="utf-8")
    return nickname


def update_index(row: dict) -> None:
    """Append/replace this project+drive entry in the master CSV (no duplicates
    when a transfer is resumed or re-run)."""
    ensure_index()
    rows = []
    if INDEX_CSV.exists():
        with open(INDEX_CSV, encoding="utf-8-sig", newline="") as f:
            rows = [r for r in csv.DictReader(f)
                    if not (r["project"] == row["project"] and r["drive_label"] == row["drive_label"])]
    rows.append(row)
    with open(INDEX_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=INDEX_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def notify(title: str, message: str) -> None:
    """Best-effort desktop notification when an overnight run finishes."""
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{message}" with title "{title}"'],
                capture_output=True, timeout=10)
        elif system == "Windows":
            script = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                "ContentType = WindowsRuntime] > $null;"
                "$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
                "[Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
                f"$t.GetElementsByTagName('text').Item(0).InnerText = '{title}';"
                f"$t.GetElementsByTagName('text').Item(1).InnerText = '{message}';"
                "$n = [Windows.UI.Notifications.ToastNotification]::new($t);"
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
                "'Archiver').Show($n);"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, timeout=15)
    except Exception:  # noqa: BLE001 — a failed popup must never fail the archive
        pass


# --------------------------------------------------------------------------- manifest

def manifest_paths(project_name: str, dest_root: Path, drive_label: str) -> tuple[Path, Path]:
    dest_manifest = dest_root / f"{project_name}_manifest.json"
    local_manifest = MANIFESTS_DIR / f"{project_name}__{drive_label}_manifest.json"
    return dest_manifest, local_manifest


def load_manifest(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"WARNING: manifest at {path} was unreadable - starting verification fresh.")
    return {}


def save_manifest(manifest: dict, *paths: Path) -> None:
    text = json.dumps(manifest, indent=2, ensure_ascii=False)
    for path in paths:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)


# --------------------------------------------------------------------------- archive

def cmd_archive(args) -> int:
    project = Path(args.project).expanduser().resolve()
    dest_base = Path(args.destination).expanduser().resolve()
    if not project.is_dir():
        sys.exit(f"ERROR: project folder not found: {project}")
    if not dest_base.is_dir():
        sys.exit(f"ERROR: destination not found: {dest_base}\n"
                 "Is the external drive plugged in and mounted?")
    if project == dest_base or dest_base.is_relative_to(project):
        sys.exit("ERROR: the destination is inside the project folder. Pick the external drive.")

    ensure_index()
    drive_label = args.drive_label or get_drive_label(dest_base)
    nickname = get_drive_nickname(drive_label, assume_yes=args.yes)
    project_name = project.name
    dest_root = dest_base / project_name
    dest_root.mkdir(exist_ok=True)

    dest_manifest_path, local_manifest_path = manifest_paths(project_name, dest_base, drive_label)
    manifest = load_manifest(dest_manifest_path)
    manifest.setdefault("project", project_name)
    manifest.setdefault("source", str(project))
    manifest["drive_label"] = drive_label
    manifest["drive_nickname"] = nickname
    manifest["destination"] = str(dest_root)
    files: dict = manifest.setdefault("files", {})

    all_files = list(iter_project_files(project))
    total_bytes = sum(p.stat().st_size for p in all_files)
    print(f"\nArchiving '{project_name}' -> {dest_root}")
    print(f"Drive: {nickname} (label '{drive_label}')")
    print(f"{len(all_files)} files, {total_bytes / 1e9:.2f} GB total.\n")

    # Free-space sanity check before an overnight run dies at 90%.
    try:
        free = os.statvfs(dest_base).f_frsize * os.statvfs(dest_base).f_bavail \
            if hasattr(os, "statvfs") else __import__("shutil").disk_usage(dest_base).free
    except Exception:  # noqa: BLE001
        free = None
    if free is not None and free < total_bytes * 1.02:
        sys.exit(f"ERROR: not enough space on the drive. Need {total_bytes/1e9:.1f} GB, "
                 f"drive has {free/1e9:.1f} GB free.")

    done_bytes = 0
    copied = skipped = failed = 0
    failures: list[str] = []
    started = dt.datetime.now()
    unsaved = 0

    for i, src in enumerate(all_files, start=1):
        rel = src.relative_to(project).as_posix()
        size = src.stat().st_size
        dest = dest_root / rel
        entry = files.get(rel)

        # Resume: skip files already copied AND verified, if untouched since.
        # With --verify, re-hash the archived copy too (slower, catches bit-rot).
        if (entry and entry.get("verified") and dest.exists()
                and dest.stat().st_size == size and entry.get("size") == size
                and (not args.verify or hash_file(dest) == entry.get("xxh64"))):
            skipped += 1
            done_bytes += size
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        ok = False
        for attempt in (1, 2):
            try:
                src_hash = copy_and_hash(src, dest)
                dest_hash = hash_file(dest)
                if src_hash == dest_hash:
                    ok = True
                    break
                print(f"  VERIFY FAILED (attempt {attempt}): {rel} - re-copying...")
            except OSError as exc:
                print(f"  COPY FAILED (attempt {attempt}): {rel} - {exc}")
        if ok:
            files[rel] = {
                "size": size,
                "xxh64": src_hash,
                "verified": True,
                "verified_at": dt.datetime.now().isoformat(timespec="seconds"),
            }
            copied += 1
        else:
            files[rel] = {"size": size, "verified": False}
            failed += 1
            failures.append(rel)

        done_bytes += size
        unsaved += 1
        if unsaved >= MANIFEST_FLUSH_INTERVAL:
            save_manifest(manifest, dest_manifest_path, local_manifest_path)
            unsaved = 0
        pct = done_bytes / total_bytes * 100 if total_bytes else 100
        print(f"  [{pct:5.1f}%] ({i}/{len(all_files)}) {rel}")

    manifest["archived_at"] = dt.datetime.now().isoformat(timespec="seconds")
    manifest["complete"] = failed == 0
    save_manifest(manifest, dest_manifest_path, local_manifest_path)

    verified_count = sum(1 for e in files.values() if e.get("verified"))
    elapsed = dt.datetime.now() - started
    log_lines = [
        f"Archive run finished {dt.datetime.now():%Y-%m-%d %H:%M}",
        f"Project: {project_name}",
        f"Source:  {project}",
        f"Drive:   {nickname} (label '{drive_label}') -> {dest_root}",
        f"Files:   {len(all_files)} total | {copied} copied | {skipped} already verified | {failed} FAILED",
        f"Size:    {total_bytes / 1e9:.2f} GB | took {str(elapsed).split('.')[0]}",
    ]

    print("\n" + "=" * 60)
    if failed == 0 and verified_count == len(all_files):
        update_index({
            "date": f"{dt.date.today():%Y-%m-%d}",
            "project": project_name,
            "drive_label": drive_label,
            "drive_nickname": nickname,
            "destination": str(dest_root),
            "files": str(len(all_files)),
            "total_gb": f"{total_bytes / 1e9:.2f}",
            "manifest": str(local_manifest_path),
        })
        log_lines.append("RESULT: 100% VERIFIED - safe to delete the source.")
        print("VERIFIED - every file was copied and its checksum matches.")
        print(f"  {len(all_files)} files, {total_bytes/1e9:.2f} GB on '{nickname}'.")
        print("\nIt is now SAFE TO DELETE THE SOURCE, but nothing is deleted")
        print("automatically. When you're ready, run:")
        print(f'  python archiver.py cleanup "{project}" "{dest_base}"')
        result = 0
        notify("Archive complete", f"{project_name}: {len(all_files)} files verified on {nickname}.")
    else:
        log_lines.append(f"RESULT: INCOMPLETE - {failed} file(s) failed. Source NOT safe to delete.")
        log_lines += [f"  failed: {rel}" for rel in failures]
        print(f"NOT COMPLETE - {failed} file(s) could not be copied/verified:")
        for rel in failures[:20]:
            print(f"  - {rel}")
        print("\nDO NOT delete the source. Fix the issue (drive full? bad cable?)")
        print("and run the exact same command again - verified files are skipped.")
        result = 1
        notify("Archive INCOMPLETE", f"{project_name}: {failed} file(s) failed. Source kept.")
    print("=" * 60)

    log_path = LOGS_DIR / f"{project_name}_{dt.datetime.now():%Y%m%d_%H%M%S}.log"
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(f"Log written to {log_path}")
    return result


# --------------------------------------------------------------------------- cleanup

def cmd_cleanup(args) -> int:
    project = Path(args.project).expanduser().resolve()
    dest_base = Path(args.destination).expanduser().resolve()
    project_name = project.name
    dest_root = dest_base / project_name
    dest_manifest_path = dest_base / f"{project_name}_manifest.json"

    if not project.is_dir():
        sys.exit(f"ERROR: source folder not found (already deleted?): {project}")
    manifest = load_manifest(dest_manifest_path)
    if not manifest or "files" not in manifest:
        sys.exit(f"ERROR: no manifest found at {dest_manifest_path}.\n"
                 "Run the archive command first; cleanup only deletes what has "
                 "been archived AND verified.")

    print(f"Re-checking the archive on '{manifest.get('drive_nickname', '?')}' "
          "before touching the source...")
    source_files = list(iter_project_files(project))
    problems = []
    for src in source_files:
        rel = src.relative_to(project).as_posix()
        entry = manifest["files"].get(rel)
        dest = dest_root / rel
        if not entry or not entry.get("verified"):
            problems.append(f"{rel}: not in the verified manifest")
        elif not dest.exists():
            problems.append(f"{rel}: missing from the archive drive")
        elif hash_file(dest) != entry["xxh64"]:
            problems.append(f"{rel}: archive copy is CORRUPT (checksum mismatch)")

    if problems:
        print(f"\nSTOPPING - {len(problems)} problem(s). The source was NOT touched:")
        for p in problems[:20]:
            print(f"  - {p}")
        print("\nRe-run the archive command to repair, then try cleanup again.")
        return 1

    print(f"All {len(source_files)} source files verified present and intact in the archive.")
    if not args.yes:
        answer = input(
            f"\nType DELETE to permanently delete the source folder\n  {project}\n> ").strip()
        if answer != "DELETE":
            print("Nothing deleted.")
            return 0
    import shutil
    shutil.rmtree(project)
    print(f"Source deleted. The project lives on '{manifest.get('drive_nickname')}' at {dest_root}")
    return 0


# --------------------------------------------------------------------------- find

def cmd_find(args) -> int:
    if not INDEX_CSV.exists():
        print("No archives indexed yet. Run an archive first.")
        return 1
    query = args.query.lower()
    with open(INDEX_CSV, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if query in " ".join(r.values()).lower()]
    if not rows:
        print(f"Nothing matching '{args.query}' in the archive index.")
        return 1
    for r in rows:
        print(f"{r['project']}\n"
              f"  drive:    {r['drive_nickname']} (label '{r['drive_label']}')\n"
              f"  location: {r['destination']}\n"
              f"  archived: {r['date']}  ({r['files']} files, {r['total_gb']} GB)\n")
    return 0


# --------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verified project archiving to external drives.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_archive = sub.add_parser("archive", help="Copy + verify a project to a drive")
    p_archive.add_argument("project", help="The finished project folder")
    p_archive.add_argument("destination", help="The external drive (or a folder on it)")
    p_archive.add_argument("--drive-label", default=None, help="Override the detected volume label")
    p_archive.add_argument("--yes", action="store_true", help="No prompts (for unattended runs)")
    p_archive.add_argument("--verify", action="store_true",
                           help="On re-runs, re-checksum already-archived files too (catches bit-rot)")
    p_archive.set_defaults(func=cmd_archive)

    p_cleanup = sub.add_parser("cleanup", help="Re-verify the archive, then delete the source")
    p_cleanup.add_argument("project", help="The source project folder to delete")
    p_cleanup.add_argument("destination", help="The drive it was archived to")
    p_cleanup.add_argument("--yes", action="store_true", help="Skip the DELETE confirmation")
    p_cleanup.set_defaults(func=cmd_cleanup)

    p_find = sub.add_parser("find", help='Which drive is a project on? e.g. find "henderson"')
    p_find.add_argument("query")
    p_find.set_defaults(func=cmd_find)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted. Progress was saved - run the same command again to resume.")
        raise SystemExit(130)
