"""Read the driver's dedicated evdev node exclusively, leaving keyboards alone."""
import fcntl
import os
from pathlib import Path
import stat
import struct

from . import buttons, session
from .buttons import Portal
from .common import ToolError

PACKET = struct.Struct('llHHi')
KEYS = dict(zip(range(183, 187), buttons.BUTTONS))
EVIOCGRAB = 0x40044590  # Linux _IOW('E', 0x90, int).


def grab_dedicated(fd, root=Path('/sys/dev/char')):
    """Revalidate the opened descriptor before suppressing desktop shortcuts."""
    info = os.fstat(fd)
    device = (root / f'{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}' / 'device').resolve()
    if (not stat.S_ISCHR(info.st_mode) or 'MAT001F:' not in str(device)
            or (device / 'name').read_text().strip() != 'Panasonic CF-19 Tablet Buttons'):
        raise ToolError('The opened device is not the dedicated tablet-button driver.')
    fcntl.ioctl(fd, EVIOCGRAB, 1)


class Direct(Portal):
    """Reuse helper pause controls while sourcing events from the four-key device."""
    def __init__(self):
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)
        self.dbus = dbus
        self.bus = dbus.SessionBus(private=True)
        self.active = set()
        self.paused = False
        self.pause_timer = self.pause_match = None
        self.fd = self.watch = self.retry = None
        self.buffer = b''
        self.dropped = False
        self.last_error = None

    def configure(self):
        raise ToolError('Dedicated-device mode uses the assignments in this app; no portal approval is needed.')

    def start(self):
        from gi.repository import GLib
        buttons.record_status(backend='direct', shortcuts={key: row[2] + ' (dedicated device)' for key,row in buttons.BUTTONS.items()})
        self.connect_device()
        self.retry = GLib.timeout_add_seconds(1, self.connect_device)

    def connect_device(self):
        from gi.repository import GLib
        if self.fd is not None:
            return True
        try:
            paths = buttons.devices()
            if len(paths) != 1:
                raise ToolError(f'Expected one dedicated tablet device, found {len(paths)}. Install/load the driver.')
            self.fd = os.open(paths[0], os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
            grab_dedicated(self.fd)
            self.watch = GLib.io_add_watch(self.fd, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.readable)
            self.buffer = b''
            self.dropped = False
            self.active.clear()
            self.last_error = None
            buttons.record_status(error='')
        except (OSError, ToolError) as exc:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            message = str(exc) + ' Use the supplied dedicated-device uaccess rule; do not run as root or join the input group.'
            if message != self.last_error:
                buttons.record_status(error=message)
                self.last_error = message
        return True

    def readable(self, fd, condition):
        from gi.repository import GLib
        try:
            if condition & (GLib.IO_HUP | GLib.IO_ERR):
                raise OSError('Tablet device disconnected')
            data = os.read(fd, PACKET.size * 64)
            if not data:
                raise OSError('Tablet device disconnected')
            self.feed(data)
            return True
        except BlockingIOError:
            return True
        except OSError as exc:
            os.close(self.fd)
            self.fd = self.watch = None
            self.active.clear()
            buttons.record_status(error=str(exc) + '; waiting for the dedicated device to return.')
            return False

    def feed(self, data):
        self.buffer += data
        while len(self.buffer) >= PACKET.size:
            packet, self.buffer = self.buffer[:PACKET.size], self.buffer[PACKET.size:]
            _, _, kind, code, value = PACKET.unpack(packet)
            if kind == 0 and code == 3:  # SYN_DROPPED: discard unreliable transitions.
                self.active.clear()
                self.dropped = True
                continue
            if self.dropped:
                if kind == 0 and code == 0:
                    self.dropped = False
                continue
            if kind != 1 or code not in KEYS or value not in (0, 1):
                continue
            key = KEYS[code]
            if value == 0:
                if key in self.active:
                    self.button_event(key, 0)
                self.active.discard(key)
                continue
            if key in self.active:
                continue
            self.active.add(key)
            self.button_event(key, 1)
            buttons.record_status(last_button=buttons.BUTTONS[key][0])
            if self.paused:
                continue
            if not session.active_unlocked():
                buttons.record_status(error='Actions suppressed: session is inactive, locked or ambiguous.')
                continue
            try:
                buttons.execute(buttons.load_settings()[key])
                buttons.record_status(error='')
            except Exception as exc:
                buttons.record_status(error=str(exc))

    def close(self):
        from gi.repository import GLib
        self.resume_actions()
        for source in (self.watch, self.retry):
            if source is not None:
                GLib.source_remove(source)
        if self.fd is not None:
            os.close(self.fd)
        self.fd = self.watch = self.retry = None
