#!/usr/bin/python3
"""Build an allowlisted, reproducible source archive. SPDX-License-Identifier: MIT"""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from toughbook import __version__

TOP = {'README.md', 'LICENSE', 'THIRD_PARTY.md', 'CHANGELOG.md', '.gitignore',
       'calibrate-screen.py', 'fix-audio.py', 'toughbook-buttons.py', 'toughbook-tools.py'}


def release_files(root=ROOT):
    result = [root/name for name in TOP]
    for folder, suffix in [('toughbook','.py'), ('tests','.py'), ('tools','.py'), ('tools','.sh'), ('docs','.md')]:
        result += [p for p in (root/folder).rglob('*'+suffix) if '__pycache__' not in p.parts]
    result += [root/'data'/name for name in ('org.toughbook.Tools.desktop.in', 'org.toughbook.Tools.svg', 'org.toughbook.Buttons.desktop.in',
        'org.toughbook.Buttons-autostart.desktop', 'toughbook-buttons.service.in')]
    driver_names = {'panasonic-hbtn.c', 'hbtn-decode.h', 'Makefile', 'dkms.conf',
                    'install.sh', 'uninstall.sh', 'README.md', 'COPYING',
                    '70-panasonic-hbtn.rules', 'test-hbtn-decode.c'}
    result += [root/'driver'/name for name in driver_names]
    if not all(p.is_file() and not p.is_symlink() for p in result):
        raise RuntimeError('A required release source is missing or is a symlink.')
    return sorted(result, key=lambda p: str(p.relative_to(root)))


def build(destination):
    name = f'toughbook-fedora-tools-{__version__}'
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.PAX_FORMAT) as archive:
        for path in release_files():
            relative = path.relative_to(ROOT)
            info = tarfile.TarInfo(str(Path(name)/relative))
            data = path.read_bytes()
            info.size, info.mtime, info.uid, info.gid = len(data), 0, 0, 0
            info.uname = info.gname = ''
            info.mode = 0o755 if relative.name in {'calibrate-screen.py','fix-audio.py','make-release.py','toughbook-buttons.py','toughbook-tools.py','install.sh','uninstall.sh','setup-ubuntu.sh'} else 0o644
            archive.addfile(info, io.BytesIO(data))
    destination.mkdir(parents=True, exist_ok=True)
    path = destination/f'{name}.tar.gz'
    path.write_bytes(gzip.compress(stream.getvalue(), mtime=0))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(path.suffix+'.sha256').write_text(f'{digest}  {path.name}\n')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT.parent,
                        help='Archive destination (default: parent of source directory)')
    print(build(parser.parse_args().output_dir))
