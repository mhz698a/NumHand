import unittest
from pathlib import Path

from sysmove import (
    build_destination_plan,
    build_direct_move_plan,
    build_source_plan,
    detect_folder_numbering,
    numbering_format,
    remove_standard_numbering,\n    build_trash_move_plan,
)


class SysMoveTests(unittest.TestCase):

    def test_remove_standard_numbering_only_matches_two_or_three_digits(self):
        self.assertEqual(
            remove_standard_numbering("01. first.txt"),
            "first.txt",
        )
        self.assertEqual(
            remove_standard_numbering("000. third.txt"),
            "third.txt",
        )
        self.assertEqual(
            remove_standard_numbering("1. first.txt"),
            "1. first.txt",
        )
        self.assertEqual(
            remove_standard_numbering("0001. fourth.txt"),
            "0001. fourth.txt",
        )

    def test_numbering_format_matches_application_convention(self):
        self.assertEqual(numbering_format(99), "{:02d}. ")
        self.assertEqual(numbering_format(100), "{:03d}. ")
        self.assertEqual(numbering_format(1000), "{:04d}. ")

    def test_destination_plan_renumbers_existing_and_appends_selected(self):
        existing = [
            Path("002. existing-two.txt"),
            Path("001. existing-one.txt"),
        ]
        selected = [
            Path("07. selected-seven.txt"),
            Path("08. selected-eight.txt"),
        ]

        plan = build_destination_plan(existing, selected, True)

        self.assertEqual(
            [final_name for _, final_name in plan],
            [
                "01. existing-one.txt",
                "02. existing-two.txt",
                "03. selected-seven.txt",
                "04. selected-eight.txt",
            ],
        )

    def test_destination_plan_can_preserve_selected_numbering_when_reorganizing(self):
        existing = [Path("001. existing.txt")]
        selected = [Path("02. selected.txt")]

        plan = build_destination_plan(existing, selected, False)

        self.assertEqual(
            plan[-1][1],
            "02. 02. selected.txt",
        )

    def test_direct_move_plan_does_not_rename_existing_destination_files(self):
        selected = [
            Path("07. selected-seven.txt"),
            Path("08. selected-eight.txt"),
        ]

        plan = build_direct_move_plan(selected, True)

        self.assertEqual(
            [final_name for _, final_name in plan],
            [
                "selected-seven.txt",
                "selected-eight.txt",
            ],
        )

    def test_trash_move_plan_removes_selected_numbering(self):
        selected = [Path("07. selected.txt"), Path("08. other.txt")]

        plan = build_trash_move_plan(selected, True)

        self.assertEqual(
            [final_name for _, final_name in plan],
            ["selected.txt", "other.txt"],
        )

    def test_trash_move_plan_can_keep_selected_numbering(self):
        selected = [Path("07. selected.txt")]

        plan = build_trash_move_plan(selected, False)

        self.assertEqual(
            plan,
            [(Path("07. selected.txt"), "07. selected.txt")],
        )

    def test_direct_move_plan_can_keep_selected_numbering(self):
        selected = [Path("07. selected.txt")]

        plan = build_direct_move_plan(selected, False)

        self.assertEqual(
            plan,
            [(Path("07. selected.txt"), "07. selected.txt")],
        )

    def test_detect_folder_numbering(self):
        self.assertEqual(
            detect_folder_numbering([Path("01. first.txt"), Path("02. second.txt")]),
            "00. ",
        )
        self.assertEqual(
            detect_folder_numbering([Path("001. first.txt"), Path("002. second.txt")]),
            "000. ",
        )
        self.assertEqual(
            detect_folder_numbering([Path("first.txt"), Path("second.txt")]),
            "sin numerar",
        )
        self.assertEqual(
            detect_folder_numbering([Path("01. first.txt"), Path("second.txt")]),
            "mixta",
        )

    def test_source_plan_closes_gaps_after_selected_files_are_removed(self):
        remaining = [
            Path("042. forty-two.txt"),
            Path("001. first.txt"),
            Path("040. forty.txt"),
            Path("039. thirty-nine.txt"),
        ]

        plan = build_source_plan(remaining)

        self.assertEqual(
            [final_name for _, final_name in plan],
            [
                "01. first.txt",
                "02. thirty-nine.txt",
                "03. forty.txt",
                "04. forty-two.txt",
            ],
        )

    def test_source_plan_removes_existing_standard_prefix_before_renumbering(self):
        remaining = [
            Path("12. twelve.txt"),
            Path("003. three.txt"),
        ]

        plan = build_source_plan(remaining)

        self.assertEqual(
            [final_name for _, final_name in plan],
            [
                "01. three.txt",
                "02. twelve.txt",
            ],
        )


if __name__ == "__main__":
    unittest.main()
