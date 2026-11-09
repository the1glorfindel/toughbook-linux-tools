"""Discover live session capabilities without a desktop-name allowlist."""
import os
from .common import ToolError


def kind():
    value = os.environ.get('XDG_SESSION_TYPE', '').lower()
    if value in ('wayland', 'x11'):
        return value
    if os.environ.get('WAYLAND_DISPLAY'):
        return 'wayland'
    if os.environ.get('DISPLAY'):
        return 'x11'
    raise ToolError('Run from a local graphical session (Wayland or X11).')


def compositor():
    if kind() == 'x11':
        return 'x11'
    try:
        import dbus
        bus = dbus.SessionBus()
        if bus.name_has_owner('org.kde.KWin'):
            return 'kde'
        if bus.name_has_owner('org.gnome.Mutter.DisplayConfig'):
            return 'gnome'
    except Exception:
        pass
    return 'libinput'


def login_session():
    """Identify this user's local graphical login; fail closed if ambiguous."""
    import dbus
    bus = dbus.SystemBus()
    manager = dbus.Interface(bus.get_object('org.freedesktop.login1', '/org/freedesktop/login1'),
                             'org.freedesktop.login1.Manager')
    identity = os.environ.get('XDG_SESSION_ID')
    paths = [manager.GetSession(identity, timeout=5)] if identity else [
        row[4] for row in manager.ListSessions(timeout=5) if int(row[1]) == os.getuid()]
    found = []
    for path in paths:
        props = dbus.Interface(bus.get_object('org.freedesktop.login1', path),
                               'org.freedesktop.DBus.Properties').GetAll('org.freedesktop.login1.Session', timeout=5)
        if (int(props['User'][0]) == os.getuid() and not props.get('Remote', False)
                and props.get('Type') in ('x11', 'wayland') and props.get('Active', False)):
            found.append(props)
    if len(found) != 1:
        raise ToolError('Cannot identify one active local graphical login. Start the helper from that session.')
    return found[0]


def active_unlocked():
    try:
        props = login_session()
        return not bool(props.get('LockedHint', True))
    except Exception:
        return False
