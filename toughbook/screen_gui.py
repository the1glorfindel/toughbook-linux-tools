"""Qt touchscreen calibration and recovery for KDE Wayland. SPDX-License-Identifier: MIT"""
import json
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QThread, QTimer, Qt, QEvent, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QInputDevice
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialog, QFileDialog, QListWidget, QMessageBox, QComboBox)

from . import screen
from .affine import TARGETS, fit, compose, from_kwin, to_kwin
from .common import ToolError, backup_path, check_model, choose, load_json, save_json, state_dir, touch_devices


class _Job(QThread):
    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn
        self.value = None
        self.error = None

    def run(self):
        try:
            self.value = self.fn()
        except Exception as exc:
            self.error = str(exc)


class _Targets(QDialog):
    measured = Signal(object)
    accepted_result = Signal()
    cancelled = Signal()

    def __init__(self, expected, parent=None):
        super().__init__(parent)
        self.expected = tuple(expected)
        self.samples = []
        self.ready = False
        self.preview = False
        self._closing = False
        self._active_touch = None
        self._stable = 0
        self._last_size = None
        self._checks = 0
        self.message = 'Preparing full-screen touch targets…'
        self.setWindowTitle('Toughbook touch calibration')
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.keep = QPushButton('Keep calibration', self)
        self.keep.clicked.connect(self.accepted_result)
        self.keep.hide()
        self.restore = QPushButton('Restore previous calibration', self)
        self.restore.clicked.connect(self.cancelled)
        self.restore.hide()
        self.showFullScreen()
        QTimer.singleShot(100, self._check_size)

    def _check_size(self):
        if self._closing:
            return
        size = (self.width(), self.height())
        self._stable = self._stable + 1 if size == self._last_size else 0
        self._last_size = size
        self._checks += 1
        if size == self.expected and self._stable >= 5:
            self.ready = True
            self.message = 'Touch each red cross with a finger. Escape restores the previous setting.'
            self.update()
        elif self._checks >= 100:
            self.message = 'Full-screen size differs from the internal display. Check scale and output settings.'
            self.update()
            self.cancelled.emit()
        else:
            QTimer.singleShot(100, self._check_size)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.ready and (self.width(), self.height()) != self.expected:
            self.ready = False
            self.samples.clear()
            self.message = 'Display size changed. Restoring the previous calibration…'
            self.cancelled.emit()
        self._place_buttons()

    def _place_buttons(self):
        y = max(0, self.height() - 76)
        self.keep.setGeometry(max(8, self.width() // 2 - 240), y, 225, 56)
        self.restore.setGeometry(max(8, self.width() // 2 + 15), y, 225, 56)

    def event(self, event):
        if event.type() == QEvent.Type.TouchBegin:
            device = event.device()
            if device and device.type() == QInputDevice.DeviceType.TouchScreen and len(event.points()) == 1:
                self._active_touch = event.points()[0].id()
                event.accept()
                return True
        elif event.type() == QEvent.Type.TouchEnd:
            device = event.device()
            if (self._active_touch is not None and device and
                device.type() == QInputDevice.DeviceType.TouchScreen and len(event.points()) == 1 and
                event.points()[0].id() == self._active_touch):
                point = event.points()[0].position()
                self._active_touch = None
                self.record_sample(point.x(), point.y())
                event.accept()
                return True
        elif event.type() == QEvent.Type.TouchCancel:
            self._active_touch = None
            event.accept()
            return True
        return super().event(event)

    def record_sample(self, x, y):
        if not self.ready or self.preview or len(self.samples) >= len(TARGETS):
            return
        if not (0 <= x < self.width() and 0 <= y < self.height()):
            return
        self.samples.append((x / self.width(), y / self.height()))
        self.update()
        if len(self.samples) == len(TARGETS):
            self.ready = False
            self.message = 'Applying the calibration preview…'
            self.measured.emit(self.samples[:])

    def show_preview(self):
        self.preview = True
        self.message = 'Test finger accuracy at the center and corners. Keep or restore the previous setting.'
        self.keep.show()
        self.restore.show()
        self._place_buttons()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('white'))
        painter.setPen(QColor('black'))
        painter.drawText(24, 36, self.message)
        if self.ready and len(self.samples) < len(TARGETS):
            x, y = TARGETS[len(self.samples)]
            px, py = int(x * self.width()), int(y * self.height())
            painter.setPen(QPen(QColor('red'), 4))
            painter.drawLine(px - 20, py, px + 20, py)
            painter.drawLine(px, py - 20, px, py + 20)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.preview:
            self.accepted_result.emit()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if not self._closing:
            self.cancelled.emit()
            event.ignore()
            return
        super().closeEvent(event)

    def finish(self):
        self._closing = True
        self.close()


class ScreenPage(QWidget):
    log = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self._thread = None
        self._status_process = None
        self._dialog = None
        self._transaction = None
        self._cancel_pending = False
        layout = QVBoxLayout(self)
        title = QLabel('<h2>Finger touch</h2>Calibrate the CF-19 finger sensor on the internal display.')
        title.setWordWrap(True)
        layout.addWidget(title)
        self.status_label = QLabel('Checking touchscreen…')
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.device_combo = QComboBox()
        self.device_combo.setToolTip('Select the Wacom finger device shown by the status check.')
        layout.addWidget(self.device_combo)
        layout.addWidget(QLabel('Before calibrating: use only the internal display, normal orientation, and 100% scale.'))
        buttons = QHBoxLayout()
        self.start_button = QPushButton('Calibrate finger touch')
        self.start_button.clicked.connect(self.start)
        buttons.addWidget(self.start_button)
        self.refresh_button = QPushButton('Refresh status')
        self.refresh_button.clicked.connect(self.refresh)
        buttons.addWidget(self.refresh_button)
        layout.addLayout(buttons)
        layout.addWidget(QLabel('Saved calibration backups'))
        self.backups = QListWidget()
        layout.addWidget(self.backups)
        recovery = QHBoxLayout()
        self.restore_button = QPushButton('Restore selected backup')
        self.restore_button.clicked.connect(self.restore_selected)
        recovery.addWidget(self.restore_button)
        browse = QPushButton('Choose another backup…')
        browse.clicked.connect(self.restore_file)
        recovery.addWidget(browse)
        layout.addLayout(recovery)
        layout.addStretch()
        self._buttons = [self.start_button, self.refresh_button, self.restore_button, browse]
        self.refresh()

    def _set_busy(self, busy):
        self._busy = busy
        for button in self._buttons:
            button.setEnabled(not busy)
        self.busy_changed.emit(busy)

    def _run(self, fn, done, failed, mutation=True):
        thread = _Job(fn, self)
        def deliver():
            if mutation and self._thread is thread:
                self._thread = None
            if thread.error is not None:
                failed(thread.error)
            else:
                done(thread.value)
        thread.finished.connect(deliver)
        if mutation:
            self._thread = thread
        thread.start()

    def refresh(self):
        self.backups.clear()
        for path in sorted(state_dir(create=False).glob('screen-*.json'), reverse=True):
            try:
                data = load_json(path, 'screen')
                self.backups.addItem(f'{path.name} — {data.get("status", "unknown")}')
                self.backups.item(self.backups.count() - 1).setData(Qt.ItemDataRole.UserRole, str(path))
            except (ValueError, OSError, KeyError):
                continue
        if self._busy or (self._status_process and self._status_process.state() != QProcess.ProcessState.NotRunning):
            return
        process = QProcess(self)
        self._status_process = process
        process.setProgram(sys.executable)
        process.setArguments([str(Path(__file__).resolve().parents[1] / 'calibrate-screen.py'), '--status'])
        def finished(code, _status):
            output = bytes(process.readAllStandardOutput()).decode(errors='replace')
            error = bytes(process.readAllStandardError()).decode(errors='replace').strip()
            if code == 0:
                try:
                    data = json.loads(output)
                    self.status_label.setText(f'{data["backend"].upper()} Wayland · {len(data["devices"])} eligible finger device(s)')
                    self.device_combo.clear()
                    for device in data['devices']:
                        self.device_combo.addItem(device['event'], device['event'])
                except (ValueError, KeyError, TypeError) as exc:
                    self.status_label.setText(f'Could not read touchscreen status: {exc}')
            else:
                self.status_label.setText(f'Unavailable: {error or output.strip()}')
            self._status_process = None
            process.deleteLater()
        process.finished.connect(finished)
        process.start()

    def start(self):
        if self._busy:
            return
        self._set_busy(True)
        self._cancel_pending = False
        self.log.emit('Checking the internal display and finger device.')
        selected = self.device_combo.currentData()
        def prepare():
            check_model()
            if screen.backend_name() != 'kde':
                raise ToolError('The graphical calibration page currently supports KDE Wayland.')
            output, width, height = screen.layout('kde')
            device = choose(touch_devices(), 'event', selected)
            kwin = screen.KWin(device)
            previous = kwin.get()
            old = from_kwin(previous['matrix'])
            path = backup_path('screen')
            data = {'kind': 'screen', 'backend': 'kde', 'identity': device['identity'],
                    'previous': previous, 'status': 'measuring', 'session': ''}
            save_json(path, data)
            return {'output': output, 'size': (width, height), 'device': device,
                    'previous': previous, 'old': old, 'path': path, 'data': data, 'changed': False}
        self._run(prepare, self._prepared, self._failure)

    def _prepared(self, transaction):
        self._transaction = transaction
        if self._cancel_pending:
            self._rollback()
            return
        self.log.emit(f'Calibration backup: {transaction["path"]}')
        dialog = _Targets(transaction['size'], self)
        self._dialog = dialog
        dialog.measured.connect(self._measured)
        dialog.cancelled.connect(self._rollback)
        dialog.accepted_result.connect(self._keep)

    def _measured(self, samples):
        tx = self._transaction
        try:
            correction, error = fit(samples, *tx['size'])
            matrix = compose(correction, tx['old'])
            tx['data'].update(matrix=matrix, fit_error_pixels=error,
                              size=list(tx['size']), status='candidate')
            save_json(tx['path'], tx['data'])
            tx['changed'] = True
        except Exception as exc:
            self._failure(str(exc))
            return
        def apply():
            screen.KWin(tx['device']).set(to_kwin(matrix), tx['output'])
            return True
        self._run(apply, self._applied, self._apply_failed)

    def _applied(self, _):
        self.log.emit('Calibration preview applied; check finger accuracy.')
        if self._cancel_pending:
            self._rollback()
        elif self._dialog:
            self._dialog.show_preview()

    def _apply_failed(self, error):
        self.log.emit(f'Could not apply calibration: {error}')
        self._rollback()

    def _keep(self):
        tx = self._transaction
        if not tx or not self._dialog or not self._dialog.preview:
            return
        tx['data']['status'] = 'accepted'
        try:
            save_json(tx['path'], tx['data'])
        except Exception as exc:
            self.log.emit(f'Could not save acceptance: {exc}; restoring the previous calibration.')
            self._rollback()
            return
        self.log.emit('Calibration saved by KWin.')
        self._finish()

    def _rollback(self):
        if not self._busy:
            return
        self._cancel_pending = True
        tx = self._transaction
        if tx is None:
            return
        if self._thread and self._thread.isRunning():
            return
        if not tx['changed']:
            try:
                tx['data']['status'] = 'cancelled'
                save_json(tx['path'], tx['data'])
            except Exception as exc:
                self.log.emit(f'Could not update backup status: {exc}')
            self._finish()
            return
        def restore():
            screen.KWin(tx['device']).restore(tx['previous'])
            tx['data']['status'] = 'cancelled'
            save_json(tx['path'], tx['data'])
            return True
        self._run(restore, lambda _: (self.log.emit('Previous calibration restored.'), self._finish()),
                  lambda error: self._failure(f'Recovery needs attention: {error}. Backup: {tx["path"]}'))

    def cancel(self):
        if self._status_process and self._status_process.state() != QProcess.ProcessState.NotRunning:
            self._status_process.kill()
        self._rollback()

    def has_background_work(self):
        return bool(self._status_process and self._status_process.state() != QProcess.ProcessState.NotRunning)

    def _failure(self, error):
        self.log.emit(error)
        self.status_label.setText(error)
        self._finish()

    def _finish(self):
        if self._dialog:
            self._dialog.finish()
            self._dialog.deleteLater()
            self._dialog = None
        self._transaction = None
        self._cancel_pending = False
        self._set_busy(False)
        self.refresh()

    def restore_selected(self):
        item = self.backups.currentItem()
        if item:
            self._restore(Path(item.data(Qt.ItemDataRole.UserRole)))

    def restore_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose calibration backup',
                str(state_dir(create=False)), 'JSON backups (*.json)')
        if path:
            self._restore(Path(path))

    def _restore(self, path):
        if self._busy:
            return
        if QMessageBox.question(self, 'Restore calibration',
                f'Restore the previous display mapping recorded in {path.name}?') != QMessageBox.StandardButton.Yes:
            return
        self._set_busy(True)
        self.log.emit(f'Restoring calibration from {path}')
        self._run(lambda: screen.restore_backup(path),
                  lambda _: (self.log.emit('Calibration restored.'), self._set_busy(False), self.refresh()),
                  lambda error: (self.log.emit(f'Restore failed: {error}'), self._set_busy(False)))

    def closeEvent(self, event):
        if self._busy:
            self._rollback()
            event.ignore()
            return
        super().closeEvent(event)
