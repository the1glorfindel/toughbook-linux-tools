"""Graphical audio repair page for the unified Toughbook Tools application."""
from __future__ import annotations

import json
import threading

from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QTextEdit,
                               QVBoxLayout, QWidget)

from . import audio
from .common import load_json, state_dir


class _AudioWorker(QThread):
    """Execute one backend operation away from the GUI thread."""

    log = Signal(str)
    prompt_requested = Signal(str, object, object)
    operation_done = Signal(object, object)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.cancel_event = threading.Event()

    def confirm(self, message):
        answered = threading.Event()
        answer = {'yes': False}
        self.prompt_requested.emit(message, answer, answered)
        while not answered.wait(.1):
            if self.cancel_event.is_set():
                return False
        return bool(answer['yes'])

    def run(self):
        try:
            result = self.operation(self)
            self.operation_done.emit(result, None)
        except Exception as exc:
            self.operation_done.emit(None, exc)


class AudioPage(QWidget):
    """Status, repair, and backup restoration controls for CF-19 audio."""

    log = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._worker = None
        self._active_prompt = None
        self._close_pending = False
        self._cancelable = False
        self._devices = []

        self.status_label = QLabel('Check audio status to find supported devices and saved repairs.')
        self.status_label.setWordWrap(True)
        self.device_combo = QComboBox()
        self.backup_combo = QComboBox()
        self.status_button = QPushButton('Refresh status')
        self.repair_button = QPushButton('Repair selected device')
        self.restore_button = QPushButton('Restore selected backup')
        self.browse_button = QPushButton('Choose backup file…')
        self.cancel_button = QPushButton('Cancel operation')
        self.cancel_button.setEnabled(False)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText('Audio status and operation messages appear here.')

        form = QFormLayout()
        form.addRow('Supported audio device', self.device_combo)
        form.addRow('Saved backup', self.backup_combo)
        actions = QHBoxLayout()
        for button in (self.status_button, self.repair_button, self.restore_button,
                       self.browse_button, self.cancel_button):
            actions.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addWidget(self.output, 1)

        self.status_button.clicked.connect(self.refresh_status)
        self.repair_button.clicked.connect(self.repair_selected)
        self.restore_button.clicked.connect(self.restore_selected)
        self.browse_button.clicked.connect(self.choose_backup)
        self.cancel_button.clicked.connect(self.cancel_operation)
        self.refresh_backups()

    def _append_log(self, message):
        self.output.append(str(message))
        self.log.emit(str(message))

    def _set_busy(self, busy):
        self.status_button.setEnabled(not busy)
        self.repair_button.setEnabled(not busy and self.device_combo.count() > 0)
        self.restore_button.setEnabled(not busy and self.backup_combo.count() > 0)
        self.browse_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.device_combo.setEnabled(not busy)
        self.backup_combo.setEnabled(not busy)
        self.busy_changed.emit(busy)

    def _start(self, operation, cancelable=True):
        if self._thread is not None:
            return
        worker = _AudioWorker(operation, self)
        worker.log.connect(self._append_log)
        worker.prompt_requested.connect(self._answer_prompt)
        worker.operation_done.connect(self._operation_finished)
        worker.finished.connect(self._thread_finished)
        self._thread, self._worker = worker, worker
        self._cancelable = cancelable
        self._set_busy(True)
        self.cancel_button.setEnabled(cancelable)
        worker.start()

    @Slot(str, object, object)
    def _answer_prompt(self, message, answer, answered):
        box = QMessageBox(self)
        box.setWindowTitle('Audio repair confirmation')
        box.setText(message)
        box.setIcon(QMessageBox.Question)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        self._active_prompt = box
        answer['yes'] = box.exec() == QMessageBox.Yes
        self._active_prompt = None
        answered.set()

    def _operation_finished(self, result, error):
        if error is not None:
            self.status_label.setText(f'Audio operation failed: {error}')
            self._append_log(str(error))
        elif isinstance(result, tuple) and len(result) == 2:
            self._show_status(*result)
        elif result is not None:
            self._append_log(f'Operation finished (result {result}).')
        self.refresh_backups()

    def _thread_finished(self):
        worker = self._worker
        self._thread = self._worker = None
        cancelable, self._cancelable = self._cancelable, False
        # QThread is parented to this page. Keep that ownership intact until
        # the page is destroyed; separately scheduling its deletion here can
        # leave a deferred delete event racing the QWidget parent teardown.
        self._set_busy(False)
        if cancelable and worker is not None and worker.cancel_event.is_set():
            self._append_log('Cancellation requested; backend recovery has finished.')
        if self._close_pending:
            self.close()

    @Slot()
    def refresh_status(self):
        if self._thread is not None:
            return

        def read_status(_worker):
            found = audio.cards()
            marker = state_dir(create=False) / 'audio-installed.json'
            installation = load_json(marker) if marker.exists() else None
            return found, installation

        self._start(read_status, cancelable=False)

    def _show_status(self, found, installation):
        try:
            self._devices = found
            self.device_combo.clear()
            for item in found:
                self.device_combo.addItem(f"{item['name']} (card {item['index']})", item)
            self.repair_button.setEnabled(bool(found) and self._thread is None)
            self.status_label.setText(
                f'{len(found)} supported device(s) found. ' +
                ('A saved installation marker is present.' if installation else 'No installation marker found.'))
            self._append_log(json.dumps({'devices': found, 'installation': installation}, indent=2))
        except Exception as exc:
            self.status_label.setText(f'Could not read audio status: {exc}')
            self._append_log(str(exc))

    def refresh_backups(self):
        selected = self.backup_combo.currentData()
        self.backup_combo.clear()
        folder = state_dir(create=False)
        if folder.exists():
            for path in sorted(folder.glob('audio-*.json'), reverse=True):
                if path.name == 'audio-installed.json':
                    continue
                self.backup_combo.addItem(path.name, str(path))
        if selected:
            index = self.backup_combo.findData(selected)
            if index >= 0:
                self.backup_combo.setCurrentIndex(index)
        self.restore_button.setEnabled(self.backup_combo.count() > 0 and self._thread is None)

    @Slot()
    def repair_selected(self):
        device = self.device_combo.currentData()
        if device is None:
            self._append_log('Refresh status and select a supported audio device first.')
            return

        def operation(worker):
            return audio.repair(device, confirm_fn=worker.confirm, start_fn=worker.confirm,
                                cancel_event=worker.cancel_event, log_fn=worker.log.emit)

        self._start(operation)

    def _restore_path(self, path):
        answer = QMessageBox.question(
            self, 'Restore audio backup',
            f'Restore the saved audio configuration from:\n{path}?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        self._start(lambda worker: audio.restore_backup(path, log_fn=worker.log.emit),
                    cancelable=False)

    @Slot()
    def restore_selected(self):
        path = self.backup_combo.currentData()
        if path:
            self._restore_path(path)

    @Slot()
    def choose_backup(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Choose audio backup', str(state_dir(create=False)),
            'Audio backup JSON (*.json);;All files (*)')
        if path:
            self._restore_path(path)

    @Slot()
    def cancel_operation(self):
        if self._worker is None or not self._cancelable:
            return
        self._worker.cancel_event.set()
        if self._active_prompt is not None:
            self._active_prompt.reject()
        self.cancel_button.setEnabled(False)
        self._append_log('Cancellation requested. The active repair will restore its saved configuration.')

    def closeEvent(self, event):
        if self._thread is not None:
            self._close_pending = True
            if self._cancelable:
                self.cancel_operation()
            event.ignore()
            return
        event.accept()
