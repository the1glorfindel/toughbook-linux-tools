# Changelog

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
