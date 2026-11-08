"""KDE and GNOME screen calibration. SPDX-License-Identifier: MIT"""
import argparse
import base64
import json
import os
import re
from pathlib import Path
import signal
import shlex
import tempfile
import time

from .affine import IDENTITY, TARGETS, compose, fit, from_kwin, to_kwin, validate
from .common import (ToolError, backup_path, check_model, choose, desktop_user,
                     load_json, require, run, save_json, state_dir, touch_devices)

RULE = Path('/etc/udev/rules.d/99-toughbook-fedora-touchscreen.rules')
IFACE = 'org.kde.KWin.InputDevice'


def dbus_module():
    try:
        import dbus
        return dbus
    except ImportError as exc:
        raise ToolError('Install python3-dbus; see README.') from exc


def backend_name():
    if os.environ.get('XDG_SESSION_TYPE') != 'wayland':
        raise ToolError('Use a local KDE or GNOME Wayland session.')
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    if 'kde' in desktop or 'plasma' in desktop:
        return 'kde'
    if 'gnome' in desktop:
        return 'gnome'
    raise ToolError('Supported desktops are KDE Plasma and GNOME on Wayland.')


def session_token():
    """Shell instance identity survives missing XDG_SESSION_ID and detects a new login."""
    dbus = dbus_module()
    owner = str(dbus.SessionBus().get_name_owner('org.gnome.Mutter.DisplayConfig'))
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip() + ':' + owner


def kde_layout(data):
    outputs = [o for o in data['outputs'] if o.get('enabled')]
    if len(outputs) != 1:
        raise ToolError('Enable only the internal display for calibration.')
    output = outputs[0]
    if (not output['name'].startswith(('LVDS', 'eDP', 'DSI')) or
            output.get('scale', 1) != 1 or output.get('rotation', 1) != 1):
        raise ToolError('Use the internal display, 100% scale, normal landscape orientation.')
    mode = next((m for m in output['modes'] if str(m['id']) == str(output['currentModeId'])), None)
    if mode is None:
        raise ToolError('Cannot identify the current display mode.')
    return output['name'], int(mode['size']['width']), int(mode['size']['height'])


def gnome_layout(current):
    _, monitors, logical, _ = current
    if len(logical) != 1 or len(logical[0][5]) != 1:
        raise ToolError('Enable only the internal display for calibration.')
    _, _, scale, transform, _, specs, _ = logical[0]
    spec = specs[0]
    if scale != 1 or transform != 0 or not str(spec[0]).startswith(('LVDS', 'eDP', 'DSI')):
        raise ToolError('Use the internal display, 100% scale, normal landscape orientation.')
    for identity, modes, _ in monitors:
        if tuple(identity) == tuple(spec):
            for mode in modes:
                if mode[-1].get('is-current', False):
                    return str(identity[0]), int(mode[1]), int(mode[2])
    raise ToolError('Cannot identify the current GNOME display mode.')


def layout(backend):
    if backend == 'kde':
        require('kscreen-doctor')
        return kde_layout(json.loads(run('kscreen-doctor', '-j').stdout))
    dbus = dbus_module()
    obj = dbus.SessionBus().get_object('org.gnome.Mutter.DisplayConfig', '/org/gnome/Mutter/DisplayConfig')
    return gnome_layout(dbus.Interface(obj, 'org.gnome.Mutter.DisplayConfig').GetCurrentState(timeout=10))


