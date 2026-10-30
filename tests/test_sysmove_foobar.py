import os
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
import tempfile
import shutil

# Ensure repository root is in sys.path when running from tests/ directory
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from pyutils.foobar_helpers import (
    capture_foobar_file_move_state,
    restore_foobar_after_file_move,
)


class TestFoobarHelpers(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.source_dir = Path(self.temp_dir) / "source"
        self.dest_dir = Path(self.temp_dir) / "dest"
        self.source_dir.mkdir()
        self.dest_dir.mkdir()

        # Create dummy audio files
        self.file1 = self.source_dir / "01. track1.mp3"
        self.file2 = self.source_dir / "02. track2.mp3"
        self.file1.write_bytes(b"dummy mp3 1")
        self.file2.write_bytes(b"dummy mp3 2")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_capture_foobar_file_move_state_playing_match(self):
        mock_fb = MagicMock()
        mock_fb.playlists.return_value = [
            {"id": "p0", "title": "Default", "isCurrent": True}
        ]
        mock_fb.first_playlist_item_path.return_value = str(self.file1)
        mock_fb.player.return_value = {
            "player": {
                "playbackState": "playing",
                "activeItem": {"playlistId": "p0", "position": 10.5, "duration": 180.0},
                "volume": {"value": -3.0, "isMuted": False},
            }
        }
        mock_fb.current_path_playbackState.return_value = str(self.file1)
        mock_fb.add_playlist.return_value = {"id": "p_aux"}

        old_to_new = {str(self.file1.resolve()): str((self.dest_dir / "01. track1.mp3").resolve())}

        state = capture_foobar_file_move_state(
            mock_fb,
            old_to_new,
            source_folder=self.source_dir,
        )

        self.assertTrue(state["playback_affected"])
        self.assertTrue(state["playlist_matches_source_folder"])
        self.assertEqual(state["new_path"], str((self.dest_dir / "01. track1.mp3").resolve()))
        self.assertEqual(state["active_playlist_id"], "p0")
        mock_fb.stop.assert_called_once()

    def test_restore_foobar_after_file_move(self):
        # Create destination file so it exists
        dest_file = self.dest_dir / "01. track1.mp3"
        dest_file.write_bytes(b"dummy mp3 1")

        mock_fb = MagicMock()
        mock_fb.playlists.return_value = [
            {"id": "p0", "title": "Default", "isCurrent": True}
        ]

        state = {
            "fb_api": mock_fb,
            "active_playlist_id": "p0",
            "auxiliary_playlist_id": "p_aux",
            "auxiliary_playlist_title": "auxiliar",
            "playback_affected": True,
            "playing_path": str(self.file1.resolve()),
            "new_path": str(dest_file.resolve()),
            "saved_position": 10.5,
            "saved_duration": 180.0,
            "saved_playback_state": "playing",
            "saved_volume": -3.0,
            "saved_is_muted": False,
            "should_sync_source_playlist": True,
            "playback_state_captured": True,
            "timeout": 3.0,
        }
        mock_fb.timeout = 3.0

        restore_foobar_after_file_move(state, self.source_dir, successful=True)

        mock_fb.select_playlist.assert_called_with("p_aux")
        mock_fb.clear_playlist.assert_any_call("p_aux")
        mock_fb.add_playlist_items.assert_any_call("p_aux", [str(dest_file.resolve())])
        mock_fb.play_item_single.assert_called_with("p_aux", 0)
        mock_fb.set_position_single.assert_called_with(10.5)
        mock_fb.play.assert_called()


class TestMoveSelectedToTrash(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.source_dir = Path(self.temp_dir) / "source"
        self.trash_dir = Path(self.temp_dir) / "trash"
        self.source_dir.mkdir()
        self.trash_dir.mkdir()

        self.file1 = self.source_dir / "01. track1.mp3"
        self.file1.write_bytes(b"dummy mp3 1")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("sysmove.capture_foobar_file_move_state")
    @patch("sysmove.restore_foobar_after_file_move")
    @patch("sysmove.QMessageBox")
    @patch("sysmove.get_trash_folder")
    @patch("sysmove.syswall.get_locking_processes")
    def test_move_selected_to_trash_foobar_calls(
        self,
        mock_get_locking,
        mock_get_trash,
        mock_msgbox,
        mock_restore_foobar,
        mock_capture_foobar,
    ):
        from sysmove import move_selected_to_trash, MoveSelectedTask
        from PyQt6.QtWidgets import QMessageBox

        mock_get_trash.return_value = self.trash_dir
        mock_get_locking.return_value = []
        mock_msgbox.question.return_value = QMessageBox.StandardButton.Yes
        mock_msgbox.StandardButton = QMessageBox.StandardButton

        mock_file = MagicMock()
        mock_file.path = str(self.file1)

        mock_model = MagicMock()
        mock_model.checked_files.return_value = [mock_file]

        mock_parent = MagicMock()
        mock_parent.folder = str(self.source_dir)

        mock_capture_foobar.return_value = {"captured": True}

        with patch("sysmove.QThreadPool.globalInstance") as mock_pool, \
             patch("sysmove.DualProgressDialog"):

            # Run the QRunnable synchronously in this test. Foobar2000 capture
            # now belongs to the worker, not the UI callback.
            mock_pool.return_value.start.side_effect = lambda task: task.run()

            move_selected_to_trash(mock_parent, mock_model)

            # Verify omit_fb=True was passed to get_locking_processes
            mock_get_locking.assert_called_once_with([self.file1], omit_fb=True)

            # Verify capture_foobar_file_move_state runs inside MoveSelectedTask.
            mock_capture_foobar.assert_called_once()
            call_args = mock_capture_foobar.call_args
            old_to_new = call_args[0][1]
            self.assertIn(str(self.file1.resolve()), old_to_new)
            self.assertEqual(
                old_to_new[str(self.file1.resolve())],
                str((self.trash_dir / "track1.mp3").resolve())
            )


if __name__ == "__main__":
    unittest.main()
