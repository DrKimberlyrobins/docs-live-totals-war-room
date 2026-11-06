#!/usr/bin/env python3
"""Read-only collection and append-only forward evidence. Python standard library."""
import argparse,concurrent.futures,csv,datetime as dt,json,os,pathlib,time,urllib.request,urllib.parse,hashlib
from zoneinfo import ZoneInfo
from engine import *
ROOT=pathlib.Path(__file__).parent
API='https://external-api.kalshi.com/trade-api/v2'
SLUG={'nba':'nba','cbb':'mens-college-basketball'}
def clock_seconds(status):
 if status.get('clock') is not None:return float(status['clock'])
 value=status.get('displayClock','')
 try:
  parts=value.split(':')
  return float(parts[0])*60+float(parts[1]) if len(parts)==2 else float(value)
 except (ValueError,TypeError):raise ValueError('Missing or invalid game clock')
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def get(url):
 for attempt in range(3):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'DocsLiveTotals/0.1 (read-only research)'}),timeout=18) as r:
    return json.load(r)
  except Exception:
   if attempt==2:raise
   time.sleep(1+attempt)
def paged(endpoint,key,**params):
 result=[];cursor=None
 for _ in range(30):
  p={**params,'limit':1000}
  if cursor:p['cursor']=cursor
  d=get(API+endpoint+'?'+urllib.parse.urlencode(p));result+=d.get(key,[]);cursor=d.get('cursor')
  if not cursor:return result
 raise RuntimeError('Pagination incomplete; refusing partial discovery')
def scoreboard(league,date):
 url=f'https://site.api.espn.com/apis/site/v2/sports/basketball/{SLUG[league]}/scoreboard?dates={date}&limit=1000'+('&groups=50' if league=='cbb' else '')
 raw=get(url);captured=utc();games=[]
 for e in raw.get('events',[]):
  c=e['competitions'][0];s=e['status'];teams=sorted(c['competitors'],key=lambda t:t['homeAway']=='home')
  games.append({'id':e['id'],'league':league,'name':e['name'],'date':e['date'],'state':s['type']['state'],'status':s['type']['detail'],'period':s.get('period',0),'clock':s.get('displayClock'),'clock_seconds':clock_seconds(s),'scores':[int(t.get('score',0)) for t in teams],'teams':[t['team']['displayName'] for t in teams],'team_ids':[t['team']['id'] for t in teams],'aliases':[[t['team'].get(k,'') for k in ('location','displayName','shortDisplayName')] for t in teams],'linescores':[[x.get('value') for x in t.get('linescores',[])] for t in teams],'score_captured_at':captured,'score_source_updated_at':e.get('lastUpdated'),'source':url,'stats':[],'missing':['Verified lineup','Current-period fouls and bonus','Pregame team efficiency and pace','Guaranteed feed latency'],'contracts':[]})
 return games

def summary(game):
 try:
  url=f"https://site.api.espn.com/apis/site/v2/sports/basketball/{SLUG[game['league']]}/summary?event={game['id']}"
  d=get(url);header=d.get('header',{}).get('competitions',[{}])[0]
  # Never combine different score/clock snapshots: summary is authoritative when available.
  st=header.get('status');ts={t['team']['id']:t for t in header.get('competitors',[])}
  if st and all(i in ts for i in game['team_ids']):
   game.update(scores=[int(ts[i].get('score',0)) for i in game['team_ids']],period=st.get('period',0),clock=st.get('displayClock'),clock_seconds=clock_seconds(st),state=st['type']['state'],status=st['type']['detail'],linescores=[[float(x.get('value',x.get('displayValue',0))) for x in ts[i].get('linescores',[])] for i in game['team_ids']])
  stats={t['team']['id']:{s['name']:s['displayValue'] for s in t.get('statistics',[])} for t in d.get('boxscore',{}).get('teams',[])}
  game['stats']=[stats.get(i,{}) for i in game['team_ids']];game['stats_captured_at']=utc();game['stats_source']=url
  if st and all(i in ts for i in game['team_ids']):game['score_captured_at']=game['stats_captured_at']
  if not all(possession(x,game['league']) is not None for x in game['stats']):game['missing'].append('Live possession inputs')
  game['stats_source_updated_at']=d.get('meta',{}).get('lastUpdated')
 except Exception as e:game['missing'].append('Box score: '+str(e))
 return game

