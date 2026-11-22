#!/bin/bash
# Usage (inside the container): install.sh <id>  -- installs out/<id>-claude.* if its score beats the current recipe, then marks it READY.
ID=$1; R=/home/node/.openclaw/workspace/painting-cookbook; D=/home/node/.openclaw/workspace/_progress/claude-refine/out; PY=/home/node/.openclaw/venv/bin/python
$PY - "$ID" <<'P' || exit 1
import json,sys,shutil,os
pid=sys.argv[1];R='/home/node/.openclaw/workspace/painting-cookbook/';D='/home/node/.openclaw/workspace/_progress/claude-refine/out/'
new=json.load(open(D+pid+'-claude.score.json'));old=json.load(open(R+'recipes/'+pid+'.score.json'))
if new['similarity']<=old['similarity']: print(pid,'not better',old['similarity'],new['similarity']); sys.exit(1)
os.makedirs(R+'recipes/before-claude',exist_ok=True)
for ext in ('json','png','score.json'): shutil.copy(R+f'recipes/{pid}.{ext}',R+f'recipes/before-claude/{pid}.{ext}')
rec=json.load(open(D+pid+'-claude.json'));rec['scores']=new
json.dump(rec,open(R+f'recipes/{pid}.json','w'),separators=(',',':'))
shutil.copy(D+pid+'-claude.png',R+f'recipes/{pid}.png');shutil.copy(D+pid+'-claude.score.json',R+f'recipes/{pid}.score.json')
m=json.load(open(R+'recipes/manifest.json'))
for e in m:
  if e['id']==pid: e['scores']=new
json.dump(m,open(R+'recipes/manifest.json','w'),indent=2);open(R+'recipes/manifest.json','a').write('\n')
print(pid,'installed',old['similarity'],'->',new['similarity'])
P
echo "READY $ID" >> /home/node/.openclaw/workspace/_progress/cookbook-ready.txt
