#!/usr/bin/env python3
"""List regular Mach-O files without spawning `file` for every Python source."""
import os
from pathlib import Path
import sys
MAGIC = {bytes.fromhex(value) for value in ('feedface','cefaedfe','feedfacf','cffaedfe','cafebabe','bebafeca','cafebabf','bfbafeca')}
for directory, _, files in os.walk(sys.argv[1]):
    for name in files:
        path = Path(directory) / name
        if path.is_symlink():
            continue
        with path.open('rb') as stream:
            if stream.read(4) in MAGIC:
                print(path)
