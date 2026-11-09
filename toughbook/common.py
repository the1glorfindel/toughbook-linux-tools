"""Shared process, state, and hardware helpers. SPDX-License-Identifier: MIT"""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


class ToolError(Exception):
    pass


def run(*args, timeout=20, check=True, env=None):
    try:
        result = subprocess.run([str(a) for a in args], capture_output=True,
                                text=True, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolError(f'Cannot run {args[0]}: {exc}') from exc
    if check and result.returncode:
        raise ToolError(f'{args[0]} failed: {result.stderr.strip() or result.stdout.strip()}')
    return result


def require(*programs):
    missing = [p for p in programs if not shutil.which(p)]
    if missing:
        raise ToolError('Missing programs: ' + ', '.join(missing) + '. See README dependencies.')


def desktop_user():
    if os.geteuid() == 0:
        raise ToolError('Run as your desktop user, without sudo. System changes request authorization separately.')


def check_model(root=Path('/sys')):
    name = (root / 'class/dmi/id/product_name').read_text().strip()
    if not name.upper().startswith('CF-19'):
        raise ToolError('This release supports Panasonic CF-19 hardware only.')
    return name


def config_dir():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config').resolve()


def state_dir(create=True):
    path = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'toughbook-fedora-tools'
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def load_json(path, kind=None):
    data = json.loads(Path(path).read_text())
    if kind and data.get('kind') != kind:
        raise ToolError(f'Not a {kind} backup.')
    return data


def backup_path(prefix):
    return state_dir() / f'{prefix}-{time.time_ns()}.json'


def snapshot(paths):
    return {str(p): base64.b64encode(p.read_bytes()).decode() if p.exists() else None
            for p in paths}


def restore_files(files, allowed):
    if set(files) != {str(p) for p in allowed}:
        raise ToolError('Backup paths do not match this user/configuration directory.')
    for name, content in files.items():
        path = Path(name)
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(content, validate=True))


def udev_properties(event):
    result = run('udevadm', 'info', '--query=property', '--name', f'/dev/input/{event}')
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def touch_devices(root=Path('/sys/class/input')):
    devices = []
    for event in sorted(root.glob('event*')):
        props = udev_properties(event.name)
        if (props.get('ID_VENDOR_ID') == '056a' and props.get('ID_MODEL_ID') == '0093'
                and props.get('ID_INPUT_TOUCHSCREEN') == '1'
                and props.get('ID_USB_INTERFACE_NUM') == '01'):
            identity = {k: props.get(k, '') for k in
                        ('ID_VENDOR_ID', 'ID_MODEL_ID', 'ID_USB_INTERFACE_NUM', 'ID_SERIAL', 'ID_PATH')}
            devices.append({'event': event.name, 'identity': identity, 'properties': props})
    return devices


def choose(items, key, selected=None):
    found = [item for item in items if selected is None or item[key] == selected]
    if len(found) != 1:
        raise ToolError('Expected one eligible device. Use --device with an entry from --status.')
    return found[0]


def confirm(prompt):
    return input(prompt + ' [y/N] ').strip().lower() in ('y', 'yes')
