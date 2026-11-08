"""Unified Qt application shell for Toughbook Tools."""
from datetime import datetime
from pathlib import Path
import sys
import json

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QPlainTextEdit, QStackedWidget, QVBoxLayout, QWidget, QFileDialog)

from .screen_gui import ScreenPage
from .audio_gui import AudioPage
from .buttons_gui import ButtonsPage


class MainWindow(QMainWindow):
    PAGES = [('Overview', 'overview'), ('Touchscreen', 'screen'), ('Audio', 'audio'), ('Tablet Buttons', 'buttons')]

    def __init__(self, page='overview'):
        super().__init__()
        self.setWindowTitle('Toughbook Tools')
        self.resize(920, 690)
        self.setMinimumSize(760, 600)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel('Toughbook Tools')
        title.setObjectName('title')
        header.addWidget(title)
        header.addStretch()
        self.copy_button = QPushButton('Copy output')
        self.save_button = QPushButton('Save output…')
        self.copy_button.clicked.connect(self.copy_output)
        self.save_button.clicked.connect(self.save_output)
        header.addWidget(self.copy_button)
        header.addWidget(self.save_button)
        layout.addLayout(header)

        self.nav = QHBoxLayout()
        self.nav_buttons = {}
        for name, key in self.PAGES:
            button = QPushButton(name)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, k=key: self.show_page(k))
            self.nav.addWidget(button)
            self.nav_buttons[key] = button
        layout.addLayout(self.nav)
        self.stack = QStackedWidget()
        self.pages = {}
        overview = self.make_overview()
        self.pages['overview'] = overview
        self.pages['screen'] = ScreenPage()
        self.pages['audio'] = AudioPage()
        self.pages['buttons'] = ButtonsPage()
        self.busy = {key: False for key in self.pages}
        self._close_pending = False
        self._allow_close = False
        for key in ('overview', 'screen', 'audio', 'buttons'):
            self.stack.addWidget(self.pages[key])
        layout.addWidget(self.stack, 1)

        self.output_toggle = QPushButton('Show troubleshooting output ▾')
        self.output_toggle.setCheckable(True)
        self.output_toggle.clicked.connect(self.toggle_output)
        layout.addWidget(self.output_toggle)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(5000)
        self.output.setPlaceholderText('Troubleshooting messages will appear here.')
        self.output.setFixedHeight(155)
        self.output.hide()
        layout.addWidget(self.output)
        self.setCentralWidget(root)
        for key in ('screen', 'audio', 'buttons'):
            self.pages[key].log.connect(self.log)
            self.pages[key].busy_changed.connect(lambda busy, k=key: self.set_busy(k, busy))
        self.log('Ready. Choose a tool to inspect or change its settings.')
        self.show_page(page if page in self.pages else 'overview')
        self.refresh_overview()
        self.setStyleSheet('''
            QWidget { font-size: 14px; }
            QLabel#title { font-size: 23px; font-weight: 650; }
            QPushButton { padding: 8px 13px; }
            QPushButton:checked { background: #315d85; color: white; }
            QFrame#card { background: palette(alternate-base); border: 1px solid palette(mid); border-radius: 8px; }
        ''')

    def make_overview(self):
        page = QWidget()
        col = QVBoxLayout(page)
        lead = QLabel('Configure your CF-19 touchscreen, audio routing, and tablet buttons.')
        lead.setWordWrap(True)
        lead.setStyleSheet('font-size: 18px;')
        col.addWidget(lead)
        self.overview_status = QLabel('Checking feature readiness…')
        self.overview_status.setWordWrap(True)
        col.addWidget(self.overview_status)
        refresh = QPushButton('Refresh overview status')
        refresh.clicked.connect(self.refresh_overview)
        col.addWidget(refresh)
        for heading, text, key in (
            ('Touchscreen', 'Inspect the touchscreen and calibrate its mapping and orientation.', 'screen'),
            ('Audio', 'Review audio devices and apply supported fixes with a backup.', 'audio'),
            ('Tablet Buttons', 'Assign actions to the four tablet controls and manage the helper/driver.', 'buttons')):
            card = QFrame(); card.setObjectName('card')
            row = QHBoxLayout(card)
            body = QVBoxLayout()
            h = QLabel(heading); h.setStyleSheet('font-weight: 650; font-size: 17px;')
            d = QLabel(text); d.setWordWrap(True)
            body.addWidget(h); body.addWidget(d)
            row.addLayout(body, 1)
            btn = QPushButton('Open')
            btn.clicked.connect(lambda checked=False, k=key: self.show_page(k))
            row.addWidget(btn)
            col.addWidget(card)
        col.addStretch()
        return page

    def refresh_overview(self):
        if getattr(self, '_overview_process', None) and self._overview_process.state() != QProcess.ProcessState.NotRunning:
            return
        process = QProcess(self)
        self._overview_process = process
        process.setProgram(sys.executable)
        process.setArguments([str(Path(__file__).resolve().parents[1] / 'toughbook-tools.py'), '--status'])
        def finished(code, _status):
            try:
                if code:
                    raise ValueError(bytes(process.readAllStandardError()).decode(errors='replace').strip())
                info = json.loads(bytes(process.readAllStandardOutput()).decode())
                screen = info.get('screen', {})
                audio = info.get('audio', {})
                buttons = info.get('buttons', {})
                lines = [
                    'Touchscreen: ' + (f'{len(screen.get("devices", []))} eligible device(s)' if not screen.get('error') else screen['error']),
                    'Audio: ' + (f'{len(audio.get("devices", []))} eligible device(s)' if not audio.get('error') else audio['error']),
                    'Tablet buttons: ' + (f'{len(buttons.get("driver_devices", []))} dedicated device(s)' if not buttons.get('error') else buttons['error'])]
                self.overview_status.setText('\n'.join(lines))
            except (ValueError, KeyError, TypeError) as exc:
                self.overview_status.setText(f'Could not read feature status: {exc}')
            self._overview_process = None
            process.deleteLater()
        process.finished.connect(finished)
        process.start()

    def show_page(self, key):
        active = next((name for name, busy in self.busy.items() if busy), None)
        if active and active != key:
            return
        self.stack.setCurrentWidget(self.pages[key])
        for item, button in self.nav_buttons.items():
            button.setChecked(item == key)

    def set_busy(self, source, busy):
        self.busy[source] = busy
        active = next((key for key, value in self.busy.items() if value), None)
        for key, button in self.nav_buttons.items():
            button.setEnabled(active is None or key == active)
        if self._close_pending and not any(self.busy.values()):
            self._allow_close = True
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event):
        if getattr(self, '_overview_process', None) and self._overview_process.state() != QProcess.ProcessState.NotRunning:
            self._overview_process.kill()
            event.ignore()
            QTimer.singleShot(100, self.close)
            return
        if self.pages['screen'].has_background_work():
            self.pages['screen'].cancel()
            event.ignore()
            QTimer.singleShot(100, self.close)
            return
        status_process = self.pages['buttons'].status_process
        if status_process and status_process.state() != QProcess.ProcessState.NotRunning:
            status_process.kill()
            event.ignore()
            QTimer.singleShot(100, self.close)
            return
        if self._allow_close or not any(self.busy.values()):
            self.pages['buttons'].shutdown()
            event.accept()
            return
        self._close_pending = True
        event.ignore()
        self.log('Closing after the active operation finishes and restores its saved state…')
        screen = self.pages['screen']
        audio = self.pages['audio']
        try:
            screen.cancel()
        except (AttributeError, RuntimeError):
            pass
        try:
            audio.cancel_operation()
        except (AttributeError, RuntimeError):
            pass
        # Driver install/removal should reach its script cleanup handler. A live
        # button monitor is safe to stop immediately.
        buttons_page = self.pages['buttons']
        process = getattr(buttons_page, 'process', None)
        if process and process.state() != process.NotRunning and buttons_page.identify_button.text().startswith('Stop'):
            process.kill()

    def log(self, message):
        stamp = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
        self.output.appendPlainText(f'[{stamp}] {message}')

    def toggle_output(self, expanded):
        self.output.setVisible(expanded)
        self.output_toggle.setText('Hide troubleshooting output ▴' if expanded else 'Show troubleshooting output ▾')

    def copy_output(self):
        QGuiApplication.clipboard().setText(self.output.toPlainText())

    def save_output(self):
        name, _ = QFileDialog.getSaveFileName(self, 'Save troubleshooting output', 'toughbook-troubleshooting.txt', 'Text files (*.txt);;All files (*)')
        if name:
            try:
                Path(name).write_text(self.output.toPlainText(), encoding='utf-8')
            except OSError as exc:
                self.log(f'Could not save output: {exc}')


def run_gui(page='overview'):
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(page)
    window.show()
    return app.exec()
