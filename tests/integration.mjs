import assert from 'node:assert/strict';
const origin='http://127.0.0.1:5173';
const anonymous=await fetch(`${origin}/api/lab`);assert.equal(anonymous.status,401);
const login=await fetch(`${origin}/signin-with-chatgpt?return_to=/`,{redirect:'manual'});
const cookie=login.headers.getSetCookie().map(x=>x.split(';')[0]).join('; ');assert.ok(cookie,'Local preview sign-in cookie required');
async function get(mode='demo'){const r=await fetch(`${origin}/api/lab?mode=${mode}`,{headers:{cookie}});const text=await r.text();let data;try{data=JSON.parse(text)}catch{data={error:text}}return {status:r.status,data};}
async function post(body,requestOrigin=origin){const r=await fetch(`${origin}/api/lab`,{method:'POST',headers:{cookie,origin:requestOrigin,'Content-Type':'application/json'},body:JSON.stringify(body)});const text=await r.text();let data;try{data=JSON.parse(text)}catch{data={error:text}}return {status:r.status,data};}
assert.equal((await get()).status,200);
assert.equal((await post({action:'refresh',mode:'demo'},'https://wrong-origin.example')).status,403);
assert.equal((await post({action:'refresh',mode:'live'})).status,409);
const refresh=await post({action:'refresh',mode:'demo'});assert.equal(refresh.status,200,JSON.stringify(refresh.data));
const board=refresh.data.board;
const {compare}=await import('../lib/odds.ts');const row=compare(board.games).find(r=>r.eligible);assert.ok(row);
const payload={action:'record',boardId:board.id,rowId:row.id,stake:10,note:'Local integration test: synthetic price; no wager.',acknowledged:true};
assert.equal((await post({...payload,stake:-10})).status,400);
const saved=await post(payload);assert.equal(saved.status,201,JSON.stringify(saved.data));
assert.equal((await post(payload)).status,409);
let loaded=await get();assert.ok(loaded.data.trades.some(t=>t.id===saved.data.id));
const settlement={action:'settle',tradeId:saved.data.id,result:'loss',source:'Synthetic integration test loss'};
assert.equal((await post(settlement)).status,200);
assert.equal((await post({...settlement,result:'win'})).status,409);
loaded=await get();assert.equal(loaded.data.trades.find(t=>t.id===saved.data.id).profit,-10);
assert.equal((await get('live')).data.board,null);
console.log('PASS: authentication, same-origin writes, missing key, demo snapshot, stake validation, paper-trade persistence, duplicate prevention, immutable settlement, loss calculation, live/demo board separation.');
