'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
const cut=(from,to)=>{const a=script.indexOf(from),b=script.indexOf(to,a);assert.ok(a>=0&&b>a,from);return script.slice(a,b);};
const code='const fmt=n=>String(n);'+cut('function median(','function kickoffForecast(')
  +cut('const HOUR=','const REF_TTL=')+cut('function valueAt(','// What happened in earlier matches')
  +cut('const MAPPED_SEATS=','function renderVerdict(')
  +';({dayDrops,pressureIndex,fullVerdict,seatsTogether,standTiming,matchdaySummary})';
const f=vm.runInNewContext(code,{},{timeout:1000});

// 24 h sales: partner 18–30 h earlier, scaled to 24 h, same locked fields only.
const t0=Date.parse('2026-11-01T12:00:00Z');
const scan=(h,v,locks=[])=>({observed_at:new Date(t0+h*3600000).toISOString(),available_seated:v,locked_fields:locks});
const drops=f.dayDrops([scan(0,1000),scan(12,950),scan(24,800),scan(36,700,['A']),scan(48,500)]);
assert.equal(drops.length,2);
assert.equal(drops[0].sold,200,'0 → 24 h');
assert.equal(drops[1].sold,300,'24 → 48 h; the 36 h scan has other locks');
assert.equal(f.dayDrops([scan(0,1000),scan(12,900)]).length,0,'no 24 h partner');
assert.equal(f.dayDrops([scan(0,1000),scan(20,900)])[0].sold,120,'20 h scaled to 24 h');

// Pressure index: 100 = median positive day at the venue.
const base=[100,100,100,200,50,-20].map(sold=>({sold}));
const p=f.pressureIndex([scan(0,1000),scan(24,800)],base);
assert.equal(p.value,200);
assert.equal(p.label,'Rekordtrøkk');
assert.equal(f.pressureIndex([scan(0,1000),scan(24,800)],base.slice(0,3)),null,'needs five baseline days');
assert.equal(f.pressureIndex([scan(0,1000),scan(24,950)],base).label,'Rolig');

// Will it sell out?
const v=x=>f.fullVerdict({mapped:19015,played:false,forecast:null,hist:null,pace:null,...x});
assert.equal(v({available:150}).level,'hot','under 1 % free now');
assert.equal(v({available:5000,pace:{status:'before_kickoff'}}).answer,'Kan bli utsolgt');
assert.equal(v({available:5000}).level,'unknown');
assert.equal(v({available:5000,hist:{center:600}}).level,'warm');
assert.equal(v({available:5000,forecast:{status:'projected',center:3000}}).level,'mild');
assert.equal(v({available:9000,hist:{center:8000}}).level,'calm');
assert.equal(v({available:9000,hist:{center:8000},played:true}),null);

// Seats together: most free first, press seats never suggested.
const rows=[{section_code:'A',free:3,capacity:90},{section_code:'B',free:40,capacity:300},{section_code:'PRESSE',free:60,capacity:60},{section_code:'C',free:12,capacity:20}];
assert.equal(f.seatsTogether(rows,4).map(r=>r.section_code).join(),'B,C');

// Stand timing in a played match.
const s=(...pts)=>pts.map(([h,free])=>({h,free,capacity:100}));
const timing=f.standTiming(new Map([['X',s([48,80],[24,60],[0,20])],['Y',s([48,50],[24,45],[0,40])]]),
  [{name:'Nord',codes:['X','Y']},{name:'Tom',codes:['Z']}]);
assert.equal(f.standTiming(new Map([['Q',s([48,0],[0,0])]]),[{name:'Stengt',codes:['Q']}]).length,0,'never-on-sale fields are not a sell-out');
assert.equal(timing.length,1);
assert.equal(timing[0].finalShare,0.3);
assert.equal(Math.round(timing[0].share24*100),64,'(105−60)/(130−60)');

// Matchday summary.
const day=f.matchdaySummary([{h:30,v:9000},{h:24,v:8800},{h:3,v:7000},{h:1,v:6400},{h:-0.1,v:6100}]);
assert.equal(day.final,6100);
assert.equal(day.sold24,2700);
assert.equal(day.sold3,900);
assert.ok(day.busiest.perHour>250);

for(const id of ['fullVerdict','pressureIndex','advicePanel','togetherSize','timingBlock','matchdayBlock','seasonBoard','shareMatch','shareDialog']){
  assert.ok(html.includes('id="'+id+'"'),id+' DOM target missing');
}
console.log('PASS: 24 h sales, pressure index, sell-out verdict, seats together, stand timing, matchday summary');
