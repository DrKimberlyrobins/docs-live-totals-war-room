"""Independent experimental live totals model. No market prices enter simulations."""
import math, random, statistics, hashlib, json, re
VERSION='0.1.0-experimental'
RULES={'nba':(48,4,12,100,1.13),'cbb':(40,2,20,69,1.04)}
def minutes(league,period,clock,state):
 length,periods,unit,*_=RULES[league]
 if state=='post': return length+max(0,period-periods)*5,0
 if state=='pre': return 0,length
 if period<=0: raise ValueError('Missing period')
 unit=unit if period<=periods else 5
 if clock<0 or clock>unit*60: raise ValueError('Invalid clock')
 elapsed=(period-1)*unit if period<=periods else length+(period-periods-1)*5
 elapsed+=unit-clock/60
 return elapsed,max(0,(length if period<=periods else length+(period-periods)*5)-elapsed)
def possession(stats,league):
 try:
  fg=float(stats['fieldGoalsMade-fieldGoalsAttempted'].split('-')[1]);ft=float(stats['freeThrowsMade-freeThrowsAttempted'].split('-')[1])
  return fg+(0.44 if league=='nba' else 0.475)*ft-float(stats['offensiveRebounds'])+float(stats.get('totalTurnovers',stats['turnovers']))
 except (KeyError,ValueError,IndexError): return None

def simulate(game,n=10000):
 if n!=10000: raise ValueError('Production simulation count must be 10000')
 league=game['league'];length,periods,unit,prior_pace,prior_ppp=RULES[league]
 elapsed,remaining=minutes(league,game['period'],game['clock_seconds'],game['state'])
 if game['state']!='in' or remaining<=0: return None
 stats=game.get('stats',[]);poss=[possession(s,league) for s in stats]
 observed=statistics.mean(poss) if len(poss)==2 and all(p is not None for p in poss) else None
 weight=elapsed/(elapsed+12)
 pace=prior_pace if observed is None or elapsed<1 else (1-weight)*prior_pace+weight*observed/elapsed*length
 pace=max(prior_pace*.6,min(prior_pace*1.5,pace))
 ppps=[]
 for i,score in enumerate(game['scores']):
  p=poss[i] if i<len(poss) else None
  ppps.append((prior_ppp*30+score)/(30+p) if p and p>0 else prior_ppp)
 margin=abs(game['scores'][0]-game['scores'][1]);late=remaining<=5
 seed=int(hashlib.sha256(json.dumps({k:game.get(k) for k in ['id','scores','period','clock_seconds','stats']},sort_keys=True).encode()).hexdigest()[:16],16)
 rng=random.Random(seed); totals=[];reg=[];teams=[];overtime=0
 for _ in range(n):
  # Shared tempo and efficiency uncertainty; conditional game strategy scenario.
  strategy=1.0
  if late and 2<=margin<=10 and rng.random()<.55: strategy=rng.uniform(1.03,1.18)
  if margin>=20 and rng.random()<.7: strategy=rng.uniform(.88,1)
  rate=pace/length*strategy
  possessions=max(0,rng.gauss(rate*remaining,max(.7,math.sqrt(rate*remaining)*.55)))
  shared=rng.gauss(0,.055 if observed is not None else .10)
  finals=[]
  for score,ppp in zip(game['scores'],ppps):
   eff=max(.35,rng.gauss(ppp+shared,.07));mu=possessions*eff
   finals.append(score+max(0,round(rng.gauss(mu,math.sqrt(max(.1,possessions))*1.05))))
  reg.append(sum(finals))
  # Explicit repeated 5 minute overtime, conditional on tied simulated score.
  ot=0
  while finals[0]==finals[1] and ot<20:
   ot+=1
   for i in range(2): finals[i]+=max(0,round(rng.gauss(rate*5*ppps[i],math.sqrt(rate*5)*1.05)))
  overtime+=ot>0;teams.append(finals);totals.append(sum(finals))
 ordered=sorted(totals);mean=statistics.mean(totals)
 return {'runs':n,'seed':seed,'model_version':VERSION,'mean':round(mean,2),'median':statistics.median(totals),'p10':ordered[999],'p90':ordered[8999],'remaining_points':round(mean-sum(game['scores']),2),'projected_scores':[round(statistics.mean(t[i] for t in teams),1) for i in range(2)],'estimated_possessions':observed,'pace':round(pace,2),'ppp':ppps,'overtime_probability':overtime/n,'confidence':'Uncalibrated / experimental','assumptions':['League pace and PPP priors, not team-specific pregame ratings','Box-score possession estimate, not exact play-by-play possessions','Late-foul and blowout scenario parameters are uncalibrated','Lineups, rotations, fatigue and current-period bonus are unavailable','Feed capture time is known; source latency is not guaranteed'],'samples':totals,'regulation_samples':reg}
