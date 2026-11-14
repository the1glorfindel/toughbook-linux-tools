# Changelog

## Unreleased — Ubuntu GNOME Wayland validation

- Record native source GUI, finger accuracy, speaker playback, button actions,
  rotation, lock/unlock and suspend/resume checks on the reference Toughbook.
- Record the user-observed smoother on-screen keyboard and rotation without
  Xorg-style blanking, scoped to this device rather than a measured benchmark.


## Unreleased — one default calibration workflow

- Default GUI and CLI calibration to system-wide login/desktop correction.
- Move legacy desktop-session calibration and backup visibility under Advanced
  options; require `--session-only` for legacy CLI measurement.


## Unreleased — system-wide finger calibration

- Add GUI/CLI measurement, installation, reboot verification and restore for
  login-screen and desktop libinput calibration on Ubuntu and Fedora.
- Preserve previous rules/startup files and KDE calibration, retire recognized
  session workarounds, and guard against double correction and stale backups.
- Include Xorg libinput driver dependencies and transaction/migration tests.


## Unreleased — validation status update

- Record the local portable build, clean-container runtime, native X11 GUI and
  isolated installation checks.
- Record confirmed Ubuntu source-installation reboot persistence, post-reboot
  speaker/button inputs and 14.07-pixel maximum finger error.
- Document the prior unexplained matrix reset, restored helper after the isolated
  uninstall check, and remaining stable portable-release acceptance work.


## Unreleased — Ubuntu GNOME X11 hardware fixes

- Preserve the GUI-capable Python interpreter across app and button installation.
- Use live shell actions on X11 and GNOME's supported overview property.
- Match PipeWire sinks by stable device name when the native card field is absent.
- Show fullscreen calibration targets on GNOME X11 and preserve touch calibration
  across rotation, including asynchronous desktop resets.
- Exclusively read the verified tablet-button device to prevent duplicate GNOME
  shortcuts, while leaving ordinary keyboards alone.
- Record coordinated physical speaker, finger calibration and button validation
  in `docs/VALIDATION.md`, including measured limits and remaining checks.

## Unreleased — portable runtime

- Bundle Python, Qt X11/Wayland, D-Bus/GLib/Tk bindings and native fix utilities.
- Preserve complete runtime installations and helper paths; isolate host programs from bundled libraries.
- Build on Debian 12 with dependency manifests, licenses, hashes and corresponding-source archives.

## Unreleased — desktop-independent fixes

- Verify native X11/Wayland Qt clients, synthetic touch sampling, GUI shutdown and XInput read-back.
- Add a repeatable display smoke check and reject XInput calls on Wayland or reused device identities.

- Detect active compositor capabilities instead of rejecting other desktop names.
- Add native X11 finger calibration/persistence and a common libinput Wayland GUI workflow.
- Default to dedicated-device button input with active/unlocked-session checks; retain optional portals.
- Add generic launcher/keyboard providers, XRandR touch-aware rotation and wlroots output rotation.
- Import session environment at helper startup and document window-manager startup commands.
- Extend generic setup packages, rollback tests and desktop compatibility guidance.

### General Linux preparation

- Share setup and dependency selection across Debian/Ubuntu, Fedora and Arch families.
- Add native Pacman commands, kernel-pkgbase header selection and desktop portal packages.
- Complete Fedora standalone calibration/polkit dependencies and retain Ubuntu setup alias.
- Add read-only setup plans, optional build prerequisites and isolated distribution tests.
- Document PipeWire session prerequisites, Arch updates and physical validation limits.


- Add Ubuntu APT/PySide6 setup and a launcher that retains the selected Python interpreter.
- Select Fedora or Ubuntu build packages in the Buttons page and use the common
  kernel-header link for DKMS builds.
- Support WirePlumber 0.4 Lua rules alongside the existing 0.5 configuration
  for the reversible speaker repair.
- Document Ubuntu first-run checks and physical validation still needed.

## 0.2.0 — 2026-11-07

- Add the Qt6 Toughbook Tools application for KDE, combining guided finger
  calibration, speaker repair, tablet-button assignments, and driver setup.
- Add a per-user application menu entry, troubleshooting output, saved-backup
  recovery controls, and migration from the standalone Buttons menu entry.
- Preserve the button portal identity through a hidden desktop entry so
  existing shortcut approvals survive the migration.

## 0.1.0 — 2026-11-06

- Add the CF-19 Mk6 MAT001F tablet-button driver, DKMS integration and narrowly
  scoped device access, with separate GPL-2.0 licensing and upstream attribution.
- Add the per-user GTK4 Toughbook Buttons settings app and Global Shortcuts portal
  helper, supporting built-in actions, installed apps and custom commands.
- Verify keyboard toggling, launcher/custom app, four display orientations with
  accurate touch, locking, suspend/resume and login persistence on Fedora KDE.
- Verify target-kernel compilation, 72 automated tests and live uninstall/reinstall.
- Preserve audio and calibration settings. GNOME physical validation remains pending.
- Retain the existing v0.0.1 tag and archives.

## 0.0.1

- Package the CF-19 Mk6 screen and speaker fixes as shell-independent Python tools.
- Preserve the tested nine-point KDE Wayland calibration and add a GNOME
  libinput/udev backend with a separate apply/login/verify workflow.
- Detect hardware and internal outputs instead of using a particular username,
  event number, ALSA card index, output connector name, or PCI address.
- Preserve private backups outside the source tree, provide explicit undo, and
  retain the original audio uninstall baseline on repeat installations.
- Document Fedora dependencies, observed causes, implementation details,
  recovery, and upstream licensing of runtime-generated profiles.
- Add isolated tests and a deterministic source-archive builder.

GNOME physical validation and clean-install validation remain pending. This is a
early release, not a claim that all CF-19 revisions or desktop layouts work.
