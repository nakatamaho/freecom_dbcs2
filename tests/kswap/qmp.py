#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Send interactive DOS commands to a research QEMU, not to a VA guest.

QMP socket and VGA dump must share a directory mounted at /work in QEMU's
container. This helper only injects keys and reads text; it asserts no PASS.
"""
import argparse
import json
from pathlib import Path
import socket
import time


def key(ch):
    special = {' ': 'spc', ':': 'shift-semicolon', '\\': 'backslash',
               '/': 'slash', '.': 'dot', '-': 'minus', '=': 'equal',
               '>': 'shift-dot', '<': 'shift-comma', '_': 'shift-minus',
               '?': 'shift-slash', '%': 'shift-5'}
    if ch in special:
        return special[ch]
    if ch.isascii() and ch.isalnum():
        return ('shift-' + ch.lower()) if ch.isupper() else ch
    raise ValueError('unsupported key: ' + repr(ch))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('socket', type=Path)
    parser.add_argument('--text')
    parser.add_argument('--screen', action='store_true')
    parser.add_argument('--quit', action='store_true')
    args = parser.parse_args()
    keys = [key(ch) for ch in args.text] if args.text is not None else []
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(15)
        s.connect(str(args.socket))
        f = s.makefile('rwb')
        greeting = json.loads(f.readline())
        if 'QMP' not in greeting:
            raise ValueError('not a QMP server')
        number = 0

        def execute(command, arguments=None):
            nonlocal number
            number += 1
            request = {'execute': command, 'id': number}
            if arguments is not None:
                request['arguments'] = arguments
            f.write((json.dumps(request) + '\n').encode())
            f.flush()
            while True:
                line = f.readline()
                if not line:
                    raise EOFError('QMP disconnected')
                reply = json.loads(line)
                if reply.get('id') == number:
                    if 'error' in reply:
                        raise RuntimeError(reply['error'])
                    return reply['return']

        execute('qmp_capabilities')
        for code in keys + (['ret'] if args.text is not None else []):
            result = execute('human-monitor-command', {'command-line': 'sendkey ' + code + ' 30'})
            if result:
                raise RuntimeError(result)
            time.sleep(.08)
        if args.screen:
            time.sleep(1)
            filename = args.socket.stem + '.vga'
            result = execute('human-monitor-command', {
                'command-line': 'pmemsave 0xb8000 4000 "' + '/work/' + filename + '"'})
            if result:
                raise RuntimeError(result)
            data = (args.socket.parent / filename).read_bytes()
            if len(data) != 4000:
                raise ValueError('short VGA dump')
            for row in range(25):
                print(data[row*160:(row+1)*160:2].decode('cp437').rstrip())
        if args.quit:
            execute('quit')


if __name__ == '__main__':
    main()
