# Toughbook Fedora Tools

**Toughbook Tools** is a Fedora KDE Wayland app for three Panasonic CF-19 Mk6
issues: inaccurate finger touch, silent internal speakers, and missing tablet
buttons. It guides calibration and speaker repair, manages the four button
assignments, and shows recovery options and troubleshooting output. The optional
button driver is GPL-2.0-only; the application is MIT licensed.

| Feature | Tested hardware | Desktop support |
| --- | --- | --- |
| Finger touch | Wacom `056a:0093` finger interface | KDE Wayland tested; GNOME experimental |
| Internal speaker | Realtek ALC269VC | Fedora PipeWire/WirePlumber; original KDE workflow tested |
| Tablet buttons | CF-19 Mk6 board `CF19-6`, ACPI `MAT001F` | KDE Wayland tested; GNOME physical validation pending |

Other CF-19 revisions, X11, the active Wacom pen, other touch controllers, and
other audio codecs are outside the tested scope. The detailed
[documentation index](docs/README.md) explains each issue and its recovery path.

## Quick start on Fedora KDE

From the extracted project directory, install the desktop dependencies, then
install and open the app as your logged-in user:

```sh
sudo dnf install python3 python3-pyside6 qt6-qtwayland python3-dbus python3-gobject libkscreen systemd-udev pipewire-utils pulseaudio-utils alsa-utils wireplumber xdg-desktop-portal xdg-desktop-portal-kde
python3 toughbook-tools.py --install
python3 toughbook-tools.py
```

Open **Toughbook Tools** from KDE's application menu afterward. The app has
Touchscreen, Audio, and Tablet Buttons pages. Its expandable troubleshooting
output shows command results. For calibration, use only the internal display in
normal landscape at 100% scale. For the speaker test, unplug wired headphones.

The Buttons page can install its optional driver and Fedora build packages
through an administrator authentication dialog. If Secure Boot is enabled,
follow the [signing and MOK guide](docs/driver-installation.md) before loading
the module. Enable the button shortcut helper in that page after installing the
driver.

Run `python3 toughbook-tools.py --status` to inspect feature readiness or
`python3 toughbook-tools.py --uninstall` to remove the app and its session
integration. Existing [command-line workflows](docs/README.md) remain available.

See [third-party notices](THIRD_PARTY.md) and the [changelog](CHANGELOG.md).
