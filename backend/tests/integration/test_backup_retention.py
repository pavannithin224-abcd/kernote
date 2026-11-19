"""Backups must not grow without bound, and must never prune an undo."""

from __future__ import annotations

from kernote.db import backup


def _make(directory, names):
    for n in names:
        (directory / n).write_bytes(b"x")


def test_keeps_the_newest_routine_snapshots(tmp_path):
    names = [f"kernote-20260101-0000{i:02d}.db" for i in range(30)]
    _make(tmp_path, names)
    removed = backup.prune(tmp_path, keep=20)
    left = sorted(p.name for p in tmp_path.iterdir())
    assert len(removed) == 10
    assert left == names[10:]  # the 10 oldest went, the newest 20 stayed


def test_safety_snapshots_are_never_pruned(tmp_path):
    safety = ["pre-restore-20250101-000000.db", "kernote-before-remove-20250101-000000.db"]
    _make(tmp_path, safety + [f"kernote-20260101-0000{i:02d}.db" for i in range(25)])
    backup.prune(tmp_path, keep=5)
    for name in safety:
        assert (tmp_path / name).exists(), name


def test_unrelated_files_are_left_alone(tmp_path):
    _make(tmp_path, ["notes.txt", "kernote-20260101-000000.db.bak", "kernote.db"])
    assert backup.prune(tmp_path, keep=0) == []
    assert len(list(tmp_path.iterdir())) == 3


def test_nothing_to_prune_under_the_limit(tmp_path):
    _make(tmp_path, ["kernote-20260101-000001.db", "kernote-20260101-000002.db"])
    assert backup.prune(tmp_path, keep=20) == []


def test_a_user_chosen_path_is_never_pruned(client, tmp_path):
    chosen = tmp_path / "mine"
    chosen.mkdir()
    _make(chosen, [f"kernote-20260101-0000{i:02d}.db" for i in range(30)])
    r = client.post("/api/v1/backup", json={"path": str(chosen / "my-backup.db")})
    assert r.status_code == 200
    assert len(list(chosen.iterdir())) == 31  # untouched: 30 + the new file
