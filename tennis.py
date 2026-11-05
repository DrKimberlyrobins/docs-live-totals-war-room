"""Read-only ATP/WTA schedule and Kalshi total-games discovery. No fabricated forecasts."""
import concurrent.futures,datetime as dt,json,pathlib,re,unicodedata
from zoneinfo import ZoneInfo
from collect import get,paged,utc
ROOT=pathlib.Path(__file__).parent
SERIES={'atp':'KXATPGTOTAL','wta':'KXWTAGTOTAL'}
WINNER_SERIES={'atp':'KXATPMATCH','wta':'KXWTAMATCH'}
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
 if not any(market['ticker'].startswith(s+'-') for s in [SERIES[match['tour']],WINNER_SERIES[match['tour']]]):return False
 text=normalized(market.get('rules_primary','')+' '+market.get('rules_secondary',''))
 if market['ticker'].startswith(WINNER_SERIES[match['tour']]+'-'):
  target=normalized(market.get('yes_sub_title') or '')
  if target not in [normalized(p) for p in match['players']]:return False
  rule_words=re.sub(r'[^a-z0-9]+',' ',unicodedata.normalize('NFKD',market.get('rules_primary','')+' '+market.get('rules_secondary','')).encode('ascii','ignore').decode().lower()).split()
  if not all(normalized(p) in text or normalized(p.split()[-1]) in rule_words for p in match['players']):return False
 elif not all(normalized(p) in text for p in match['players']):return False
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
  jobs={pool.submit(paged,'/markets','markets',series_ticker=s,status='open'):(t,kind) for mapping,kind in [(SERIES,'match_completed_games'),(WINNER_SERIES,'match_winner')] for t,s in mapping.items()}
  for f,(t,kind) in jobs.items():
   try:
    retrieved=f.result();captured=utc()
    for m in retrieved:
     row={k:m.get(k) for k in ['ticker','event_ticker','title','rules_primary','rules_secondary','floor_strike','strike_type','status','updated_time','yes_ask_dollars','yes_bid_dollars','no_ask_dollars','no_bid_dollars','yes_ask_size_fp','volume_fp','yes_sub_title','no_sub_title']};row.update(captured_at=captured,tour=t,scope=kind,depth_status='Order-book depth not verified');markets.append(row)
   except Exception as e:errors.append(t+' Kalshi totals: '+str(e))
 unmatched=[]
 for m in markets:
  candidates=[g for g in matches if market_matches(g,m)]
  if len(candidates)==1:candidates[0]['contracts'].append(m)
  else:unmatched.append(m)
 # Optional authenticated point-level source; no credential enters the output JSON.
 from tennis_live import fetch_live,convert,calculate,name
 import hashlib
 from audit import read_rows
 out=ROOT/'data';out.mkdir(exist_ok=True);forecast_path=out/'tennis_forecasts.jsonl';grade_path=out/'tennis_grades.jsonl';forecast_path.touch(exist_ok=True);grade_path.touch(exist_ok=True)
 forecasts=read_rows(forecast_path);seen={f['fingerprint'] for f in forecasts}
 try:payload,provider=fetch_live(utc())
 except Exception as e:payload=None;provider={'connected':False,'status':str(e)};errors.append('Point-level provider unavailable: '+str(e))
 # API Tennis is independently connected, with missing source latency kept explicit.
 from api_tennis import fetch as fetch_api,find as find_api,evidence as api_evidence
 try:
  api_rows,api_status=fetch_api();api_captured=utc()
  if api_rows is not None:
   provider=api_status;provider['captured_at']=api_captured
   for game in matches:
    if game['state']!='in':continue
    try:
     row,order=find_api(api_rows,game);ev=api_evidence(row,order,api_captured)
     game['live_evidence']=ev;game['captured_at']=api_captured
     if ev['set_scores'] and all(ev['set_scores']):
      game['set_scores']=ev['set_scores'];game['completed_games']=sum(map(sum,ev['set_scores']))
     game['notes'].append('API Tennis live server and point evidence retrieved; source-origin update time unavailable')
     game['prediction_status']='Live API Tennis connected. Automatic recommendation blocked: source-origin latency and match format not verified. Player picker accepts checked inputs.'
    except ValueError as e:game['notes'].append(str(e))
   provider['matched_live_games']=sum('live_evidence' in g for g in matches)
 except Exception as e:errors.append(str(e));provider={'connected':False,'status':str(e)}
 for match in matches:
  if match['state']!='in' or payload is None:continue
  try:
   candidates=[s for s in payload.get('summaries',[]) if {name(c.get('name','')) for c in s.get('sport_event',{}).get('competitors',[])}=={name(p) for p in match['players']}]
   if len(candidates)!=1:raise ValueError('No unique point-level source match')
   state=convert(candidates[0],match);projection=calculate(state,ROOT)
   if (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(provider['captured_at'])).total_seconds()>60:raise ValueError('Provider snapshot aged past 60 seconds during processing')
   for c in match['contracts']:
    p=None
    if c['scope']=='match_completed_games' and c.get('strike_type')=='greater' and c.get('floor_strike') is not None:p=sum(x>float(c['floor_strike']) for x in projection['samples'])/projection['runs']
    elif c['scope']=='match_winner':
     target=[i for i,player in enumerate(match['players']) if name(player)==name(c.get('yes_sub_title') or '')]
     if len(target)==1:p=projection['match_probabilities'][target[0]]
    if p is not None:c['model_p_yes']=p;c['model_p_no']=1-p
   del projection['samples'];match['set_scores']=[[pair[i] for pair in state['completedSets']]+[state['games'][i]] for i in [0,1]];match['completed_games']=sum(map(sum,state['completedSets']))+sum(state['games']);match['captured_at']=provider['captured_at'];match.update(projection=projection,simulations_completed=projection['runs'],model_state=state,prediction_status='Experimental point-level forecast; uncalibrated prior and strategy assumptions')
   fingerprint=hashlib.sha256(json.dumps({'game':match['id'],'state':state,'version':projection['model_version']},sort_keys=True).encode()).hexdigest()
   if fingerprint not in seen:
    record={'fingerprint':fingerprint,'timestamp':utc(),'kind':'forward_experimental_tennis','game_id':match['id'],'players':match['players'],'provider':provider,'state':state,'projection':projection,'contracts':match['contracts']}
    with forecast_path.open('a') as f:f.write(json.dumps(record,separators=(',',':'))+'\n')
    forecasts.append(record);seen.add(fingerprint)
  except Exception as e:match['prediction_status']='Blocked: '+str(e)
 grades=read_rows(grade_path);graded={g['fingerprint'] for g in grades};lookup={g['id']:g for g in matches}
 for record in forecasts:
  if record['fingerprint'] in graded:continue
  final=lookup.get(record['game_id'])
  if not final or final['state']!='post' or any(k in str(final['status']).lower() for k in ['retir','walkover','cancel','abandon','default']):continue
  lines=final['set_scores']
  if not lines or len(lines)!=2 or len(lines[0])!=len(lines[1]):continue
  pairs=list(zip(*lines));wins=[sum(pair[i]>pair[1-i] for pair in pairs) for i in [0,1]]
  def valid_set(pair):return (max(pair)==6 and min(pair)<=4) or (max(pair)==7 and min(pair) in [5,6])
  if not all(valid_set(pair) for pair in pairs) or max(wins)!=(record['state']['bestOf']+1)//2:continue
  winner=0 if wins[0]>wins[1] else 1;actual=sum(map(sum,lines));p=record['projection']['match_probabilities'][winner]
  grade={'fingerprint':record['fingerprint'],'graded_at':utc(),'winner':record['players'][winner],'actual_games':actual,'total_error':record['projection']['mean']-actual,'match_brier':(1-p)**2,'favorite_correct':p>.5,'source':final['source'],'paper_profit':None}
  with grade_path.open('a') as f:f.write(json.dumps(grade,separators=(',',':'))+'\n')
  grades.append(grade)
 result={'generated_at':utc(),'date':date.isoformat(),'matches':sorted(matches,key=lambda x:({'in':0,'pre':1,'post':2}.get(x['state'],3),x['date'])),'market_count':len(markets),'matched_count':sum(len(m['contracts']) for m in matches),'unmatched_contracts':unmatched,'errors':errors,'simulations_completed':sum(g['simulations_completed'] for g in matches),'paper_positions':0,'provider':provider,'forecast_count':len(forecasts),'grading':{'count':len(grades),'rows':grades},'limitations':['Independent 10,000-run engine is available; API Tennis evidence is gated on source latency and verified scoring format','ESPN website-feed licensing, latency and serving semantics are unverified','Sportradar live timelines investigated but not connected; authenticated provider access is required','Browser analyses are conditional on supplied inputs and remain separate from repository paper results','Retirements may resolve some contracts to a fair price rather than a binary win or loss']}
 out=ROOT/'data';out.mkdir(exist_ok=True);(out/'tennis.json').write_text(json.dumps(result,separators=(',',':')));print(json.dumps({k:result[k] for k in ['generated_at','market_count','matched_count','errors']}));return result
if __name__=='__main__':run()
