# Toughbook Tools for Fedora and Ubuntu

**Toughbook Tools** is a KDE/GNOME Wayland app for three Panasonic CF-19 Mk6
issues: inaccurate finger touch, silent internal speakers, and missing tablet
buttons. It guides calibration and speaker repair, manages the four button
assignments, and shows recovery options and troubleshooting output. The optional
button driver is GPL-2.0-only; the application is MIT licensed.

| Feature | Tested hardware | Desktop support |
| --- | --- | --- |
| Finger touch | Wacom `056a:0093` finger interface | KDE Wayland tested; GNOME experimental |
| Internal speaker | Realtek ALC269VC | PipeWire/WirePlumber; Fedora KDE workflow tested |
| Tablet buttons | CF-19 Mk6 board `CF19-6`, ACPI `MAT001F` | KDE Wayland tested; GNOME physical validation pending |

Other CF-19 revisions, X11, the active Wacom pen, other touch controllers, and
other audio codecs are outside the tested scope. The detailed
[documentation index](docs/README.md) explains each issue and its recovery path.

## Quick start: Toughbook Tools GUI

### Ubuntu

On Ubuntu, log in to a GNOME or KDE **Wayland** session and run this from the
project directory as your desktop user:

```sh
bash tools/setup-ubuntu.sh
```

The script installs APT dependencies, including matching kernel headers when
available, then installs the app menu launcher. It uses Ubuntu's PySide6 package
when available or a persistent Python environment on releases such as 24.04
that lack it. It does not install or load the optional tablet-button driver;
use the Buttons page for that after checking the hardware. The launcher uses
the same Python interpreter used at installation, so keep the
`~/.local/share/toughbook-tools-python` environment if the script created it.
Ubuntu hardware behavior still needs validation on the target
installation; see [Ubuntu bring-up](docs/ubuntu.md).

### Fedora

On Fedora KDE Wayland, install the dependencies, then install the app from the
project directory as your logged-in user:

```sh
sudo dnf install python3 python3-pyside6 qt6-qtwayland python3-dbus python3-gobject libkscreen systemd-udev pipewire-utils pulseaudio-utils alsa-utils wireplumber xdg-desktop-portal xdg-desktop-portal-kde
python3 toughbook-tools.py --install
```

Open **Toughbook Tools** from KDE's application menu, or run
`python3 toughbook-tools.py`. Use its Touchscreen, Audio, and Tablet Buttons
pages for guided setup and recovery. Expand **Troubleshooting output** to see
operation results. Calibrate with only the internal display active, in normal
landscape at 100% scale; unplug wired headphones before testing the speaker.

The Buttons page can install its optional driver and distribution build packages
through an administrator authentication dialog. If Secure Boot is enabled,
follow the [signing and MOK guide](docs/driver-installation.md) before loading
the module. Enable the button shortcut helper in that page after installing the
driver.

## Independent scripts

Each tool also runs directly from the project directory:

| Script | Purpose | Detailed guide |
| --- | --- | --- |
| `python3 calibrate-screen.py` | Finger-touch calibration and restore | [Touchscreen](docs/screen-calibration.md) |
| `python3 fix-audio.py` | Speaker repair and restore | [Audio](docs/audio-fix.md) |
| `python3 toughbook-buttons.py` | Button settings, status, monitor, and helper | [Tablet buttons](docs/tablet-buttons.md) |

Run any script with `--help` for its command options. The optional button
driver can also be installed independently; see the [driver guide](docs/driver-installation.md).
For an overall status check, run `python3 toughbook-tools.py --status`.
To remove the GUI and its session integration, run
`python3 toughbook-tools.py --uninstall`; saved settings and backups remain.

For causes, detailed setup, and troubleshooting, start with the
[documentation index](docs/README.md).

See [third-party notices](THIRD_PARTY.md) and the [changelog](CHANGELOG.md).
