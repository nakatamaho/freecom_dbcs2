# SPDX-License-Identifier: GPL-2.0-or-later
"""Assemble KSSF's actual reload span at its required 8086 ISA boundary."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CpuContractTests(unittest.TestCase):
    def test_long_reload_branch_does_not_silently_require_a_386(self):
        source = (ROOT / 'tools/kssf.asm').read_text()
        cpu = re.search(r'^CPU\s+8086\b[^\n]*', source, re.MULTILINE)
        self.assertIsNotNone(cpu, 'KSSF must explicitly constrain its instruction set')
        span = source[source.index('mainloop:'):source.index('exit:', source.index('mainloop:'))]
        # Symbolic data addresses stand in for the generated context interface;
        # its operands retain their actual instruction widths. No guest artifact
        # or saved generated header is an input to this boundary regression.
        names = set(re.findall(r'\?[A-Za-z_]+', span)) | {
            'ctxt_owner', 'execBlock', 'tsrend', 'STACK_SIZE', 'context',
            'eb_envseg', 'eb_cmdline', 'shellCmdLine',
        }
        definitions = ''.join('%define ' + name + ' 512\n' for name in sorted(names))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for directive in (cpu.group(0), ''):
                assembly = 'BITS 16\n' + directive + '\n' + definitions + span + '\nexit:\nerrExecShell:\n'
                (root / 'span.asm').write_text(assembly)
                subprocess.run(['nasm', '-f', 'bin', str(root / 'span.asm'),
                                '-o', str(root / 'span.bin')], check=True)
                binary = (root / 'span.bin').read_bytes()
                if directive:
                    self.assertEqual(binary[-5:-2], b'\x74\x03\xe9')
                else:
                    # Prove the original unconstrained span does cross rel8.
                    self.assertEqual(binary[-4:-2], b'\x0f\x85')
                self.assertEqual(len(binary) + int.from_bytes(binary[-2:], 'little', signed=True), 0)


if __name__ == '__main__':
    unittest.main()
