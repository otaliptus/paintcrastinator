#!/bin/bash
# Usage (inside the container): run.sh <id> [seed]
set -e
ID=$1; SEED=${2:-7}; R=/home/node/.openclaw/workspace/painting-cookbook; D=/home/node/.openclaw/workspace/_progress/claude-refine/out; PY=/home/node/.openclaw/venv/bin/python
mkdir -p $D; cd $R
$PY -c "
import json;r=json.load(open('recipes/$ID.json'));import os;r['stages']=r['stages'][:int(os.environ.get('KEEP','2'))];r['strokeCount']=sum(len(s['strokes']) for s in r['stages']);json.dump(r,open('$D/$ID-base.json','w'))"
node tools/render.mjs $D/$ID-base.json $D/$ID-base.png >/dev/null
$PY /home/node/.openclaw/workspace/_progress/claude-refine/greedy_planner.py $ID $D/$ID-base.png $D/$ID-claude.json $SEED
node tools/render.mjs $D/$ID-claude.json $D/$ID-claude.png >/dev/null
$PY tools/score.py references/$ID.jpg $D/$ID-claude.png --output $D/$ID-claude.score.json >/dev/null
$PY -c "
import json;n=json.load(open('$D/$ID-claude.score.json'));o=json.load(open('recipes/$ID.score.json'))
print('$ID', 'old', o['similarity'], 'new', n['similarity'], 'ssim', round(o['ssim'],3),'->',round(n['ssim'],3), 'dE', round(o['mean_delta_e'],2),'->',round(n['mean_delta_e'],2), 'edge', round(o['edge_similarity'],3),'->',round(n['edge_similarity'],3))"