def probability(samples,threshold,operator='greater'):
 if operator=='greater': return sum(x>threshold for x in samples)/len(samples)
 if operator=='greater_or_equal': return sum(x>=threshold for x in samples)/len(samples)
 raise ValueError('Unsupported settlement operator')
def fee(price,quantity=1,multiplier=1):
 return math.ceil((.07*quantity*price*(1-price)*multiplier-1e-12)*100)/100

def quote(book,side,quantity=1):
 """Executable buy VWAP from complementary bids; insufficient depth returns None."""
 fp=book.get('orderbook_fp');ob=fp or book.get('orderbook',{})
 key=('no' if side=='yes' else 'yes')+('_dollars' if fp else '')
 levels=sorted([(1-float(p)/(1 if fp else 100),float(q)) for p,q in ob.get(key,[])])
 left=quantity;cost=0
 for ask,size in levels:
  taken=min(left,size);cost+=taken*ask;left-=taken
  if left<=1e-9: return {'ask':levels[0][0],'quantity_at_best':levels[0][1],'vwap':cost/quantity,'slippage':cost/quantity-levels[0][0]}
 return None

def norm(s): return re.sub(r'[^a-z0-9]','',s.lower())
def matches(game,market):
 if game['league']=='nba' and not market['ticker'].startswith('KXNBA'):return False
 if game['league']=='cbb' and not market['ticker'].startswith('KXNCAAMB'):return False
 # Date derived from contract event ticker, not quote timestamp or closing date.
 import datetime
 date=datetime.datetime.fromisoformat(game['date'].replace('Z','+00:00')).astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).strftime('%y%b%d').upper()
 event=market.get('event_ticker','')
 if '-'+date not in event:return False
 text=norm(market.get('rules_primary',''))
 return all(any(norm(a) in text for a in aliases if len(norm(a))>=4) for aliases in game['aliases'])
def contract_type(ticker):
 prefix=ticker.split('-')[0]
 if 'TEAMTOTAL' in prefix:return 'team'
 if '1HTOTAL' in prefix:return '1h'
 if '2HTOTAL' in prefix:return '2h'
 for q in range(1,5):
  if f'{q}QTOTAL' in prefix:return f'q{q}'
 return 'full' if prefix in ('KXNBATOTAL','KXNCAAMBTOTAL') else 'unsupported'

TERMS_URL='https://assets.kalshi.com/contract_terms/BASKETBALLTOTALS.pdf'
TERMS_SHA256='c48fb1f6bd54fa6a2298e9f6c75b4c0ce31009ad609719ef119e179429652217'
def overtime_rule(rules,scope,verified_terms=False):
 lower=rules.lower()
 if any(t in lower for t in ['excluding overtime','does not include overtime','regulation only']):return 'excluded'
 if any(t in lower for t in ['including overtime','includes overtime','overtime included']):return 'included'
 if verified_terms and scope=='full':return 'included'
 if verified_terms and scope in ['1h','2h','q1','q2','q3','q4']:return 'excluded'
 return 'unverified'
