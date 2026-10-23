"""Recognize the green football pitch as a stable coordinate anchor (Pillow only)."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from io import BytesIO
from PIL import Image, ImageFilter

REF=(337.,298.,243.,157.)
@dataclass
class Pitch:
    x:float;y:float;w:float;h:float
    def json(self):return {'x':round(self.x,1),'y':round(self.y,1),'w':round(self.w,1),'h':round(self.h,1)}

def locate(data:bytes,css_w:float|None=None,css_h:float|None=None)->Pitch|None:
    im=Image.open(BytesIO(data)).convert('RGB');ow,oh=im.size
    factor=max(1,round(max(ow,oh)/680));dw=max(1,ow//factor);dh=max(1,oh//factor)
    im=im.resize((dw,dh),Image.Resampling.BILINEAR);pixels=im.load()
    m=Image.new('L',(dw,dh));put=m.load()
    for y in range(max(10,int(dh*.12)),dh):
        for x in range(int(dw*.74)):
            r,g,b=pixels[x,y]
            if 55<=g<=190 and r<125 and b<140 and g>r*1.34 and g>b*1.10:put[x,y]=255
    m=m.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))
    a=m.tobytes();seen=bytearray(len(a));results=[]
    for i,v in enumerate(a):
        if not v or seen[i]:continue
        q=deque([i]);seen[i]=1;n=0;lx=hx=i%dw;ly=hy=i//dw
        while q:
            j=q.popleft();x=j%dw;y=j//dw;n+=1;lx=min(lx,x);hx=max(hx,x);ly=min(ly,y);hy=max(hy,y)
            for k in (j-1 if x else -1,j+1 if x<dw-1 else -1,j-dw if y else -1,j+dw if y<dh-1 else -1):
                if k>=0 and a[k] and not seen[k]:seen[k]=1;q.append(k)
        w=hx-lx+1;h=hy-ly+1
        if w>=45 and h>=35 and 1.25<w/h<2.2 and n/(w*h)>.32:results.append((n,lx,ly,w,h))
    if not results:return None
    _,x,y,w,h=max(results)
    return Pitch(x*(css_w or ow)/dw,y*(css_h or oh)/dh,w*(css_w or ow)/dw,h*(css_h or oh)/dh)

def to_screen(xy,pitch):
    x,y,w,h=REF
    return (round(pitch.x+(xy[0]-x)*pitch.w/w),round(pitch.y+(xy[1]-y)*pitch.h/h))

def to_reference(xy,pitch):
    x,y,w,h=REF
    return (round(x+(xy[0]-pitch.x)*w/pitch.w,2),round(y+(xy[1]-pitch.y)*h/pitch.h,2))