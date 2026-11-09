"""Qt controls for user button assignments and the dedicated kernel driver."""
from pathlib import Path
import os
import json
import shutil
import subprocess
import sys

from PySide6.QtCore import QProcess, QTimer, Signal, Qt
from PySide6.QtWidgets import (QComboBox, QCompleter, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from . import runtime
from . import buttons
from . import distro
from .common import ToolError, save_json


class ButtonsPage(QWidget):
    log = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.assignments = {}
        self.process = None
        self.status_process = None
        outer = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); col = QVBoxLayout(content)
        intro = QLabel('Single press assignments for the four front controls. Brightness controls stay with the existing driver.')
        intro.setWordWrap(True); col.addWidget(intro)
        diagram = QLabel('Tablet edge:  [ Keyboard ]   [ ○ Circle ]   [ ↻ Screen ]   [ Key ]')
        diagram.setWordWrap(True); col.addWidget(diagram)
        self.driver_label = QLabel('Driver status: checking…'); self.driver_label.setWordWrap(True)
        col.addWidget(self.driver_label)
        driver_buttons = QHBoxLayout()
        self.install_button = QPushButton('Install driver…')
        self.load_button = QPushButton('Load driver…')
        self.remove_button = QPushButton('Remove driver…')
        try:
            package_distro = distro.distro_id()
        except ToolError:
            package_distro = 'supported distribution'
        self.packages_button = QPushButton(f'Install {distro.family_name(package_distro)} prerequisites…')
        self.identify_button = QPushButton('Identify physical buttons')
        for b in (self.packages_button, self.install_button, self.load_button, self.remove_button, self.identify_button): driver_buttons.addWidget(b)
        col.addLayout(driver_buttons)
        self.driver_instructions = QLabel('Install requires a compiler, matching kernel headers, DKMS, and mokutil. Secure Boot stays enabled; if enabled, complete DKMS MOK enrollment manually before loading the module.')
        self.driver_instructions.setWordWrap(True); col.addWidget(self.driver_instructions)
        if Path('/sys/firmware/efi').exists() and shutil.which('mokutil'):
            try:
                state = runtime.host_run([shutil.which('mokutil'), '--sb-state'], capture_output=True, text=True, timeout=5)
                self.driver_instructions.setText(self.driver_instructions.text() + '\nSecure Boot: ' + (state.stdout.strip() or state.stderr.strip()))
            except (OSError, subprocess.TimeoutExpired) as exc:
                self.driver_instructions.setText(self.driver_instructions.text() + f'\nSecure Boot status unavailable: {exc}')
        elif not Path('/sys/firmware/efi').exists():
            self.driver_instructions.setText(self.driver_instructions.text() + '\nLegacy boot: EFI Secure Boot is not active.')
        self.install_button.clicked.connect(lambda: self.run_driver('install'))
        self.load_button.clicked.connect(lambda: self.run_driver('load'))
        self.remove_button.clicked.connect(lambda: self.run_driver('uninstall'))
        self.packages_button.clicked.connect(self.install_packages)
        self.identify_button.clicked.connect(self.identify)

        group = QGroupBox('Assignments')
        form = QFormLayout(group)
        self.kind = {}; self.value = {}; self.builtin_choice = {}; self.app_choice = {}
        try:
            current = buttons.load_settings()
        except Exception as exc:
            current = buttons.defaults()
            self.log.emit(f'Could not load assignments: {exc}. Defaults are shown; save to replace the invalid settings.')
        app_choices = self.app_choices()
        for key, row in buttons.BUTTONS.items():
            line = QHBoxLayout()
            combo = QComboBox()
            combo.addItem('Built-in action', 'builtin')
            combo.addItem('Executable with arguments', 'command')
            combo.addItem('Shell command', 'shell')
            combo.addItem('Installed application (.desktop ID)', 'application')
            edit = QLineEdit()
            edit.setPlaceholderText('Executable and arguments, shell text, or application.desktop')
            assigned = current[key]
            index = combo.findData(assigned['type'])
            combo.setCurrentIndex(index if index >= 0 else 0)
            builtin = QComboBox()
            for action, label in (('keyboard','Toggle on-screen keyboard'), ('launcher','Open application launcher'),
                                  ('rotate','Rotate display'), ('lock','Lock session'), ('disabled','Disabled')):
                builtin.addItem(label, action)
            builtin.setCurrentIndex(max(0, builtin.findData(assigned['value'] if assigned['type'] == 'builtin' else row[3])))
            app = QComboBox()
            for app_id, app_name in app_choices:
                app.addItem(app_name, app_id)
            if assigned['type'] == 'application' and app.findData(assigned['value']) < 0:
                app.addItem(f'Missing: {assigned["value"]}', assigned['value'])
            if assigned['type'] == 'application':
                app.setCurrentIndex(app.findData(assigned['value']))
            edit.setText(assigned['value'] if assigned['type'] in ('command','shell') else '')
            combo.currentIndexChanged.connect(lambda _i, c=combo, e=edit, b=builtin, a=app: self.configure_editor(c, e, b, a))
            line.addWidget(combo); line.addWidget(builtin, 1); line.addWidget(app, 1); line.addWidget(edit, 1)
            caption = QLabel(f'{row[0]} ({row[2]})')
            caption.setToolTip(f'Windows function: {row[1]}')
            form.addRow(caption, line)
            self.kind[key] = combo; self.value[key] = edit; self.builtin_choice[key] = builtin; self.app_choice[key] = app
            self.configure_editor(combo, edit, builtin, app)
        col.addWidget(group)
        actions = QHBoxLayout()
        save = QPushButton('Save assignments'); reset = QPushButton('Reset defaults')
        save.clicked.connect(self.save_settings); reset.clicked.connect(self.reset_settings)
        actions.addWidget(save); actions.addWidget(reset); actions.addStretch(); col.addLayout(actions)

        helper = QGroupBox('Shortcut helper')
        hcol = QVBoxLayout(helper)
        self.backend_combo = QComboBox()
        self.backend_combo.addItem('Dedicated tablet device (all desktops)', 'direct')
        self.backend_combo.addItem('Desktop shortcut portal', 'portal')
        try:
            self.backend_combo.setCurrentIndex(self.backend_combo.findData(buttons.helper_backend()))
        except Exception as exc:
            self.log.emit(str(exc))
        hcol.addWidget(self.backend_combo)
        self.portal_label = QLabel(''); self.portal_label.setWordWrap(True)
        self.session_label = QLabel(''); self.session_label.setWordWrap(True)
        hcol.addWidget(self.portal_label); hcol.addWidget(self.session_label)
        hbuttons = QHBoxLayout()
        start = QPushButton('Install / start login helper'); configure = QPushButton('Configure shortcuts…')
        self.configure_button = configure
        start.clicked.connect(self.start_helper); configure.clicked.connect(self.configure_shortcuts)
        hbuttons.addWidget(start); hbuttons.addWidget(configure); hbuttons.addStretch(); hcol.addLayout(hbuttons)
        col.addWidget(helper)
        self.live_label = QLabel(); self.live_label.setWordWrap(True); self.live_label.setTextInteractionFlags(self.live_label.textInteractionFlags() | Qt.TextSelectableByMouse)
        col.addWidget(self.live_label); col.addStretch()
        scroll.setWidget(content); outer.addWidget(scroll)
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh_status); self.timer.start(2000)
        self.refresh_status()

    @staticmethod
    def app_choices():
        try:
            import gi
            gi.require_version('Gio', '2.0')
            from gi.repository import Gio
            return sorted([(a.get_id(), a.get_name()) for a in Gio.AppInfo.get_all() if a.should_show() and a.get_id()], key=lambda a: a[1].casefold())
        except Exception:
            return []

    def configure_editor(self, combo, edit, builtin, app):
        kind = combo.currentData()
        builtin.setVisible(kind == 'builtin')
        app.setVisible(kind == 'application')
        edit.setVisible(kind in ('command','shell'))
        edit.setPlaceholderText('Executable and arguments' if kind == 'command' else 'Explicit shell command')

    def gather(self):
        data = {}
        for key in buttons.BUTTONS:
            kind = self.kind[key].currentData()
            value = (self.builtin_choice[key].currentData() if kind == 'builtin' else
                     self.app_choice[key].currentData() if kind == 'application' else self.value[key].text().strip())
            data[key] = {'type':kind, 'value':value}
        return buttons.validate(data)

    def save_settings(self):
        try:
            save_json(buttons.settings_path(), self.gather())
            self.log.emit('Button assignments saved. The helper reads settings on each press.')
        except Exception as exc: self.log.emit(f'Could not save assignments: {exc}')

    def reset_settings(self):
        for key, row in buttons.BUTTONS.items():
            self.kind[key].setCurrentIndex(self.kind[key].findData('builtin'))
            self.builtin_choice[key].setCurrentIndex(self.builtin_choice[key].findData(row[3]))
            self.value[key].clear()
        self.save_settings()

    def start_helper(self):
        if self.process and self.process.state() != QProcess.NotRunning:
            return
        process = QProcess(self)
        self.process = process
        runtime.configure_process(process, runtime.command('toughbook-buttons.py', '--install', '--backend', self.backend_combo.currentData()))
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(lambda: self.log.emit(bytes(process.readAllStandardOutput()).decode(errors='replace').rstrip()))
        def finished(code, _status):
            self.process = None
            self.busy_changed.emit(False)
            self.log.emit('Helper started. Direct mode needs no shortcut approval; portal mode opens the desktop dialog.' if code == 0 else f'Helper installation failed ({code}). Review output.')
            self.refresh_status()
            process.deleteLater()
        process.finished.connect(finished)
        process.start()
        self.busy_changed.emit(True)

    def configure_shortcuts(self):
        try:
            import dbus
            proxy = dbus.SessionBus().get_object(buttons.CONTROL_IFACE, buttons.CONTROL_PATH)
            dbus.Interface(proxy, buttons.CONTROL_IFACE).Configure(timeout=15)
            self.log.emit('Shortcut configuration opened. Press each physical button in the desktop dialog.')
        except Exception as exc: self.log.emit(f'Cannot configure shortcuts: {exc}. Install/start the helper first.')

    def refresh_status(self):
        if self.status_process and self.status_process.state() != QProcess.NotRunning:
            return
        process = QProcess(self)
        self.status_process = process
        runtime.configure_process(process, runtime.command('toughbook-buttons.py', '--status'))
        def finished(code, _status):
            try:
                if code:
                    raise ValueError(bytes(process.readAllStandardError()).decode(errors='replace').strip())
                self._show_status(json.loads(bytes(process.readAllStandardOutput()).decode()))
            except (ValueError, TypeError, KeyError) as exc:
                self.live_label.setText(f'Status unavailable: {exc}')
            self.status_process = None
            process.deleteLater()
        process.finished.connect(finished)
        process.start()

    def _show_status(self, info):
        try:
            session = info['session']
            bindings = session.get('shortcuts', {})
            self.driver_label.setText('Driver status: ' + (', '.join(info['driver_devices']) if info['driver_devices'] else 'dedicated tablet input device not detected'))
            self.install_button.setEnabled(not bool(info['driver_devices']))
            backend = session.get('backend', info.get('backend', 'direct'))
            self.configure_button.setEnabled(backend == 'portal')
            self.portal_label.setText('Button delivery: ' + backend + '\nPortal (optional): ' + info['portal'])
            self.session_label.setText('Session helper: ' + ('running' if session.get('pid') else 'stopped'))
            lines = [f'{row[0]}: {bindings.get(key, "unbound")}' for key,row in buttons.BUTTONS.items()]
            if session.get('last_button'): lines.append('Last physical button: ' + session['last_button'])
            if session.get('paused'): lines.append('Button actions paused for identification (up to 60 seconds).')
            if session.get('error'): lines.append('Status: ' + session['error'])
            self.live_label.setText('Live identification\n' + '\n'.join(lines))
        except Exception as exc: self.live_label.setText(f'Status unavailable: {exc}')

    def identify(self):
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.kill()
            return
        try:
            self._helper_control('PauseActions')
        except Exception as exc:
            self.log.emit(f'Cannot pause button actions for identification: {exc}. Start/restart the helper first.')
            return
        self.process = QProcess(self)
        runtime.configure_process(self.process, runtime.command('toughbook-buttons.py', '--monitor'))
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        process = self.process
        process.readyReadStandardOutput.connect(lambda: self.log.emit(bytes(process.readAllStandardOutput()).decode(errors='replace').rstrip()))
        self.process.finished.connect(self.identify_finished)
        self.process.start(); self.identify_button.setText('Stop identification')
        self.busy_changed.emit(True)

    def identify_finished(self, code, status):
        try:
            self._helper_control('ResumeActions')
        except Exception as exc:
            self.log.emit(f'Could not resume button actions immediately: {exc}. The helper resumes automatically within 60 seconds.')
        self.identify_button.setText('Identify physical buttons'); self.busy_changed.emit(False)
        if code: self.log.emit(f'Button identification ended with status {code}.')
        self.process.deleteLater()
        self.process = None

    def _helper_control(self, method):
        import dbus
        proxy = dbus.SessionBus().get_object(buttons.CONTROL_IFACE, buttons.CONTROL_PATH)
        getattr(dbus.Interface(proxy, buttons.CONTROL_IFACE), method)(timeout=10)

    def _start_privileged(self, argv, label):
        process = QProcess(self)
        self.process = process
        self._driver_label = label
        runtime.configure_process(process, ['/usr/bin/pkexec', *argv], host=True)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(lambda: self.log.emit(bytes(process.readAllStandardOutput()).decode(errors='replace').rstrip()))
        def launch_error(err):
            self.log.emit(f'{label}: could not launch: {err}')
            if err == QProcess.ProcessError.FailedToStart and self.process is process:
                self.process = None
                self._driver_steps = []
                self.busy_changed.emit(False)
                process.deleteLater()
        process.errorOccurred.connect(launch_error)
        process.finished.connect(self.driver_finished)
        self.log.emit(f'{label}: starting.')
        process.start()
        self.busy_changed.emit(True)

    def install_packages(self):
        if self.process and self.process.state() != QProcess.NotRunning:
            return
        try:
            package_distro = distro.distro_id()
            command = distro.driver_install_command()
        except ToolError as exc:
            self.log.emit(str(exc))
            return
        label = f'Install {distro.family_name(package_distro)} prerequisites'
        if QMessageBox.question(self, label,
                f'Install the driver build packages with {Path(command[0]).name}? This selects headers for the running kernel. After a kernel update, reboot before building.\n\n' + ' '.join(command[4:] if package_distro == 'arch' else command[3:]),
                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes:
            return
        self._driver_steps = [(label, command)]
        label, argv = self._driver_steps.pop(0)
        self._start_privileged(argv, label)

    def run_driver(self, action):
        if self.process and self.process.state() != QProcess.NotRunning: return
        if action == 'load':
            self._driver_steps = [('Load driver', [shutil.which('modprobe') or '/sbin/modprobe', 'panasonic-hbtn'])]
            label, argv = self._driver_steps.pop(0)
            self._start_privileged(argv, label)
            return
        script = runtime.resources() / 'driver' / ('install.sh' if action == 'install' else 'uninstall.sh')
        detail = ('The installer checks the supported device, competing drivers, DKMS, and the current kernel headers. The module will then be loaded. If Secure Boot requires MOK enrollment, finish it manually and retry loading.' if action == 'install' else 'The module will be unloaded, then this driver version’s DKMS registration, source, and udev rule will be removed.')
        answer = QMessageBox.question(self, f'{action.title()} tablet button driver', detail + '\n\nRun the fixed repository script through pkexec?', QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if answer != QMessageBox.Yes: return
        install = ('Install driver', ['/usr/bin/bash', str(script)])
        modprobe = shutil.which('modprobe') or '/sbin/modprobe'
        load = ('Load driver', [modprobe, 'panasonic-hbtn'])
        unload = ('Unload driver', [modprobe, '-r', 'panasonic-hbtn'])
        remove = ('Remove driver', ['/usr/bin/bash', str(script)])
        loaded = Path('/sys/module/panasonic_hbtn').exists()
        self._driver_steps = [install, load] if action == 'install' else ([unload, remove] if loaded else [remove])
        label, argv = self._driver_steps.pop(0)
        self._start_privileged(argv, label)

    def driver_finished(self, code, status):
        self.log.emit(f'{self._driver_label} finished with status {code}.')
        if self.process:
            self.process.deleteLater()
        if code == 0 and self._driver_steps:
            label, argv = self._driver_steps.pop(0)
            self._start_privileged(argv, label)
            return
        if code != 0:
            advice = (' If Secure Boot rejected the module, enroll the configured DKMS MOK certificate and retry loading.'
                      if self._driver_label == 'Load driver' else '')
            self.log.emit('Review the output above.' + advice)
        self._driver_steps = []
        self.process = None
        self.busy_changed.emit(False)
        self.refresh_status()

    def shutdown(self):
        self.timer.stop()
        if self.status_process and self.status_process.state() != QProcess.NotRunning:
            self.status_process.kill()
        if self.process and self.identify_button.text().startswith('Stop'):
            self.process.kill()
            try:
                self._helper_control('ResumeActions')
            except Exception:
                pass
