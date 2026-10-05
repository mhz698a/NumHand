import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from sysprog import DualProgressDialog

app = QApplication.instance() or QApplication([])


class TestDualProgressDialog(unittest.TestCase):

    def setUp(self):
        self.dialog = DualProgressDialog("Test Dual Progress")

    def tearDown(self):
        self.dialog.close()

    def test_initial_state(self):
        self.assertEqual(self.dialog.windowTitle(), "Test Dual Progress")
        self.assertEqual(self.dialog.sub_bar.value(), 0)
        self.assertEqual(self.dialog.main_bar.value(), 0)

    def test_set_progress(self):
        self.dialog.set_progress(
            sub_current=5,
            sub_total=10,
            sub_message="Subtarea 5/10: archivo.txt",
            main_current=15,
            main_total=30,
            main_message="Etapa 1/3: Respaldo"
        )

        self.assertEqual(self.dialog.sub_bar.value(), 5)
        self.assertEqual(self.dialog.sub_bar.maximum(), 10)
        self.assertEqual(self.dialog.sub_label.text(), "Subtarea 5/10: archivo.txt")

        self.assertEqual(self.dialog.main_bar.value(), 15)
        self.assertEqual(self.dialog.main_bar.maximum(), 30)
        self.assertEqual(self.dialog.main_label.text(), "Etapa 1/3: Respaldo")

    def test_cancel_signal(self):
        canceled_emitted = []

        def on_canceled():
            canceled_emitted.append(True)

        self.dialog.canceled.connect(on_canceled)
        self.dialog.cancel_button.click()

        self.assertTrue(len(canceled_emitted) > 0)


if __name__ == "__main__":
    unittest.main()
