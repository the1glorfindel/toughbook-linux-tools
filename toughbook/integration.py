"""Per-user Toughbook Tools app installation. SPDX-License-Identifier: MIT"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

from . import runtime
from .common import ToolError, config_dir, desktop_user


APP_ID = 'org.toughbook.Tools'


def paths():
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    return (data / 'toughbook-tools', data / f'applications/{APP_ID}.desktop',
            data / 'applications/org.toughbook.Buttons.desktop')


def icon_path():
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    return data / 'icons/hicolor/scalable/apps/org.toughbook.Tools.svg'


def install_app(page='overview'):
    """Install/update the complete source tree and unified launcher for this user."""
    desktop_user()
    target, launcher, old_launcher = paths()
    root = runtime.application_root()
    target.parent.mkdir(parents=True, exist_ok=True)
    launcher.parent.mkdir(parents=True, exist_ok=True)
    service = config_dir() / 'systemd/user/toughbook-buttons.service'
    had_service = service.is_file()
    was_active = False
    was_failed = False
    if had_service:
        was_active = runtime.host_run(['systemctl', '--user', 'is-active', '--quiet',
                                     'toughbook-buttons.service']).returncode == 0
        was_failed = runtime.host_run(['systemctl', '--user', 'is-failed', '--quiet',
                                     'toughbook-buttons.service']).returncode == 0
        if was_active:
            stopped = runtime.host_run(['systemctl', '--user', 'stop', 'toughbook-buttons.service'],
                                     capture_output=True, text=True)
            if stopped.returncode:
                raise ToolError('Cannot stop the existing button helper for upgrade: ' + stopped.stderr.strip())
    # Stage the full project before replacing files; this also works when run
    # from the installed copy. Preserve the legacy button helper's service state.
    with tempfile.TemporaryDirectory(prefix='toughbook-tools-') as temp:
        stage = Path(temp) / 'toughbook-tools'
        ignored = ['__pycache__', '.git', '*.pyc']
        if not runtime.frozen():
            ignored += ['dist', 'build', '.venv', '.packaging-work']
        shutil.copytree(root, stage, ignore=shutil.ignore_patterns(*ignored))
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(stage, target)
    from .screen import install_activation
    install_activation(target / 'calibrate-screen.py')
    content_root = runtime.resources(target)
    template = content_root / 'data/org.toughbook.Tools.desktop.in'
    from .buttons import exec_quote
    command = ' '.join(exec_quote(arg) for arg in runtime.command('toughbook-tools.py', '--page', page, root=target))
    content = template.read_text().replace('@PYTHON_EXEC@', command)
    temporary = launcher.with_suffix('.desktop.tmp')
    temporary.write_text(content)
    temporary.replace(launcher)
    icon = icon_path()
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(content_root / 'data/org.toughbook.Tools.svg', icon)
    # Migrate an existing helper service to the complete installed tree while
    # retaining whether it was active. Merely installing the app never starts it.
    if had_service:
        service.parent.mkdir(parents=True, exist_ok=True)
        service_command = ' '.join(exec_quote(arg, systemd=True) for arg in runtime.command('toughbook-buttons.py', root=target))
        service.write_text((content_root/'data/toughbook-buttons.service.in').read_text().replace('@SERVICE_EXEC@', service_command))
    if (config_dir() / 'autostart/org.toughbook.Buttons.desktop').exists():
        from .buttons import write_autostart
        write_autostart(target / 'toughbook-buttons.py')
    # The portal still registers as org.toughbook.Buttons and requires app info
    # for that ID. Keep its desktop file hidden from the menu.
    button_command = ' '.join(exec_quote(arg) for arg in runtime.command('toughbook-buttons.py', root=target))
    button_entry = (content_root / 'data/org.toughbook.Buttons.desktop.in').read_text().replace('@PYTHON_EXEC@', button_command)
    if 'NoDisplay=true' not in button_entry:
        button_entry += '\nNoDisplay=true\n'
    old_launcher.write_text(button_entry)
    legacy = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'toughbook-buttons'
    if legacy != target and legacy.exists():
        shutil.rmtree(legacy)
    runtime.host_run(['systemctl', '--user', 'daemon-reload'], capture_output=True)
    if was_active or was_failed:
        runtime.host_run(['systemctl', '--user', 'start', 'toughbook-buttons.service'], check=True)
    return target


def uninstall_app():
    """Remove app and optional helper integration while retaining user settings."""
    desktop_user()
    from .buttons import integration as remove_button_helper
    remove_button_helper(False)
    target, launcher, old_launcher = paths()
    launcher.unlink(missing_ok=True)
    old_launcher.unlink(missing_ok=True)
    icon_path().unlink(missing_ok=True)
    (config_dir() / 'autostart/org.toughbook.Touchscreen.desktop').unlink(missing_ok=True)
    if target.exists():
        shutil.rmtree(target)
    runtime.host_run(['systemctl', '--user', 'daemon-reload'], capture_output=True)


def status():
    target, launcher, _ = paths()
    return {'installed': launcher.is_file() and target.is_dir(),
            'source_directory': str(target), 'launcher': str(launcher)}
