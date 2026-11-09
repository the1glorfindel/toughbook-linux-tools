"""Query the actual display through native Qt, independently of the desktop shell."""
import json
import os
import sys

def main():
    # XWayland's synthetic output geometry must not stand in for native Wayland.
    os.environ['QT_QPA_PLATFORM'] = 'wayland' if os.environ.get('XDG_SESSION_TYPE') != 'x11' and (os.environ.get('XDG_SESSION_TYPE') == 'wayland' or os.environ.get('WAYLAND_DISPLAY')) else 'xcb'
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication(sys.argv)
    screens = app.screens()
    output = []
    for screen in screens:
        geometry = screen.geometry()
        output.append({'name': screen.name(), 'width': geometry.width(), 'height': geometry.height(),
                       'x': geometry.x(), 'y': geometry.y(), 'scale': screen.devicePixelRatio(),
                       'normal': screen.orientation() in (Qt.ScreenOrientation.PrimaryOrientation,
                                                         Qt.ScreenOrientation.LandscapeOrientation)})
    print(json.dumps(output))


if __name__ == '__main__':
    main()
