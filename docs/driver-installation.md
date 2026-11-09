# Tablet-button driver: cause, setup, and recovery

The CF-19 Mk6 exposes its four front controls as an ACPI `MAT001F` tablet
device. The reference Fedora installation did not bind a driver to this device, so the controls
may be absent from input devices and desktop shortcut settings. The separate
`panasonic-hbtn` module binds this device and emits F13–F16. It does not replace
the brightness driver or alter the ordinary keyboard. The settings application
and desktop shortcuts are described in the [button guide](tablet-buttons.md).

## Supported firmware events

The driver is limited to Panasonic CF-19 Mk6 DMI hardware (`CF19-6`) and the
exact HINF values observed from the reference Mk6:

| Button | HINF press / release | Scan code | Linux key |
| --- | --- | --- | --- |
| Keyboard | `0x3a` / `0x3b` | `0x3a` | F13 |
| Circle | `0x38` / `0x39` | `0x38` | F14 |
| Screen/Rotation | `0x36` / `0x37` | `0x36` | F15 |
| Key | `0x34` / `0x35` | `0x34` | F16 |

On ACPI notification `0x80`, it reads HINF, emits `MSC_SCAN`, and sends the
matching key edge. Unknown full firmware values are warned about and ignored;
they are not guessed or converted to a nearby key. The module creates only the
`Panasonic CF-19 Tablet Buttons` input device. The separate GPL license and
upstream attribution are in [driver/COPYING](../driver/COPYING).

## Install on Debian-based, Fedora or Arch-based Linux

Run these commands from the repository root. Install the running kernel's
matching development files; the script builds and registers the module through
DKMS. It checks for an existing module, source directory, udev rule, and
competing driver before installation. Resolve a refusal by inspecting the
existing installation first; the script will not replace or unbind it.

```sh
sudo dnf install make gcc kernel-devel-$(uname -r) dkms mokutil openssl
sudo bash driver/install.sh
```

On Debian or Ubuntu, use the matching headers for the running kernel:

```sh
sudo apt-get update
sudo apt-get install build-essential linux-headers-$(uname -r) dkms mokutil openssl
sudo bash driver/install.sh
```

On Arch, select headers for your actual kernel package. For the stock `linux`
kernel on an up-to-date system:

```sh
sudo pacman -S --needed base-devel linux-headers dkms mokutil openssl kmod systemd
sudo bash driver/install.sh
```

Use `linux-lts-headers`, `linux-zen-headers`, or the matching custom package as
appropriate. Reboot after a rolling kernel update before building. The shared
`python3 tools/setup-linux.py --driver-prerequisites` command and GUI
**Install prerequisites** control select APT, DNF or Pacman and derive Arch
headers from the running kernel's `pkgbase` file. See [kernel header details](linux.md).

All three families use `/lib/modules/$(uname -r)/build`. If it is missing,
install matching headers or boot a packaged kernel with headers available.

The installer installs the dedicated-device udev rule and builds/signs the
module, but intentionally does **not** load it. Complete Secure Boot signing
and enrollment if needed (below), then load explicitly:

```sh
sudo modprobe panasonic-hbtn
python3 toughbook-buttons.py --status
python3 toughbook-buttons.py --monitor
```

Run the monitor as the desktop user. The udev rule grants active-session access
to the named tablet device and marks only it as a keyboard so libinput forwards
the F13–F16 keys. Do not run the GUI/helper as root or add your user to the
broad `input` group. On later boots, ACPI modalias discovery should load the
installed module automatically.

## Secure Boot

MOK enrollment below assumes a shim/MOK boot chain. For Arch or another
installation using a different trust chain, configure DKMS signing with a key
trusted by that kernel/firmware setup; generating a MOK alone does not establish
trust.

Never disable Secure Boot automatically or as an installation workaround. On
EFI systems, the installer reports its state and DKMS signs according to the
host's configuration. Check state and the installed signer with:

```sh
sudo mokutil --sb-state
sudo modinfo -F signer panasonic-hbtn
```

