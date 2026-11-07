"""Small dependency-free affine fit and format conversions. SPDX-License-Identifier: MIT"""
import math
from .common import ToolError

IDENTITY = [1., 0., 0., 0., 1., 0.]
TARGETS = [(x, y) for y in (.12, .5, .88) for x in (.12, .5, .88)]


def validate(values, length=6):
    values = list(map(float, values))
    if len(values) != length or not all(math.isfinite(v) for v in values):
        raise ToolError('Invalid calibration matrix or sample.')
    return values


def solve(rows, targets):
    m = [[sum(v[i] * v[j] for v in rows) for j in range(3)] +
         [sum(v[i] * t for v, t in zip(rows, targets))] for i in range(3)]
    for i in range(3):
        k = max(range(i, 3), key=lambda k: abs(m[k][i]))
        m[i], m[k] = m[k], m[i]
        if abs(m[i][i]) < 1e-9:
            raise ToolError('Samples do not span the screen. Please retry.')
        divisor = m[i][i]
        m[i] = [v / divisor for v in m[i]]
        for k in range(3):
            if k != i:
                divisor = m[k][i]
                m[k] = [v - divisor * u for v, u in zip(m[k], m[i])]
    return [row[3] for row in m]


def fit(samples, width, height):
    if len(samples) != len(TARGETS) or width <= 0 or height <= 0:
        raise ToolError('Nine samples and valid fullscreen dimensions are required.')
    rows = [validate([*p, 1], 3) for p in samples]
    a, b, c = solve(rows, [x for x, y in TARGETS])
    d, e, f = solve(rows, [y for x, y in TARGETS])
    error = max(math.hypot((a*x+b*y+c-tx)*width, (d*x+e*y+f-ty)*height)
                for (x, y, _), (tx, ty) in zip(rows, TARGETS))
    if error > 20:
        raise ToolError(f'Inconsistent taps (maximum fit error {error:.1f} px). Please retry.')
    if a*e-b*d <= 0:
        raise ToolError('Unexpected reversed axes. Use normal landscape orientation.')
    return validate([a, b, c, d, e, f]), error


def compose(new, old):
    a, b, c, d, e, f = validate(new)
    g, h, i, j, k, l = validate(old)
    return [a*g+b*j, a*h+b*k, a*i+b*l+c, d*g+e*j, d*h+e*k, d*i+e*l+f]


def to_kwin(values):
    a, b, c, d, e, f = validate(values)
    # KWin embeds the libinput 3x3 transform in the top-left of a 4x4 matrix.
    return [a,b,c,0, d,e,f,0, 0,0,1,0, 0,0,0,1]


def from_kwin(text):
    values = validate(text.split(','), 16)
    if any(abs(values[i]-expected) > 1e-6 for i, expected in
           [(3,0),(7,0),(8,0),(9,0),(10,1),(11,0),(12,0),(13,0),(14,0),(15,1)]):
        raise ToolError('Unsupported existing KWin transformation.')
    return values[:3] + values[4:7]
