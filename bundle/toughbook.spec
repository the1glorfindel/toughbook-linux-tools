# SPDX-License-Identifier: MIT
from pathlib import Path
import os
import shutil
import sys
import sysconfig

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(Path(SPECPATH)))
from metadata import collect

binaries = []
for name in ('pactl', 'pw-play', 'amixer', 'alsactl', 'xinput', 'xrandr', 'wlr-randr'):
    path = shutil.which(name)
    if not path:
        raise RuntimeError('Missing portable build client: ' + name)
    binaries.append((path, 'bin'))
libdir = Path('/usr/lib') / sysconfig.get_config_var('MULTIARCH')
# Ship GLVND dispatch libraries, not host-specific Mesa/NVIDIA driver modules.
for name in ('libGL.so.1', 'libEGL.so.1', 'libGLX.so.0', 'libGLdispatch.so.0',
             'libxcb.so.1', 'libwayland-client.so.0', 'libwayland-cursor.so.0',
             'libwayland-egl.so.1', 'libharfbuzz.so.0', 'libdrm.so.2'):
    path = libdir / name
    if not path.is_file():
        raise RuntimeError('Missing portable graphics dispatch library: ' + name)
    binaries.append((str(path), '.'))
for folder in ('pipewire-0.3', 'spa-0.2', 'alsa-lib'):
    source = libdir/folder
    for file in source.rglob('*.so'):
        binaries.append((str(file), str(Path(folder)/file.relative_to(source).parent)))

datas = [(str(ROOT/name), name) for name in ('data', 'docs', 'driver')]
datas += [(str(ROOT/name), '.') for name in ('README.md', 'LICENSE', 'THIRD_PARTY.md', 'CHANGELOG.md')]
datas += [(str(ROOT/'tools/check-display.py'), 'tools'),
          ('/usr/share/alsa', 'alsa'), ('/usr/share/sounds/alsa', 'sounds/alsa')]

a = Analysis([str(ROOT/'bundle/freeze.py')], pathex=[str(ROOT)], binaries=binaries, datas=datas,
             hiddenimports=['dbus.mainloop.glib', 'gi.repository.Gio', 'gi.repository.GLib',
                            'gi.repository.GObject', 'tkinter', 'ctypes', 'ctypes.util', 'PySide6.QtTest'],
             excludes=['PyQt5', 'PyQt6', 'PySide2', 'numpy', 'matplotlib'],
             hooksconfig={'gi': {'icons': [], 'themes': []}}, noarchive=False)
# Qt Widgets uses its built-in style; avoid an optional GTK theme adapter
# that would otherwise pull an entire second GUI toolkit into this runtime.
a.binaries = [row for row in a.binaries if not row[0].endswith('/platformthemes/libqgtk3.so')]
collect(a, ROOT, Path(os.environ['TOUGHBOOK_METADATA_DIR']))
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='toughbook-tools',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='toughbook-tools')
