#!/usr/bin/env node
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const html=fs.readFileSync(new URL('../v2.html',import.meta.url),'utf8');
const v1=fs.readFileSync(new URL('../index.html',import.meta.url),'utf8');
assert.match(html,/<title>Ministaut V2/);
assert.match(v1,/<title>Ministaut · RBK og RBK Kvinner<\/title>/);
const js=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(js,'V2 script exists');
new vm.Script(js,{filename:'ministaut-v2.js'});
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
assert.equal(new Set(ids).size,ids.length,'Duplicate DOM ids');
const available=new Set(ids);
for(const m of js.matchAll(/\$\(['"]([^'"]+)['"]\)/g)){
 assert.ok(available.has(m[1]),'Missing element: '+m[1]);
}
for(const x of ['ministaut_matches?select=','ministaut_koteng_matches?select=','ministaut_scans','ministaut_koteng_scans','matchCards','stadiumMap','dailyPulse','chartInspect','tickets']){
 assert.ok(html.includes(x),'Missing V1 feature: '+x);
}
assert.equal((html.match(/data-chart-hours="/g)||[]).length,4);
assert.ok(html.includes('Lerkendal_stadion_at_night.jpg'));
const colors=[...html.matchAll(/#([a-f\d]{3,8})\b/gi)].map(m=>m[1]);
for(let c of colors){
 if(c.length<=4)c=c.split('').map(x=>x+x).join('');
 const [r,g,b]=[0,2,4].map(i=>parseInt(c.slice(i,i+2),16));
 const neutral=Math.max(r,g,b)-Math.min(r,g,b)<=35;
 const gold=r>=g*.84 && g>=b*.81;
 assert.ok(neutral||gold,'Non-grayscale/non-gold hex: #'+c);
}
console.log('V2 structure OK: '+ids.length+' IDs, '+colors.length+' palette values, JS syntax valid, V1 preserved.');
