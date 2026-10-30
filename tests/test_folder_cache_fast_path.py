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

    updated = cache.sync_folder(folder, files=paths)
    assert {path.name for path in updated} == {path.name for path in paths}
    assert {path.name for path in cache.get_cached_files(folder)} == {
        path.name for path in paths
    }
