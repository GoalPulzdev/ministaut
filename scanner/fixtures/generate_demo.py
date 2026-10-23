from pathlib import Path
import json
p=Path(__file__).resolve().parents[1]
a=json.loads((p/'anchors_v15.json').read_text(encoding='utf-8'))
chosen=['QA','RA','PA','OA','LB','K','JB','IB','TA','UA','VA','WA','XA','AA','BA','CB','DB','C','DA','FA','PRESSE']
rects=[]
for i,name in enumerate(chosen):
 x,y=a[name]
 rects.append(f'<div class="zone" data-name="{name}" data-free="{101+i}" data-cap="{301+i}" style="left:{int(x)-6}px;top:{int(y)-6}px"></div>')
html=f'''<!doctype html><html lang="no"><head><meta charset="utf-8"><title>TEST: Syntetisk Lerkendal</title><style>
*{{box-sizing:border-box}}body{{background:#101513;color:white;margin:0;font-family:Arial}}
header{{height:178px;background:linear-gradient(100deg,#002f26 25%,#00845a);padding:10px}}
#body{{display:flex}}#map{{position:relative;width:900px;height:660px;background:#eee;overflow:hidden}}
#stage{{position:absolute;top:0;left:0;width:906px;height:650px;transform:translate(68px,70px) scale(.87);transform-origin:top left}}
#pitch{{position:absolute;left:337px;top:298px;width:243px;height:157px;background:repeating-linear-gradient(90deg,#095341 0px,#095341 24px,#178363 24px,#178363 48px);border:3px solid white}}
.zone{{position:absolute;width:12px;height:12px;background:#bda869;cursor:pointer;border:1px solid #655744;z-index:2}}
.zone:hover{{background:#4cf09e}}#tip{{position:fixed;left:700px;top:210px;display:none;background:#142719;color:white;padding:14px;border:1px solid #5eca88;z-index:4;pointer-events:none}}
</style></head><body><header><h2>DEMO – dette er syntetiske tall, ikke RBKs billettsalg</h2></header>
<div id="body"><div id="map"><div id="stage"><div id="pitch"></div>{''.join(rects)}</div></div><aside>Shopping cart is empty · TEST</aside></div>
<div id="tip" role="tooltip"></div><script>
for(const el of document.querySelectorAll('.zone')){{
 el.addEventListener('mouseenter',()=>{{const t=document.getElementById('tip');t.style.display='block';
 t.innerHTML=`SECTION ${{el.dataset.name}} GATE 13<br>FREE SEATS <b>${{el.dataset.free}} / ${{el.dataset.cap}}</b>`}});
 el.addEventListener('mouseleave',()=>{{document.getElementById('tip').style.display='none'}});
}}
</script></body></html>'''
(p/'fixtures/demo_21_fields.html').write_text(html,encoding='utf-8')