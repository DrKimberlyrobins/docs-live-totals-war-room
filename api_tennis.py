"""API Tennis REST ingestion. Keys and request URLs never enter saved evidence."""
import json,os,re,urllib.parse,urllib.request
from tennis import normalized
ENDPOINT='https://api.api-tennis.com/tennis/'
def fetch(method="get_livescore",**params):
 key=os.environ.get('API_TENNIS_KEY')
 if not key:return None,{'connected':False,'status':'API Tennis key not configured'}
 request=urllib.request.Request(ENDPOINT,data=urllib.parse.urlencode({'method':method,'APIkey':key,'timezone':'UTC',**params}).encode(),headers={'Accept':'application/json'})
 try:
  with urllib.request.urlopen(request,timeout=25) as response:payload=json.load(response)
 except Exception:raise RuntimeError('API Tennis request failed; check account access and quota') from None
 if payload.get('success')!=1:raise ValueError('API Tennis rejected request; check subscription and key')
 rows=payload.get('result',[])
 if not isinstance(rows,list):raise ValueError('API Tennis returned an unexpected result shape')
 return rows,{'connected':True,'source':ENDPOINT,'live_events_received':len(rows),'status':f'API Tennis connected: {len(rows)} live events received; source-origin latency unverified'}
def player_matches(full,short):
 if normalized(full)==normalized(short):return True
 a=full.replace('-',' ').split();b=short.replace('-',' ').split()
 return len(a)>1 and len(b)>1 and normalized(a[-1])==normalized(b[-1]) and normalized(a[0])[0]==normalized(b[0])[0]
def find(rows,match):
 candidates=[]
 for row in rows:
  if row.get('event_live')!='1' or row.get('event_type_type','').lower()!=match['tour']+' singles':continue
  if row.get('event_date')!=match['date'][:10]:continue
  names=[row.get('event_first_player',''),row.get('event_second_player','')]
  for order in [(0,1),(1,0)]:
   if all(player_matches(match['players'][i],names[order[i]]) for i in [0,1]):candidates.append((row,order));break
 if len(candidates)!=1:raise ValueError('No unique API Tennis player/date match')
 return candidates[0]
def evidence(row,order,captured):
 scores=sorted(row.get('scores',[]),key=lambda s:int(s['score_set']))
 pairs=[]
 for score in scores:
  raw=[score['score_first'],score['score_second']]
  if any(not re.fullmatch(r'\d+(?:\.\d+|\s*\(\d+\))?',str(x)) for x in raw):raise ValueError('Set score notation unavailable')
  # Decimal/parenthetical suffix is a tiebreak-point annotation, never fractional games.
  pairs.append([int(re.match(r'\d+',str(raw[i]))[0]) for i in order])
 server={'First Player':0,'Second Player':1}.get(row.get('event_serve'))
 return {'provider':'API Tennis','event_key':row.get('event_key'),'captured_at':captured,'source_updated_at':None,'source_latency':'Unavailable; capture time is not source update time','server_index':order.index(server) if server is not None else None,'reported_point_score':row.get('event_game_result'),'set_scores':[[p[i] for p in pairs] for i in [0,1]],'raw_set_scores':scores,'statistics':row.get('statistics',[]),'pointbypoint':row.get('pointbypoint',[]),'status':row.get('event_status'),'players':[row.get('event_first_player'),row.get('event_second_player')],'player_keys':[row.get('first_player_key'),row.get('second_player_key')],'order':list(order),'tournament':row.get('tournament_name'),'event_type':row.get('event_type_type')}

RULE_SOURCES={'atp':'https://www.atptour.com/en/corporate/rulebook','wta':'https://www.wtatennis.com/wta-rules','slam':'https://www.wtatennis.com/news/3043764/tennis-explained-learn-the-game'}
def format_rules(match):
 title=normalized(match.get('tournament',''))
 if any(x in title for x in ['nextgen','exhibition','doubles','utr']):raise ValueError('Special event requires its own scoring model')
 slam=any(x in title for x in ['australianopen','rolandgarros','frenchopen','wimbledon','usopen'])
 qualifying='qual' in str(match.get('round','')).lower()
 if slam and qualifying:raise ValueError('Grand Slam qualifying format needs event-specific rules')
 return {'bestOf':5 if slam and match['tour']=='atp' else 3,'finalTiebreakTarget':10 if slam else 7,'rule_source':RULE_SOURCES['slam' if slam else match['tour']],'format_basis':'Grand Slam singles preset' if slam else 'ATP/WTA tour singles: best of three standard advantage tiebreak sets'}
def finished(pair):
 a,b=pair;return (max(a,b)==6 and min(a,b)<=4) or (max(a,b)==7 and min(a,b) in [5,6])
def state_from_evidence(ev,match):
 rules=format_rules(match);order=ev.get('order',[0,1]);notes=[]
 sets=list(map(list,zip(*ev['set_scores'])))
 if not sets:raise ValueError('Provider has not supplied set scores yet')
 status=re.fullmatch(r'Set (\d+)',str(ev.get('status','')),re.I)
 if not status:raise ValueError('Match is between sets, suspended, or no longer active')
 current=int(status[1]);completed=sets[:current-1]
 if len(completed)!=current-1 or not all(finished(x) for x in completed):raise ValueError('Set transition has not synchronized yet')
 games=sets[current-1] if len(sets)>=current else [0,0]
 if finished(games):raise ValueError('Completed set is awaiting next-set update')
 if len(sets)>current:raise ValueError('Set number and scoreboard disagree')
 raw=str(ev.get('reported_point_score','')).split(' - ')
 if len(raw)!=2:raise ValueError('Current point score unavailable')
 raw=[raw[i].strip().upper() for i in order]
 tb=games==[6,6]
 if tb:
  if not all(x.isdigit() for x in raw):raise ValueError('Tiebreak point counts unavailable')
  points=list(map(int,raw))
 else:
  mapping={'0':0,'15':1,'30':2,'40':3,'A':4,'AD':4,'ADV':4}
  if any(x not in mapping for x in raw):raise ValueError('Point notation unsupported')
  points=[mapping[x] for x in raw]
 server=ev.get('server_index')
 if server not in [0,1]:raise ValueError('Current server unavailable')
 won=[];totals=[]
 for i in order:
  pid=str(ev['player_keys'][i]);rows=[x for x in ev.get('statistics',[]) if str(x.get('player_key'))==pid and x.get('stat_period')=='match']
  direct=[x for x in rows if x.get('stat_name','').lower()=='service points won']
  if len(direct)==1:parts=direct
  else:parts=[x for x in rows if x.get('stat_name','').lower() in ['1st serve points won','2nd serve points won']]
  if not parts or (not direct and len(parts)!=2) or any(not isinstance(x.get('stat_won'),int) or not isinstance(x.get('stat_total'),int) for x in parts):
   won.append(0);totals.append(0);notes.append(match['players'][len(won)-1]+': serving counts unavailable; league prior used')
  else:won.append(sum(x['stat_won'] for x in parts));totals.append(sum(x['stat_total'] for x in parts))
 notes+=['Source-origin latency is unavailable; forecast is conditional on the captured score','Serving statistics may update behind the point score','Injury, retirement and historical surface form are not modeled']
 return {'players':match['players'],'tour':match['tour'],'status':'live','bestOf':rules['bestOf'],'finalTiebreakTarget':rules['finalTiebreakTarget'],'completedSets':completed,'games':games,'points':points,'server':server,'serveWon':won,'serveTotal':totals},dict(rules,notes=notes)
