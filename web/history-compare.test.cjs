'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(script);
const start=script.indexOf('const HOUR=');
const end=script.indexOf('function scanTables(',start);
const med=script.slice(script.indexOf('function median('),script.indexOf('function kickoffForecast('));
assert.ok(start>0&&end>start&&med.length>0);
const f=vm.runInNewContext(med+script.slice(start,end)+';({curve,valueAt,historyForecast,rankFastSections,opponentName,hoursText})',{},{timeout:1000});

// Curve: hours before kickoff, newest last, scans long after kickoff dropped.
const kickoff='2026-10-28T17:00:00Z';
const at=h=>new Date(Date.parse(kickoff)-h*3600000).toISOString();
const c=f.curve([{observed_at:at(2),available_seated:7000},{observed_at:at(48),available_seated:8200},
  {observed_at:at(-0.08),available_seated:6078},{observed_at:at(-3),available_seated:6000}],kickoff);
assert.deepEqual(c.map(p=>p.v),[8200,7000,6078],'ordered by hours before kickoff, post-match scan dropped');

// Reading at the same point: interpolate, never outside the measured period or across long gaps.
const ref=[{h:48,v:8000},{h:36,v:7500},{h:24,v:7000},{h:12,v:6500},{h:0,v:6000}];
assert.equal(f.valueAt(ref,48),8000);
assert.equal(f.valueAt(ref,30),7250);
assert.equal(f.valueAt(ref,60),null);
assert.equal(f.valueAt([{h:40,v:5},{h:10,v:1}],20),null,'no interpolation across a 30 h gap');

// History forecast: share-based and count-based readings, never above current.
const r=f.historyForecast({h:24,v:3500},[{title:'HamKam',points:ref}]);
assert.equal(r.basis.length,1);
assert.equal(r.basis[0].ratio,3000,'3500 × 6000/7000');
assert.equal(r.basis[0].diff,2500,'3500 − 1000 sold');
assert.equal([r.low,r.high,r.center].join(),'2500,3000,2750');
assert.equal(f.historyForecast({h:24,v:3500},[{title:'Uten slutt',points:[{h:48,v:8000},{h:20,v:7000}]}]),null,'needs a reading near kickoff');
assert.equal(f.historyForecast({h:0.2,v:3500},[{title:'HamKam',points:ref}]),null,'no forecast at kickoff');
const up=f.historyForecast({h:24,v:100},[{title:'Frigitt',points:[{h:24,v:1000},{h:0,v:1500}]}]);
assert.ok(up.high<=100,'released tickets in an old match never push the estimate above now');

// Fields: earliest to run out first; fields empty from the start are excluded.
const series=(...p)=>p.map(([h,free])=>({h,free,capacity:100}));
const ranked=f.rankFastSections([{title:'HamKam',sections:new Map([
  ['C',series([48,40],[30,0],[0,0])],
  ['D',series([48,60],[10,0],[0,0])],
  ['E',series([48,90],[0,5])],
  ['A',series([48,0],[0,0])],
  ['F',series([48,90],[0,60])],
  ['PRESSE',series([48,9],[0,0])]])}]);
assert.equal(JSON.stringify(ranked.map(s=>s.code)),'["C","D","E"]');
assert.equal(ranked[0].emptyHours,30);
assert.equal(ranked[2].finalShare,0.05);

assert.equal(f.opponentName('Rosenborg – HamKam'),'HamKam');
assert.equal(f.hoursText(30),'30 t');
assert.equal(f.hoursText(60),'2,5 døgn');
for(const id of ['comparePanel','compareChart','compareNow','historyForecast','fastSections','alertRelease','sectionAlert']){
  assert.ok(html.includes('id="'+id+'"'),id+' DOM target missing');
}
console.log('PASS: same-clock comparison, history forecast, fields that go first, alert hooks');
