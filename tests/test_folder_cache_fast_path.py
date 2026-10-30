import os

import pytest

import sys_folder_cache


def test_get_cached_files_uses_saved_listing_without_scanning(tmp_path, monkeypatch):
    folder = tmp_path / "music"
    folder.mkdir()
    expected = [folder / "track2.mp3", folder / "track10.mp3"]
    for path in expected:
        path.write_bytes(b"audio")

    cache = sys_folder_cache.FolderCache(tmp_path / "cache.db")
    cache.list_files(folder)

    def unexpected_scan(*args, **kwargs):
        pytest.fail("The cached-listing fast path must not enumerate the folder")

    monkeypatch.setattr(sys_folder_cache.os, "scandir", unexpected_scan)

    cached = cache.get_cached_files(folder)
    assert {path.name for path in cached} == {path.name for path in expected}


def test_get_cached_files_invalidates_when_directory_timestamp_changes(tmp_path):
    folder = tmp_path / "music"
    folder.mkdir()
    (folder / "track.mp3").write_bytes(b"audio")

    cache = sys_folder_cache.FolderCache(tmp_path / "cache.db")
    cache.list_files(folder)
    assert cache.get_cached_files(folder) is not None

    info = folder.stat()
    os_mtime_ns = info.st_mtime_ns + 1_000_000_000
    os.utime(folder, ns=(info.st_atime_ns, os_mtime_ns))

    assert cache.get_cached_files(folder) is None


def test_sync_folder_persists_known_paths_without_scanning(tmp_path, monkeypatch):
    folder = tmp_path / "music"
    folder.mkdir()
    paths = [folder / "track2.mp3", folder / "track10.mp3"]
    for path in paths:
        path.write_bytes(b"audio")

    cache = sys_folder_cache.FolderCache(tmp_path / "cache.db")

    def unexpected_scan(*args, **kwargs):
        pytest.fail("Known-path cache updates must not enumerate the folder")

    monkeypatch.setattr(sys_folder_cache.os, "scandir", unexpected_scan)

    progress = []
    updated = cache.sync_folder(
        folder,
        files=paths,
        progress_callback=lambda current, total, path: progress.append(
            (current, total, path.name)
        ),
    )
    assert {path.name for path in updated} == {path.name for path in paths}
    assert [item[2] for item in progress] == ["track2.mp3", "track10.mp3"]
    assert all(total == 2 for _, total, _ in progress)
    assert {path.name for path in cache.get_cached_files(folder)} == {
        path.name for path in paths
    }


def test_load_folder_keeps_intentional_50ms_delay_per_file(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import sysutils

    folder = tmp_path / "music"
    folder.mkdir()
    for name in ("track1.mp3", "track2.mp3", "track3.mp3"):
        (folder / name).write_bytes(b"audio")

    cache = sys_folder_cache.FolderCache(tmp_path / "cache.db")
    cache.list_files(folder)

    delays = []
    monkeypatch.setattr(
        sysutils,
        "QThread",
        SimpleNamespace(msleep=delays.append),
    )

    file_utils = SimpleNamespace(
        folder_cache=cache,
        recover_backup_sync=lambda path: True,
    )
    task = sysutils.LoadFolderTask(folder, file_utils)
    task.run()

    assert delays == [50, 50, 50]
