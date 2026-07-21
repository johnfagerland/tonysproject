"""Validation-loop tests for the archiver.

Covers the three required scenarios:
1. Interrupt mid-transfer, rerun, verify resume + no duplicate index entries.
2. Corrupt a destination byte, verify the hash check catches and re-copies it.
3. Large-file streaming: memory stays flat (hashing reads in chunks, never the
   whole file).

Run from the archiver/ folder:  python -m pytest tests/ -v
"""

import csv
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def archiver(tmp_path, monkeypatch):
    """Import archiver with its index redirected into the temp dir."""
    monkeypatch.setenv("ARCHIVER_INDEX_DIR", str(tmp_path / "index"))
    for mod in ("archiver",):
        sys.modules.pop(mod, None)
    import archiver as mod
    return mod


def make_project(root: Path, n_files: int = 6) -> Path:
    project = root / "Henderson_2026"
    (project / "footage").mkdir(parents=True)
    (project / "exports").mkdir()
    for i in range(n_files):
        sub = "footage" if i % 2 == 0 else "exports"
        (project / sub / f"file with spaces #{i}.mov").write_bytes(
            os.urandom(1024) * (i + 1)
        )
    (project / "footage" / ".DS_Store").write_bytes(b"junk")  # must be skipped
    return project


def run_archive(archiver, project, dest, *extra):
    return archiver.main([
        "archive", str(project), str(dest), "--yes", "--drive-label", "TEST_DRIVE", *extra,
    ])


def test_full_archive_verifies_and_indexes(archiver, tmp_path):
    project = make_project(tmp_path)
    dest = tmp_path / "drive"
    dest.mkdir()
    assert run_archive(archiver, project, dest) == 0

    manifest = json.loads((dest / "Henderson_2026_manifest.json").read_text(encoding="utf-8"))
    assert manifest["complete"] is True
    assert len(manifest["files"]) == 6
    assert all(e["verified"] for e in manifest["files"].values())
    assert ".DS_Store" not in " ".join(manifest["files"])

    with open(archiver.INDEX_CSV, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["project"] == "Henderson_2026"
    assert rows[0]["drive_label"] == "TEST_DRIVE"

    # Local copy of the manifest exists too
    assert list(archiver.MANIFESTS_DIR.glob("Henderson_2026__TEST_DRIVE*")), "local manifest missing"


def test_interrupted_transfer_resumes_without_recopy_or_duplicate_index(archiver, tmp_path, monkeypatch):
    project = make_project(tmp_path)
    dest = tmp_path / "drive"
    dest.mkdir()

    # Flush the manifest after every file so the simulated crash behaves like a
    # real long transfer (the default flushes every 25 files).
    monkeypatch.setattr(archiver, "MANIFEST_FLUSH_INTERVAL", 1)

    # Simulate a crash: kill the process after 3 files have copied.
    real_copy = archiver.copy_and_hash
    calls = {"n": 0}

    def dying_copy(src, dst):
        if calls["n"] >= 3:
            raise KeyboardInterrupt
        calls["n"] += 1
        return real_copy(src, dst)

    monkeypatch.setattr(archiver, "copy_and_hash", dying_copy)
    with pytest.raises(KeyboardInterrupt):
        run_archive(archiver, project, dest)

    copied_files = [p for p in sorted((dest / "Henderson_2026").rglob("*")) if p.is_file()]
    assert len(copied_files) == 3
    manifest = json.loads((dest / "Henderson_2026_manifest.json").read_text(encoding="utf-8"))
    assert sum(1 for e in manifest["files"].values() if e.get("verified")) == 3

    # Rerun for real: the 3 verified files must be skipped, the rest copied.
    copies = {"n": 0}

    def counting_copy(src, dst):
        copies["n"] += 1
        return real_copy(src, dst)

    monkeypatch.setattr(archiver, "copy_and_hash", counting_copy)
    assert run_archive(archiver, project, dest) == 0
    assert copies["n"] == 3, "resume should copy only the 3 remaining files"

    # And rerunning a third time copies nothing and does not duplicate the index row.
    copies["n"] = 0
    assert run_archive(archiver, project, dest) == 0
    assert copies["n"] == 0
    with open(archiver.INDEX_CSV, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1, "re-running must not create duplicate index entries"


def test_corrupted_destination_byte_is_caught_and_recopied(archiver, tmp_path):
    project = make_project(tmp_path)
    dest = tmp_path / "drive"
    dest.mkdir()
    assert run_archive(archiver, project, dest) == 0

    # Flip one byte in an archived file and invalidate its manifest entry the way
    # bit-rot would look on a re-run (size same, content different).
    victim = next(p for p in (dest / "Henderson_2026").rglob("*.mov"))
    data = bytearray(victim.read_bytes())
    data[10] ^= 0xFF
    victim.write_bytes(bytes(data))

    rel = victim.relative_to(dest / "Henderson_2026").as_posix()
    manifest_path = dest / "Henderson_2026_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # cleanup must detect the corruption and refuse to delete the source
    assert archiver.hash_file(victim) != manifest["files"][rel]["xxh64"]
    result = archiver.main(["cleanup", str(project), str(dest), "--yes"])
    assert result == 1
    assert project.exists(), "source must never be deleted when the archive is corrupt"

    # Re-archiving with --verify re-hashes archived copies, catches the bad
    # byte, and re-copies that file.
    assert run_archive(archiver, project, dest, "--verify") == 0
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert archiver.hash_file(victim) == manifest["files"][rel]["xxh64"]

    # Now cleanup succeeds and deletes the source.
    assert archiver.main(["cleanup", str(project), str(dest), "--yes"]) == 0
    assert not project.exists()


def test_hashing_streams_in_chunks_memory_stays_flat(archiver, tmp_path):
    """A sparse multi-GB file must hash without being read into RAM at once.
    We verify the read pattern: no single read() call larger than CHUNK_SIZE."""
    big = tmp_path / "big.bin"
    with open(big, "wb") as f:
        f.seek(2 * 1024 * 1024 * 1024)  # 2 GB sparse
        f.write(b"end")

    max_read = 0
    real_open = open

    class SpyFile:
        def __init__(self, f):
            self._f = f

        def read(self, n=-1):
            nonlocal max_read
            data = self._f.read(n)
            max_read = max(max_read, len(data))
            return data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self._f.close()

    import builtins
    orig = builtins.open

    def spy_open(path, mode="r", *a, **k):
        f = orig(path, mode, *a, **k)
        if "b" in mode and "r" in mode and str(path) == str(big):
            return SpyFile(f)
        return f

    builtins.open = spy_open
    try:
        digest = archiver.hash_file(big)
    finally:
        builtins.open = orig

    assert digest
    assert 0 < max_read <= archiver.CHUNK_SIZE, (
        f"hashing read {max_read} bytes in one call - not streaming"
    )


def test_find_answers_which_drive(archiver, tmp_path, capsys):
    project = make_project(tmp_path)
    dest = tmp_path / "drive"
    dest.mkdir()
    run_archive(archiver, project, dest)
    assert archiver.main(["find", "henderson"]) == 0
    out = capsys.readouterr().out
    assert "Henderson_2026" in out
    assert "TEST_DRIVE" in out
    assert archiver.main(["find", "no-such-project"]) == 1
