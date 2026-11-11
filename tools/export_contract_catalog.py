#!/usr/bin/env python3
"""Inventory ALL client MIDs and bytecode reference candidates, not inferred schemas.

Usage: python3 tools/export_contract_catalog.py <assets/src_64> <luajit> <output.json>
The output separates observed names from unverified request/response contracts.
"""
import json
from pathlib import Path
import subprocess
import sys

root, executable, output = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
program = 'xyd={}; dofile(' + json.dumps(str(root / 'app/common/network/mid.lua')) + '); for k,v in pairs(xyd.mid) do print(k,v) end'
definitions = subprocess.check_output([executable, '-e', program], text=True)
entries = []
files = [(str(p.relative_to(root)), p.read_bytes()) for p in sorted((root / 'app').rglob('*.lua'))
         if p.name != 'mid.lua']

def uleb(number):
    data = bytearray()
    while number >= 128:
        data.append((number & 127) | 128)
        number >>= 7
    data.append(number)
    return bytes(data)

for line in definitions.splitlines():
    name, number = line.split()
    value = name.encode()
    # LuaJIT KGC string encoding: ULEB(length + 5), then raw UTF-8.
    marker = uleb(len(value) + 5) + value
    entries.append({'mid': int(number), 'name': name,
                    'reference_candidates': [path for path, blob in files if marker in blob],
                    'schema_status': 'not_verified'})
output.write_text(json.dumps({'source': 'Original APK 1.631.0 src_64',
    'warning': 'Reference candidates are string-constant matches, not proof of call sites or complete schemas. No server logic is inferred.',
    'endpoints': sorted(entries, key=lambda item: (item['mid'], item['name']))}, indent=2) + '\n')
print(f'Exported {len(entries)} named MIDs to {output}')
