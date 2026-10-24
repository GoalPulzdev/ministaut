'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
// Offline regression test: this never invokes the ticket scanner or Supabase.
const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
const start=html.indexOf('function sectionTiles(){');
const end=html.indexOf('function drawStadiumMap(',start);
assert.ok(start>=0&&end>start,'stadium map function must exist');
const tiles=vm.runInNewContext(html.slice(start,end)+'\nsectionTiles();',Object.create(null),{timeout:1000});
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
assert.ok(byCode.get('LB').x>=byCode.get('MB').x+byCode.get('MB').w,'north/east must not overlap');
assert.ok(byCode.get('HB').x>=byCode.get('GB').x+byCode.get('GB').w,'south/east must not overlap');
assert.ok(byCode.get('TA').x<byCode.get('U').x&&byCode.get('U').x<byCode.get('UB').x,'Coop VIP ordering');
assert.ok(byCode.get('PRESSE').y>byCode.get('DA').y+byCode.get('DA').h,'press must sit below lower south row');
assert.ok(byCode.get('PRESSE').y-byCode.get('DA').y-byCode.get('DA').h<=10,'press must stay attached');
assert.ok(!byCode.has('SB')&&!byCode.has('ØVRE ØST'),'standing inventory is separate');
console.log('PASS: 60 sectors, correct topology, no collisions, standing areas excluded.');