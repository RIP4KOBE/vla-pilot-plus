"""Controlled child fixture: only pipes, signal handling and bounded sleeps."""
import os
import signal
import sys
import time

mode = sys.argv[1]
valid = b'a' * 40 + b' blob 3\nabc\n'
if mode == 'good':
    os.write(1, valid)
elif mode == 'maximum':
    os.write(1, b'a' * 40 + b' blob 1048576\n')
    for _ in range(256):
        os.write(1, b'x' * 4096)
    os.write(1, b'\n')
elif mode == 'split':
    for b in valid:
        os.write(1, bytes([b]))
        time.sleep(.001)
elif mode == 'empty':
    os.write(1, b'a' * 40 + b' blob 0\n\n')
elif mode == 'missing':
    os.write(1, b'b' * 40 + b'^{commit}:file.txt missing\n')
elif mode == 'type':
    os.write(1, b'a' * 40 + b' tree 3\nabc\n')
elif mode == 'size':
    os.write(1, b'a' * 40 + b' blob 1048577\n')
elif mode == 'mismatch':
    os.write(1, b'a' * 40 + b' blob 4\n')
elif mode == 'leading-zero':
    os.write(1, b'a' * 40 + b' blob 03\nabc\n')
elif mode == 'bad-oid':
    os.write(1, b'z' * 40 + b' blob 3\nabc\n')
elif mode == 'header':
    os.write(1, b'x' * 129)
elif mode == 'short':
    os.write(1, valid[:-2])
elif mode == 'no-trailer':
    os.write(1, valid[:-1])
elif mode == 'bad-trailer':
    os.write(1, valid[:-1] + b'X')
elif mode == 'excess':
    os.write(1, valid + b'X')
elif mode == 'later-excess':
    os.write(1, valid)
    time.sleep(.02)
    os.write(1, b'X')
elif mode == 'stderr':
    os.write(1, valid)
    os.write(2, b'e')
elif mode == 'stderr-overflow':
    for _ in range(17):
        os.write(2, b'e' * 4096)
elif mode == 'nonzero':
    os.write(1, valid)
    sys.exit(7)
elif mode == 'timeout':
    time.sleep(2)
elif mode == 'ignore-term':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    time.sleep(2)
elif mode == 'closed-pipes':
    os.close(1)
    os.close(2)
    time.sleep(2)
else:
    raise ValueError('unexpected fixture mode')
