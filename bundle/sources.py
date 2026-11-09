"""Collect corresponding sources and their license notices. SPDX-License-Identifier: MIT"""
from concurrent.futures import ThreadPoolExecutor
import ctypes
import hashlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
from urllib.request import urlopen
import zipfile


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def download(record, destination):
    path = destination/record['filename']
    if path.exists() and record.get('sha256') and digest(path) != record['sha256']:
        path.unlink()
    if not path.exists():
        print('Source download: ' + record['name'], flush=True)
        temporary = path.with_suffix(path.suffix + '.partial')
        with urlopen(record['url'], timeout=120) as response, temporary.open('wb') as output:
            shutil.copyfileobj(response, output, 1024 * 1024)
        if record.get('sha256') and digest(temporary) != record['sha256']:
            temporary.unlink()
            raise RuntimeError('Source digest mismatch: ' + record['name'])
        temporary.replace(path)
    return {**record, 'sha256': digest(path)}


def license_member(name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or len(relative.parts) < 2:
        return None
    if relative.suffix in ('.py', '.pyc', '.pyo'):
        return None
    basename = relative.name.upper()
    if (basename.startswith(('LICENSE', 'COPYING', 'COPYRIGHT', 'NOTICE')) or
            'LICENSES' in relative.parts or basename == 'QT_ATTRIBUTION.JSON'):
        return Path(*relative.parts[1:])
    return None


def extract_licenses(record, source_dir, destination):
    path = source_dir/record['filename']
    target_root = destination/record['name']
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                relative = license_member(member.filename)
                if relative is not None and not member.is_dir() and member.file_size < 4 * 1024 * 1024:
                    target = target_root/relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(member))
    else:
        with tarfile.open(path) as archive:
            for member in archive:
                relative = license_member(member.name)
                if relative is not None and member.isfile() and member.size < 4 * 1024 * 1024:
                    target = target_root/relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(member).read())


def upstream(work):
    import PySide6
    source_dir = work/'sources'
    source_dir.mkdir(parents=True, exist_ok=True)
    version = importlib.metadata.version('PySide6_Essentials')
    records = [{'name': name, 'version': version, 'filename': name+'-'+version+'.tar.gz',
                'url': f'https://codeload.github.com/qt/{name}/tar.gz/refs/tags/v{version}'}
               for name in ('qtbase', 'qtwayland', 'qtsvg', 'qtimageformats')]
    records.append({'name': 'pyside-setup', 'version': version, 'filename': 'pyside-setup-'+version+'.tar.gz',
                    'url': f'https://codeload.github.com/pyside/pyside-setup/tar.gz/refs/tags/v{version}'})
    # Qt's wheels include ICU independently of the build distribution packages.
    library = next((Path(PySide6.__file__).parent/'Qt/lib').glob('libicuuc.so.*'))
    major = library.name.split('.so.')[1].split('.')[0]
    value = (ctypes.c_uint8 * 4)()
    getattr(ctypes.CDLL(str(library)), 'u_getVersion_' + major)(value)
    icu = '.'.join(map(str, value[:2]))
    records.append({'name': 'icu', 'version': icu, 'filename': 'icu-'+icu+'.tar.gz',
                    'url': 'https://codeload.github.com/unicode-org/icu/tar.gz/refs/tags/release-' + icu.replace('.', '-')})
    for name in ('PyInstaller', 'pyinstaller-hooks-contrib', 'altgraph', 'packaging'):
        version = importlib.metadata.version(name)
        with urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=30) as response:
            metadata = json.load(response)
        source = next(file for file in metadata['urls'] if file['packagetype'] == 'sdist')
        records.append({'name': name, 'version': version, 'filename': source['filename'],
                        'url': source['url'], 'sha256': source['digests']['sha256']})
    with ThreadPoolExecutor(max_workers=4) as executor:
        completed = list(executor.map(lambda record: download(record, source_dir), records))
    for record in completed:
        extract_licenses(record, source_dir, work/'upstream-licenses')
    (source_dir/'UPSTREAM-SOURCES.json').write_text(json.dumps(completed, indent=2) + '\n')
    return completed


def native(manifest, work):
    source_dir = work/'sources'
    pairs = sorted({(package['source'], package['source_version']) for package in manifest['native_packages']})
    for name, version in pairs:
        print('Debian corresponding source: ' + name + '=' + version, flush=True)
        subprocess.run(['apt-get', '-qq', 'source', '--download-only', '--only-source', name+'='+version],
                       cwd=source_dir, check=True)


def index(manifest, work):
    source_dir = work/'sources'
    pairs = sorted({(package['source'], package['source_version']) for package in manifest['native_packages']})
    files = {path.name: digest(path) for path in sorted(source_dir.iterdir()) if path.is_file() and path.name != 'SOURCES-INDEX.json'}
    (source_dir/'SOURCES-INDEX.json').write_text(json.dumps({'native_sources': pairs, 'files_sha256': files}, indent=2) + '\n')
