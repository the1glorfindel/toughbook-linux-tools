# Toughbook Fedora Tools

Portable scripts for **Panasonic Toughbook CF-19** finger-touch calibration and
internal-speaker repair on a standard Fedora desktop. Version **0.1.0**. Applications are MIT licensed; the tablet-button module is GPL-2.0-only.
The optional experimental tablet-button feature adds a kernel module and a
per-user session helper; see [Toughbook Buttons](docs/tablet-buttons.md).

Run the audio/calibration tools with the system Python from Bash, fish, or another shell; no pip, virtual
environment, shell change, custom kernel module, or permanent service is needed.

## Compatibility

| Feature | Desktop | Validation |
| --- | --- | --- |
| Finger calibration | Fedora KDE, Wayland | Original workflow hardware-tested on Fedora 44, CF-19 Mk6, Wacom `056a:0093` |
| Finger calibration | Fedora Workstation GNOME, Wayland | Experimental; implemented and simulated, physical GNOME validation pending |
| Tablet buttons | Fedora 44 KDE, Wayland, CF-19 Mk6 (`CF19-6`) | Driver, four defaults, custom app, rotated touch and suspend/resume and login persistence hardware-tested |
| Internal speaker | Fedora PipeWire + WirePlumber 0.5+ (KDE or GNOME) | Original workflow hardware-tested on Fedora 44, CF-19 Mk6, Realtek ALC269VC |

The public-release refactor has automated tests but has **not** been reapplied to
the reference laptop or tested on a clean installation. Other CF-19 revisions
can contain different hardware. These tools refuse devices outside the listed
hardware rather than applying a generic fix. X11 desktops, the active Wacom pen,
other touch controllers, other Realtek codecs, and other laptops are not covered.

Calibration requires the internal display alone, normal landscape orientation,
and 100% scaling. Disconnect/disable external screens first. Keep the physical
keyboard or touchpad available for Enter/Escape and recovery. Read the
[screen explanation](docs/screen-calibration.md) and
[audio explanation](docs/audio-fix.md) before running.

## Fedora dependencies

Install only the dependencies for the feature you need. `sudo` is for package
installation and the optional GNOME udev-rule operation; run the tools themselves
as your regular desktop user.

Screen calibration, both desktops:

```sh
sudo dnf install python3 python3-tkinter python3-dbus xorg-x11-server-Xwayland systemd-udev
```

KDE additionally uses `kscreen-doctor` for display discovery:

```sh
sudo dnf install libkscreen
```

Audio (the standard Fedora PipeWire/WirePlumber stack must already be active):

```sh
sudo dnf install python3 pipewire-utils pulseaudio-utils alsa-utils wireplumber
```

`pactl` is supplied by `pulseaudio-utils` and communicates with Fedora's
`pipewire-pulse` compatibility server. Installing these utilities does not mean
replacing PipeWire with the PulseAudio server. `pw-play` is used for playback;
the tools do not assume an ALSA PCM named `pulse` exists.

Package names were checked against the reference Fedora 44 RPM ownership and
Fedora package metadata. The tools use system `systemctl`, `install`, and `rm`
commands provided on standard Fedora desktops; GNOME installation also needs
`sudo`. No dependencies are downloaded automatically.

## Run from the extracted directory

Both entrypoints support `--help`. Use `--status` to inspect eligible devices.
If more than one eligible device is listed, select one with `--device NAME`.

```sh
python3 calibrate-screen.py --status
python3 calibrate-screen.py
```

Tap the nine crosses with your **finger** or a passive stylus. In KDE, test the
preview, press Enter to keep it, or Escape to undo. KDE saves the setting in your
user configuration and restores it on login.

On GNOME, Enter saves a **candidate**, not a live change. The tool prints a command
using the candidate's backup path:

```sh
python3 calibrate-screen.py --apply /path/printed/by/the/tool.json
```

This installs one narrowly matched system udev rule and refreshes properties for
that event device. Log out and back in manually, then run the printed verification
command. Do not change display layout or scaling between measurement and verification.

```sh
python3 calibrate-screen.py --verify /path/printed/by/the/tool.json
```

Audio:

```sh
python3 fix-audio.py --status
python3 fix-audio.py
```

Unplug wired headphones and answer the listening prompts. The tool tests the
mixer workaround, installs a private per-user profile only if you hear sound,
restarts WirePlumber, and tests again. A successful run selects the internal
speaker as the default output. It may briefly interrupt other audio streams.
If playback or confirmation fails, it restores previous configuration and mixer
state. Success does not establish headphone-jack switching behavior; test that
separately on your hardware.

## Saved state and undo

State lives under `$XDG_STATE_HOME/toughbook-fedora-tools`, normally
`~/.local/state/toughbook-fedora-tools`. It includes private JSON backups,
calibration results, and ALSA state files. Nothing is written into the source
folder, so the scripts can run from a read-only extraction or a path with spaces.

Use the **exact backup path printed by the tool**:

```sh
python3 calibrate-screen.py --restore /path/to/screen-backup.json
python3 fix-audio.py --restore /path/to/audio-backup.json
```

For audio, retain the JSON **and its adjacent `.alsa-state` file**. Repeated
successful installations retain the first installation's undo baseline; the tool
prints it again and `fix-audio.py --status` reports it. If the directory already
contained a manually installed workaround, that is treated as preexisting user
configuration and restored on uninstall.

KDE restoration is live. GNOME restoration removes/replaces only this tool's
rule, refreshes that device, and requires logout/login. GNOME's rule is system-wide
for the matched hardware; KDE calibration and audio settings are per-user. No
command automatically logs you out or reboots the computer.

Ordinary cancellation and application errors roll back incomplete live changes.
A power loss or `SIGKILL` cannot run cleanup: use the printed backup manually.
GNOME verification failure keeps the backup/rule for inspection; use `--restore`
to undo it. Do not delete state until satisfied with the fix and your undo needs.
Deleting the extracted scripts alone does not uninstall saved configuration.

Exit codes: `0` success/status, `1` error or incomplete recovery, `2` cancelled or
negative verification, `130` terminal interruption/EOF. Unexpected hardware or
package formats stop with an explanatory error.

## Troubleshooting, development, and release

- A successful `--help` does not prove all desktop dependencies are installed.
- Run inside the real desktop terminal, not over SSH or in a restricted container.
- For service failures, inspect `journalctl --user -u wireplumber -b`.
- For missing outputs, select **Analog Stereo** in desktop Sound settings first.
- After a PipeWire profile package update, rerun the audio tool to regenerate its
  private copies from the newly installed defaults, retaining the undo baseline.
- Avoid posting complete backups/status output publicly without review: runtime
  output can include local paths and device identifiers.

Run the dependency-free tests and build a clean archive:

```sh
python3 -m unittest discover -s tests -v
python3 tools/make-release.py
```

See [validation](docs/VALIDATION.md), [third-party notices](THIRD_PARTY.md), and
[the changelog](CHANGELOG.md). No uploaded release or remote repository is created
by these tools or the archive builder.

## Configurable tablet buttons

Run `python3 toughbook-buttons.py --help` or see the [setup and customization guide](docs/tablet-buttons.md). The GTK4 app includes defaults, custom applications/commands, driver/session status, and live identification. The driver builds against the target Fedora kernel and the KDE workflows are hardware-tested on the Mk6. Login autostart and saved assignments survive logout/login; GNOME remains awaiting physical validation.
