import {z} from 'zod';
import {getChatGPTUser} from '@/app/chatgpt-auth';
import {database,providerKey} from '@/lib/storage';
import {BOOKS,compare,demoGames,pnl,type Board,type Game,type Row} from '@/lib/odds';
export const dynamic='force-dynamic';
const response=(data:unknown,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
const outcome=z.object({name:z.string().min(1).max(200),description:z.string().max(200).optional(),price:z.number().positive().max(1001),point:z.number().finite().optional()});
const game=z.object({id:z.string().min(1).max(100),sport_key:z.literal('americanfootball_nfl'),home_team:z.string().max(200),away_team:z.string().max(200),commence_time:z.string().datetime(),bookmakers:z.array(z.object({key:z.string(),title:z.string(),last_update:z.string().optional(),markets:z.array(z.object({key:z.string(),last_update:z.string().optional(),outcomes:z.array(outcome).max(2000)})).max(50)})).max(30)});
const action=z.discriminatedUnion('action',[
 z.object({action:z.literal('refresh'),mode:z.enum(['demo','live']),eventId:z.string().regex(/^[a-zA-Z0-9_-]{1,100}$/).optional()}),
 z.object({action:z.literal('record'),boardId:z.string().uuid(),rowId:z.string().max(1000),stake:z.number().finite().positive().max(10000),note:z.string().max(2000).default(''),acknowledged:z.literal(true)}),
 z.object({action:z.literal('settle'),tradeId:z.string().uuid(),result:z.enum(['win','loss','push','void']),source:z.string().trim().min(5).max(1000)})
]);
export async function GET(request:Request){
 const user=await getChatGPTUser();if(!user)return response({error:'Sign in to view your saved research.'},401);
 try{
  const db=database(),mode=new URL(request.url).searchParams.get('mode')==='demo'?'demo':'live';
  const board=await db.prepare('SELECT payload FROM boards WHERE owner=? AND mode=? ORDER BY created DESC LIMIT 1').bind(user.userId,mode).first<{payload:string}>();
  const rows=await db.prepare('SELECT t.*,s.result,s.profit,s.created AS settled_at,s.source AS settlement_source FROM trades t LEFT JOIN settlements s ON s.trade_id=t.id AND s.owner=t.owner WHERE t.owner=? ORDER BY t.created DESC LIMIT 1000').bind(user.userId).all();
  return response({connected:!!providerKey(),board:board?JSON.parse(board.payload):null,trades:rows.results.map(t=>({...t,quote:JSON.parse(t.quote as string)}))});
 }catch{return response({error:'Research storage is temporarily unavailable. Your saved records have not been changed.'},503);}
}
export async function POST(request:Request){
 const origin=request.headers.get('origin');if(!origin||origin!==new URL(request.url).origin)return response({error:'Use the dashboard to make changes.'},403);
 const user=await getChatGPTUser();if(!user)return response({error:'Sign in before saving research.'},401);
 if(Number(request.headers.get('content-length')??0)>20000)return response({error:'Request too large.'},413);
 let input:z.infer<typeof action>;try{input=action.parse(await request.json());}catch{return response({error:'Check the action, stake, and required fields.'},400);}
 try{
  const db=database(),owner=user.userId;
  if(input.action==='refresh'){
   const latest=await db.prepare('SELECT created,payload FROM boards WHERE owner=? AND mode=? ORDER BY created DESC LIMIT 1').bind(owner,input.mode).first<{created:string;payload:string}>();
   if(latest&&Date.now()-Date.parse(latest.created)<60000)return response({error:'Wait one minute between refreshes to conserve data credits.'},429);
   let games:Game[],remaining:string|null=null;
   if(input.mode==='demo'){games=demoGames();}
   else{
    const key=providerKey();if(!key)return response({error:'Live odds need an ODDS_API_KEY server secret from The Odds API. No subscription has been purchased.'},409);
    if(input.eventId){const previous=latest?JSON.parse(latest.payload) as Board:null;if(!previous?.games.some(g=>g.id===input.eventId&&Date.parse(g.commence_time)>Date.now()))return response({error:'Refresh the main board and select an upcoming game first.'},400);}
    const endpoint=input.eventId?`events/${encodeURIComponent(input.eventId)}/odds`:'odds';
    const url=new URL(`https://api.the-odds-api.com/v4/sports/americanfootball_nfl/${endpoint}`);
    url.search=new URLSearchParams({apiKey:key,bookmakers:BOOKS.map(b=>b.key).join(','),markets:input.eventId?'player_pass_yds,player_rush_yds,player_reception_yds,player_receptions':'h2h,spreads,totals',oddsFormat:'decimal',dateFormat:'iso'}).toString();
    let upstream:Response;try{upstream=await fetch(url,{signal:AbortSignal.timeout(15000)});}catch{return response({error:'Odds provider did not respond. The previous snapshot is preserved.'},502);}
    if(!upstream.ok)return response({error:upstream.status===401?'The provider rejected the API key.':upstream.status===429?'Provider quota or rate limit reached.':'The provider could not serve this market. The previous snapshot is preserved.'},502);
    const raw=await upstream.json();games=z.array(game).max(100).parse(input.eventId?[raw]:raw) as Game[];
    if(input.eventId&&latest){const old=JSON.parse(latest.payload) as Board;const props=games[0];games=old.games.map(g=>g.id!==props.id?g:{...g,bookmakers:BOOKS.flatMap(b=>{const previous=g.bookmakers.find(x=>x.key===b.key),current=props.bookmakers.find(x=>x.key===b.key);if(!previous&&!current)return [];return [{key:b.key,title:b.name,markets:[...(previous?.markets.filter(m=>!m.key.startsWith('player_')).map(m=>({...m,last_update:m.last_update??previous.last_update}))??[]),...(current?.markets.map(m=>({...m,last_update:m.last_update??current.last_update}))??[])]}];})});}
    remaining=upstream.headers.get('x-requests-remaining');
   }
   const board:Board={id:crypto.randomUUID(),mode:input.mode,created:new Date().toISOString(),games,remaining};
   await db.prepare('INSERT INTO boards (id,owner,mode,created,payload) VALUES (?,?,?,?,?)').bind(board.id,owner,board.mode,board.created,JSON.stringify(board)).run();
   return response({board,connected:!!providerKey()});
  }
  if(input.action==='record'){
   const stored=await db.prepare('SELECT payload FROM boards WHERE id=? AND owner=?').bind(input.boardId,owner).first<{payload:string}>();if(!stored)return response({error:'Snapshot not found.'},404);
   const board=JSON.parse(stored.payload) as Board;
   const row=compare(board.games).find(r=>r.id===input.rowId);if(!row?.eligible||!row.best)return response({error:'This quote is stale, closed, or does not pass the research filters. Refresh the board.'},409);
   const id=crypto.randomUUID();
   const inserted=await db.prepare('INSERT INTO trades (id,owner,board_id,row_id,mode,created,stake,quote,note) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(owner,board_id,row_id) DO NOTHING').bind(id,owner,board.id,row.id,board.mode,new Date().toISOString(),input.stake,JSON.stringify(row),input.note).run();
   if(!inserted.meta.changes)return response({error:'This candidate is already recorded from this snapshot.'},409);
   return response({saved:true,id},201);
  }
  const trade=await db.prepare('SELECT quote,stake,mode FROM trades WHERE id=? AND owner=?').bind(input.tradeId,owner).first<{quote:string;stake:number;mode:string}>();
  if(!trade)return response({error:'Paper trade not found.'},404);
  const row=JSON.parse(trade.quote) as Row;
  if(trade.mode==='live'&&Date.parse(row.start)>Date.now())return response({error:'Wait until the event starts, then verify the final result before settling.'},409);
  const profit=pnl(trade.stake,row.best!.decimal,input.result);
  const inserted=await db.prepare('INSERT INTO settlements (trade_id,owner,result,created,profit,source) VALUES (?,?,?,?,?,?) ON CONFLICT(trade_id) DO NOTHING').bind(input.tradeId,owner,input.result,new Date().toISOString(),profit,input.source).run();
  if(!inserted.meta.changes)return response({error:'This result is already settled. Original records are immutable.'},409);
  return response({settled:true,profit});
 }catch(error){if(error instanceof z.ZodError)return response({error:'The provider returned an unexpected data format. No snapshot was saved.'},502);return response({error:'Unable to save this operation. Your existing records are preserved; please retry.'},503);}
}
