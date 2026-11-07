# Silent internal speaker: issue and solution

## What was observed

The tested CF-19 Mk6 used the Intel HDA controller and Realtek ALC269VC codec.
`snd_hda_intel` and `snd_hda_codec_alc269` were already loaded. Fedora exposed an
analog stereo output, the Speaker and Master controls were enabled, and
Panasonic's separate firmware mute flag was off. Playback could run without
producing audible internal-speaker output.

The crucial observation was that enabling and raising the mixer control named
**Headphone** restored the **internal speaker**. This machine's speaker playback
therefore depends on a control whose name suggests it belongs only to headphones.
That is an observed behavioral dependency; the scripts do not claim to establish
the exact board wiring or a universal Realtek bug.

The standard ALSA Card Profile speaker path explicitly turns that control off:

```ini
[Element Headphone]
switch = off
volume = off
```

Manually unmuting it can work temporarily, but selecting the speaker route again
can mute it again. No new kernel module was required for the confirmed fix.

An earlier diagnostic used `speaker-test -D pulse`. The reference Fedora install
had no ALSA PCM with that name, so that test failed before playing. This was a
separate test-tool problem. The public script uses native `pw-play` instead.

## How the script fixes it

The script discovers the ALSA card behind PipeWire, validates the CF-19 model and
ALC269VC codec, and finds its analog stereo sink. It does not assume card 0,
`PCH`, or a particular PCI address. It backs up the current profile files, active
port, sink volume/mute, default output, and ALSA mixer state before testing.

With wired headphones unplugged, it selects the speaker, disables ALSA auto-mute,
and enables the Headphone control at 80% with output volume at 60%. These are test
levels, not fixed permanent loudness requirements. Native playback is directed
to that specific sink. Only an affirmative listening result advances installation.

The persistent change is a private speaker path that changes just the primary
Headphone element to:

```ini
[Element Headphone]
switch = mute
volume = merge
```

`switch = mute` lets normal route mute handling control this element instead of
forcing it off. `volume = merge` includes its gain in normal volume handling.
The rest of Fedora's installed path is retained, including upstream license text
and common directives. A private profile set replaces references to the standard
speaker path with this tool's path. A WirePlumber rule selects that profile set
only for the discovered internal card.

Files, relative to `$XDG_CONFIG_HOME` (normally `~/.config`):

```text
alsa-card-profile/paths/cf19-output-speaker.conf
alsa-card-profile/profile-sets/cf19.conf
wireplumber/wireplumber.conf.d/51-cf19-speaker.conf
```

System files under `/usr/share` are untouched. The script restarts WirePlumber,
selects the private speaker port, sets it as default output, plays again, and
requires another affirmative listening result. Ordinary failure/cancellation
restores configuration, routing, and hardware mixer state. Saved files take
effect again on future logins, and normal volume/mute controls remain available.

## Restore, updates, and limits

Every attempt retains a private JSON backup and adjacent `.alsa-state` file.
`--restore BACKUP` resolves the card again, restores/removes only the three tool
configuration files, restarts WirePlumber, and restores routing and mixer values.
Do not separate or delete the paired backup files. Repeated successful runs keep
the original uninstall baseline rather than replacing it with an already modified
configuration. Files that existed before the first run are restored verbatim.

An update cannot overwrite these per-user files, but it may change the upstream
defaults from which they were generated. Rerun the script after relevant PipeWire
updates to refresh private copies. Unexpected default-file formats cause a clean
stop rather than an assumed rewrite.

If this test remains silent, do not assume the kernel must be rebuilt: test wired
headphones, firmware/concealed-mode settings, hardware speaker health, and codec
routing. The stock driver supports additional pin overrides if diagnosis warrants
them, but this release neither performs pin retasking nor builds a module.

Headphone insertion/removal, suspend/resume, and persistence after a full reboot
remain acceptance checks for each machine. Speaker confirmation alone does not
prove those scenarios. Other CF-19 revisions and codecs may need different fixes.

## Sources

- [PipeWire device properties and local ACP search directories](https://github.com/PipeWire/pipewire/blob/master/doc/dox/config/pipewire-props.7.md)
- [Upstream speaker path](https://github.com/PipeWire/pipewire/blob/master/spa/plugins/alsa/mixer/paths/analog-output-speaker.conf)
- [WirePlumber ALSA configuration](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/alsa.html)
- [Kernel HD-Audio reconfiguration documentation](https://docs.kernel.org/sound/hd-audio/notes.html)
