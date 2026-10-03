#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Independent PC FreeDOS KSSF regression. Not a VA media producer.

Needs a running QEMU/mtools container with --workdir /work and OUTPUT mounted
there, and the documented OW 1.9 build image. All guests are disposable.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BOOT_URL = 'https://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/distributions/1.4/FD14-FloppyEdition.zip'
BOOT_SHA = '45b1fa7c52dd996c3bfa5e352ffcd410781b952a6ad629f15a4c9ec4bbaefc5a'
PAYLOADS = {'command.com': 'COMMAND.COM', 'tools/kssf.com': 'KSSF.COM',
            'tests/kswap/PROBE.COM': 'PROBE.COM', 'tests/kswap/HOG.COM': 'HOG.COM',
            'tests/kswap/MZ.EXE': 'MZ.EXE'}


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def probe(data):
    match = re.fullmatch(rb'PSP allocation paragraphs: ([0-9A-F]{4})\r\n'
                         rb'Live COMMAND-named MCBs: ([0-9A-F]{4})\r\n', data)
    require(match is not None, 'missing or malformed MCB probe result')
    return tuple(int(value, 16) for value in match.groups())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--runtime-container', required=True)
    ap.add_argument('--build-image', default='freedos-pc88va-m19:local')
    args = ap.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    require(not (out / 'result.json').exists(), 'use a new output directory')
    require(not run('git', 'status', '--porcelain', cwd=ROOT).strip(), 'commit source first')
    revision = run('git', 'rev-parse', 'HEAD', cwd=ROOT).decode().strip()
    epoch = run('git', 'show', '-s', '--format=%ct', 'HEAD', cwd=ROOT).decode().strip()
    archive = run('git', 'archive', 'HEAD', cwd=ROOT)
    (out / 'source.tar').write_bytes(archive)
    builds = []
    for number in (1, 2):
        directory = out / ('build-' + str(number))
        directory.mkdir()
        cid = run('docker', 'create', '--network', 'none', '--platform', 'linux/amd64',
                  '--entrypoint', '/bin/bash', '-e', 'SOURCE_DATE_EPOCH=' + epoch,
                  '-v', str(out / 'source.tar') + ':/input/source.tar:ro', args.build_image,
                  '-ec', 'cd /work; tar xf /input/source.tar; bash tests/kswap/build.sh >build.log 2>&1').decode().strip()
        subprocess.run(['docker', 'start', '-a', cid], check=False)
        run('docker', 'cp', cid + ':/work/build.log', str(directory / 'build.log'))
        code = run('docker', 'inspect', '--format', '{{.State.ExitCode}}', cid).strip()
        require(code == b'0', 'build failed; container retained: ' + cid)
        records = {}
        for source, target in PAYLOADS.items():
            run('docker', 'cp', cid + ':/work/' + source, str(directory / target))
            records[target] = sha((directory / target).read_bytes())
        run('docker', 'rm', cid)
        builds.append(records)
    require(builds[0] == builds[1], 'independent build bytes differ')
    download = out / 'FD14-FloppyEdition.zip'
    if not download.exists():
        with urllib.request.urlopen(BOOT_URL, timeout=120) as response:
            download.write_bytes(response.read())
    require(sha(download.read_bytes()) == BOOT_SHA, 'FreeDOS download identity mismatch')
    with zipfile.ZipFile(download) as z:
        boot = z.read('144m/x86BOOT.img')
    (out / 'AUTOEXEC.BAT').write_bytes(b'@ECHO OFF\r\nECHO KSSF READY\r\n')

    def guest(*command):
        return run('docker', 'exec', '-u', str(os.getuid()) + ':' + str(os.getgid()),
                   args.runtime_container, *command)

    def qmp(tag, *options):
        return run(sys.executable, str(ROOT / 'tests/kswap/qmp.py'),
                   str(out / (tag + '.qmp')), *options)

    results = []
    for size in (512, 8192, 32752):
        tag = 'ksw' + str(size)
        negative = size == 32752
        image = out / (tag + '.img')
        require(not image.exists(), 'refusing to reuse a guest image')
        image.write_bytes(boot)
        (out / 'FDCONFIG.SYS').write_bytes(('FILES=20\r\nBUFFERS=10\r\nDOS=LOW\r\n'
            'SHELL=A:\\KSSF.COM A:\\COMMAND.COM /E:%d /P\r\n' % size).encode())
        guest('mcopy', '-o', '-i', image.name, 'FDCONFIG.SYS', 'AUTOEXEC.BAT', '::')
        for name in PAYLOADS.values():
            guest('mcopy', '-o', '-i', image.name, 'build-1/' + name, '::' + name)
        guest('qemu-system-i386', '-machine', 'pc', '-m', '16', '-accel', 'tcg',
              '-drive', 'file=' + image.name + ',format=raw,if=floppy', '-boot', 'a',
              '-display', 'none', '-qmp', 'unix:/work/' + tag + '.qmp,server=on,wait=off',
              '-daemonize', '-pidfile', tag + '.pid')
        screens = []
        commands = []
        try:
            for _ in range(30):
                time.sleep(1)
                screen = qmp(tag, '--screen')
                if b'KSSF READY' in screen and b'A:\\>' in screen:
                    break
            else:
                raise RuntimeError('boot did not reach the shell')

            def send(command):
                commands.append(command)
                screen = qmp(tag, '--text', command, '--screen')
                screens.append(screen.decode())
                require(b'PANIC' not in screen and b'context is missing' not in screen,
                        'guest corruption or lost context')
                require(b'A:\\>' in screen, 'no root prompt after command')

            if negative:
                send('HOG')
                for i in range(2):
                    send('call /s PROBE')
                    send('ren PROBE.OUT OOM%d.OUT' % i)
            else:
                send('set KEEP=HELLO')
                send('alias CHECK=echo ALIASOK')
                send('PROBE')
                send('ren PROBE.OUT BASE.OUT')
                send('call /s PROBE ARGUMENTS')
                send('ren PROBE.OUT FIRST.OUT')
                send('ren TAIL.OUT ARGS.OUT')
                send('history > HIST.TXT')
                send('echo %KEEP% > ENV.TXT')
                send('CHECK > ALIAS.TXT')
                for i in range(20):
                    send('call /s PROBE')
                    send('ren PROBE.OUT S%02d.OUT' % i)
                send('call /s MZ.EXE')
                # Test ERRORLEVEL before any unrelated command can change it.
                send('echo %ERRORLEVEL% > RC.TXT')
                send('CHECK > ALIAS2.TXT')
                send('echo %KEEP% > ENV2.TXT')
            send('echo FINISHED > DONE.TXT')
        finally:
            qmp(tag, '--quit')
            (out / (tag + '-commands.json')).write_text(json.dumps(commands, indent=2) + '\n')
            (out / (tag + '-screens.json')).write_text(json.dumps(screens, indent=2) + '\n')

        def read(name):
            return guest('mtype', '-i', image.name, '::' + name)

        require(read('DONE.TXT').strip() == b'FINISHED', 'workflow incomplete')
        if negative:
            samples = [probe(read('OOM%d.OUT' % i)) for i in range(2)]
            require(all(0 < allocation <= 1024 and owners > 0 for allocation, owners in samples),
                    'OOM must fall back to ordinary execution with shell resident')
            require(samples[0] == samples[1], 'failed swaps changed allocation accounting')
            require(any('Unable' in text or 'memory' in text.lower() for text in screens),
                    'missing allocation failure diagnostic')
        else:
            baseline = probe(read('BASE.OUT'))
            samples = [probe(read('S%02d.OUT' % i)) for i in range(20)]
            require(baseline[1] > 0, 'ordinary command did not retain the shell')
            require(all(owners == 0 and allocation > baseline[0] for allocation, owners in samples),
                    'swapped child did not gain memory / retained a live shell')
            require(len(set(samples)) == 1, 'repeated swaps leaked or changed allocation accounting')
            require(read('ARGS.OUT').strip() == b'ARGUMENTS', 'lost command tail')
            require(b'set KEEP=HELLO' in read('HIST.TXT'), 'lost history')
            for name in ('ENV.TXT', 'ENV2.TXT'):
                require(read(name).strip() == b'HELLO', 'lost environment')
            for name in ('ALIAS.TXT', 'ALIAS2.TXT'):
                require(read(name).strip() == b'ALIASOK', 'lost alias')
            require(read('MZ.OK') == b'MZ relocation OK\r\n', 'MZ did not execute')
            require(read('RC.TXT').strip() == b'7', 'lost child return code')
        results.append({'environment_bytes': size, 'negative': negative,
                        'samples': samples, 'guest_disk_sha256': sha(image.read_bytes())})
    record = {'source_revision': revision, 'source_archive_sha256': sha(archive),
              'source_date_epoch': epoch, 'two_builds_equal': True, 'binaries': builds[0],
              'build_image_id': run('docker', 'image', 'inspect', '--format', '{{.Id}}', args.build_image).decode().strip(),
              'qemu_version': guest('qemu-system-i386', '--version').decode(),
              'runtime_tools': guest('sha256sum', '/usr/bin/qemu-system-i386', '/usr/bin/mtools').decode(),
              'boot_archive_sha256': BOOT_SHA, 'boot_image_sha256': sha(boot),
              'cases': results, 'scope': 'Independent PC FreeDOS regression; VA and hardware NOT RUN'}
    (out / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
    print('PC FreeDOS KSSF regression passed; no VA or hardware claim.')


if __name__ == '__main__':
    main()
