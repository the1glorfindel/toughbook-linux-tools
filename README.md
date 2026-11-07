# Toughbook Fedora Tools

Small Fedora utilities for three Panasonic CF-19 Mk6 issues: inaccurate finger
touch coordinates, silent internal speakers, and missing tablet-button actions.
The calibration and audio tools use Fedora's existing desktop/audio stack. The
optional button feature adds a narrowly matched kernel module and a per-user
GTK settings app. The applications are MIT licensed; the module is GPL-2.0-only.

## Supported setup

| Feature | Verified setup | Other support |
| --- | --- | --- |
| Finger calibration | CF-19 Mk6, Fedora 44 KDE Wayland | GNOME Wayland is experimental; physical validation pending |
| Internal speaker | CF-19 Mk6, Fedora 44 PipeWire/WirePlumber | KDE and GNOME |
| Tablet buttons | CF-19 Mk6 (`CF19-6`), Fedora 44 KDE Wayland | GNOME physical validation pending |

Other CF-19 revisions, X11, the Wacom pen, other touch controllers, and other
audio codecs are outside the tested scope. The tools check hardware before
changing settings. Detailed causes, limitations, and recovery steps are in the
[documentation index](docs/README.md).

## Quick start

Run the tools as your logged-in desktop user. Use `--help` for all options.

### Finger-touch calibration

```sh
sudo dnf install python3 python3-tkinter python3-dbus xorg-x11-server-Xwayland systemd-udev libkscreen
python3 calibrate-screen.py --status
python3 calibrate-screen.py
```

Use one internal display, normal landscape orientation, and 100% scaling. Tap
the targets with a finger or passive stylus. KDE previews the result; Enter
keeps it and Escape restores the previous setting. GNOME requires a separate
apply and logout/login; follow the [calibration guide](docs/screen-calibration.md).

### Internal-speaker repair

```sh
sudo dnf install python3 pipewire-utils pulseaudio-utils alsa-utils wireplumber
python3 fix-audio.py --status
python3 fix-audio.py
```

Unplug wired headphones and follow both listening checks. Audio may briefly
interrupt while WirePlumber restarts. See the [audio guide](docs/audio-fix.md)
for rollback and troubleshooting.

### Tablet buttons (optional)

```sh
sudo dnf install python3 python3-gobject gtk4 python3-dbus xdg-desktop-portal xdg-desktop-portal-kde libkscreen make gcc kernel-devel-$(uname -r) dkms mokutil openssl
python3 toughbook-buttons.py --status
```

If Secure Boot is enabled, complete the signing and MOK enrollment steps in the
[driver guide](docs/driver-installation.md) before loading the module.

```sh
sudo bash driver/install.sh
sudo modprobe panasonic-hbtn
python3 toughbook-buttons.py --install
python3 toughbook-buttons.py
```

The defaults toggle the on-screen keyboard, open the application launcher,
rotate the internal display, and lock the session. Assignments can be changed
in the app. GNOME dependencies and behavior are documented in the
[button guide](docs/tablet-buttons.md).

## Documentation

- [Documentation index](docs/README.md) — issue guides, driver setup, and development.
- [Third-party notices](THIRD_PARTY.md) and [changelog](CHANGELOG.md).
