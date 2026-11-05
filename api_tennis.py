"""API Tennis REST ingestion. Keys and request URLs never enter saved evidence."""
import json,os,re,urllib.parse,urllib.request
from tennis import normalized
ENDPOINT='https://api.api-tennis.com/tennis/'
def fetch():
 key=os.environ.get('API_TENNIS_KEY')
 if not key:return None,{'connected':False,'status':'API Tennis key not configured'}
 request=urllib.request.Request(ENDPOINT,data=urllib.parse.urlencode({'method':'get_livescore','APIkey':key,'timezone':'UTC'}).encode(),headers={'Accept':'application/json'})
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
  if any(not re.fullmatch(r'\d+',str(x)) for x in raw):raise ValueError('Non-integer set score needs explicit tiebreak parsing')
  pairs.append([int(raw[i]) for i in order])
 server={'First Player':0,'Second Player':1}.get(row.get('event_serve'))
 return {'provider':'API Tennis','event_key':row.get('event_key'),'captured_at':captured,'source_updated_at':None,'source_latency':'Unavailable; capture time is not source update time','server_index':order.index(server) if server is not None else None,'reported_point_score':row.get('event_game_result'),'set_scores':[[p[i] for p in pairs] for i in [0,1]],'statistics':row.get('statistics',[]),'pointbypoint':row.get('pointbypoint',[]),'status':row.get('event_status'),'players':[row.get('event_first_player'),row.get('event_second_player')]}
