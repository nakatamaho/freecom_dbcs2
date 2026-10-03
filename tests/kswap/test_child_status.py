# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the actual status decoder with synthetic DOS API responses."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include <assert.h>
#define dprintf(x) ((void)0)
#define CBREAK_ERRORLEVEL 130
static int ctrlBreak, errorlevel, reports, calls, displays;
static unsigned dos_status;
#ifdef DISP_EXITCODE
static int exitReason;
static void displayExitcode(void) { ++displays; }
#endif
typedef struct { unsigned r_ax; } IREGS;
static void intrpt(int n, IREGS *r) {
 assert(n==0x21 && r->r_ax==0x4d00); ++calls; r->r_ax=dos_status;
}
static void error_bad_mcb_chain(void) { reports=7; }
static void error_out_of_dos_memory(void) { reports=8; }
static void error_exe_corrupt(void) { reports=13; }
static void error_unknown(int rc) { reports=rc; }
'''
CASES = r'''
int main(void) {
 int i, reason; unsigned codes[]={0,7,8,13,255};
 for(reason=0;reason<4;reason++) for(i=0;i<5;i++) {
  unsigned status=(reason<<8)|codes[i];
  ctrlBreak=errorlevel=reports=calls=displays=0;
  setChildStatus(status);
  assert(calls==0 && reports==0);
  assert(ctrlBreak==(reason==1 || reason==2));
  assert(errorlevel==((ctrlBreak && !codes[i])?130:codes[i]));
#ifdef DISP_EXITCODE
  assert(exitReason==reason && displays==1);
#endif
  ctrlBreak=errorlevel=reports=calls=displays=0; dos_status=status;
  setErrorLevel(0);
  assert(calls==1 && reports==0);
  assert(errorlevel==((ctrlBreak && !codes[i])?130:codes[i]));
 }
 for(i=1;i<5;i++) {
  ctrlBreak=errorlevel=reports=calls=displays=0;
  setErrorLevel(codes[i]);
  assert(calls==0 && reports==codes[i] && errorlevel==codes[i]);
#ifdef DISP_EXITCODE
  assert(exitReason==-1 && displays==1);
#endif
 }
 ctrlBreak=1; calls=reports=0; setChildStatus(0);
 assert(errorlevel==130 && calls==0 && reports==0);
 return 0;
}
'''


class ChildStatusTests(unittest.TestCase):
    def test_actual_decoder_distinguishes_api_errors_from_child_status(self):
        source = (ROOT / 'lib/exec1.c').read_text()
        functions = source[source.index('void setChildStatus(unsigned status)'):]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'test.c').write_text(HARNESS + functions + CASES)
            for flags in ([], ['-DDISP_EXITCODE']):
                with self.subTest(flags=flags):
                    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', *flags,
                                    str(root / 'test.c'), '-o', str(root / 'test')], check=True)
                    subprocess.run([str(root / 'test')], check=True)


if __name__ == '__main__':
    unittest.main()
