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

Ubuntu compatibility is prepared in code and documentation but has not yet been
validated on a live Ubuntu installation. In particular, confirm the
WirePlumber 0.4 audio path on Ubuntu 24.04 and the installed kernel's DKMS
build/signing behavior before treating those features as verified.

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

Use a separate vanilla Debian, Ubuntu, Fedora or Arch installation or backup first. Record the distribution,
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
- Follow README setup commands on vanilla Fedora KDE/Workstation, Debian/Ubuntu
  GNOME/KDE and Arch KDE/GNOME, recording package and Python-interpreter versions.
- Confirm helpful failures when a required dependency is absent.
- Verify the checksum, run tests from the extracted archive, and review its file list.
- Promote GNOME from experimental only after the physical GNOME checks pass.

## Tablet buttons (0.1.0)

Hardware validation on Fedora 44 KDE Wayland, CF-19 Mk6 (`CF19-6`), running
`7.2.15-200.fc44.x86_64`:

- The module builds for the running kernel; portable C decoder tests compile with
  `-std=c99 -Wall -Wextra -Werror`. BTF generation is skipped without vmlinux/pahole;
  module linking and DKMS installation succeed. DKMS signs the installed module.
- The user’s ordered physical test established full HINF pairs `0x3a/0x3b`
  (Keyboard), `0x38/0x39` (Circle), `0x36/0x37` (Screen/Rotation), and `0x34/0x35`
  (Key). The driver accepts those exact pairs and rejects unknown firmware values.
- Dedicated-device monitoring confirmed F13–F16 press/release pairs without a
  device grab or ordinary-keyboard monitoring. A narrowly matched udev rule grants
  the active user access and marks the four-key device as a keyboard for libinput.
- KWin recognizes the device. The Global Shortcuts portal grants the physical
  desktop keysyms: Tools, Launch (5), Launch (6), Launch (7), respectively. Conflicts
  and the provisional shifted bindings were corrected through the portal dialog.
- The user confirmed all four defaults, keyboard toggling, application menu,
  rotation through four orientations with accurate finger touch, and session lock.
  The calibration matrix and touchscreen output mapping match the saved baseline.
- The user confirmed GUI customization with Emoji Selector on Circle, then
  suspend/resume and working buttons afterward. Kernel logs confirm a deep S3
  suspend and resume. The user’s custom Circle assignment is retained.
- Driver removal/reinstallation was exercised during bring-up. Live per-user
  uninstall removed app, menu, autostart and service entries; reinstall restored
  them. Preferences were byte-for-byte unchanged. Desktop entries and the user
  service pass their installed validators. The helper is left running.
- All 72 automated tests pass, including decoder vectors, argument handling,
  persistence, discovery, portal requests/conflicts/restarts, duplicate activation
  suppression, mocked desktop actions/recovery, removal and archive reproducibility.

Logout/login validation subsequently passed: the helper started automatically
at 21:09:37 CST on 2026-11-06, restored all four portal bindings and the saved
Circle → Emoji Selector assignment, and reported no errors. The user confirmed
all four buttons worked as before. The touchscreen calibration matrix and output
assignment remained identical to the saved baseline.
GNOME remains awaiting physical validation. Hold bindings and worn-switch debounce
are outside this first version. See [tablet-button guide](tablet-buttons.md).
Version 0.1.0 includes these changes. The existing `v0.0.1` tag and archives remain unchanged.

## Unified Toughbook Tools GUI (0.2.0; physical GUI acceptance pending)

The Qt6 application combines KDE touch calibration, graphical audio confirmations,
button assignments, driver guidance, recovery controls, and expandable command
output. Automated tests cover target sampling, GUI assignment persistence,
audio prompts and worker completion, the per-user installation archive, and
portal identity preservation. The desktop file validates and the menu entry is
discoverable under the name **Toughbook Tools** on the reference KDE session.
The migrated button helper restarted with its existing four portal bindings.

Physical use of the new Qt calibration targets, audible speaker test, button
identification pause, and privileged driver controls remains to be checked by
the user. These GUI workflows are not yet hardware-validated.

## General Linux preparation (unreleased)

Shared setup now selects Debian/Ubuntu, Fedora or Arch packages, including the
appropriate desktop portal and kernel headers for optional driver builds.
Automated checks cover distribution identities/derivatives, package-manager
commands, APT candidates/PySide fallback, KDE helper selection, Arch kernel
variants and failure cases, read-only setup plans, and interpreter selection.
Fedora dependencies include standalone Tk/XWayland calibration and polkit.