If Secure Boot is enabled, find the certificate configured for DKMS in
`/etc/dkms/framework.conf`, any files under `/etc/dkms/framework.conf.d/`, and
the DKMS build output. Upstream defaults use `/var/lib/dkms/mok.pub`. Test
enrollment, and if needed import that certificate:

```sh
sudo mokutil --test-key /var/lib/dkms/mok.pub
# Run the next command only if the test reports that this key is not enrolled.
sudo mokutil --import /var/lib/dkms/mok.pub
```

Use the actual configured certificate path if different. Import asks you to set
a temporary password. Reboot manually and complete **Enroll MOK** in the
firmware/shim enrollment screen, then rerun `mokutil --test-key`. Keep the DKMS
private signing key safe and persistent so later kernel rebuilds use the same
enrolled certificate. A legacy BIOS boot does not use EFI Secure Boot.

See [DKMS module signing](https://github.com/dkms-project/dkms#module-signing)
and [Red Hat kernel signing](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/10/html/managing_monitoring_and_updating_the_kernel/signing-a-kernel-and-modules-for-secure-boot).

## Troubleshooting

- **Installer says matching kernel headers are missing:** install
  `kernel-devel-$(uname -r)` on Fedora, `linux-headers-$(uname -r)` on
  Debian/Ubuntu, or the matching `<pkgbase>-headers` on Arch
  and retry. Confirm `/lib/modules/$(uname -r)/build` points to a real directory.
  Also install `make`, `gcc`, `dkms`,
  `modinfo`, and `udevadm` (the packages above provide these tools).
- **Installer refuses an existing source, rule, module, or binding:** inspect
  `/usr/src/panasonic-hbtn-0.1.0`,
  `/etc/udev/rules.d/70-panasonic-hbtn.rules`, `modinfo panasonic-hbtn`, and the
  driver linked under `/sys/bus/acpi/devices/MAT001F:*/driver`. Do not delete or
  unbind another driver's files blindly. Remove a previous copy only with its
  own uninstall procedure after confirming ownership.
- **DKMS build fails:** inspect `dkms status` and
  `/var/lib/dkms/panasonic-hbtn/0.1.0/build/make.log`. Confirm the current
  kernel headers are installed and retry after resolving the reported compiler
  or kernel API error. The installer cleans files created by a failed attempt.
- **`modprobe` reports a key rejection:** check Secure Boot state, module signer,
  and enrollment of the matching configured certificate. Finish MOK enrollment
  manually and retry; never disable Secure Boot to bypass signing.
- **Module loads but no tablet events appear:** check `lsmod`,
  `python3 toughbook-buttons.py --status`, and `sudo journalctl -k -b`. Confirm
  the machine matches the supported CF-19 Mk6 and exposes `MAT001F`. Then inspect
  the dedicated input device and test with `python3 toughbook-buttons.py --monitor`
  as the logged-in user.
- **Monitor reports permission denied:** verify
  `/etc/udev/rules.d/70-panasonic-hbtn.rules` exists, then reload rules and
  refresh only the tablet event device. Replace `eventN` with the device shown
  by `python3 toughbook-buttons.py --status`:

  ```sh
  sudo udevadm control --reload-rules
  sudo udevadm trigger --action=add /sys/class/input/eventN
  ```

  If access is still denied, log out/in to refresh the session ACL. Do not use
  root for the monitor and do not broaden permissions to every input device.
- **Kernel log reports an unknown HINF event:** save the exact warning and
  firmware/model identity for diagnosis. The driver intentionally ignores
  unknown values; do not assign an action by changing the mapping speculatively.

## Remove

Stop the user helper and any running monitor first. Then remove the app's
per-user integration, unload the module, and remove its DKMS registration:

```sh
python3 toughbook-buttons.py --uninstall
sudo modprobe -r panasonic-hbtn
sudo bash driver/uninstall.sh
```

If the module is busy, stop processes using the tablet device and retry, or
reboot manually after DKMS removal. The uninstall script removes this version's
DKMS source/registration and udev rule; it does not unload the live module,
reboot, unbind another driver, or change calibration/audio settings. Settings
remain in `$XDG_CONFIG_HOME/toughbook-buttons` unless explicitly removed.
