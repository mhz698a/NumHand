import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sys_engine_dest import build_apply_order_listfiles


class ApplyOrderPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_entry(self, filename, clean_name):
        path = self.folder / filename
        path.write_text("unchanged content", encoding="utf-8")
        entry = type("FileEntryStub", (), {})()
        entry.path = path
        entry.clean_name = clean_name
        return entry

    def test_plan_includes_only_files_whose_final_names_change(self):
        unchanged = self.make_entry("01. alpha.txt", "alpha.txt")
        renamed = self.make_entry("02. old.txt", "new.txt")
        unnumbered = self.make_entry("notes.txt", "notes.txt")

        plan = build_apply_order_listfiles(
            [unchanged, renamed, unnumbered], self.folder, "{:02d}. "
        )

        self.assertEqual([item["file"] for item in plan], [renamed, unnumbered])
        self.assertEqual(plan[0]["final_path"].name, "02. new.txt")
        self.assertEqual(plan[1]["final_path"].name, "03. notes.txt")
        self.assertTrue(unchanged.path.exists())
        self.assertEqual(unchanged.path.read_text(encoding="utf-8"), "unchanged content")


if __name__ == "__main__":
    unittest.main()