These checks do not install packages on clean Debian/Arch systems or validate
hardware there. Before claiming physical support, follow the acceptance checklist
on each family, record package/kernel/desktop versions, confirm PipeWire/Pulse
session configuration, and exercise DKMS upgrades and Secure Boot with the host's
actual trust chain. Non-systemd and immutable systems are outside automatic setup.
Historical state/rule/archive names containing `fedora` remain for compatibility
so existing preferences and recovery backups continue to resolve.

Repository metadata verification during this preparation found all selected
runtime/build-tool packages in Debian 12 and 13 main and Arch core/extra indexes.
Debian 12 selected the PySide6 venv fallback; Debian 13 selected native PySide6.
Fedora 44 official repositories provided all selected package names except the
exact development package for the diagnostic host's older running kernel,
`7.2.11-200.fc44.x86_64`. This confirms the need to reboot into a kernel with
available matching development files before building; app setup is independent.
No system packages or live hardware configuration were changed for these checks.
The isolated Python 3.14 / PySide6 6.12 offscreen suite passes, including archive
reproducibility, CLI help, portable C decoder and cross-distribution setup tests.
GUI test teardown now explicitly disposes of widgets before QApplication exits;
this addresses an intermittent shutdown crash also observed on the unchanged suite.

## Desktop-independent backends (unreleased)

The desktop-name allowlists have been removed. New automated coverage exercises
capability detection, generic setup dependencies, native XInput finger-only
matching, X11 calibration/persistence and rollback, non-GNOME libinput apply and
restore, direct F13–F16 delivery, partial/dropped packets, repeat suppression,
inactive/locked-session gating, provider fallbacks and XRandR/wlroots recovery.
Generic GUI candidates require explicit application and new-login verification;
writing a candidate alone is not reported as an accepted calibration.

Physical acceptance on native X11 and additional Wayland compositors remains
pending. Test dedicated-device ACL revocation/VT switching, lock/unlock, reconnect,
suspend/resume and login persistence on each target session. Confirm rotation
preserves finger alignment and unavailable provider protocols fail clearly.
Keep the existing Fedora/KDE evidence separate from these new simulated paths.

The added XInput/XRandR, generic portal and wlr-randr package names were checked
against official Debian 12/13, Arch core/extra and Fedora 44 repository metadata.
No system packages, driver state or live display/audio/input configuration were
changed. Run the full suite with Qt's offscreen platform as in the development
guide; physical desktop acceptance remains a separate step.

## Xorg/X11 and Wayland compatibility verification

Native client checks passed on 2026-11-09 using isolated servers on the Fedora 44
diagnostic host with Python 3.14 and PySide6/Qt 6.12. These are stronger than offscreen mocks,
but do not establish physical CF-19 hardware acceptance.

| Check | X11: Xvfb 21.1.25 + Openbox 3.6.1 | Wayland: headless Weston 15.0.1 |
| --- | --- | --- |
| Native Qt platform | `xcb` passed | `wayland` passed; XWayland disabled |
| Native output metadata | 1024×768, scale 1 passed | 1024×768, scale 1 passed |
| Fullscreen target readiness | Passed | Passed |
| Nine synthetic touchscreen taps, coordinates within one pixel, preview acceptance | Passed | Passed |
| All four GUI pages and clean shutdown | Passed | Passed |
| Real XInput matrix apply/read-back/restore | Passed on Xvfb synthetic pointer; unrelated keyboard unchanged | Explicitly rejected before any XInput query |
| 180° output metadata | Not exercised on Xvfb | Correctly reported non-normal |
| Full automated suite with explicit session type | 125 tests passed | 125 tests passed |

The added protocol checks cover conflicting/stale display variables, absent
sessions, refusal to use XInput on Wayland, and rejection of reused XInput IDs or
changed event-node identities before writing a matrix. Source-archive content,
reproducibility and extracted CLI help checks also pass.

`tools/check-display.py` preserves the native smoke check. It redirects app
configuration/state and D-Bus to temporary locations, opens native GUI windows,
and prints a JSON report. `--xvfb-input` modifies only an explicitly identified
Xvfb synthetic pointer inside the temporary server. No real event node, udev rule,
module, sound setting or system package was changed by this verification.
See [development instructions](development.md) to repeat the checks.

X11 fullscreen calibration requires a window manager honoring fullscreen requests;
a bare Xvfb server kept the default 640×480 dialog and was correctly refused.
The X11 pass above uses Openbox. Virtual output names (`screen`, `headless`) are
not mistaken for eligible internal hardware by the calibration layout guard.
Actual touch accuracy, ALSA/speaker behavior, real display rotation with finger
alignment, direct-device ACL/lock/VT behavior, suspend and login persistence on
CF-19 hardware still require the physical acceptance checklist on both protocols.
