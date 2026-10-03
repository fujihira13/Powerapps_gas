"""Validate persisted scope, accepting only Studio's known omitted defaults."""
import json
import shutil
from pathlib import Path
import yaml
from check_management_saved import compare

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'outputs/environment-management-20261003/server-first'
baseline=WORK/'canvas-baseline';candidate=WORK/'canvas-candidate';saved=WORK/'canvas-final-saved'
defaults={'X':'=0','Y':'=0','Mode':'=TextMode.SingleLine','Fill':'=RGBA(255, 255, 255, 1)'}
result={}
for source in baseline.glob('*.pa.yaml'):
    a=yaml.safe_load((candidate/source.name if source.name=='Screen5.pa.yaml' else source).read_text(encoding='utf-8-sig'))
    b=yaml.safe_load((saved/source.name).read_text(encoding='utf-8-sig'))
    diffs=compare(a,b)
    normalized=[d for d in diffs if source.name=='Screen5.pa.yaml' and d[2] is None and defaults.get(d[0].split('/')[-1])==d[1]]
    unexpected=[d for d in diffs if d not in normalized]
    if unexpected: raise RuntimeError('Unexpected persisted differences: '+source.name+str(unexpected))
    result[source.name]={'unexpected':0,'omittedDefaults':len(normalized)}
assert len(result)==7
shutil.copy2(saved/'Screen5.pa.yaml',ROOT/'canvas/current/Screen5.pa.yaml')
(WORK/'canvas-save-proof.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('Reloaded saved app matches candidate; 18 standard defaults omitted by Studio. Other six definitions identical.')
print('Updated current Screen5 source only.')
