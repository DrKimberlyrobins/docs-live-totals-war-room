"""Read-only ATP/WTA schedule and Kalshi total-games discovery. No fabricated forecasts."""
import concurrent.futures,datetime as dt,json,pathlib,re,unicodedata
from zoneinfo import ZoneInfo
from collect import get,paged,utc
ROOT=pathlib.Path(__file__).parent
SERIES={'atp':'KXATPGTOTAL','wta':'KXWTAGTOTAL'}
def normalized(s):return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
def parse_matches(raw,tour,date,captured,url):
 matches=[]
 for event in raw.get('events',[]):
  for grouping in event.get('groupings',[]):
   if grouping.get('grouping',{}).get('slug') not in ['mens-singles','womens-singles']:continue
   for c in grouping.get('competitions',[]):
    players=c.get('competitors',[])
    if len(players)!=2 or any(p.get('type')!='athlete' for p in players):continue
    try:day=dt.datetime.fromisoformat(c['date'].replace('Z','+00:00')).date()
    except (KeyError,ValueError):continue
    if abs((day-date).days)>1:continue
    names=[p.get('athlete',{}).get('displayName','') for p in players]
    if not all(names):continue
    lines=[[int(x['value']) for x in p.get('linescores',[]) if x.get('value') is not None] for p in players]
    status=c.get('status',{});state=status.get('type',{}).get('state');missing=['Reliable source-origin latency','Current point score','Verified serve/return probabilities and surface adjustment','Verified match and tiebreak format','Verified retirement settlement handling']
    # A possession flag in an undocumented generic feed is not verified serving information.
    missing.append('Verified current server')
    matches.append({'id':tour+':'+c['id'],'tour':tour,'players':names,'date':c['date'],'tournament':event.get('name'),'round':c.get('round',{}).get('displayName'),'state':state,'status':status.get('type',{}).get('detail'),'set_scores':lines,'completed_games':sum(map(sum,lines)) if any(lines) else None,'reported_format_periods':c.get('format',{}).get('regulation',{}).get('periods'),'captured_at':captured,'source':url,'contracts':[],'missing':missing,'simulations_completed':0,'prediction_status':'BLOCKED: incomplete verified point/server/format/player inputs','notes':[x.get('text') for x in c.get('notes',[])]})
 return matches

def market_matches(match,market):
 if not market['ticker'].startswith(SERIES[match['tour']]+'-'):return False
 text=normalized(market.get('rules_primary','')+' '+market.get('rules_secondary',''))
 if not all(normalized(name) in text for name in match['players']):return False
 day=dt.datetime.fromisoformat(match['date'].replace('Z','+00:00')).strftime('%y%b%d').upper()
 return '-'+day in market.get('event_ticker','')

def run(date=None):
 date=date or dt.datetime.now(ZoneInfo('America/Chicago')).date();matches=[];markets=[];errors=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  def scores(tour):
   url=f'https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard?dates={date:%Y%m%d}'
   return parse_matches(get(url),tour,date,utc(),url)
  jobs={pool.submit(scores,t):t for t in SERIES}
  for f,t in jobs.items():
   try:matches+=f.result()
   except Exception as e:errors.append(t+' score feed: '+str(e))
  jobs={pool.submit(paged,'/markets','markets',series_ticker=s,status='open'):t for t,s in SERIES.items()}
  for f,t in jobs.items():
   try:
    captured=utc()
    for m in f.result():
     row={k:m.get(k) for k in ['ticker','event_ticker','title','rules_primary','rules_secondary','floor_strike','strike_type','status','updated_time','yes_ask_dollars','yes_bid_dollars','no_ask_dollars','no_bid_dollars','yes_ask_size_fp','volume_fp']};row.update(captured_at=captured,tour=t,scope='match_completed_games',depth_status='Order-book depth not verified');markets.append(row)
   except Exception as e:errors.append(t+' Kalshi totals: '+str(e))
 unmatched=[]
 for m in markets:
  candidates=[g for g in matches if market_matches(g,m)]
  if len(candidates)==1:candidates[0]['contracts'].append(m)
  else:unmatched.append(m)
 result={'generated_at':utc(),'date':date.isoformat(),'matches':sorted(matches,key=lambda x:({'in':0,'pre':1,'post':2}.get(x['state'],3),x['date'])),'market_count':len(markets),'matched_count':sum(len(m['contracts']) for m in matches),'unmatched_contracts':unmatched,'errors':errors,'simulations_completed':0,'paper_positions':0,'limitations':['This is a match and market discovery board, not a completed tennis prediction engine','ESPN website-feed licensing, latency and serving semantics are unverified','Sportradar live timelines investigated but not connected; authenticated provider access is required','No tennis probabilities, EV, simulated runs or paper entries are fabricated','Retirements may resolve some contracts to a fair price rather than a binary win or loss']}
 out=ROOT/'data';out.mkdir(exist_ok=True);(out/'tennis.json').write_text(json.dumps(result,separators=(',',':')));print(json.dumps({k:result[k] for k in ['generated_at','market_count','matched_count','errors']}));return result
if __name__=='__main__':run()
