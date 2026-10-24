'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
// Offline regression test: this never invokes the ticket scanner or Supabase.
const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
const start=html.indexOf('const SEAT_LAYOUT=[');
const end=html.indexOf('function drawStadiumMap(',start);
assert.ok(start>=0&&end>start,'stadium map function must exist');
const geometry=vm.runInNewContext(html.slice(start,end)+'\n({tiles:sectionTiles(),pitchBox,stadiumFrame});',Object.create(null),{timeout:1000});
const {tiles,pitchBox,stadiumFrame}=geometry;
const byCode=new Map(tiles.map(t=>[t.code,t]));
const expected=['SA','RA','QA','PA','OA','NA','MA','Q','P','O','N','RB','QB','PB','OB','NB','MB',
 'TA','UA','VA','WA','XA','TB','UB','U','VB','V','WB','W','XB',
 'LB','KB','JB','IB','HB','K','J','I','AB','BB','CB','DB','EB','FB','GB',
 'A','B','C','D','E','F','G','AA','BA','CA','DA','EA','FA','GA','PRESSE'];
assert.equal(tiles.length,60);
assert.deepEqual([...byCode.keys()].sort(),expected.sort());
for(let i=0;i<tiles.length;i++){
 const a=tiles[i];
 assert.ok(a.x>=0&&a.y>=0&&a.w>0&&a.h>0&&a.x+a.w<=780&&a.y+a.h<=710,a.code+' outside map');
 for(let j=i+1;j<tiles.length;j++){
  const b=tiles[j];
  assert.ok(!(Math.max(a.x,b.x)<Math.min(a.x+a.w,b.x+b.w)&&Math.max(a.y,b.y)<Math.min(a.y+a.h,b.y+b.h)),a.code+' overlaps '+b.code);
 }
}
const ordered=(codes,axis)=>codes.every((c,i)=>i===0||byCode.get(codes[i-1])[axis]<byCode.get(c)[axis]);
assert.ok(ordered(['SA','RA','QA','PA','OA','NA','MA'],'x'));
assert.ok(ordered(['RB','QB','PB','OB','NB','MB'],'x'));
assert.ok(ordered(['TA','UA','VA','WA','XA'],'y'));
assert.ok(ordered(['TB','UB','VB','WB','XB'],'y'));
assert.ok(ordered(['LB','KB','JB','IB','HB'],'y'));
assert.ok(ordered(['K','J','I'],'y'));
assert.ok(ordered(['AB','BB','CB','DB','EB','FB','GB'],'x'));
assert.ok(ordered(['AA','BA','CA','DA','EA','FA','GA'],'x'));
assert.ok(byCode.get('LB').y>=byCode.get('MB').y+byCode.get('MB').h,'north/east corner must have safe vertical clearance');
assert.ok(byCode.get('HB').x>=byCode.get('GB').x+byCode.get('GB').w,'south/east must not overlap');
// Upper Coop -> VIP Coop -> lower Coop, in physically separate parallel lanes.
const coopRows=[
 ['TA',null,'TB'],
 ['UA','U','UB'],
 ['VA','V','VB'],
 ['WA','W','WB'],
 ['XA',null,'XB']
];
for(const [upperCode,vipCode,lowerCode] of coopRows){
 const upper=byCode.get(upperCode),lower=byCode.get(lowerCode);
 assert.ok(upper.x+upper.w<lower.x,upperCode+' must be outside the lower Coop tier');
 assert.equal(upper.y,lower.y,upperCode+' and '+lowerCode+' must align');
 assert.equal(upper.h,lower.h,upperCode+' and '+lowerCode+' must share row height');
 if(vipCode){
  const vip=byCode.get(vipCode);
  assert.ok(upper.x+upper.w<vip.x&&vip.x+vip.w<lower.x,
   vipCode+' must occupy its own lane between upper and lower Coop, never B row');
  assert.equal(vip.y,lower.y,vipCode+' must be on the lower Coop tier');
  assert.equal(vip.h,lower.h,vipCode+' must be aligned with the B-field');
 }
}
assert.ok(byCode.get('XB').x+byCode.get('XB').w<byCode.get('AB').x,
 'south-west corner: XB must not overlap AB');
assert.ok(byCode.get('PRESSE').y+byCode.get('PRESSE').h<byCode.get('DA').y,
 'press must sit above the outer south rail');
assert.ok(byCode.get('DA').y-byCode.get('PRESSE').y-byCode.get('PRESSE').h<=10,
 'press must stay attached to the south rail');
const railGroups=[
 ['SA','RA','QA','PA','OA','NA','MA'],
 ['Q','P','O','N'],
 ['RB','QB','PB','OB','NB','MB'],
 ['AB','BB','CB','DB','EB','FB','GB'],
 ['A','B','C','D','E','F','G'],
 ['PRESSE'],
 ['AA','BA','CA','DA','EA','FA','GA']
];
assert.equal(stadiumFrame.centerX,pitchBox.x+pitchBox.w/2);
assert.equal(stadiumFrame.northEdge,pitchBox.y);
assert.equal(stadiumFrame.southEdge,pitchBox.y+pitchBox.h);
for(const codes of railGroups){
 const rail=codes.map(code=>byCode.get(code));
 const left=Math.min(...rail.map(t=>t.x));
 const right=Math.max(...rail.map(t=>t.x+t.w));
 assert.ok(Math.abs((left+right)/2-stadiumFrame.centerX)<0.001,
    codes[0]+' rail must be exactly centered on pitch');
 const y=rail[0].y;
 assert.ok(rail.every(t=>t.y===y),codes[0]+' rail must have common baseline');
}
const north=['SA','Q','RB'].map(code=>byCode.get(code));
assert.ok(north.every(t=>t.y+t.h<=pitchBox.y));
const south=['AB','A','PRESSE','AA'].map(code=>byCode.get(code));
assert.ok(south.every(t=>t.y>=pitchBox.y+pitchBox.h));
for(const tile of tiles){
 const intersects=Math.max(tile.x,pitchBox.x)<Math.min(tile.x+tile.w,pitchBox.x+pitchBox.w)&&
  Math.max(tile.y,pitchBox.y)<Math.min(tile.y+tile.h,pitchBox.y+pitchBox.h);
 assert.ok(!intersects,tile.code+' must stay outside pitch');
}
assert.ok(Math.abs((byCode.get('PRESSE').x+byCode.get('PRESSE').w/2)-stadiumFrame.centerX)<.001,
 'press box centered on stadium centerline');
assert.ok(!byCode.has('SB')&&!byCode.has('ØVRE ØST'),'standing inventory is separate');
console.log('PASS: 60 sectors, 3 Coop lanes with VIP U/V/W, correct corners and south/north rails, zero collisions.');