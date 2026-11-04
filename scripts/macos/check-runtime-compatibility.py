#!/usr/bin/env python3
"""Reject a bundle that raises CutNotes' macOS 15 deployment target."""
from pathlib import Path
import re
import subprocess
import sys
root=Path(__file__).resolve().parent
paths=subprocess.check_output([sys.executable,str(root/'macho-files.py'),sys.argv[1]],text=True).splitlines()
failures=[]
for path in paths:
    output=subprocess.check_output(['/usr/bin/otool','-hvl',path],text=True)
    if Path(path).suffix == '.o' or re.search(r'\bOBJECT\b', output):
        failures.append(str(Path(path).relative_to(sys.argv[1])) + ': link-time object must not ship')
    versions=re.findall(r'\bminos\s+([\d.]+)',output)
    versions += re.findall(r'cmd LC_VERSION_MIN_MACOSX\s+cmdsize \d+\s+version ([\d.]+)', output)
    if any(tuple(map(int,version.split('.')[:2])) > (15,0) for version in versions):
        failures.append(str(Path(path).relative_to(sys.argv[1]))+': '+', '.join(versions))
if failures:
    sys.exit('Runtime packaging validation failed:\n'+'\n'.join(failures))
print(f'Checked minimum OS for {len(paths)} Mach-O files.')
