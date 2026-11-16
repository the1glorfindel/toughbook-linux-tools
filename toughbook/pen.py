"""Native KDE Wayland mapping for the reference CF-19 pen side button. MIT."""
from pathlib import Path
import shutil
from . import session
from .common import ToolError, config_dir, state_dir, save_json, load_json, run, udev_properties

ACTIONS = {'default': None, 'right': 'TabletToolButton,273',
           'middle': 'TabletToolButton,274', 'left': 'TabletToolButton,272'}
MISSING = '__TOUGHBOOK_NO_PEN_MAPPING__'
KEY = '331'  # Linux BTN_STYLUS, not the pen tip or a front-panel button.


def connect():
    if session.compositor() != 'kde' or session.kind() != 'wayland':
        raise ToolError('Pen side-button selection currently requires KDE Plasma Wayland. GNOME and X11 mappings are not managed by this control.')
    import dbus
    bus = dbus.SessionBus()
    plugins = bus.get_object('org.kde.KWin', '/Plugins')
    props = dbus.Interface(plugins, 'org.freedesktop.DBus.Properties')
    available = list(map(str, props.Get('org.kde.KWin.Plugins', 'AvailablePlugins', timeout=5)))
    candidates = [name for name in available if name.endswith('_buttonrebinds') or name == 'buttonrebinds']
    if len(candidates) != 1:
        raise ToolError('KWin does not expose a supported button-rebinding plugin.')
    found = []
    for event in Path('/sys/class/input').glob('event*'):
        if (event/'device/name').read_text().strip() != 'Wacom ISDv4 93 Pen':
            continue
        identity = udev_properties(event.name)
        if (identity.get('ID_VENDOR_ID'), identity.get('ID_MODEL_ID'), identity.get('ID_USB_INTERFACE_NUM')) != ('056a','0093','00'):
            continue
        obj = bus.get_object('org.kde.KWin', '/org/kde/KWin/InputDevice/'+event.name)
        values = dbus.Interface(obj, 'org.freedesktop.DBus.Properties').GetAll('org.kde.KWin.InputDevice', timeout=5)
        if values.get('tabletTool'):
            found.append(str(values['name']))
    if len(found) != 1:
        raise ToolError('Cannot identify exactly one supported CF-19 pen device.')
    pair = next(((shutil.which('kreadconfig'+v), shutil.which('kwriteconfig'+v))
                 for v in ('6','5') if shutil.which('kreadconfig'+v) and shutil.which('kwriteconfig'+v)), None)
    if pair is None:
        raise ToolError('KDE configuration utilities are missing; install the KDE desktop dependencies.')
    loaded = list(map(str, props.Get('org.kde.KWin.Plugins', 'LoadedPlugins', timeout=5)))
    return {'name':found[0], 'reader':pair[0], 'writer':pair[1]}


def arguments(context):
    return ['--file', str(config_dir()/'kcminputrc'), '--group','ButtonRebinds',
            '--group','TabletTool', '--group',context['name'], '--key',KEY]


def read(context):
    value = run(context['reader'], *arguments(context), '--default', MISSING).stdout.rstrip('\n')
    return None if value == MISSING else value


def write(context, value):
    args = ['--delete'] if value is None else [value]
    run(context['writer'], *arguments(context), *args)


def backup_path():
    return state_dir()/'pen-side-button.json'


def status():
    context = connect(); value = read(context)
    action = next((key for key, mapping in ACTIONS.items() if mapping == value), 'custom')
    if action == 'custom':
        action = next((key for key, mapping in ACTIONS.items() if mapping and value == mapping.replace('TabletToolButton,', 'MouseButton,')), 'custom')
    return {'device':context['name'], 'action':action, 'mapping':value}


def apply(action):
    if action not in ACTIONS:
        raise ToolError('Select Desktop default, Right click, Middle click or Left click.')
    context = connect(); previous = read(context); path = backup_path()
    if path.exists():
        baseline = load_json(path, 'pen-side-button')
        if baseline['device'] != context['name']:
            raise ToolError('The saved pen mapping belongs to another device.')
    else:
        save_json(path, {'kind':'pen-side-button', 'device':context['name'], 'previous':previous})
    try:
        write(context, ACTIONS[action])
        if read(context) != ACTIONS[action]:
            raise ToolError('KDE did not retain the requested pen mapping.')
    except Exception:
        write(context, previous)
        raise
    return status()


def restore():
    context = connect(); path = backup_path(); baseline = load_json(path, 'pen-side-button')
    if baseline['device'] != context['name']:
        raise ToolError('The saved pen mapping belongs to another device.')
    previous = read(context)
    try:
        write(context, baseline['previous'])
        if read(context) != baseline['previous']:
            raise ToolError('KDE did not retain the restored pen mapping; the backup has been kept.')
    except Exception:
        write(context, previous)
        raise
    path.unlink()
    return status()
