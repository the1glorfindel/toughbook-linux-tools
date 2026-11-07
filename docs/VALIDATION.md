# Validation and release status

## Evidence already available

The original implementations were confirmed by a user on a Panasonic CF-19 Mk6
with Fedora 44 KDE Wayland, a Wacom ISDv4 93 finger sensor (`056a:0093`, interface
01), and Realtek ALC269VC audio. The successful audio run included a WirePlumber
restart and a second affirmative listening result. That evidence establishes the
workarounds; it does not validate every path in this public-release refactor.

The reference installation remains untouched during release preparation. No
public-release script was applied to its live desktop, audio configuration, or
udev rules. GNOME Shell is not installed in the diagnostic environment.

## Automated validation

Run from the extracted source root:

```sh
python3 -m unittest discover -s tests -v
python3 calibrate-screen.py --help
python3 fix-audio.py --help
python3 tools/make-release.py
```

Tests use synthetic identities and temporary configuration/state directories.
They simulate D-Bus, audio playback, service restarts, and privileged commands;
they do not access sound/input devices, restart services, or invoke sudo.

Coverage includes affine recovery/composition and bad samples; fullscreen
readiness and resizing; KDE/GNOME layout checks; finger-only discovery; a
nonzero ALSA card index; missing dependencies and bounded process timeouts;
GNOME rule generation, activation failure, and recovery; KDE live rollback;
audio silence/playback/service failure, cancellation, and exact file restoration;
and retention of the first audio baseline on repeated installations.

The archive builder uses an allowlist of source, tests, and docs. It excludes
bytecode, runtime state, private logs, old prototypes, and Git metadata, normalizes
archive ownership and timestamps, and emits a SHA-256 checksum beside the archive.

## Physical acceptance checklist — pending for the public refactor

Use a separate vanilla Fedora installation or backup first. Record the Fedora,
KWin/GNOME, PipeWire/WirePlumber, and kernel versions plus CF-19 revision and
sensor/codec IDs. Do not mark an item passed solely because its simulation passes.

### KDE calibration

- Confirm fullscreen targets span the internal screen at 100% scaling.
- Measure with a finger; check center, edges, and corners after accepting.
- Verify Escape/window close and an interrupted preview restore prior settings.
- Verify correct input after logout/login and reboot, and test explicit restore.
- Repeat calibration to ensure existing correction is composed correctly.

### GNOME calibration (experimental)

- Confirm layout detection, target spacing, and finger-to-pointer emulation.
- Confirm measurement alone changes no system rule.
- Apply the candidate, inspect its exact match, and verify the pen is unaffected.
- Confirm verification refuses the old session and succeeds after logout/login.
- Measure actual target errors, reboot, and repeat verification.
- Test restore for both an originally absent rule and a preexisting tool rule.
- Test sudo cancellation and an activation error without losing the previous rule.

### Audio, each desktop

- Confirm first playback, then playback after the WirePlumber restart.
- Test normal application sound, volume, and mute at several levels.
- Verify the first undo baseline survives a second installation.
- Test logout/login, full reboot, suspend/resume, and headphone insertion/removal.
- Restore and confirm original configuration, route, default output, and mixer state.
- Confirm an unsupported card causes no mixer/configuration changes.

### Packaging/dependencies

- Extract into a path with spaces and run both entrypoints from another directory.
- Follow README dependency commands on vanilla Fedora KDE and Workstation.
- Confirm helpful failures when a required dependency is absent.
- Verify the checksum, run tests from the extracted archive, and review its file list.
- Promote GNOME from experimental only after the physical GNOME checks pass.
