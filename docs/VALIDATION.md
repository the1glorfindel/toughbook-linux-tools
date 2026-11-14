# Validation and release status

## Evidence already available

The original implementations were confirmed by a user on a Panasonic CF-19 Mk6
with Fedora 44 KDE Wayland, a Wacom ISDv4 93 finger sensor (`056a:0093`, interface
01), and Realtek ALC269VC audio. The successful audio run included a WirePlumber
restart and a second affirmative listening result. That evidence establishes the
workarounds; it does not validate every path in this public-release refactor.

The early Fedora release-preparation checks used an isolated diagnostic
environment. Later Ubuntu checks below used the live reference Toughbook,
including its GNOME Shell session. Those later results supersede the earlier
isolation limits only for the explicitly recorded checks.

Initial Ubuntu compatibility preparation had no live installation evidence.
The Ubuntu GNOME X11 section below now records specific hardware checks,
including the WirePlumber 0.4 audio path. Clean setup and the installed kernel's
DKMS build/signing behavior still need separate validation.

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

## Physical acceptance checklist — remaining scope varies by platform

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

## Ubuntu GNOME X11 hardware checks (2026-11-09)

Coordinated live checks used a CF-192NYZX1M running Ubuntu 24.04.4,
GNOME Shell 46.0, native X11, kernel 6.17.0-23-generic, Qt 6.12.0 and
WirePlumber 0.4.17. Hardware identities were Wacom `056a:0093` interface 01
and Realtek ALC269VC (`10ec0269`). These results supersede the earlier pending
Ubuntu statements only for the checks listed here; they do not establish clean
installation, other desktop/protocol support, or the entire acceptance checklist.

Code revision `9a442ee` passed all 158 automated tests both locally and on the
Toughbook. Earlier revisions were tested and corrected during the same session:

- Installing with `/usr/bin/python3 toughbook-buttons.py --install` now retains
  the working managed virtual-environment interpreter in the GUI and hidden
  Buttons entries, both autostarts and the helper service. The helper is active
  with an empty error status.
- The user confirmed internal-speaker playback before and after a WirePlumber
  restart on `31822f8`; the legacy 0.4 rule path and saved recovery baseline were
  exercised. PipeWire sink matching uses the stable device name when the native
  card field is absent. The initially proposed object-ID fallback failed after
  restart and was replaced before this pass.
- GNOME X11 fullscreen targets initially failed with the dialog window type.
  A normal window type reached 1024x768. The user completed nine physical finger
  samples, accepted the preview and confirmed calibration success on `c3be2a7`.
  The saved fit error was 6.35 pixels, with matching login activation data.
- Native automated Escape cancellation preserved both the live transform and
  saved activation bytes. This was an injected native Escape, not a physical
  keypress by the user.
- Rotation initially lost calibration because the desktop reset the XInput
  transform. Stabilization and bounded transient-readback retries corrected it.
  On `b7daee3`, three rotated physical verification measurements passed the
  existing 20-pixel maximum-error gate: right 19.80, inverted 12.25 and left
  13.91 pixels. A complete rotation cycle returned to the accepted landscape
  transform without recovery. Landscape verification initially failed at
  20.13 pixels, then passed at 19.53 pixels on a repeat without changing the
  calibration or threshold. The user accepted the passing measurements; these
  near-threshold results do not establish greater precision.
- On `f32a747`, the user confirmed the physical Keyboard button enables GNOME's
  keyboard for a finger-touched text field, no longer opens Settings, and leaves
  ordinary keyboard typing working. A live exclusive-access probe showed the
  tablet device busy while the helper ran, available after stopping it, and busy
  again after restart. The helper revalidates the opened dedicated device before
  grabbing it; ordinary keyboards are not opened or grabbed.
- Native GUI checks on `2272671` rendered all four pages through Qt's `xcb`
  platform. Identification received a physical Rotation press/release pair
  through the helper without running the action. Stopping the helper terminated
  the command-line monitor with a clear error; restarting restored normal helper
  status. On `9a442ee`, live D-Bus checks confirmed `paused=true` on pause,
  `paused=false` on resume, empty errors and exclusive device access retained.
- On the final code, the user explicitly confirmed Circle opens the launcher,
  rotation cycles work, Key locks the session, Circle/Rotation do not act while
  locked, and Circle works again after unlocking. An earlier timed observer
  captured no transitions, so this pass is based on the user's physical report,
  not an automated lock-state timeline.
