#!/usr/bin/env python3
"""Exercise native Qt on an isolated X11/Wayland display; no physical hardware changes."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def command(*argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f'{argv[0]} exited {result.returncode}')
    return result.stdout


def check_xvfb_input():
    """Label only Xvfb's synthetic mouse, then exercise the real XInput interface."""
    from toughbook.xinput import XInput
    listing = command('xinput', 'list', '--short')
    mouse = re.search(r'Xvfb mouse\s+id=(\d+)', listing)
    keyboard = re.search(r'Xvfb keyboard\s+id=(\d+)', listing)
    if not mouse or not keyboard:
        raise RuntimeError('--xvfb-input requires Xvfb synthetic devices; refusing other input devices.')
    keyboard_before = command('xinput', 'list-props', keyboard[1])
    x11, xi = ctypes.CDLL('libX11.so.6'), ctypes.CDLL('libXi.so.6')
    x11.XOpenDisplay.argtypes, x11.XOpenDisplay.restype = [ctypes.c_char_p], ctypes.c_void_p
    x11.XInternAtom.argtypes, x11.XInternAtom.restype = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int], ctypes.c_ulong
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xi.XOpenDevice.argtypes, xi.XOpenDevice.restype = [ctypes.c_void_p, ctypes.c_ulong], ctypes.c_void_p
    xi.XChangeDeviceProperty.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
                                       ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    xi.XCloseDevice.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError('Cannot open the isolated X11 display.')
    try:
        pointer = xi.XOpenDevice(display, int(mouse[1]))
        if not pointer:
            raise RuntimeError('Cannot open the Xvfb synthetic pointer.')
        try:
            node = b'/dev/input/event-toughbook-test'
            # XA_STRING is 31; PropModeReplace is 0. This property exists only
            # inside the temporary X server, not in /dev or the udev database.
            xi.XChangeDeviceProperty(display, pointer,
                                    x11.XInternAtom(display, b'Device Node', 0),
                                    31, 8, 0, node, len(node))
        finally:
            xi.XCloseDevice(display, pointer)
    finally:
        x11.XCloseDisplay(display)
    device = XInput({'event': 'event-toughbook-test'})
    previous = device.get()
    try:
        device.set([1.05, 0., -.02, 0., 1.02, -.01])
    finally:
        device.restore(previous)
    if max(abs(a-b) for a,b in zip(device.get()['matrix'], previous['matrix'])) > 1e-5:
        raise RuntimeError('The synthetic pointer matrix was not restored.')
    if command('xinput', 'list-props', keyboard[1]) != keyboard_before:
        raise RuntimeError('An unrelated synthetic keyboard property changed.')
    return True


