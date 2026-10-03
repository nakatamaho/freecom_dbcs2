#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Run from a clean source archive inside the OW 1.9 Linux/amd64 container.
set -euo pipefail
: "${SOURCE_DATE_EPOCH:?pass the source commit timestamp}"
export PATH=/opt/openwatcom-1.9/binl:$PATH
export WATCOM=/opt/openwatcom-1.9 INCLUDE=/opt/openwatcom-1.9/h
export LIB='/opt/openwatcom-1.9/lib286;/opt/openwatcom-1.9/lib286/dos'
export LC_ALL=C TZ=UTC
python3 - <<'PY'
from datetime import datetime, timezone
import os
from pathlib import Path
stamp = datetime.fromtimestamp(int(os.environ['SOURCE_DATE_EPOCH']), timezone.utc)
source = Path('config.std').read_text()
assert source.count('$(CFG):') == 1
flags = ('CFLAGS2 = -DFREECOM_BUILD_DATE=\\"' + stamp.strftime('%b %d %Y') +
         '\\" -DFREECOM_BUILD_TIME=\\"' + stamp.strftime('%H:%M:%S') + '\\"\n')
Path('config.mak').write_text(source.replace('$(CFG):', flags + '$(CFG):', 1))
PY
gcc utilsc/critstrs.c -o utilsc/critstrs.exe
bash build.sh ibmpc no-xms-swap wc english
(cd tools && nasm -f bin kssf.asm -o kssf.com)
nasm -f bin tests/kswap/probe.asm -o tests/kswap/PROBE.COM
nasm -f bin tests/kswap/hog.asm -o tests/kswap/HOG.COM
nasm -f bin tests/kswap/mz.asm -o tests/kswap/MZ.EXE