- The user also explicitly confirmed all four buttons identify with named paired
  edges and no assigned actions. The captured GUI log independently contains
  the Rotation pair only; the all-four result is the user's confirmation.
  Final read-only audit found 31 installed code/data files matching the tested
  worktree, saved/live finger matrices agreeing within `1e-4`, the speaker sink
  unmuted, and the direct helper active with no error and `paused=false`.
  The final installed `9a442ee` GUI also rendered all four pages through `xcb`
  and shut down cleanly. No requested physical confirmations remained pending.

At the end of the November 9 session, reboot/login persistence, suspend/resume,
VT switching and ACL revocation, headphone insertion/removal and complete audio
restore remained pending. The later checks below supersede the reboot/login item
for the existing Ubuntu source installation only.


## Portable build and Ubuntu retest (2026-11-10 to 2026-11-12)

Current status: suitable for a preview release, with stable portable acceptance
still incomplete. These checks used Panasonic CF-192NYZX1M, Ubuntu 24.04.4 LTS,
GNOME Shell 46 native X11, and kernel `6.17.0-23-generic`. The portable 0.2.0
runtime was built from `3f4770f` using rootless Podman and Debian 12, with Python
3.11.2 and Qt/PySide 6.12.0. Build outputs remain local; this record does not
assert publication or tagging of a release.

| Check | Result and scope |
| --- | --- |
| Automated suite | 158 tests passed; 11 release checks also passed after source packaging. |
| Source archive and GNOME extension | Built; source checksum and extension ZIP integrity verified. |
| Kernel driver | Module compiled for `6.17.0-23-generic`; the newly built module was not loaded. This does not validate fresh DKMS installation or Secure Boot signing. |
| Portable packaging | Runtime and matching dependency-source archives built; archive checksums and extracted runtime file hashes passed. |
| Clean-container runtime | Imports and bundled native-client checks passed without system Python and with networking disabled. |
| Native portable X11 GUI | `xcb`, 1024×768 at scale 1; nine synthetic touches within one pixel, preview acceptance, all four pages, and clean shutdown passed. |
| Isolated portable installation | Install, relocation into paths with spaces, upgrade from the installed copy, uninstall, and retained settings passed. No existing helper was migrated in this check. |
| Speaker playback | User heard both left/right samples played with the portable audio client, including after reboot. |
| Physical button input | Portable monitor captured named press/release pairs for Keyboard, Circle, Rotation, and Key before and after reboot, through the existing source helper. Actions were paused during identification and restored afterward. |
| Source installation reboot/login | Changed kernel boot ID confirmed a full reboot. Saved calibration matched live XInput automatically, the source helper started without error, and configuration files were unchanged. |
| Physical finger verification | Existing calibration measured 11.44 pixels maximum error before reboot and 14.07 after reboot; both passed the 20-pixel gate. Measurements used a source Qt target harness, not the portable GUI's calibration workflow. |

Before the successful pre-reboot finger test, the live XInput matrix was identity
while the saved calibration remained intact. Maximum error was 75.00 pixels.
Reapplying the saved matrix with the portable `--tool screen --activate` command
restored accuracy. The reset cause is unknown. The subsequent full reboot restored
the saved matrix automatically, but one successful reboot does not rule out an
intermittent reset.

The isolated uninstall check briefly stopped the real source helper because
`systemctl --user` still addressed the live user manager despite temporary XDG
paths and an isolated D-Bus address. The helper was restarted and verified active
with empty error status and `paused=false`. Installation checks therefore establish
file relocation/settings behavior, not complete service isolation.

### Remaining acceptance work

- Native GNOME Wayland portable GUI and physical hardware checks; earlier isolated
  source Wayland smoke results do not establish portable GNOME Wayland acceptance.
- Portable suspend/resume, VT switching and input ACL revocation; the later
  local source and libinput-pilot suspend checks are recorded below.
- Live source-to-portable helper migration, assigned actions with the portable
  helper, and portable installation reboot/login persistence.
- Headphone insertion/removal, complete audio restore, fresh distribution setup,
  DKMS/signing, and additional desktops or hardware revisions.
- Repeat persistence checks if the unexplained live-matrix reset recurs.

The November 9 physical assigned-action results still apply to that source
installation; the later identification tests do not repeat those action checks.


## System-wide libinput finger pilot (2026-11-14)

A reversible local configuration trial on the reference Ubuntu GNOME X11 CF-19
moved the saved sensor correction from XInput's coordinate transform into
`LIBINPUT_CALIBRATION_MATRIX`. A narrowly matched udev rule selects only the
`056a:0093` finger interface `01`, serial and physical path, and clears its
conflicting tablet classification. A late Xorg InputClass selects libinput for
`Wacom ISDv4 93 Finger`; pen and eraser retain the Wacom driver. The kernel
product name lacks the driver's former `touch` suffix; an initial Xorg rule using
that suffix did not match and was corrected before this trial.

