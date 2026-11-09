# Development and source archives

## Run checks

Install the GUI dependencies from the main README first. From the repository root:

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
```

On Debian releases using the private PySide6 environment, run tests with
`~/.local/share/toughbook-tools-python/bin/python` instead of `python3`.

The suite uses mocks and temporary state for desktop, audio, device discovery,
and rollback behavior; it does not prove physical hardware behavior. Some tests
also use available system tools such as a C compiler and udev/systemd validators.
The portable driver decoder test is part of the suite and compiles with
`-std=c99 -Wall -Wextra -Werror` when a compiler is available.

For a direct decoder check:

```sh
cc -std=c99 -Wall -Wextra -Werror -o /tmp/test-hbtn driver/test-hbtn-decode.c
/tmp/test-hbtn
```

Building/loading the kernel module is a separate, host-kernel-specific check;
see [driver installation](driver-installation.md). Physical button, display,
touch, sound, suspend, and login checks are recorded in
[validation status](VALIDATION.md).

## Native X11 and Wayland smoke checks

`tools/check-display.py` exercises real Qt platform plugins, stable fullscreen
geometry, nine synthetic touch events, preview acceptance, all GUI pages and clean
shutdown. Run it on an isolated test display, not as a substitute for physical
hardware acceptance. The script isolates app configuration/state and D-Bus and
never applies a real calibration/audio repair or starts the button helper.
It requires the GUI dependencies and PySide6's QtTest module. Optional display-test
packages are Xvfb, Openbox, xauth/xvfb-run and Weston; they are not runtime app
requirements and are not installed by ordinary setup.

For X11, start an Xvfb server at 1024×768 and a fullscreen-capable window manager
such as Openbox, then run inside that display:

```sh
XDG_SESSION_TYPE=x11 QT_QPA_PLATFORM=xcb python3 tools/check-display.py --expect x11 --xvfb-input
```

For example, with distribution-provided `xvfb-run` and Openbox:

```sh
xvfb-run -a -s '-screen 0 1024x768x24' sh -c 'openbox --sm-disable & sleep 1; XDG_SESSION_TYPE=x11 QT_QPA_PLATFORM=xcb python3 tools/check-display.py --expect x11 --xvfb-input'
```

`--xvfb-input` requires the synthetic Xvfb mouse/keyboard and applies, reads back
and restores a non-identity matrix through the production XInput code. It verifies
the unrelated keyboard is unchanged. It refuses other input devices. A bare
Xvfb server without a window manager may not honor fullscreen and is insufficient.

For native Wayland, start a private headless Weston compositor with software
rendering, a 1024×768 output and kiosk shell, without enabling XWayland. Point the
client's `XDG_RUNTIME_DIR`/`WAYLAND_DISPLAY` at its private socket, then run:

```sh
XDG_SESSION_TYPE=wayland QT_QPA_PLATFORM=wayland python3 tools/check-display.py --expect wayland
```

On the tested Weston 15, its headless flags are `--backend=headless`,
`--renderer=pixman`, `--shell=kiosk-shell.so`, `--width=1024`, `--height=768`,
`--no-config` and `--idle-time=0`. Use a private runtime directory (mode 0700)
and socket; older Weston versions may use different backend flags. Repeat with
`--transform=rotate-180`, then query metadata without opening targets:

```sh
XDG_SESSION_TYPE=wayland QT_QPA_PLATFORM=wayland python3 tools/check-display.py --expect wayland --metadata-only --expect-rotated
```

A pass on either protocol requires its actual Qt plugin; `offscreen` and XWayland
as a substitute for native Wayland are rejected. Full suite protocol checks use:

```sh
XDG_SESSION_TYPE=x11 QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
XDG_SESSION_TYPE=wayland QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
```

The native smoke check intentionally bypasses hardware-changing operations, so
calibration accuracy, physical buttons, audible playback and persistence remain
separate checks in [validation status](VALIDATION.md).

## Build and inspect a source archive

```sh
python3 tools/make-release.py
python3 -m unittest discover -s tests -p test_release.py -v
```

The archive is written beside the repository by default, with a SHA-256 file.
The builder allowlists source and test files, all Markdown under `docs/`, the
driver sources/license/build files, the shared Linux setup entrypoint and legacy alias, desktop integration
templates, and the app icon.
It omits Git metadata, bytecode, and runtime state, and normalizes timestamps
and ownership for reproducibility. The release test checks repeatability,
required content, extracted command-line help, and absence of local home paths.

No command here publishes an archive or changes a Git tag.
