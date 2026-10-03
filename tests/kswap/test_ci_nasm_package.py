# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the CI extraction line against an original synthetic Unix ZIP."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]


class NasmPackageTests(unittest.TestCase):
    def test_unix_origin_uppercase_entries_reach_the_configured_tool_directory(self):
        lines = (ROOT / 'ci_prereq.sh').read_text().splitlines()
        commands = [s.strip() for s in lines if s.strip().startswith('unzip ') and '${HERE}/nasm.zip' in s]
        self.assertEqual(len(commands), 1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs, output, control = (root / name for name in ('inputs', 'output', 'control'))
            for directory in (inputs, output, control):
                directory.mkdir()
            with zipfile.ZipFile(inputs / 'nasm.zip', 'w') as archive:
                for name in ('NASM.EXE', 'CWSDPMI.EXE'):
                    item = zipfile.ZipInfo('DEVEL/NASM/' + name)
                    item.create_system = 3  # Unix; unzip -L does not lowercase these.
                    item.external_attr = 0o100644 << 16
                    archive.writestr(item, b'synthetic fixture, not a DOS executable')
            subprocess.run(['unzip', '-L', '-q', str(inputs / 'nasm.zip')],
                           cwd=control, check=True)
            self.assertTrue((control / 'DEVEL/NASM/NASM.EXE').is_file())
            self.assertFalse((control / 'devel/nasm/nasm.exe').exists())
            subprocess.run(['sh', '-ec', commands[0]], cwd=output,
                           env=dict(os.environ, HERE=str(inputs)), check=True)
            for name in ('nasm.exe', 'cwsdpmi.exe'):
                self.assertEqual((output / 'devel/nasm' / name).read_bytes(),
                                 b'synthetic fixture, not a DOS executable')


if __name__ == '__main__':
    unittest.main()