Xorg logs from both GDM and the desktop confirm the finger driver selection.
The active and default libinput matrices match the saved calibration, while the
XInput coordinate transform is identity in normal landscape. The old calibration
startup entries and local reset guard are disabled, preventing double correction.
The original Xorg TransformationMatrix-only workaround had loaded but was later
overwritten; that startup-only approach did not resolve the resets.

Confirmed pilot results:

- User reported accurate touch on the boot-time login screen and lock screen.
  Reaching the password field with touch and on-screen keyboard availability were
  not separately recorded as acceptance results.
- Journal evidence confirms suspend/resume; both matrices remained unchanged,
  the button helper remained active and the guard remained inactive. The user
  confirmed accurate touch after waking.
- User confirmed accurate touch in all four button-driven orientations. Returning
  to landscape restored the identity coordinate transform and retained the
  libinput correction.
- A source Qt verification harness measured nine physical finger targets at
  1024x768: maximum error 9.63 pixels, passing the existing 20-pixel gate. The
  user accepted the result; no calibration was changed by this measurement.
- User confirmed pen/eraser behavior functioned as intended after the trial.

The device trial passed these checks without a custom kernel module or calibration
watchdog. At the time of the pilot, this was not an app installation mode. The integration
section below records the subsequent implementation. Native Wayland,
portable integration, broader hardware and repeated-cycle endurance remain
unvalidated by this pilot. Backups and install/rollback scripts are retained
locally outside the repository; no pilot artifacts or user identities are packaged
in a release.


## App integration of system-wide calibration

The Finger touch GUI and `--system-wide` CLI now create system calibration
candidates. Apply/verify/restore handle both the udev rule and Xorg finger-driver
selection, migrate per-user activation, handle KDE overrides, and prevent legacy
X11 double correction. Ubuntu/Fedora setup includes the Xorg libinput driver.

181 automated tests passed during integration, including partial-write rollback,
authorization denial, stale configuration, unrelated startup entries, KDE override
migration/restore, driver/display composition, reboot verification and rejection
of double calibration. These are simulated workflow checks, not fresh physical
Ubuntu/Fedora acceptance. Existing portable artifacts predate this integration
and must be rebuilt and revalidated before release.

The integrated source app also passed the native Ubuntu GNOME X11 smoke check:
1024x768, `xcb`, nine synthetic touches within one pixel, preview acceptance,
all four pages and clean shutdown. This did not install a candidate or repeat the
physical pilot checks through the new app workflow.


## Native Ubuntu GNOME Wayland hardware checks (2026-11-14)

The reference CF-192NYZX1M was switched to native GNOME Wayland on Ubuntu
24.04.4, GNOME Shell 46.0, kernel `7.0.0-43-generic`. The source app used
Python 3.12.3 and Qt/PySide 6.12.0. The earlier system-wide libinput rule remained
installed; these checks did not reinstall or restore a candidate through the app.

- Qt reported native `wayland`, internal LVDS-1 at 1024x768, scale 1, normal
  landscape. Native GUI smoke checks passed nine synthetic touches within one
  pixel, preview acceptance, all four pages and clean shutdown.
- Nine physical finger targets passed the 20-pixel gate with maximum error
  **18.89 pixels**. The source verification harness changed no calibration.
- The user confirmed both speaker samples. Playback used bundled native clients
  from the earlier portable artifact; this does not establish portable GUI
  acceptance or fresh audio-repair installation on Wayland.
- The installed source helper and monitor captured all four named paired button
  edges while actions were paused, then resumed normal actions without errors.
- The user confirmed rotation and finger accuracy in all four orientations,
  the Keyboard action, and Circle opening the launcher/overview.
- The user confirmed Key locks, accurate unlock-screen finger input, Circle and
  Rotation actions blocked while locked, and Circle working after unlock.
- Journal evidence confirms a completed suspend/resume cycle. The user confirmed
  accurate touch and working Keyboard/Circle actions after waking; the helper
  remained active.

The user reports that this Toughbook works better with GNOME Wayland than Xorg:
the on-screen keyboard feels more fluid, and rotation appears instant without
the blanking seen on Xorg. No latency or frame timing was measured; this is a
subjective comparison of the tested installation.

Wayland pen/eraser regression, boot-time login-screen touch behavior after this
session switch, app-managed calibration install/restore, clean setup, and rebuilt
portable Wayland runtime acceptance remain pending. These source-app results do
not validate every Ubuntu desktop, Fedora configuration or Toughbook revision.
The earlier pending GNOME Wayland source checks are superseded only for the
specific checks listed here. The default-workflow change also passed 185 automated
tests before this physical session.
