# Portable runtime

The x86_64 portable archive contains the Python interpreter, PySide6/Qt with
native X11 and Wayland plugins, D-Bus Python bindings, GLib/Gio introspection,
Tcl/Tk, and the userspace clients used by the fixes: pactl, pw-play, amixer,
alsactl, xinput, xrandr and wlr-randr. Their required shared libraries, ALSA
configuration and speaker-test WAV files travel with the app.

Extract the archive and run:

```sh
./toughbook-tools
./toughbook-tools --status
./toughbook-tools --install
```

Installation copies the complete runtime to your per-user application directory,
adds the menu launcher and preserves existing preferences/backups. Keep the
executable and `_internal` directory together; neither Python nor pip is needed
on the target. `--uninstall` removes app/session integration but retains settings.

The independent tools are available through the same executable:

```sh
./toughbook-tools --tool screen --status
./toughbook-tools --tool audio --status
./toughbook-tools --tool buttons --status
./toughbook-tools --tool buttons --install --backend direct
./toughbook-tools --bundle-info
```

## Host components

A portable app cannot supply a running kernel or safely replace the desktop's
services. The host provides Linux x86_64, glibc 2.36 or newer (Debian 12+, Ubuntu
24.04+, and current Fedora/Arch), its graphics drivers/fonts and Xorg or Wayland
session. Audio repair needs the host's running PipeWire/Pulse compatibility
server, WirePlumber and its matching ACP profiles. Per-user configuration is
still generated from those host profiles, so it matches the running audio stack.

Systemd/logind, D-Bus, udevadm and polkit/pkexec or sudo remain host integrations.
Optional desktop actions use the installed keyboard/launcher/locker providers,
GNOME's gsettings or KWin's matching kscreen-doctor. The optional kernel driver
ships as source: DKMS, compiler, signing tools and exact running-kernel headers
must be installed for that host. A prebuilt module would not work across arbitrary
kernels. Distribution setup and the driver page remain available for these needs.

Bundled libraries are used by the app and its native clients. Before calling
host services, package managers, privilege tools or desktop applications, the app
cleans its library/plugin environment to avoid substituting bundled libraries
into those unrelated programs.

## Building

Use a rootless Podman or Docker container and an x86_64 build machine:

```sh
python3 tools/make-bundle.py --output-dir dist
```

The build uses Debian 12 as its older glibc baseline and the pinned Python
requirements in `bundle/requirements.txt`. The artifact includes a dependency
manifest, third-party copyright/license texts, per-file hashes and an archive
SHA-256 checksum. Do not build on a newer distribution and claim compatibility
with older glibc versions. A companion `*-sources.tar.gz` contains matching Debian dependency sources,
Qt/PySide/ICU sources, Python build-tool sources, and the application source/build
recipe. Distribute it alongside the runtime and its checksums; the runtime
manifest records the companion archive's name and SHA-256. Dependencies retain
their own licenses under `_internal/licenses`; they do not acquire the app's MIT
license. `FILES.sha256` covers the extracted runtime files.

Source downloads need network access and substantial disk space. Use
`--work-dir /path/to/build-cache` to retain downloads between builds. Build tags
and Python dependencies are pinned, and native versions are inventoried; this
workflow does not claim byte-identical container or runtime builds.

Validation must include clean-host imports, relocated installation/helper paths,
and the native display smoke checks for both X11 and Wayland. Physical CF-19
calibration, sound, buttons and kernel builds remain separate acceptance checks.
