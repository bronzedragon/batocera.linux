#!/usr/bin/env python3
"""Import Thomas Daley's 2017 GB_ROM_INFO.txt as advisory GB/GBC ROM metadata.

The input catalog does not contain SHA-1/CRC32 fingerprints. Metadata signatures
must NEVER be treated as exact identification or proof of network-link support.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

SEPARATOR = '------------------- ROM INFO -------------------'
FIELDS = ('Title','CGB Flag','SGB Flag','Cartridge Type','ROM Size','RAM Size',
          'Destination','New Licensee','Old Licensee','ROM Version','Header Checksum','Global Checksum')

def parse_records(text):
    for section in text.split(SEPARATOR)[1:]:
        lines = [line.strip() for line in section.splitlines() if line.strip()]
        if not lines: continue
        filename = lines[0]
        if not filename.lower().endswith(('.gb','.gbc')): continue
        meta = {'filename':filename, 'system_hint':Path(filename).suffix.lower().lstrip('.')}
        for line in lines[1:]:
            for field in FIELDS:
                if line.startswith(field) and (len(line)==len(field) or line[len(field)].isspace()):
                    meta[field] = line[len(field):].strip()
                    break
        size_line = next((l for l in lines[1:] if l.startswith('Size: ')),None)
        if size_line:
            try: meta['file_size'] = int(size_line.split()[1])
            except (IndexError,ValueError): pass
        for key,new_key in (('Header Checksum','header_checksum'),('Global Checksum','global_checksum')):
            value=meta.pop(key, None)
            if value:
                match=re.match(r'0x([0-9A-Fa-f]+)\s+\((Pass|Fail)\)',value)
                if match:
                    meta[new_key]={'value':match.group(1).lower(), 'valid':match.group(2)=='Pass'}
        for key,new_key in (('CGB Flag','cgb_flag'),('SGB Flag','sgb_flag'),('ROM Version','rom_version')):
            value=meta.pop(key,None)
            if value:
                m=re.match(r'0x([0-9A-Fa-f]+)',value)
                if m:meta[new_key]=int(m.group(1),16)
        for key in FIELDS:
            if key in meta:meta[key.lower().replace(' ','_')]=meta.pop(key)
        yield meta

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    records=list(parse_records(args.source.read_text(encoding='utf-8-sig',errors='replace')))
    obj={'schema_version':1,'source_title':'GB_ROM_INFO.txt','source_author':'Thomas Daley',
         'source_date':'2017-05-15','usage':'advisory_metadata_only',
         'warning':'NO SHA-1/CRC32; never promote these entries to exact_hash',
         'record_count':len(records),'records':records}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print('records:',len(records))
    print('platforms:',dict(Counter(r['system_hint'] for r in records)))
    print('header and global checksum both pass:',sum(r.get('header_checksum',{}).get('valid') and r.get('global_checksum',{}).get('valid') for r in records))

if __name__=='__main__':main()