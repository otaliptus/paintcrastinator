#!/usr/bin/env python3
"""Semantic directional planner for Monet's figures and windswept hillside."""
from pathlib import Path
import json
import cv2
import numpy as np
from PIL import Image
from plan_intermediate import segment, stripes, contours, allocate

ROOT=Path(__file__).resolve().parents[1]
pid='woman-with-a-parasol'
source=np.asarray(Image.open(ROOT/'references'/f'{pid}.jpg').convert('RGB'),dtype=np.float32)/255
h,w=source.shape[:2]
regions,ground=segment(source,pid,34)
sx,sy=w/1000,h/800

def poly(points):
    m=np.zeros((h,w),np.uint8)
    p=np.array([(int(x*sx),int(y*sy)) for x,y in points],np.int32)
    cv2.fillPoly(m,[p],1)
    return m

def ellipse(cx,cy,rx,ry):
    m=np.zeros((h,w),np.uint8)
    cv2.ellipse(m,(int(cx*sx),int(cy*sy)),(int(rx*sx),int(ry*sy)),0,0,360,1,-1)
    return m

def select(mask):
    result=[]
    for original in regions:
        m=cv2.bitwise_and(original['mask'],mask)
        area=int(m.sum())
        if area<18: continue
        yy,xx=np.nonzero(m)
        r=dict(original)
        r.update(mask=m,area=area,points=np.column_stack([xx,yy]).astype(float))
        cs,_=cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        if cs:
            r['polygon']=cv2.approxPolyDP(max(cs,key=cv2.contourArea),1.8,True).reshape(-1,2)
            result.append(r)
    return result

canopy=poly([(135,145),(155,105),(210,70),(270,62),(325,83),(350,130),(330,175),(285,197),(235,203),(180,190)])
woman=poly([(280,190),(335,184),(357,225),(347,274),(370,323),(374,369),(405,430),(409,497),(382,552),(325,574),(225,565),(202,533),(216,471),(231,409),(242,341),(263,279)])
head=ellipse(310,214,43,49)
child=poly([(144,390),(177,389),(192,421),(190,457),(204,493),(178,513),(133,505),(120,474),(130,435)])
yy,xx=np.mgrid[:h,:w]
grass=(yy>(474*sy+xx*.055*sy/sx)).astype(np.uint8)
sky=(1-np.maximum.reduce([canopy,woman,child,grass])).astype(np.uint8)

groups=[
 ('sky-and-clouds','Sky and clouds',sky,390,20,'edges','wanderer-sea-of-fog'),
 ('green-parasol','Green parasol',canopy,185,10,'edges',pid),
 ('woman-and-veil','Woman and veil',woman,480,9,'edges',pid),
 ('child','The child',child,115,6,'edges',pid),
 ('grass-and-wildflowers','Grass and wildflowers',grass,529,8,'sqrt',pid),
]
stages=[]
for gid,label,mask,count,diameter,mode,direction_pid in groups:
    rr=select(mask)
    sets=[stripes(r,direction_pid,min(diameter,max(2.2,min(np.ptp(r['points'][:,0])+1,np.ptp(r['points'][:,1])+1)*.58))) for r in rr]
    if gid=='green-parasol':
        edge=[contours(r) for r in rr]
        strokes=allocate(sets,rr,count-35,mode)+allocate(edge,rr,35,'edges')
    else:
        strokes=allocate(sets,rr,count,mode)
    coverage={'sky-and-clouds':1.8,'green-parasol':2.5,'woman-and-veil':3.0,'child':2.5,'grass-and-wildflowers':4.0}[gid]
    for s in strokes:
        s.pop('weight',None)
        s['s']=round(s['s']*coverage,1)
        s['stage']=gid
    stages.append({'id':gid,'label':label,'strokes':strokes})
    assert len(strokes)==count,(gid,len(strokes))
# A slim real shaft gives the canopy its unmistakable parasol structure.
stages[1]['strokes'].append({'p':[249*sx,162*sy,286*sx,340*sy],'c':'#463e2e','s':3.4,'o':.9,'stage':'green-parasol'})
recipe={'id':pid,'title':'Woman with a Parasol','artist':'Claude Monet','year':'1875','description':'A windblown figure and child stand beneath a green parasol on a flowered hillside.','width':w,'height':h,'ground':'#879ca8','reference':f'../references/{pid}.jpg','seed':6100,'profile':'directional-flat','planner':'CIE Lab regions clipped into semantic sky, parasol, figure, child and grass masks','credit':{'author':'Claude Monet','licence':'Public domain','source':'Wikimedia Commons','url':'https://commons.wikimedia.org/wiki/File:Claude_Monet_-_Woman_with_a_Parasol_-_Madame_Monet_and_Her_Son_-_Google_Art_Project.jpg'},'regions':len(regions),'strokeCount':1700,'stages':stages}
(ROOT/'recipes'/f'{pid}.json').write_text(json.dumps(recipe,separators=(',',':'))+'\n')
print('Planned semantic parasol:',sum(len(s['strokes']) for s in stages),'strokes;',[(s['id'],len(s['strokes'])) for s in stages])