def native_check(args):
    from PySide6 import __version__ as pyside_version
    from PySide6.QtCore import QEvent, QPoint, qVersion
    from PySide6.QtGui import QInputDevice, QFontDatabase
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from toughbook import screen, session
    from toughbook.affine import TARGETS
    from toughbook.common import ToolError
    from toughbook.screen_gui import _Targets

    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    families = QFontDatabase.families()
    if not families:
        raise RuntimeError('No usable fonts are available for the application interface.')
    expected_platform = 'xcb' if args.expect == 'x11' else 'wayland'
    if session.kind() != args.expect or not app.platformName().startswith(expected_platform):
        raise RuntimeError(f'Expected native {args.expect}/{expected_platform}, got {session.kind()}/{app.platformName()}.')
    outputs = json.loads(command(sys.executable, str(Path(screen.__file__).with_name('display_info.py'))))
    report = {'session': session.kind(), 'qt_platform': app.platformName(),
              'python_version': sys.version.split()[0], 'pyside_version': pyside_version,
              'qt_version': qVersion(), 'font_families': len(families), 'outputs': outputs}
    try:
        screen.generic_layout(outputs)
        report['calibration_layout_eligible'] = True
    except ToolError:
        report['calibration_layout_eligible'] = False
    if args.expect_rotated and not any(not output['normal'] for output in outputs):
        raise RuntimeError('A rotated output was reported as normal.')
    if args.metadata_only:
        return report
    if args.xvfb_input:
        report['xinput_apply_readback_restore'] = check_xvfb_input()
        report['unrelated_keyboard_unchanged'] = True

    def pump_until(predicate, timeout=12):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            app.processEvents()
            QTest.qWait(20)
        if not predicate():
            raise RuntimeError('Timed out waiting for native GUI state. X11 requires a fullscreen-capable window manager.')

    size = app.primaryScreen().size()
    dialog = _Targets((size.width(), size.height()))
    measured = []
    dialog.measured.connect(measured.append)
    try:
        pump_until(lambda: dialog.ready)
        device = QTest.createTouchDevice(QInputDevice.DeviceType.TouchScreen)
        for x, y in TARGETS:
            point = QPoint(int(x * dialog.width()), int(y * dialog.height()))
            QTest.touchEvent(dialog, device).press(0, point, dialog).commit()
            QTest.qWait(10)
            QTest.touchEvent(dialog, device).release(0, point, dialog).commit()
            QTest.qWait(10)
        if len(measured) != 1 or len(measured[0]) != 9:
            raise RuntimeError(f'Expected one nine-tap result, got {len(measured)} results/{len(dialog.samples)} taps.')
        for (x, y), (tx, ty) in zip(measured[0], TARGETS):
            if max(abs(x-tx) * dialog.width(), abs(y-ty) * dialog.height()) > 1.01:
                raise RuntimeError('Native touch coordinates differ from the injected target by more than one pixel.')
        report['fullscreen_nine_synthetic_touches'] = True
        report['touch_coordinates_within_one_pixel'] = True
        dialog.show_preview()
        accepted = []
        dialog.accepted_result.connect(lambda: accepted.append(True))
        dialog.keep.click()
        if not accepted:
            raise RuntimeError('The preview acceptance control failed.')
        report['preview_accept'] = True
    finally:
        dialog.finish()
        dialog.deleteLater()
        app.sendPostedEvents(None, QEvent.DeferredDelete)
    from toughbook.gui import MainWindow
    window = MainWindow()
    try:
        window.show()
        pump_until(window.isVisible)
        for page in ('overview', 'screen', 'audio', 'buttons'):
            window.show_page(page)
            app.processEvents()
            if window.stack.currentWidget() is not window.pages[page]:
                raise RuntimeError(f'Cannot open the {page} page.')
        QTest.qWait(1500)
        window.close()
        pump_until(lambda: not window.isVisible())
        report['all_gui_pages_and_shutdown'] = True
    finally:
        window.close()
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.DeferredDelete)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expect', choices=('x11', 'wayland'), required=True)
    parser.add_argument('--xvfb-input', action='store_true', help='Test only Xvfb synthetic device properties')
    parser.add_argument('--metadata-only', action='store_true', help='Query native output geometry/orientation only')
    parser.add_argument('--expect-rotated', action='store_true', help='Require a non-normal output in metadata-only mode')
    args = parser.parse_args()
    if args.xvfb_input and args.expect != 'x11':
        parser.error('--xvfb-input is only valid with --expect x11')
    if args.expect_rotated and not args.metadata_only:
        parser.error('--expect-rotated requires --metadata-only')
    # Isolate state and D-Bus from the real login even if run from a live desktop.
    # The caller supplies the private X11/Wayland server and its runtime directory.
    with tempfile.TemporaryDirectory(prefix='toughbook-display-check-') as folder:
        root = Path(folder)
        for variable, name in (('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'), ('XDG_STATE_HOME', 'state')):
            os.environ[variable] = str(root / name)
        os.environ['DBUS_SESSION_BUS_ADDRESS'] = 'unix:path=' + str(root / 'absent-bus')
        try:
            print(json.dumps(native_check(args), indent=2))
            return 0
        except Exception as exc:
            print(f'Display check failed: {exc}', file=sys.stderr)
            return 1


if __name__ == '__main__':
    raise SystemExit(main())
