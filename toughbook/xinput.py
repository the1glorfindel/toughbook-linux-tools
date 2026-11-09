"""Native X11 calibration, matched to the discovered finger event node only."""
import re
from . import session
from .affine import validate
from .common import ToolError, require, run, udev_properties


class MappingNotApplied(ToolError):
    """The same finger device remains present but its matrix did not stick."""


class XInput:
    def __init__(self, device):
        if session.kind() != 'x11':
            raise ToolError('XInput calibration requires native X11; use the libinput workflow on Wayland.')
        require('xinput')
        self.identity = device
        node = '/dev/input/' + device['event']
        self.node = node
        found = []
        for identity in run('xinput', 'list', '--id-only').stdout.split():
            if not identity.isdigit():
                continue
            props = run('xinput', 'list-props', identity).stdout
            match = re.search(r'Device Node \(\d+\):\s*"([^"]+)"', props)
            if match and match[1] == node:
                found.append(identity)
        if len(found) != 1:
            raise ToolError('Cannot identify exactly one native X11 finger device. Do not use xinput under XWayland.')
        self.id = found[0]

    def get(self):
        if 'identity' in self.identity:
            actual = udev_properties(self.identity['event'])
            if any(actual.get(key, '') != value for key, value in self.identity['identity'].items()):
                raise ToolError('The finger device identity changed; rediscover it before calibrating.')
        props = run('xinput', 'list-props', self.id).stdout
        node = re.search(r'Device Node \(\d+\):\s*"([^"]+)"', props)
        if not node or node[1] != self.node:
            raise ToolError('The XInput device changed; refusing to change another input device.')
        match = re.search(r'Coordinate Transformation Matrix \(\d+\):\s*([^\n]+)', props)
        if not match:
            raise ToolError('The X11 finger device has no Coordinate Transformation Matrix.')
        values = validate(match[1].split(','), 9)
        if values[6:] != [0., 0., 1.]:
            raise ToolError('Unsupported X11 perspective transform.')
        return {'matrix': values[:6]}

    def set(self, matrix, output=None):
        matrix = validate(matrix)
        self.get()  # XInput IDs can be reused after a device disconnects.
        run('xinput', 'set-prop', self.id, 'Coordinate Transformation Matrix',
            *matrix, 0, 0, 1)
        actual = self.get()['matrix']
        if max(abs(a-b) for a,b in zip(actual, matrix)) > 1e-4:
            raise MappingNotApplied('X11 did not accept the calibration.')

    def restore(self, previous):
        self.set(previous['matrix'])
