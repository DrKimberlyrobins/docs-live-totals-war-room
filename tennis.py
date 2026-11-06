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
    matches.append({'id':tour+':'+c['id'],'tour':tour,'players':names,'date':c['date'],'tournament':event.get('name'),'round':c.get('round',{}).get('displayName'),'state':state,'status':status.get('type',{}).get('detail'),'set_scores':lines,'completed_games':sum(map(sum,lines)) if any(lines) else None,'reported_format_periods':c.get('format',{}).get('regulation',{}).get('periods'),'captured_at':captured,'source':url,'contracts':[],'missing':missing,'simulations_completed':0,'prediction_status':'Scheduled: automatic forecast begins during play' if state=='pre' else 'Completed game: see result and archived forecasts' if state=='post' else 'Live provider update pending','notes':[x.get('text') for x in c.get('notes',[])]})
 return matches

def market_matches(match,market):
 if match['tour'] not in SERIES:return False
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
 from api_tennis import fetch as fetch_api,find as find_api,evidence as api_evidence,state_from_evidence,player_matches,ENDPOINT
 from tennis_live import calculate
 from tennis_value import evaluate
 from collect import API
 from audit import read_rows
 import hashlib
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  def scores(tour):
   url=f'https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard?dates={date:%Y%m%d}'
   return parse_matches(get(url),tour,date,utc(),url)
  jobs={pool.submit(scores,t):t for t in SERIES}
  for f,t in jobs.items():
   try:matches+=f.result()
   except Exception as e:errors.append(t+' score feed unavailable')
  jobs={pool.submit(paged,'/markets','markets',series_ticker=s,status='open'):(t,kind) for mapping,kind in [(SERIES,'match_completed_games'),(WINNER_SERIES,'match_winner')] for t,s in mapping.items()}
  for f,(t,kind) in jobs.items():
   try:
    retrieved=f.result();captured=utc()
    for m in retrieved:
     row={k:m.get(k) for k in ['ticker','event_ticker','title','rules_primary','rules_secondary','floor_strike','strike_type','status','updated_time','yes_ask_dollars','yes_bid_dollars','no_ask_dollars','no_bid_dollars','yes_ask_size_fp','volume_fp','yes_sub_title','no_sub_title']};row.update(captured_at=captured,tour=t,scope=kind,depth_status='Order-book depth not collected for inactive games');markets.append(row)
   except Exception:errors.append(t+' Kalshi discovery unavailable')
 provider={'connected':False,'status':'API Tennis key not configured'};api_rows=None;fixtures=[]
 try:
  api_rows,provider=fetch_api();api_captured=utc();provider['captured_at']=api_captured
  if api_rows is not None:
   try:fixtures,_=fetch_api('get_fixtures',date_start=str(date-dt.timedelta(days=1)),date_stop=str(date+dt.timedelta(days=1)))
   except Exception:errors.append('API Tennis fixture history unavailable; live feed retained')
 except Exception as e:provider={'connected':False,'status':str(e)};errors.append(str(e))
 # Add provider-only singles and keep stable ESPN identity for already tracked matches.
 combined={str(r.get('event_key')):r for r in (fixtures or [])}
 combined.update({str(r.get('event_key')):r for r in (api_rows or [])})
 for row in combined.values():
  typ=row.get('event_type_type','').lower();tour='atp' if typ=='atp singles' else 'wta' if typ=='wta singles' else None
  status=str(row.get('event_status') or '')
  terminal=any(word in status.lower() for word in ('finish','retir','walkover','cancel','abandon'))
  active=str(row.get('event_live'))=='1' and not terminal
  # Show live events outside our ATP/WTA singles model without running that model on them.
  if not tour and not active:continue
  tour=tour or 'other'
  names=[row.get('event_first_player',''),row.get('event_second_player','')]
  if not all(names):continue
  # Resolve abbreviations only through a unique Kalshi full-player name.
  for i,n in enumerate(names):
   full={m['yes_sub_title'] for m in markets if m['scope']=='match_winner' and m['tour']==tour and m.get('yes_sub_title') and player_matches(m['yes_sub_title'],n)}
   if len(full)==1:names[i]=full.pop()
  candidates=[g for g in matches if tour!='other' and g['tour']==tour and g['date'][:10]==row.get('event_date') and any(all(player_matches(g['players'][i],names[o[i]]) for i in [0,1]) for o in [(0,1),(1,0)])]
  if len(candidates)==1:
   game=candidates[0];game['api_event_key']=str(row['event_key'])
   if active:game['state']='in';game['status']=status
   elif 'finished' in status.lower():
    game['state']='post';game['status']=status
    try:
     order=next(o for o in [(0,1),(1,0)] if all(player_matches(game['players'][i],names[o[i]]) for i in [0,1]))
     game['set_scores']=api_evidence(row,order,api_captured)['set_scores'];game['source']=ENDPOINT
    except (ValueError,StopIteration):pass
   continue
  if candidates:continue
  state='in' if active else 'post' if terminal else 'pre'
  try:
   ev=api_evidence(row,(0,1),api_captured);lines=ev['set_scores']
  except (KeyError,ValueError,TypeError):lines=[[],[]]
  matches.append({'id':tour+':api:'+str(row['event_key']),'api_event_key':str(row['event_key']),'tour':tour,'event_type':row.get('event_type_type'),'players':names,'date':row['event_date']+'T'+str(row.get('event_time') or '00:00')+':00Z','tournament':row.get('tournament_name'),'round':row.get('tournament_round'),'state':state,'status':status or 'Scheduled','set_scores':lines,'completed_games':sum(map(sum,lines)) if any(lines) else None,'reported_format_periods':None,'captured_at':api_captured,'source':ENDPOINT,'contracts':[],'missing':['Source-origin latency','Historical surface-adjusted serving ability'],'simulations_completed':0,'prediction_status':'Scheduled: live analysis begins when play starts' if state=='pre' else 'Final result' if state=='post' else 'Waiting for synchronized point state','notes':[]})
 unmatched=[]
 for m in markets:
  candidates=[g for g in matches if market_matches(g,m)]
  if len(candidates)==1:candidates[0]['contracts'].append(m)
  else:unmatched.append(m)
 out=ROOT/'data';out.mkdir(exist_ok=True);forecast_path=out/'tennis_forecasts.jsonl';grade_path=out/'tennis_grades.jsonl';forecast_path.touch(exist_ok=True);grade_path.touch(exist_ok=True)
 forecasts=read_rows(forecast_path);seen={f['fingerprint'] for f in forecasts};series_cache={}
 for match in matches:
  if match['state']!='in':continue
  if match['tour'] not in SERIES:
   match['prediction_status']='Live score only · this event type is outside the ATP/WTA singles model'
   continue
  if api_rows is None:
   match['prediction_status']='Live provider temporarily unavailable';continue
  try:
   row,order=find_api(api_rows,match);ev=api_evidence(row,order,api_captured);match['live_evidence']=ev
   state,rules=state_from_evidence(ev,match);projection=calculate(state,ROOT)
   projection['assumptions']+=rules['notes'];projection['format']=rules
   match['set_scores']=ev['set_scores'];match['completed_games']=sum(map(sum,ev['set_scores']));match['captured_at']=api_captured
   match['missing']=['Source-origin delay guarantee','Historical surface/injury adjustments','Retirement probability and discretionary fair-price settlement']
   match['notes']+=rules['notes']
   match.update(projection={k:v for k,v in projection.items() if k!='samples'},simulations_completed=projection['runs'],model_state=state,prediction_status='Automatic 10,000-run forecast · conditional on captured score and normal completion')
   for c in match['contracts']:
    p=None
    if c['scope']=='match_completed_games' and c.get('strike_type')=='greater' and c.get('floor_strike') is not None:p=sum(x>float(c['floor_strike']) for x in projection['samples'])/projection['runs']
    elif c['scope']=='match_winner':
     target=[i for i,player in enumerate(match['players']) if normalized(player)==normalized(c.get('yes_sub_title') or '')]
     if len(target)==1:p=projection['match_probabilities'][target[0]]
    if p is None:continue
    c['model_p_yes']=p;c['model_p_no']=1-p
    try:
     series=c['ticker'].split('-')[0]
     if series not in series_cache:series_cache[series]=get(API+'/series/'+series).get('series',{})
     book=get(API+'/markets/'+c['ticker']+'/orderbook');c['value']=evaluate(c,p,book,series_cache[series]);c['depth_status']=c['value']['depth_status']
    except Exception:c['depth_status']='Current depth or fee retrieval unavailable'
   fingerprint=hashlib.sha256(json.dumps({'game':match['id'],'state':state,'version':projection['model_version'],'quotes':[{k:c.get(k) for k in ['ticker','yes_ask_dollars','no_ask_dollars']} for c in match['contracts']]},sort_keys=True).encode()).hexdigest()
   if fingerprint not in seen:
    # Immutable forward record. Quotes are separately timestamped; no retrospective fills.
    record={'fingerprint':fingerprint,'timestamp':utc(),'kind':'forward_experimental_tennis','game_id':match['id'],'players':match['players'],'provider':provider,'state':state,'input_evidence':{k:v for k,v in ev.items() if k!='pointbypoint'},'projection':match['projection'],'contracts':match['contracts']}
    with forecast_path.open('a') as f:f.write(json.dumps(record,separators=(',',':'))+'\n')
    forecasts.append(record);seen.add(fingerprint)
  except Exception as e:match['prediction_status']='Awaiting synchronized input: '+str(e)
 provider['matched_live_games']=sum('live_evidence' in g for g in matches)
 provider['automatic_forecasts']=sum(g['simulations_completed']>0 for g in matches)
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
 result={'generated_at':utc(),'date':date.isoformat(),'matches':sorted(matches,key=lambda x:({'in':0,'pre':1,'post':2}.get(x['state'],3),x['date'])),'market_count':len(markets),'matched_count':sum(len(m['contracts']) for m in matches),'unmatched_contracts':unmatched,'errors':errors,'simulations_completed':sum(g['simulations_completed'] for g in matches),'paper_positions':0,'provider':provider,'forecast_count':len(forecasts),'grading':{'count':len(grades),'rows':grades},'limitations':['Automatic point-level forecasts use real service counts when supplied and labeled league priors otherwise','Source-origin delay is unavailable; captured time is the request time, not guaranteed court time','GitHub scheduled collection is best effort, nominally five minutes; model values are conditional snapshots, not verified live edges','Retirement/fair-price outcomes and injury changes are not modeled','No hypothetical fill or trading return is invented']}
 (out/'tennis.json').write_text(json.dumps(result,separators=(',',':')));print(json.dumps({k:result[k] for k in ['generated_at','market_count','matched_count','errors','simulations_completed','provider']}));return result
if __name__=='__main__':run()