def append(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a') as f:f.write(json.dumps(obj,separators=(',',':'))+'\n')
def run(date):
 out=ROOT/'data';out.mkdir(exist_ok=True);(out/'grades.jsonl').touch(exist_ok=True);errors=[];games=[]
 dates=[(date+dt.timedelta(days=i)).strftime('%Y%m%d') for i in (-1,0,1)]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  jobs={pool.submit(scoreboard,l,d):(l,d) for l in SLUG for d in dates}
  for f,key in jobs.items():
   try:games+=f.result()
   except Exception as e:errors.append(f'Scoreboard {key}: {e}')
  active=[g for g in games if g['state']=='in']
  # Refresh each active snapshot only after market discovery, immediately before simulation.
 # Discover series instead of assuming every scoring market is a full-game total.
 markets=[];series=[];terms_verified=False
 try:
  with urllib.request.urlopen(TERMS_URL,timeout=18) as response:terms_verified=hashlib.sha256(response.read()).hexdigest()==TERMS_SHA256
  if not terms_verified:errors.append('Kalshi contract terms changed; settlement defaults blocked')
 except Exception as e:errors.append('Kalshi contract terms unavailable: '+str(e))
 try:
  series=[s for s in get(API+'/series?category=Sports').get('series',[]) if s['ticker'].startswith(('KXNBA','KXNCAAMB')) and 'TOTAL' in s['ticker'] and 'SERIES' not in s['ticker'] and 'SUMMER' not in s['ticker']]
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   jobs={pool.submit(paged,'/markets','markets',series_ticker=s['ticker'],status='open'):s for s in series}
   for f,s in jobs.items():
    try:
     for m in f.result():m['contract_terms_url']=s.get('contract_terms_url');m['fee_type']=s.get('fee_type');m['fee_multiplier']=s.get('fee_multiplier');m['captured_at']=utc();markets.append(m)
    except Exception as e:errors.append(f"Kalshi {s['ticker']}: {e}")
 except Exception as e:errors.append('Kalshi discovery: '+str(e))
 # Reject ambiguous team-name matches across the full collected schedule.
 matching={}
 for m in markets:
  candidates=[g['id'] for g in games if matches(g,m)]
  if len(candidates)==1:matching[m['ticker']]=candidates[0]
 archive=out/'forecasts.jsonl' 
 old=[]
 if archive.exists():old=[json.loads(x) for x in archive.read_text().splitlines() if x]
 fingerprints={x['fingerprint'] for x in old};new=[]
 by_ticker={}
 from paper import choose,input_errors,settlement,save_report
 paper_path=out/'paper_positions.jsonl';paper_results_path=out/'paper_results.jsonl'
 paper_path.touch(exist_ok=True);paper_results_path.touch(exist_ok=True)
 positions=[json.loads(x) for x in paper_path.read_text().splitlines() if x]
 for g in games:
  if g['state']=='in':summary(g)
  sim=None
  try:
   issues=input_errors(g,utc()) if g['state']=='in' else []
   if issues:g['missing']+=issues
   sim=simulate(g) if g['state']=='in' and not issues else None
  except Exception as e:g['missing'].append('Model: '+str(e))
  if sim:g['projection']={k:v for k,v in sim.items() if not k.endswith('samples')}
  books={}
  candidates=[m for m in markets if matching.get(m['ticker'])==g['id'] and contract_type(m['ticker'])=='full'] if sim else []
  candidates.sort(key=lambda m:abs(float(m.get('floor_strike') or 0)-sim['mean']))
  def fresh_quote(m):
   ticker=m['ticker'];fresh=get(API+'/markets/'+urllib.parse.quote(ticker,safe=''))['market'];market_captured=utc();book=get(API+'/markets/'+urllib.parse.quote(ticker,safe='')+'/orderbook');captured=utc()
   return ticker,{**m,**fresh,'captured_at':market_captured},book,captured
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
   for f in [pool.submit(fresh_quote,m) for m in candidates[:8]]:
    try:
     ticker,fresh,book,captured=f.result();books[ticker]=(book,captured);by_ticker[ticker]=fresh
    except Exception as e:g['missing'].append('Fresh quote: '+str(e))
  for original in markets:
   m=by_ticker.get(original['ticker'],original)
   if matching.get(m['ticker'])!=g['id']:continue
   typ=contract_type(m['ticker']);rules=m.get('rules_primary','')+'\n'+m.get('rules_secondary','')
   c={k:m.get(k) for k in ['ticker','event_ticker','title','rules_primary','rules_secondary','floor_strike','strike_type','status','updated_time','captured_at','volume_fp','yes_ask_dollars','yes_bid_dollars','no_ask_dollars','no_bid_dollars','fee_type','fee_multiplier']};c['type']=typ
   # Rules text must explicitly establish overtime treatment before pricing a contract.
   c['overtime']=overtime_rule(rules,typ,terms_verified and m.get('contract_terms_url')==TERMS_URL)
   c['contract_terms_url']=m.get('contract_terms_url');c['terms_sha256']=TERMS_SHA256 if terms_verified and m.get('contract_terms_url')==TERMS_URL else None
   c['recommendation']='NO VERIFIED EDGE';c['reason']='Uncalibrated model; team priors, lineup and source latency unverified'
   if sim and typ=='full' and m.get('strike_type')=='greater' and m.get('floor_strike') is not None and c['overtime']!='unverified':
    c['p_yes']=probability(sim['samples' if c['overtime']=='included' else 'regulation_samples'],float(m['floor_strike']));c['p_no']=1-c['p_yes']
   if g['state']=='in' and typ=='full':
    try:
     if m['ticker'] not in books:raise RuntimeError('Depth not sampled: bounded to eight nearest full-game thresholds per active game')
     book,captured=books[m['ticker']]
     if book is None:raise RuntimeError(captured)
     c['orderbook_captured_at']=captured;c['orderbook']=book
     for side in ['yes','no']:
      q=quote(book,side)
      if q:
       q['fee']=fee(q['vwap'],multiplier=float(m['fee_multiplier'])) if m.get('fee_multiplier') is not None and m.get('fee_type') in ['quadratic','quadratic_with_maker_fees'] else None
       p=c.get('p_'+side);q['difference']=p-q['vwap'] if p is not None else None;q['net_ev']=p-q['vwap']-q['fee'] if p is not None and q['fee'] is not None else None;c[side+'_execution']=q
    except Exception as e:c['orderbook_error']=str(e)
   g['contracts'].append(c)
  if sim:
   # One immutable record per actual input state; no duplicate forecasts on unchanged polling.
   fingerprint=hashlib.sha256(json.dumps({'id':g['id'],'seed':sim['seed'],'version':VERSION},sort_keys=True).encode()).hexdigest()
   if fingerprint not in fingerprints:
    rec={'fingerprint':fingerprint,'timestamp':utc(),'kind':'forward_experimental','game':g,'model_version':VERSION,'simulation':g['projection'],'recommendation':'NO VERIFIED EDGE','paper_position':None}
    append(archive,rec);new.append(rec);fingerprints.add(fingerprint)
   paper=choose(g,g['projection'],utc(),positions)
   if paper:append(paper_path,paper);positions.append(paper)
 # Settlements live separately; never overwrite the pre-outcome evidence.
 grades=out/'grades.jsonl';graded=set()
 if grades.exists():graded={json.loads(x)['fingerprint'] for x in grades.read_text().splitlines() if x}
 game_lookup={g['id']:g for g in games}
 all_grades=[json.loads(x) for x in grades.read_text().splitlines() if x] if grades.exists() else []
 for rec in old+new:
  if rec['fingerprint'] in graded:continue
  g=game_lookup.get(rec['game']['id'])
  if not g or g['state']!='post':continue
  actual=sum(g['scores']);settlements=[]
  for c in rec['game']['contracts']:
   if c.get('p_yes') is None:continue
   try:
    market=get(API+'/markets/'+urllib.parse.quote(c['ticker'],safe=''))['market']
    if market.get('status')!='finalized' or market.get('result') not in ['yes','no']:continue
    y=int(market['result']=='yes');settlements.append({'ticker':c['ticker'],'result':market['result'],'probability':c['p_yes'],'brier':(c['p_yes']-y)**2,'settlement_ts':market.get('settlement_ts'),'paper_return':None})
   except Exception:pass
  grade={'fingerprint':rec['fingerprint'],'graded_at':utc(),'actual_total':actual,'forecast_error':rec['simulation']['mean']-actual,'source':g['source'],'settlements':settlements,'paper_return':None}
  # Don't freeze incomplete contract settlements; retry on next collection.
  if any(c.get('p_yes') is not None for c in rec['game']['contracts']) and len(settlements)<sum(c.get('p_yes') is not None for c in rec['game']['contracts']):continue
  append(grades,grade);all_grades.append(grade)
 board={'generated_at':utc(),'date':date.isoformat(),'model_version':VERSION,'games':games,'errors':errors,'market_count':len(markets),'matched_count':sum(len(g['contracts']) for g in games),'series':[{'ticker':s['ticker'],'title':s['title']} for s in series],'forecast_count':len(old)+len(new),'new_forecasts':len(new),'data_policy':'ESPN public website feed; undocumented API, redistribution/license/SLA not established. No guaranteed live latency. Kalshi official public read-only API.','grading':{'graded_forecasts':len(all_grades),'mae':round(statistics.mean(abs(x['forecast_error']) for x in all_grades),2) if all_grades else None,'brier':statistics.mean(s['brier'] for g in all_grades for s in g['settlements']) if any(g['settlements'] for g in all_grades) else None,'positions':0,'hypothetical_returns':None}}
 paper_results=[json.loads(x) for x in paper_results_path.read_text().splitlines() if x];settled_ids={r['position_id'] for r in paper_results}
 for position in positions:
  if position['position_id'] in settled_ids:continue
  try:
   market=get(API+'/markets/'+urllib.parse.quote(position['ticker'],safe=''))['market'];result=settlement(position,market,utc())
   if result:append(paper_results_path,result);paper_results.append(result)
  except Exception as e:errors.append('Paper settlement pending: '+str(e))
 paper_summary=save_report(out);board['paper']={k:v for k,v in paper_summary.items() if k!='rows'}
 from audit import write_review
 write_review(out)
 temp=out/'board.tmp';temp.write_text(json.dumps(board,separators=(',',':')));temp.replace(out/'board.json')
 write_sheets_board(out, board)
 print(json.dumps({k:board[k] for k in ['generated_at','market_count','matched_count','forecast_count','new_forecasts','errors']}))
def write_sheets_board(out, board):
 """Publish a flat, timestamped view of the same collector snapshot."""
 fields = [
  'League', 'Matchup', 'Tip (UTC)', 'Status', 'Period', 'Clock', 'Away', 'Home',
  'Total', 'Projected total', 'P10', 'P90', 'Runs', 'Kalshi matches',
  'Score captured (UTC)', 'Collector snapshot (UTC)', 'Game ID',
 ]
 temp = out / 'sheets-board.tmp'
 with temp.open('w', newline='', encoding='utf-8') as stream:
  rows = csv.writer(stream)
  rows.writerow(fields)
  for game in sorted(board['games'], key=lambda g: ({'in': 0, 'pre': 1, 'post': 2}.get(g['state'], 3), g['date'])):
   projection = game.get('projection') or {}
   away, home = game['scores']
   has_score = game['state'] in ('in', 'post') and away is not None and home is not None
   rows.writerow([
    'NBA' if game['league'] == 'nba' else 'NCAA men', game['name'], game['date'],
    game['status'], game['period'] if has_score else None, f"{game['clock']} left" if has_score and game.get('clock') else None,
    away if has_score else None, home if has_score else None, away + home if has_score else None,
    projection.get('mean'), projection.get('p10'), projection.get('p90'), projection.get('runs'),
    len(game['contracts']), game.get('score_captured_at'), board['generated_at'], game['id'],
   ])
 temp.replace(out / 'sheets-board.csv')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--date');args=p.parse_args();run(dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(ZoneInfo('America/Chicago')).date())
