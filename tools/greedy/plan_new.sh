#!/bin/bash
# Usage (in the container): newrun.sh <id> <strokes>  -- plans a brand-new recipe from its skeleton, renders, scores, installs, READY.
set -e
ID=$1; N=$2; R=/home/node/.openclaw/workspace/painting-cookbook; C=/home/node/.openclaw/workspace/_progress/claude-refine; D=$C/out; PY=/home/node/.openclaw/venv/bin/python
cd $R
$PY $C/new_recipe.py $ID >/dev/null
node tools/render.mjs $D/$ID-skeleton.json $D/$ID-base.png >/dev/null
RECIPE=$D/$ID-skeleton.json KEEP=0 TOTAL=$N MINSIZE=${MINSIZE:-2.2} $PY $C/greedy_planner.py $ID $D/$ID-base.png $D/$ID-claude.json >/dev/null
node tools/render.mjs $D/$ID-claude.json $D/$ID-claude.png >/dev/null
$PY tools/score.py references/$ID.jpg $D/$ID-claude.png --output $D/$ID-claude.score.json >/dev/null
$PY - $ID <<'P'
import json,sys,shutil,os
pid=sys.argv[1];R='/home/node/.openclaw/workspace/painting-cookbook/';D='/home/node/.openclaw/workspace/_progress/claude-refine/out/'
sc=json.load(open(D+pid+'-claude.score.json'));rec=json.load(open(D+pid+'-claude.json'));rec['scores']=sc
if os.path.exists(R+f'recipes/{pid}.json'):
  os.makedirs(R+'recipes/before-claude',exist_ok=True)
  for ext in ('json','png','score.json'):
    if os.path.exists(R+f'recipes/{pid}.{ext}'): shutil.copy(R+f'recipes/{pid}.{ext}',R+f'recipes/before-claude/{pid}.{ext}')
json.dump(rec,open(R+f'recipes/{pid}.json','w'),separators=(',',':'))
shutil.copy(D+pid+'-claude.png',R+f'recipes/{pid}.png');shutil.copy(D+pid+'-claude.score.json',R+f'recipes/{pid}.score.json')
m=json.load(open(R+'recipes/manifest.json'));m=[e for e in m if e['id']!=pid]
m.append({k:rec[k] for k in ['id','title','artist','year','width','height','strokeCount','scores','credit','description']})
json.dump(m,open(R+'recipes/manifest.json','w'),indent=2);open(R+'recipes/manifest.json','a').write('\n')
print(pid,rec['strokeCount'],'strokes, score',sc['similarity'])
P
