import os
import sys
import tempfile


class SingleInstance:
    def __init__(self, lockname):
        self.lockfile = os.path.join(tempfile.gettempdir(), f'{lockname}.lock')
        self.fp = None

    def acquire(self):
        if os.path.exists(self.lockfile):
            print('多重起動防止: 既に起動しています。')
            sys.exit(1)
        self.fp = open(self.lockfile, 'w')
        self.fp.write(str(os.getpid()))
        self.fp.flush()

    def release(self):
        if self.fp:
            self.fp.close()
        if os.path.exists(self.lockfile):
            os.remove(self.lockfile)
