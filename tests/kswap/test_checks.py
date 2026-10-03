# SPDX-License-Identifier: GPL-2.0-or-later
import unittest
from run import at_root_prompt, probe, require
from qmp import key


class Checks(unittest.TestCase):
    def test_probe(self):
        self.assertEqual(probe(b'PSP allocation paragraphs: 8F6B\r\n'
                               b'Live COMMAND-named MCBs: 0000\r\n'), (0x8f6b, 0))

    def test_reject_missing_malformed_or_extra_probe_data(self):
        valid = b'PSP allocation paragraphs: 8F6B\r\nLive COMMAND-named MCBs: 0000\r\n'
        for data in (b'', valid[:-2], valid + b'PASS', valid.replace(b'8F6B', b'-001'),
                     valid.replace(b'8F6B', b'12345'), valid.replace(b'0000', b'G000'),
                     valid.replace(b'\r\n', b'\n')):
            with self.subTest(data=data), self.assertRaises(RuntimeError):
                probe(data)

    def test_failed_gate_raises(self):
        with self.assertRaises(RuntimeError):
            require(False, 'not run')

    def test_reject_stale_prompt_during_a_resource_question(self):
        self.assertTrue(at_root_prompt(b'READY\nA:\\>\n\n'))
        self.assertFalse(at_root_prompt(b'A:\\>call /s PROBE\nEnter another location:\n'))
        self.assertFalse(at_root_prompt(b''))

    def test_keys(self):
        self.assertEqual(key('%'), 'shift-5')
        with self.assertRaises(ValueError):
            key('\n')


if __name__ == '__main__':
    unittest.main()
