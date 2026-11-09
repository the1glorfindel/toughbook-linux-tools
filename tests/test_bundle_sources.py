"""Portable source collection must preserve notices without extracting unsafe paths."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('bundle_sources', Path(__file__).resolve().parents[1]/'bundle/sources.py')
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)


class BundleSourceTests(unittest.TestCase):
    def test_license_selection_rejects_traversal_and_executable_code(self):
        for name in ('/pkg/LICENSE', 'pkg/../LICENSE', 'pkg/LICENSE.py', 'pkg/licenses.py'):
            self.assertIsNone(sources.license_member(name))
        self.assertEqual(sources.license_member('pkg/LICENSES/LGPL-3.0-only.txt'), Path('LICENSES/LGPL-3.0-only.txt'))

    def test_license_extraction_ignores_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with tarfile.open(root/'source.tar.gz', 'w:gz') as archive:
                legal = tarfile.TarInfo('pkg/LICENSE')
                legal.size = 6
                archive.addfile(legal, io.BytesIO(b'notice'))
                link = tarfile.TarInfo('pkg/COPYING')
                link.type, link.linkname = tarfile.SYMTYPE, '/etc/passwd'
                archive.addfile(link)
            sources.extract_licenses({'filename': 'source.tar.gz', 'name': 'sample'}, root, root/'notices')
            self.assertEqual((root/'notices/sample/LICENSE').read_text(), 'notice')
            self.assertFalse((root/'notices/sample/COPYING').exists())

    def test_download_rejects_wrong_source_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            record = {'name': 'sample', 'filename': 'source.tar', 'url': 'https://example.invalid/source', 'sha256': '0'*64}
            with patch.object(sources, 'urlopen', return_value=io.BytesIO(b'wrong source')):
                with self.assertRaisesRegex(RuntimeError, 'digest mismatch'):
                    sources.download(record, Path(folder))
            self.assertFalse((Path(folder)/'source.tar').exists())

    def test_source_index_covers_application_and_native_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'sources').mkdir()
            (root/'sources/app.tar.gz').write_bytes(b'application')
            sources.index({'native_packages': [{'source': 'libexample', 'source_version': '1.0'}]}, root)
            import json
            index = json.loads((root/'sources/SOURCES-INDEX.json').read_text())
            self.assertEqual(index['files_sha256']['app.tar.gz'], hashlib.sha256(b'application').hexdigest())
            self.assertEqual(index['native_sources'], [['libexample', '1.0']])