class KWin:
    def __init__(self, device):
        dbus = dbus_module()
        obj = dbus.SessionBus().get_object('org.kde.KWin', '/org/kde/KWin/InputDevice/' + device['event'])
        self.props = dbus.Interface(obj, 'org.freedesktop.DBus.Properties')
        if not self.props.Get(IFACE, 'touch', timeout=10) or not self.props.Get(IFACE, 'supportsCalibrationMatrix', timeout=10):
            raise ToolError('KWin does not support calibration for this touchscreen.')
        if int(self.props.Get(IFACE, 'orientationDBus', timeout=10)) not in (0, 2):
            raise ToolError('Reset touchscreen orientation to normal in KDE before calibration.')

    def get(self):
        return {'matrix': str(self.props.Get(IFACE, 'calibrationMatrix', timeout=10)),
                'output': str(self.props.Get(IFACE, 'outputName', timeout=10))}

    def set(self, matrix, output):
        self.props.Set(IFACE, 'outputName', output, timeout=10)
        self.props.Set(IFACE, 'calibrationMatrix', ','.join(map(str, matrix)), timeout=10)
        actual = list(map(float, self.get()['matrix'].split(',')))
        if len(actual) != 16 or max(abs(x-y) for x, y in zip(actual, matrix)) > 1e-4:
            raise ToolError('KWin did not accept the calibration.')

    def restore(self, previous):
        self.set(validate(previous['matrix'].split(','), 16), previous['output'])


def make_rule(identity, matrix):
    # All comparisons apply to this input event, including the USB interface and path.
    expected = {'ID_VENDOR_ID', 'ID_MODEL_ID', 'ID_USB_INTERFACE_NUM', 'ID_SERIAL', 'ID_PATH'}
    if set(identity) != expected or not all(identity.values()):
        raise ToolError('Incomplete device identity; refusing a broad udev rule.')
    if (identity['ID_VENDOR_ID'], identity['ID_MODEL_ID'], identity['ID_USB_INTERFACE_NUM']) != ('056a', '0093', '01'):
        raise ToolError('Unsupported touchscreen identity.')
    if any(not re.fullmatch(r'[A-Za-z0-9_.:+/-]+', value) for value in identity.values()):
        raise ToolError('Device identity contains unsupported udev pattern characters.')
    matches = ['ACTION!="remove"', 'SUBSYSTEM=="input"', 'KERNEL=="event*"', 'ENV{ID_INPUT_TOUCHSCREEN}=="1"']
    matches += [f'ENV{{{key}}}=={json.dumps(value)}' for key, value in sorted(identity.items())]
    matches += ['ENV{LIBINPUT_CALIBRATION_MATRIX}="' + ' '.join(map(str, validate(matrix))) + '"']
    return '# Generated by toughbook-fedora-tools (MIT). Finger input only.\n' + ', '.join(matches) + '\n'


def install_rule(content, device):
    require('sudo', 'udevadm', 'install', 'rm')
    if content is None:
        run('sudo', 'rm', '-f', '--', RULE, timeout=120)
    else:
        with tempfile.TemporaryDirectory(prefix='cf19-rule-') as folder:
            candidate = Path(folder) / 'touchscreen.rules'
            candidate.write_bytes(content)
            run('sudo', 'install', '-m', '0644', '--', candidate, RULE, timeout=120)
    run('sudo', 'udevadm', 'control', '--reload-rules', timeout=120)
    run('sudo', 'udevadm', 'trigger', '--action=change', f'/sys/class/input/{device["event"]}', timeout=120)
    run('udevadm', 'settle', timeout=20)


def find_saved_device(data):
    return choose([d for d in touch_devices() if d['identity'] == data['identity']], 'event')


def restore_backup(path):
    data = load_json(path, 'screen')
    device = find_saved_device(data)
    if data['backend'] == 'kde':
        if backend_name() != 'kde':
            raise ToolError('Restore a KDE calibration from a KDE Wayland session.')
        KWin(device).restore(data['previous'])
    elif data['backend'] == 'gnome':
        content = data['previous']['rule']
        install_rule(base64.b64decode(content, validate=True) if content is not None else None, device)
        print('Rule restored. Log out and back in to activate the previous calibration.')
    else:
        raise ToolError('Unknown backup backend.')
    data['status'] = 'restored'
    save_json(path, data)


