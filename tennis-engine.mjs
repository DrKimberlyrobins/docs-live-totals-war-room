// Independent point -> game -> set -> match simulation. No market prices enter.
export const VERSION='tennis-1.0-experimental';
export function finishedSet(a,b){return (Math.max(a,b)===6&&Math.min(a,b)<=4)||(Math.max(a,b)===7&&[5,6].includes(Math.min(a,b)));}
export function pointScore(a,b,tiebreak=false){
 if(tiebreak){if(!Number.isInteger(a)||!Number.isInteger(b)||a<0||b<0)throw Error('Tiebreak points must be nonnegative integers');return [a,b];}
 const map={'0':0,'15':1,'30':2,'40':3,'AD':4};const p=[map[String(a).toUpperCase()],map[String(b).toUpperCase()]];
 if(p.some(x=>x===undefined)||p.some((x,i)=>x===4&&p[1-i]!==3))throw Error('Use 0, 15, 30, 40 or AD (advantage requires opponent 40)');return p;
}
function rng(seed){let s=seed>>>0;return ()=>{s+=0x6D2B79F5;let t=s;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};}
function normal(r){return Math.sqrt(-2*Math.log(Math.max(r(),1e-12)))*Math.cos(2*Math.PI*r());}
function gamma(k,r){if(k<1)return gamma(k+1,r)*Math.pow(r(),1/k);const d=k-1/3,c=1/Math.sqrt(9*d);for(let i=0;i<10000;i++){const z=normal(r),v=Math.pow(1+c*z,3);if(v<=0)continue;const u=r();if(u<1-.0331*z**4||Math.log(u)<.5*z*z+d*(1-v+Math.log(v)))return d*v;}throw Error('Parameter sampling failed');}
function beta(a,b,r){const x=gamma(a,r),y=gamma(b,r);return x/(x+y);}
export function validate(s){
 if(!s||!Array.isArray(s.players)||s.players.length!==2||s.players.some(x=>!String(x).trim()))throw Error('Two player names are required');
 if(![3,5].includes(s.bestOf))throw Error('Verified best-of-three or best-of-five format required');
 if(![0,1].includes(s.server))throw Error('Current server must be player A or B');
 if(![7,10].includes(s.finalTiebreakTarget))throw Error('Final-set tiebreak target must be 7 or 10; advantage sets/match tiebreak replacement unsupported');
 if(!Array.isArray(s.completedSets)||!Array.isArray(s.games)||s.games.length!==2||s.games.some(x=>!Number.isInteger(x)||x<0||x>6))throw Error('Invalid set/game state');
 const wins=[0,0];for(const set of s.completedSets){if(!Array.isArray(set)||set.length!==2||set.some(x=>!Number.isInteger(x)||x<0)||!finishedSet(...set))throw Error('Completed sets must be valid completed tiebreak sets');wins[set[0]>set[1]?0:1]++;if(Math.max(...wins)>=Math.ceil(s.bestOf/2))throw Error('Match already completed');}
 if(s.completedSets.length>=s.bestOf||finishedSet(...s.games))throw Error('Current set already complete; update set state');
 if(!Array.isArray(s.points)||s.points.length!==2||s.points.some(x=>!Number.isInteger(x)||x<0))throw Error('Invalid point state');
 const tb=s.games[0]===6&&s.games[1]===6,target=s.completedSets.length===s.bestOf-1?s.finalTiebreakTarget:7;
 if(tb){if(Math.max(...s.points)>=target&&Math.abs(s.points[0]-s.points[1])>=2)throw Error('Tiebreak already complete');}
 else if(s.points.some((x,i)=>x>3&&(x!==4||s.points[1-i]!==3)))throw Error('Invalid normal-game point state');
 for(const key of ['serveWon','serveTotal'])if(!Array.isArray(s[key])||s[key].length!==2)throw Error('Both players’ service-points-won and total service points are required');
 for(let i=0;i<2;i++)if(!Number.isInteger(s.serveWon[i])||!Number.isInteger(s.serveTotal[i])||s.serveWon[i]<0||s.serveTotal[i]<0||s.serveWon[i]>s.serveTotal[i])throw Error('Invalid service point counts');
 if(!['atp','wta'].includes(s.tour))throw Error('Select ATP or WTA');
 if(s.status!=='live')throw Error('Only active matches can be simulated; retired/suspended/final matches are blocked');
 return wins;
}
export function simulate(s,runs=10000){
 const initialWins=validate(s);if(runs!==10000)throw Error('Exactly 10,000 simulations required');
 const seedState=Object.fromEntries(['players','tour','status','bestOf','finalTiebreakTarget','completedSets','games','points','server','serveWon','serveTotal'].map(k=>[k,s[k]]));
 const seed=Array.from(JSON.stringify(seedState)).reduce((h,c)=>Math.imul(h^c.charCodeAt(0),16777619)>>>0,2166136261),r=rng(seed);
 const prior=s.tour==='atp'?.64:.60,weight=80,alpha=s.serveWon.map(x=>x+weight*prior),betaParam=s.serveTotal.map((x,i)=>x-s.serveWon[i]+weight*(1-prior));
 const baseGames=s.completedSets.reduce((n,set)=>n+set[0]+set[1],0)+s.games[0]+s.games[1];const totals=[],setCounts={},nextGame=[0,0],currentSet=[0,0],match=[0,0],tbSamples=[];
 for(let trial=0;trial<runs;trial++){
  const ps=[beta(alpha[0],betaParam[0],r),beta(alpha[1],betaParam[1],r)];let wins=[...initialWins],games=[...s.games],points=[...s.points],server=s.server,total=baseGames,firstGame=true,firstSet=true,tbCount=0,iterations=0;
  while(Math.max(...wins)<Math.ceil(s.bestOf/2)){
   if(++iterations>10000)throw Error('Simulation exceeded point guard; unsupported state');
   const tb=games[0]===6&&games[1]===6;
   if(tb){
    const played=points[0]+points[1],firstServer=server^(Math.floor((played+1)/2)%2),target=wins[0]+wins[1]===s.bestOf-1?s.finalTiebreakTarget:7;
    let t=played;
    while(!(Math.max(...points)>=target&&Math.abs(points[0]-points[1])>=2)){
     if(++iterations>10000)throw Error('Tiebreak point guard');
     const serving=firstServer^(Math.floor((t+1)/2)%2),pA=serving===0?ps[0]:1-ps[1];points[r()<pA?0:1]++;t++;
    }
    const w=points[0]>points[1]?0:1;games[w]++;total++;tbCount++;server=1-firstServer;
    if(firstGame){nextGame[w]++;firstGame=false;}
   }else{
    while(!(Math.max(...points)>=4&&Math.abs(points[0]-points[1])>=2)){
     if(++iterations>10000)throw Error('Normal-game point guard');const pA=server===0?ps[0]:1-ps[1];points[r()<pA?0:1]++;
    }
    const w=points[0]>points[1]?0:1;games[w]++;total++;server=1-server;
    if(firstGame){nextGame[w]++;firstGame=false;}
   }
   points=[0,0];
   if(finishedSet(...games)){const w=games[0]>games[1]?0:1;wins[w]++;games=[0,0];if(firstSet){currentSet[w]++;firstSet=false;}}
  }
  match[wins[0]>wins[1]?0:1]++;totals.push(total);tbSamples.push(tbCount);const key=wins.join('–');setCounts[key]=(setCounts[key]||0)+1;
 }
 totals.sort((a,b)=>a-b);const mean=totals.reduce((a,b)=>a+b,0)/runs;
 return {model_version:VERSION,runs,seed,mean,median:(totals[4999]+totals[5000])/2,p10:totals[999],p90:totals[8999],remaining_games:mean-baseGames,match_probabilities:match.map(x=>x/runs),current_set_probabilities:currentSet.map(x=>x/runs),next_game_probabilities:nextGame.map(x=>x/runs),serve_posterior_means:alpha.map((a,i)=>a/(a+betaParam[i])),serve_observed:s.serveWon.map((w,i)=>s.serveTotal[i]?w/s.serveTotal[i]:null),set_score_probabilities:Object.fromEntries(Object.entries(setCounts).map(([k,v])=>[k,v/runs])),samples:totals,assumptions:[`Uncalibrated ${s.tour.toUpperCase()} service-point prior ${prior} with ${weight} pseudo-points per player`,'Current-match serving evidence includes opponent return impact; no verified historical surface adjustment','Point probabilities vary between simulations and remain fixed within each simulation','No injury, retirement, medical-timeout, fatigue or psychological adjustment','Standard advantage games and tiebreak sets only; no doubles, no-ad or match-tiebreak replacement']};
}
export function marketProbability(result,threshold,operator='greater'){
 if(!Number.isFinite(threshold))throw Error('Invalid threshold');if(operator!=='greater')throw Error('Unsupported settlement operator');return result.samples.filter(x=>x>threshold).length/result.runs;
}
