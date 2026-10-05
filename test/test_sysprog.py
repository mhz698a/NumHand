import pytest
from PyQt6.QtCore import Qt
from sysprog import DualProgressDialog
from sysutils import WorkerSignals


def test_dual_progress_dialog_initialization(qtbot):
    dialog = DualProgressDialog(title="Test Dialog")
    qtbot.add_widget(dialog)

    assert dialog.windowTitle() == "Test Dialog"
    assert dialog.sub_bar.minimum() == 0
    assert dialog.sub_bar.maximum() == 0
    assert dialog.main_bar.minimum() == 0
    assert dialog.main_bar.maximum() == 0


def test_dual_progress_dialog_update_progress(qtbot):
    dialog = DualProgressDialog(title="Test Dialog")
    qtbot.add_widget(dialog)

    dialog.update_progress(
        sub_current=3,
        sub_total=10,
        sub_label="Calculando hash y respaldando 3/10: archivo.txt",
        main_current=1,
        main_total=4,
        main_label="Respaldo (Etapa 1 de 4)"
    )

    assert dialog.sub_bar.value() == 3
    assert dialog.sub_bar.maximum() == 10
    assert dialog.sub_label.text() == "Calculando hash y respaldando 3/10: archivo.txt"

    assert dialog.main_bar.value() == 1
    assert dialog.main_bar.maximum() == 4
    assert dialog.main_label.text() == "Respaldo (Etapa 1 de 4)"


def test_dual_progress_dialog_canceled_signal_on_button(qtbot):
    dialog = DualProgressDialog(title="Test Dialog")
    qtbot.add_widget(dialog)

    with qtbot.waitSignal(dialog.canceled, timeout=1000):
        qtbot.mouseClick(dialog.cancel_button, Qt.MouseButton.LeftButton)


def test_worker_signals_progress_emit(qtbot):
    signals = WorkerSignals()

    received_args = []

    def handle_progress(s_curr, s_tot, s_lbl, m_curr, m_tot, m_lbl):
        received_args.append((s_curr, s_tot, s_lbl, m_curr, m_tot, m_lbl))

    signals.progress.connect(handle_progress)

    signals.progress.emit(1, 5, "Sublabel", 2, 4, "Mainlabel")

    assert len(received_args) == 1
    assert received_args[0] == (1, 5, "Sublabel", 2, 4, "Mainlabel")
