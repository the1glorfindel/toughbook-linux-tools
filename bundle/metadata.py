"""Inventory bundled libraries and preserve redistribution notices. SPDX-License-Identifier: MIT"""
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def collect(analysis, root, work):
    work.mkdir(parents=True, exist_ok=True)
    source_files = {str(Path(row[1]).resolve()) for row in analysis.binaries if Path(row[1]).is_file()}
    # Include the providers of copied configuration files and WAV samples too.
    source_files.update(str(path) for pattern in ('/usr/share/alsa/alsa.conf', '/usr/share/sounds/alsa/*.wav')
                        for path in Path('/').glob(pattern.lstrip('/')) if path.is_file())
    for source in list(source_files):
        for prefix in ('/usr/lib/', '/usr/bin/', '/usr/sbin/'):
            if source.startswith(prefix):
                alias = source[4:]
                if Path(alias).exists():
                    source_files.add(alias)
    found = subprocess.run(['dpkg-query', '-S', *sorted(source_files)], capture_output=True, text=True)
    owners = sorted({line.rsplit(': ', 1)[0] for line in found.stdout.splitlines() if ': ' in line})
    records = []
    if owners:
        result = subprocess.run(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\n',
                                 *owners], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            name, version, source, source_version = line.split('\t')
            records.append({'name': name, 'version': version, 'source': source, 'source_version': source_version})
    licenses = work / 'licenses'
    if licenses.exists():
        shutil.rmtree(licenses)
    licenses.mkdir()
    for record in records:
        name = record['name'].split(':')[0]
        copyright = Path('/usr/share/doc') / name / 'copyright'
        if not copyright.is_file():
            raise RuntimeError(f'No native dependency copyright notice: {name}')
        target = licenses/'debian'/name
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(copyright, target/'copyright')
    shutil.copytree('/usr/share/common-licenses', licenses/'common-licenses', dirs_exist_ok=True)
    upstream_licenses = work.parent/'upstream-licenses'
    if upstream_licenses.is_dir():
        shutil.copytree(upstream_licenses, licenses/'upstream', dirs_exist_ok=True)
    wheels = []
    for name in ('PySide6_Essentials', 'shiboken6', 'PyInstaller', 'pyinstaller-hooks-contrib', 'altgraph', 'packaging'):
        dist = importlib.metadata.distribution(name)
        wheels.append({'name': name, 'version': dist.version, 'homepage': dist.metadata.get('Home-page', '')})
        for file in dist.files or []:
            if file.name.lower().startswith(('license', 'copyright', 'copying', 'notice')) and file.suffix not in ('.py', '.pyc'):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    # Flatten the wheel-relative path without allowing parent traversal.
                    relative = Path(*[part for part in file.parts if part not in ('..', '.')])
                    target = licenses/'python'/name/relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    sys.path.insert(0, str(root))
    from toughbook import __version__
    manifest = {'application': 'Toughbook Tools', 'version': __version__,
                'revision': __import__('os').environ.get('TOUGHBOOK_REVISION', 'unknown'),
                'architecture': platform.machine(), 'minimum_glibc': '2.36',
                'python': platform.python_version(), 'build_os_release': Path('/etc/os-release').read_text(),
                'native_packages': records, 'python_packages': wheels,
                'upstream_sources': json.loads((work.parent/'sources/UPSTREAM-SOURCES.json').read_text()),
                'host_requirements': ['Linux kernel and matching optional DKMS build prerequisites',
                    'glibc >= 2.36', 'Xorg or Wayland compositor and graphics drivers',
                    'systemd/logind and D-Bus session/system services',
                    'PipeWire with Pulse compatibility, WirePlumber and matching ACP profiles for audio repair',
                    'udevadm; polkit/pkexec or sudo for privileged operations',
                    'optional desktop-specific action providers and kscreen-doctor for KWin']}
    (work/'BUNDLE-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    analysis.datas += [('BUNDLE-MANIFEST.json', str(work/'BUNDLE-MANIFEST.json'), 'DATA')]
    for source in licenses.rglob('*'):
        if source.is_file():
            analysis.datas += [(str(Path('licenses')/source.relative_to(licenses)), str(source), 'DATA')]
