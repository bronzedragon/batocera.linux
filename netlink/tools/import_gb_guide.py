#!/usr/bin/env python3
"""Convert a user-provided ReyVGM Game Boy guide into NetLink *reference* data.

Tags are claims about original hardware, not validation of any emulated
NetLink session. Never use the resulting reference table as a hash whitelist.
"""
import argparse
import json
import re
from pathlib import Path

UNDERLINE = re.compile(r'^[¯￣]{3,}$')
TAG = re.compile(r'#([^#]+?)(?=\s+#|$)')
PLAYER_RANGE = re.compile(r'^(\d+)(?:-(\d+))? Players$')
CANONICAL = {'Link Cable','4P Adapter','Infrared','SNES Controller','Super Multitap',
             'Passing','Holding','Transfer','SaveMigration','LinkOther','GBKiss',
             'Competitive','Cooperative','Compet&Co-op','Barcode','Printer',
             'GB Only','SGB Only','Japan Only','No Link'}
SOURCE = 'https://gamefaqs.gamespot.com/gameboy/916375-game-boy/faqs/82719'

def parse_guide(text):
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if 'The Games  ' in line)
    stop = next(i for i, line in enumerate(lines) if '/ Thanks ' in line)
    results=[]
    for i in range(start+1,stop-2):
        if not lines[i].strip() or not UNDERLINE.fullmatch(lines[i+1].strip()):
            continue
        title=lines[i].strip()
        j=i+2
        while j < stop and not lines[j].strip(): j+=1
        taglines=[]
        # Single collection may list multiple modes, each with different tags.
        if title == 'Namco Gallery Vol.3':
            while j < stop and lines[j].strip() and '#' in lines[j]:
                taglines.append(lines[j].strip())
                j+=1
        else:
            while j < stop and lines[j].lstrip().startswith('#'):
                taglines.append(lines[j].strip()); j+=1
        if not taglines:
            raise ValueError(f'Could not read tags for {title} on line {i+1}')
        modes=[]
        for raw in taglines:
            # On the special collection, preserve the sub-game name.
            label, sep, raw_tags = raw.partition(': #')
            if sep and title == 'Namco Gallery Vol.3':
                raw_tags='#'+raw_tags
            else:
                label=None
                raw_tags=raw
            tags=[t.strip() for t in TAG.findall(raw_tags)]
            unrecognized=[t for t in tags if t not in CANONICAL and not PLAYER_RANGE.fullmatch(t)]
            if unrecognized: raise ValueError(f'Unexpected tags for {title}: {unrecognized}')
            players=[]
            for tag in tags:
                match=PLAYER_RANGE.fullmatch(tag)
                if match:
                    players.append({'min':int(match.group(1)), 'max':int(match.group(2) or match.group(1))})
            modes.append({
                **({'game_in_collection':label} if label else {}),
                'tags':tags,
                'links':{'cable':'Link Cable' in tags, 'four_player_adapter':'4P Adapter' in tags,
                         'infrared':'Infrared' in tags,'gbkiss':'GBKiss' in tags,
                         'snes_controller':'SNES Controller' in tags,
                         'super_multitap':'Super Multitap' in tags},
                'no_link': 'No Link' in tags,
                'player_ranges':players,
                'regional_restriction': 'japan_only' if 'Japan Only' in tags else None,
            })
        results.append({'title':title,'system':'gb','source_line':i+1,'modes':modes})
    return {'schema_version':1,'source':SOURCE,'source_author':'ReyVGM',
            'provenance':'user-provided guide; unverified by NetLink',
            'game_count':len(results),'games':results}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    result=parse_guide(args.source.read_text(encoding='utf-8-sig'))
    if result['game_count'] != 393:
        raise ValueError(f'Expected 393 guide entries; got {result["game_count"]}')
    args.destination.parent.mkdir(parents=True,exist_ok=True)
    args.destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Imported',result['game_count'],'entries')
    for key in ('cable','four_player_adapter','infrared','snes_controller'):
        print(key, sum(any(m['links'][key] for m in g['modes']) for g in result['games']))

if __name__=='__main__':main()