class CalibrationWindow:
    """Mouse-emulated finger taps, as used in the hardware-tested prototype."""
    def __init__(self, expected, callback, verify=False):
        try:
            import tkinter as tk
        except ImportError as exc:
            raise ToolError('Install Tk and XWayland (Fedora: python3-tkinter, xorg-x11-server-Xwayland; Ubuntu: python3-tk, xwayland).') from exc
        self.root = tk.Tk()
        self.root.title('Toughbook touchscreen calibration')
        self.root.attributes('-fullscreen', True)
        self.canvas = tk.Canvas(self.root, bg='white', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.expected, self.callback, self.verify = expected, callback, verify
        self.samples, self.ready, self.accepted = [], False, False
        self.size, self.stable, self.applied = None, 0, False
        self.started = time.monotonic()
        self.root.bind('<Escape>', lambda e: self.root.destroy())
        self.root.protocol('WM_DELETE_WINDOW', self.root.destroy)
        self.canvas.bind('<Configure>', self.resize)
        self.canvas.bind('<ButtonRelease-1>', self.tap)
        self.root.after(100, self.wait_fullscreen)

    def wait_fullscreen(self):
        size = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.stable = self.stable + 1 if size == self.size else 0
        self.size = size
        if size == self.expected and self.stable >= 5:
            self.ready = True
            self.draw()
        elif time.monotonic() - self.started > 10:
            self.error = ToolError('Fullscreen dimensions do not match the display. Check scaling and XWayland.')
            self.root.destroy()
        else:
            self.root.after(100, self.wait_fullscreen)

    def resize(self, event):
        if self.ready and (event.width, event.height) != self.size:
            if self.applied:
                self.root.destroy()  # Caller rolls back an unaccepted live change.
            else:
                self.ready = False
                self.samples.clear()
                self.started = time.monotonic()
                self.stable = 0
                self.root.after(100, self.wait_fullscreen)

    def draw(self):
        c = self.canvas
        c.delete('all')
        w, h = self.size
        x, y = TARGETS[len(self.samples)]
        c.create_text(w/2, 30, text='Tap each cross with your finger. Escape cancels.')
        c.create_line(x*w-18, y*h, x*w+18, y*h, fill='red', width=3)
        c.create_line(x*w, y*h-18, x*w, y*h+18, fill='red', width=3)

    def tap(self, event):
        if not self.ready:
            return
        w, h = self.size
        if self.applied:
            self.canvas.create_oval(event.x-4, event.y-4, event.x+4, event.y+4, fill='blue')
            return
        self.samples.append((event.x/w, event.y/h))
        if len(self.samples) < 9:
            self.draw()
            return
        try:
            if self.verify:
                error = max(((w*(x-tx))**2+(h*(y-ty))**2)**.5
                            for (x, y), (tx, ty) in zip(self.samples, TARGETS))
                if error > 20:
                    raise ToolError(f'Verification missed targets by up to {error:.1f}px. Restore or recalibrate.')
                message = f'Verified (maximum error {error:.1f}px). Enter accepts; Escape cancels.'
            else:
                correction, error = fit(self.samples, w, h)
                message = self.callback(correction, error, self.samples, self.size)
            self.applied = True
            self.canvas.delete('all')
            self.canvas.create_text(w/2, h/2, text=message, width=w-80)
            self.root.bind('<Return>', self.accept)
        except Exception as exc:
            self.error = exc
            self.root.destroy()

    def accept(self, event):
        self.accepted = True
        self.root.destroy()

    def run(self):
        previous_signals = {sig: signal.signal(sig, lambda signum, frame: self.root.destroy())
                            for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            self.root.mainloop()
        finally:
            for sig, handler in previous_signals.items():
                signal.signal(sig, handler)
        if hasattr(self, 'error'):
            raise self.error
        return self.accepted


def command(flag, path):
    script = Path(__file__).resolve().parent.parent / 'calibrate-screen.py'
    return shlex.join(['python3', str(script), flag, str(path)])


def apply_pending(path):
    data = load_json(path, 'screen')
    if data['backend'] != 'gnome' or data['status'] != 'candidate':
        raise ToolError('Select a pending GNOME candidate backup.')
    if backend_name() != 'gnome':
        raise ToolError('Apply the GNOME candidate from a GNOME Wayland session.')
    device = find_saved_device(data)
    current = base64.b64encode(RULE.read_bytes()).decode() if RULE.exists() else None
    if current != data['previous']['rule']:
        raise ToolError('The installed rule changed since measurement; recalibrate first.')
    if list(data.get('size', [])) != list(layout('gnome')[1:]):
        raise ToolError('Display dimensions changed since measurement; recalibrate first.')
    matrix = validate(data['matrix'])
    rule = make_rule(device['identity'], matrix).encode()
    # Track an interrupted installation so --restore can always recover it.
    data['status'] = 'pending-login'
    data['session'] = session_token()
    save_json(path, data)
    try:
        install_rule(rule, device)
    except BaseException:
        restore_backup(path)
        raise
    print('Rule installed. Log out and back in, then run:')
    print(command('--verify', path))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Calibrate CF-19 Wacom finger input on KDE/GNOME Wayland.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--status', action='store_true', help='List eligible devices and session backend; no changes')
    group.add_argument('--apply', metavar='BACKUP', help='Install a measured GNOME candidate (uses sudo)')
    group.add_argument('--verify', metavar='BACKUP', help='Verify GNOME calibration after a new login')
    group.add_argument('--restore', metavar='BACKUP', help='Restore a saved KDE setting or GNOME rule')
    parser.add_argument('--device', help='Eligible event name from --status, for ambiguous devices')
    args = parser.parse_args(argv)
    desktop_user()
    require('udevadm')
    check_model()
    if args.restore:
        restore_backup(args.restore)
        return 0
    backend = backend_name()
    if args.status:
        print(json.dumps({'backend': backend, 'devices': touch_devices()}, indent=2))
        return 0
    if args.apply:
        apply_pending(args.apply)
        return 0
    output, width, height = layout(backend)
    if args.verify:
        data = load_json(args.verify, 'screen')
        device = find_saved_device(data)
        if backend != 'gnome' or data['backend'] != 'gnome' or data['status'] != 'pending-login':
            raise ToolError('Verification requires an applied GNOME candidate.')
        if data.get('session') == session_token():
            raise ToolError('Log out and back in before verification.')
        actual = device['properties'].get('LIBINPUT_CALIBRATION_MATRIX', '').split()
        if len(actual) != 6 or max(abs(a-b) for a,b in zip(validate(actual), validate(data['matrix']))) > 1e-5:
            raise ToolError('udev does not report the expected calibration; restore and inspect the rule.')
        if not CalibrationWindow((width,height), None, verify=True).run():
            return 2
        data['status'] = 'accepted'
        save_json(args.verify, data)
        print('Calibration verified.')
        return 0
    device = choose(touch_devices(), 'event', args.device)
    kwin = KWin(device) if backend == 'kde' else None
    previous = kwin.get() if kwin else {'rule': base64.b64encode(RULE.read_bytes()).decode() if RULE.exists() else None}
    old = from_kwin(previous['matrix']) if kwin else validate(
        device['properties'].get('LIBINPUT_CALIBRATION_MATRIX', '1 0 0 0 1 0').split())
    path = backup_path('screen')
    data = {'kind': 'screen', 'backend': backend, 'identity': device['identity'],
            'previous': previous, 'status': 'measuring', 'session': session_token() if backend == 'gnome' else ''}
    save_json(path, data)
    changed = False
    accepted = False

    def measured(correction, error, samples, size):
        nonlocal changed
        matrix = compose(correction, old)
        data.update(matrix=matrix, fit_error_pixels=error, size=list(size), status='candidate')
        save_json(path, data)
        if kwin:
            changed = True
            kwin.set(to_kwin(matrix), output)
            return 'Calibration applied. Test taps. Enter keeps it; Escape restores the previous calibration.'
        return 'Candidate measured. Enter saves it; Escape discards it.\nInstallation and logout/login are required next.'

    print(f'Backup: {path}', flush=True)
    try:
        accepted = CalibrationWindow((width,height), measured).run()
    finally:
        if not accepted:
            if changed:
                kwin.restore(previous)
            data['status'] = 'cancelled'
            save_json(path, data)
    if not accepted:
        return 2
    if kwin:
        data['status'] = 'accepted'
        save_json(path, data)
        print('Calibration saved by KWin.')
    else:
        print('Install the candidate with:')
        print(command('--apply', path))
    return 0
