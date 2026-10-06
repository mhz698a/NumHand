import unittest
from pathlib import Path

from sysmove import (
    build_destination_plan,
    numbering_format,
    remove_standard_numbering,
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

    def test_destination_plan_preserves_existing_order_and_appends_selected(self):
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

    def test_destination_plan_can_preserve_selected_numbering(self):
        existing = [Path("001. existing.txt")]
        selected = [Path("02. selected.txt")]

        plan = build_destination_plan(existing, selected, False)

        self.assertEqual(
            plan[-1][1],
            "02. 02. selected.txt",
        )


if __name__ == "__main__":
    unittest.main()
