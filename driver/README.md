# Panasonic CF-19 tablet buttons

This modernized GPL-2.0-only driver binds ACPI ID `MAT001F` only when DMI
identifies a Panasonic CF-19 with board `CF19-6` (Mk6). It exposes an input
device named **Panasonic CF-19 Tablet Buttons**. On ACPI notify `0x80` it
evaluates `HINF`. Bit 0 is 0 on press and 1 on release. Only these exact pairs,
observed during the user's ordered four-button test, are accepted:

| Physical button | Press / release | Scan code | Linux key |
|---|---|---|---|
| Keyboard | `0x3a` / `0x3b` | `0x3a` | F13 |
| Circle | `0x38` / `0x39` | `0x38` | F14 |
| Rotation | `0x36` / `0x37` | `0x36` | F15 |
| Key | `0x34` / `0x35` | `0x34` | F16 |

Other CF-19 revisions and firmware encodings are intentionally unsupported.
The upstream driver masked upper bits and assigned different keys; this Mk6
implementation validates the complete event before mapping it. Physical input delivery and all four default desktop actions were subsequently
confirmed on Fedora 44 KDE Wayland; GNOME remains awaiting physical validation.

Every mapped event emits `MSC_SCAN` with the decoded scan code, then the
mapped key press or release. Unknown firmware events are reported with ratelimited warnings and
ignored.

## Build and DKMS

Install matching Fedora kernel development files and run
`make KVER=$(uname -r)`. The pure decoder vectors are in
`test-hbtn-decode.c` and can be compiled with a C compiler. DKMS installation is provided by `sudo ./install.sh`;
removal is `sudo ./uninstall.sh`. The installer checks every
`/sys/bus/acpi/devices/MAT001F:*` instance and refuses to displace another
bound driver. It installs a udev `uaccess` rule matching only the named
Panasonic input device. It marks only this device as a keyboard so libinput
forwards its F13–F16 keys to the compositor. Neither script loads/unloads the module or disables
Secure Boot. With Secure Boot enabled, arrange module signing and MOK
enrollment before loading it.

## Provenance and license

Modernized from Heiher's `panasonic-hbtn` CF-18/19 driver, Copyright (C) 2012,
which is derived from `panasonic-laptop.c`, Copyright (C) 2002-2004 John
Belmonte. The upstream HINF behavior, scan codes, and Heiher attribution are
retained; the tablet button key assignments are F13–F16. This work remains
under GNU GPL version 2 only; full license text is in [COPYING](COPYING). See the
[upstream source](https://github.com/hevz/panasonic-hbtn) and the
[CF-19 modernization](https://github.com/cyberpunkcoder/panasonic-hbtn).

## Fedora commands (from the project root)

```sh
sudo dnf install make gcc kernel-devel-$(uname -r) dkms mokutil openssl
make -C driver KVER=$(uname -r)
cc -Wall -Wextra -Werror -o /tmp/test-hbtn driver/test-hbtn-decode.c
/tmp/test-hbtn
sudo bash driver/install.sh
sudo modprobe panasonic-hbtn
python3 toughbook-buttons.py --monitor
```

The installer deliberately leaves loading to the explicit `modprobe` command.
ACPI modalias discovery loads the installed module on later boots. It refuses
preexisting source/rule files and competing drivers; inspect those before an
upgrade. Failed DKMS setup removes only the files created by that attempt.
Check `journalctl -k -b` for unknown firmware event warnings. An `HINF` press
and release remain separate transitions; no synthetic Enter or auto-release is
injected. Suspend/resume clears any stale held keys. There is no brightness code
in this module. The physical mappings, paired input delivery and suspend/resume were verified
on the Mk6. Press-and-hold timing and switch debounce remain outside this version.

### Secure Boot

Check `mokutil --sb-state` on an EFI boot. Legacy BIOS boots do not use EFI
Secure Boot. Never disable Secure Boot to make installation succeed.

Modern DKMS signs its builds using its configured `mok_signing_key` and
`mok_certificate`. Inspect `/etc/dkms/framework.conf`, drop-ins under
`/etc/dkms/framework.conf.d/`, and the DKMS build output for the actual certificate
path. With upstream defaults that certificate is `/var/lib/dkms/mok.pub`:

```sh
sudo mokutil --test-key /var/lib/dkms/mok.pub
# If it is not enrolled:
sudo mokutil --import /var/lib/dkms/mok.pub
```

The import asks for a temporary enrollment password. Reboot manually and complete
**Enroll MOK** in the firmware/shim MOK manager using that password; then rerun
`--test-key`. Use your configured certificate path if it differs. Retain and
protect DKMS's private key so future kernel rebuilds use the same enrolled key.
If your DKMS installation does not sign automatically, configure its documented
signing-key/certificate settings before building; do not sign a compressed module
in place. Verify `modinfo -F signer panasonic-hbtn` and a successful explicit
`modprobe` before calling installation complete. Enrollment and reboot require
physical user interaction; no script performs them.

See [DKMS signing documentation](https://github.com/dkms-project/dkms#module-signing)
and [Red Hat's kernel signing guide](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/10/html/managing_monitoring_and_updating_the_kernel/signing-a-kernel-and-modules-for-secure-boot).

### Uninstall

```sh
python3 toughbook-buttons.py --uninstall
sudo modprobe -r panasonic-hbtn
sudo bash driver/uninstall.sh
```

The uninstall script removes this version's DKMS registration/source and uaccess
rule. If the module is busy, stop the helper/monitor and retry unloading, or reboot
manually after removal. No script unbinds a competing driver, reboots, or edits
calibration/audio configuration.
