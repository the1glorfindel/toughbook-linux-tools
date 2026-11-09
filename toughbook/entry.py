"""Shared source and portable executable entrypoint. SPDX-License-Identifier: MIT"""
import argparse
import json
import os
from pathlib import Path
import runpy
import sys

from . import runtime
from .cli import dispatch
from .common import ToolError


def launch_application(argv):
    parser = argparse.ArgumentParser(description='Launch an installed desktop application with the host environment.')
    parser.add_argument('desktop_id')
    args = parser.parse_args(argv)
    if '/' in args.desktop_id or not args.desktop_id.endswith('.desktop'):
        raise ToolError('Expected an installed .desktop application ID.')
    from gi.repository import Gio
    app = Gio.DesktopAppInfo.new(args.desktop_id)
    if app is None:
        raise ToolError(f'Application {args.desktop_id} is missing.')
    context = Gio.AppLaunchContext()
    environment = runtime.host_environment()
    for key in os.environ:
        if key not in environment:
            context.unsetenv(key)
    for key, value in environment.items():
        context.setenv(key, value)
    if not app.launch([], context):
        raise ToolError(f'Could not launch {args.desktop_id}.')
    return 0


def check_runtime():
    import dbus
    import dbus.mainloop.glib
    import gi
    import tkinter
    from PySide6 import QtCore, QtGui, QtWidgets, QtTest
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio, GLib
    tcl = tkinter.Tcl()
    clients = {name: runtime.native_program(name) for name in runtime.BUNDLED_PROGRAMS}
    if runtime.frozen() and not all(clients.values()):
        raise ToolError('The portable bundle is missing a required native client.')
    print(json.dumps({'frozen': runtime.frozen(), 'python': sys.version.split()[0],
                      'qt': QtCore.qVersion(), 'dbus': dbus.__version__,
                      'glib': [GLib.MAJOR_VERSION, GLib.MINOR_VERSION, GLib.MICRO_VERSION],
                      'tcl': tcl.eval('info patchlevel'),
                      'clients': clients}, indent=2))
    return 0


def _main(argv):
    runtime.initialize()
    if argv[:1] == ['--bundle-info']:
        path = runtime.resources() / 'BUNDLE-MANIFEST.json'
        if not path.is_file():
            raise ToolError('This source checkout has no portable bundle manifest.')
        print(path.read_text())
        return 0
    if argv[:1] == ['--exec-tool']:
        if not runtime.frozen() or len(argv) < 2:
            raise ToolError('Native client execution is available in the portable bundle only.')
        program = runtime.native_program(argv[1])
        if not program:
            raise ToolError('The requested bundled client is missing.')
        os.execve(program, [program, *argv[2:]], dict(os.environ))
    tool = 'app'
    if argv[:1] == ['--tool']:
        if len(argv) < 2:
            raise ToolError('Missing tool name.')
        tool, argv = argv[1], argv[2:]
    elif argv and Path(argv[0]).name in runtime.TOOLS:
        tool, argv = runtime.TOOLS[Path(argv[0]).name], argv[1:]
    sys.argv = [sys.executable if runtime.frozen() else sys.argv[0], *argv]
    if tool == 'app':
        from .app import main
        return main(argv)
    if tool == 'screen':
        from .screen import main
        return main(argv)
    if tool == 'audio':
        from .audio import main
        return main(argv)
    if tool == 'buttons':
        from .buttons import main
        return main(argv)
    if tool == 'display':
        from .display_info import main
        return main()
    if tool == 'launch-application':
        return launch_application(argv)
    if tool == 'check-runtime':
        return check_runtime()
    if tool == 'check-display':
        script = runtime.resources() / 'tools/check-display.py'
        sys.argv = [str(script), *argv]
        runpy.run_path(str(script), run_name='__main__')
        return 0
    raise ToolError(f'Unknown application tool: {tool}')


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    return dispatch(lambda: _main(arguments))
