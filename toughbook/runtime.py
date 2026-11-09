"""Source/frozen runtime paths and safe host subprocesses. SPDX-License-Identifier: MIT"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

TOOLS = {'toughbook-tools.py': 'app', 'calibrate-screen.py': 'screen',
         'fix-audio.py': 'audio', 'toughbook-buttons.py': 'buttons',
         'display_info.py': 'display', 'check-display.py': 'check-display',
         'launch-application': 'launch-application'}
BUNDLED_PROGRAMS = ('pactl', 'pw-play', 'amixer', 'alsactl', 'xinput', 'xrandr', 'wlr-randr')
_ORIGINAL = {}


def frozen():
    return bool(getattr(sys, 'frozen', False))


def application_root():
    return Path(sys.executable).resolve().parent if frozen() else Path(__file__).resolve().parents[1]


def resources(root=None):
    if root is not None:
        root = Path(root)
        return root / '_internal' if (root / '_internal').is_dir() else root
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


def command(script, *args, root=None):
    name = Path(script).name
    if name not in TOOLS:
        raise ValueError(f'Unknown application tool: {name}')
    root = Path(root) if root is not None else application_root()
    if frozen():
        return [str(root / 'toughbook-tools'), '--tool', TOOLS[name], *map(str, args)]
    if name == 'launch-application':
        return [sys.executable, str(root / 'toughbook-tools.py'), '--tool', name, *map(str, args)]
    script_path = root / ('toughbook/display_info.py' if name == 'display_info.py' else
                          'tools/check-display.py' if name == 'check-display.py' else name)
    return [sys.executable, str(script_path), *map(str, args)]


def native_program(name):
    if name not in BUNDLED_PROGRAMS:
        raise ValueError(f'Not a bundled client program: {name}')
    path = resources() / 'bin' / name
    return str(path) if path.is_file() else None


def which(name):
    if frozen() and name in BUNDLED_PROGRAMS:
        path = native_program(name)
        if path:
            return path
    return shutil.which(name)


def initialize():
    if not frozen():
        return
    root = resources()
    host_path = os.environ.get('TOUGHBOOK_HOST_PATH', os.environ.get('PATH', ''))
    host_path = os.pathsep.join(part for part in host_path.split(os.pathsep) if part != str(root / 'bin'))
    os.environ['TOUGHBOOK_HOST_PATH'] = host_path
    values = {'PATH': str(root / 'bin') + os.pathsep + host_path}
    for name, relative in (('ALSA_CONFIG_DIR', 'alsa'), ('ALSA_CONFIG_PATH', 'alsa/alsa.conf'),
                           ('ALSA_PLUGIN_DIR', 'alsa-lib'), ('PIPEWIRE_MODULE_DIR', 'pipewire-0.3'),
                           ('SPA_PLUGIN_DIR', 'spa-0.2')):
        if (root / relative).exists():
            values[name] = str(root / relative)
    for name, value in values.items():
        if name not in _ORIGINAL:
            _ORIGINAL[name] = host_path if name == 'PATH' else os.environ.get(name)
        os.environ[name] = value


def host_environment(base=None):
    env = dict(os.environ if base is None else base)
    if not frozen():
        return env
    for name in ('LD_LIBRARY_PATH', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH',
                 'GI_TYPELIB_PATH', 'GIO_MODULE_DIR', 'GIO_EXTRA_MODULES',
                 'ALSA_CONFIG_DIR', 'ALSA_CONFIG_PATH', 'ALSA_PLUGIN_DIR',
                 'PIPEWIRE_MODULE_DIR', 'SPA_PLUGIN_DIR', 'PYTHONHOME', 'PYTHONPATH'):
        env.pop(name, None)
    if env.get('LD_LIBRARY_PATH_ORIG'):
        env['LD_LIBRARY_PATH'] = env['LD_LIBRARY_PATH_ORIG']
    env.pop('LD_LIBRARY_PATH_ORIG', None)
    for name, value in _ORIGINAL.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    # Never leak the PyInstaller worker state to unrelated packaged applications.
    for name in list(env):
        if name.startswith('_PYI_') or name in ('PYINSTALLER_RESET_ENVIRONMENT', 'TOUGHBOOK_HOST_PATH'):
            env.pop(name, None)
    return env


def program_invocation(argv, env=None):
    argv = list(map(str, argv))
    if not frozen():
        return argv, env
    bundled = native_program(argv[0]) if argv[0] in BUNDLED_PROGRAMS else None
    if bundled:
        return [bundled, *argv[1:]], dict(os.environ if env is None else env)
    return argv, host_environment(env)


def host_run(*args, **kwargs):
    if frozen():
        kwargs['env'] = host_environment(kwargs.get('env'))
    return subprocess.run(*args, **kwargs)


def host_popen(*args, **kwargs):
    if frozen():
        kwargs['env'] = host_environment(kwargs.get('env'))
    return subprocess.Popen(*args, **kwargs)


def configure_process(process, argv, host=False):
    process.setProgram(str(argv[0]))
    process.setArguments(list(map(str, argv[1:])))
    if host and frozen():
        from PySide6.QtCore import QProcessEnvironment
        env = QProcessEnvironment()
        for key, value in host_environment().items():
            env.insert(key, value)
        process.setProcessEnvironment(env)


def data_file(relative, fallback):
    path = resources() / relative
    return path if frozen() and path.is_file() else Path(fallback)
