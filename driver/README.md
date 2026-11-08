# CF-19 tablet-button kernel module

This directory contains the GPL-2.0-only `panasonic-hbtn` driver for the
Panasonic CF-19 Mk6 tablet buttons. It binds only ACPI `MAT001F` on matching
CF-19 Mk6 DMI hardware; it does not contain brightness handling.

See the [driver installation and troubleshooting guide](../docs/driver-installation.md)
for Fedora/Ubuntu builds, DKMS, Secure Boot, event mapping, and removal instructions.

The driver was modernized from Heiher's 2012 `panasonic-hbtn`, derived from
John Belmonte's 2002–2004 `panasonic-laptop.c`. Attribution and full GPLv2-only
terms are in [COPYING](COPYING). Sources: [Heiher](https://github.com/hevz/panasonic-hbtn)
and the [CF-19 modernization](https://github.com/cyberpunkcoder/panasonic-hbtn).
