export const BOOKS = [
  {key:'draftkings',name:'DraftKings'}, {key:'fanduel',name:'FanDuel'},
  {key:'betmgm',name:'BetMGM'}, {key:'williamhill_us',name:'Caesars'},
  {key:'fanatics',name:'Fanatics'}, {key:'betrivers',name:'BetRivers'},
];
export const MARKETS:Record<string,string> = {h2h:'Moneyline',spreads:'Spread',totals:'Total',player_pass_yds:'Passing yards',player_rush_yds:'Rushing yards',player_reception_yds:'Receiving yards',player_receptions:'Receptions'};
export type Outcome={name:string;price:number;point?:number;description?:string};
export type Game={id:string;sport_key:string;home_team:string;away_team:string;commence_time:string;bookmakers:{key:string;title:string;last_update?:string;markets:{key:string;last_update?:string;outcomes:Outcome[]}[]}[]};
export type Quote={book:string;name:string;decimal:number;updated:string;pairedProbability:number|null;fresh:boolean};
export type Row={id:string;eventId:string;event:string;start:string;market:string;selection:string;point:number|null;player:string;quotes:Quote[];best:Quote|null;probability:number|null;edge:number|null;references:number;dispersion:number|null;status:string;eligible:boolean;conditional:boolean};
export type Board={id:string;mode:'demo'|'live';created:string;games:Game[];remaining:string|null};
export function decimalFromAmerican(a:number){if(!Number.isFinite(a)||Math.abs(a)<100)throw new Error('Invalid American odds');return a>0?1+a/100:1+100/-a;}
export function american(d:number){if(!Number.isFinite(d)||d<=1)return '—';const a=d>=2?Math.round((d-1)*100):-Math.round(100/(d-1));return a>0?`+${a}`:String(a);}
export function pnl(stake:number,d:number,result:string){if(!Number.isFinite(stake)||stake<=0||!Number.isFinite(d)||d<=1)throw new Error('Invalid stake or price');if(result==='win')return stake*(d-1);if(result==='loss')return -stake;if(result==='push'||result==='void')return 0;throw new Error('Invalid result');}
export function median(v:number[]){const a=[...v].sort((x,y)=>x-y);return a.length%2?a[Math.floor(a.length/2)]:(a[a.length/2-1]+a[a.length/2])/2;}
function validPrice(d:number){return Number.isFinite(d)&&d>1&&d<=1001;}
function opponent(o:Outcome,other:Outcome,market:string,game:Game){
 if(o===other)return false;
 if(market==='h2h')return [game.home_team,game.away_team].includes(o.name)&&[game.home_team,game.away_team].includes(other.name)&&o.name!==other.name;
 if(market==='spreads')return [game.home_team,game.away_team].includes(o.name)&&[game.home_team,game.away_team].includes(other.name)&&o.name!==other.name&&o.point===-(other.point??NaN);
 return ((o.name==='Over'&&other.name==='Under')||(o.name==='Under'&&other.name==='Over'))&&o.point===other.point&&(o.description??'')===(other.description??'');
}
export function compare(games:Game[],now=Date.now()):Row[]{
 const groups=new Map<string,Row>();
 for(const game of games){
  if(game.sport_key!=='americanfootball_nfl'||!Number.isFinite(Date.parse(game.commence_time)))continue;
  for(const book of game.bookmakers){
   const known=BOOKS.find(b=>b.key===book.key);if(!known)continue;
   for(const market of book.markets){
    if(!MARKETS[market.key])continue;
    for(const o of market.outcomes){
     if(!validPrice(o.price)||!o.name)continue;
     if(market.key!=='h2h'&&(!Number.isFinite(o.point)||!Number.isInteger((o.point??0)*2)))continue;
     if(market.key.startsWith('player_')&&!o.description)continue;
     const id=JSON.stringify([game.id,market.key,o.description??'',o.name,o.point??null]);
     const row=groups.get(id)??{id,eventId:game.id,event:`${game.away_team} @ ${game.home_team}`,start:game.commence_time,market:market.key,selection:o.name,point:o.point??null,player:o.description??'',quotes:[],best:null,probability:null,edge:null,references:0,dispersion:null,status:'',eligible:false,conditional:market.key==='h2h'||Number.isInteger(o.point)};
     const updated=market.last_update??book.last_update??'';
     const age=now-Date.parse(updated);const fresh=Number.isFinite(age)&&age>=-30000&&age<=120000;
     const opponents=market.outcomes.filter(x=>opponent(o,x,market.key,game)&&validPrice(x.price));
     // A three-way moneyline is not interchangeable with the two-way/tie-void market.
     const paired=opponents.length===1&&(market.key!=='h2h'||market.outcomes.length===2)?(1/o.price)/(1/o.price+1/opponents[0].price):null;
     const quote={book:book.key,name:known.name,decimal:o.price,updated,pairedProbability:paired,fresh};
     const previous=row.quotes.findIndex(x=>x.book===quote.book);
     if(previous<0)row.quotes.push(quote);else if(Date.parse(updated)>Date.parse(row.quotes[previous].updated))row.quotes[previous]=quote;
     groups.set(id,row);
    }
   }
  }
 }
 for(const row of groups.values()){
  row.quotes.sort((a,b)=>b.decimal-a.decimal);
  row.best=row.quotes.find(q=>q.fresh)??null;
  const refs=row.quotes.filter(q=>q.fresh&&q.book!==row.best?.book&&q.pairedProbability!==null).map(q=>q.pairedProbability!);
  row.references=refs.length;
  if(refs.length>=3){row.probability=median(refs);row.dispersion=Math.max(...refs)-Math.min(...refs);row.edge=row.best?row.probability*row.best.decimal-1:null;}
  row.status=Date.parse(row.start)<=now?'Started / closed':!row.best?'Stale prices':refs.length<3?'Insufficient references':row.dispersion!>.08?'Reference disagreement':row.conditional?'Push/tie model required':(row.edge??0)>=.02?'Research candidate':'No estimated edge';
  row.eligible=row.status==='Research candidate';
 }
 return [...groups.values()].sort((a,b)=>Number(b.eligible)-Number(a.eligible)||(b.edge??-999)-(a.edge??-999));
}
export function demoGames(now=Date.now()):Game[]{
 const stamp=new Date(now).toISOString(),start=new Date(now+2*86400000).toISOString();
 return [{id:'simulation-baltimore-buffalo',sport_key:'americanfootball_nfl',home_team:'Baltimore Ravens',away_team:'Buffalo Bills',commence_time:start,bookmakers:BOOKS.map((b,i)=>({key:b.key,title:b.name,last_update:stamp,markets:[
  {key:'spreads',last_update:stamp,outcomes:[{name:'Baltimore Ravens',point:-2.5,price:[2.12,1.91,1.9,1.92,1.91,1.9][i]},{name:'Buffalo Bills',point:2.5,price:1.91}]},
  {key:'totals',last_update:stamp,outcomes:[{name:'Over',point:47.5,price:1.91},{name:'Under',point:47.5,price:[1.91,2.08,1.91,1.9,1.92,1.91][i]}]},
  {key:'h2h',last_update:stamp,outcomes:[{name:'Baltimore Ravens',price:1.74},{name:'Buffalo Bills',price:2.2}]},
  {key:'player_receptions',last_update:stamp,outcomes:[{name:'Over',description:'Illustrative receiver',point:4.5,price:[1.91,1.91,2.1,1.91,1.91,1.91][i]},{name:'Under',description:'Illustrative receiver',point:4.5,price:1.91}]},
 ]}))}];
}
