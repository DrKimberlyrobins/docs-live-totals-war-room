"""Optional official Sportradar Tennis v3 adapter. Credentials stay in server environment."""
import datetime as dt,json,os,re,subprocess,urllib.request,pathlib
from audit import age_seconds
from tennis import normalized
LEVELS={'atp_1000','atp_500','atp_250','wta_1000','wta_500','wta_250','wta_international','wta_premier','wta_master'}
def name(s):
 parts=s.split(',');return normalized(' '.join(reversed(parts)) if len(parts)==2 else s)
def convert(summary,match):
 event=summary.get('sport_event',{});context=event.get('sport_event_context',{});status=summary.get('sport_event_status',{})
 if status.get('status')!='live':raise ValueError('Provider match is not live')
 if context.get('competition',{}).get('type')!='singles':raise ValueError('Only singles supported')
 if event.get('coverage',{}).get('sport_event_properties',{}).get('scores')!='live':raise ValueError('Live coverage not established')
 if context.get('competition',{}).get('level') not in LEVELS:raise ValueError('Event scoring rules need a separate verified preset')
 best=context.get('mode',{}).get('best_of')
 if best!=3:raise ValueError('Automatic adapter currently supports standard best-of-three tour singles only; other formats use manual mode')
 players=event.get('competitors',[]);qualifiers=[];ids=[]
 for p in match['players']:
  found=[x for x in players if name(x.get('name',''))==name(p) and not x.get('virtual')]
  if len(found)!=1:raise ValueError('Ambiguous player identity')
  qualifiers.append(found[0]['qualifier']);ids.append(found[0]['id'])
 gs=status.get('game_state',{});server=qualifiers.index(gs['serving'])
 current=re.match(r'^(\d+)',status.get('match_status',''))
 if not current:raise ValueError('Current set number unavailable')
 current=int(current[1]);sets={x['number']:x for x in status.get('period_scores',[]) if x.get('type')=='set'}
 if current not in sets or any(i not in sets for i in range(1,current)):raise ValueError('Incomplete set scores')
 def pair(row):return [int(row[q+'_score']) for q in qualifiers]
 games=pair(sets[current]);tb=gs.get('tie_break') is True;raw=pair(gs)
 if tb:points=raw
 else:
  mapping={0:0,15:1,30:2,40:3}
  try:points=[mapping[x] for x in raw]
  except KeyError:raise ValueError('Unrecognized point score')
  if gs.get('advantage'):
   if raw!=[40,40] or gs['advantage'] not in qualifiers:raise ValueError('Invalid advantage state')
   points[qualifiers.index(gs['advantage'])]=4
 if tb!=(games==[6,6]):raise ValueError('Tiebreak flag and game score disagree')
 stats=summary.get('statistics',{}).get('totals',{}).get('competitors',[]);won=[];total=[]
 for pid in ids:
  rows=[x['statistics'] for x in stats if x.get('id')==pid and 'statistics' in x]
  if len(rows)!=1:raise ValueError('Player serving statistics unavailable')
  w=rows[0].get('service_points_won');l=rows[0].get('service_points_lost')
  if not isinstance(w,int) or not isinstance(l,int):raise ValueError('Serving point counts unavailable')
  won.append(w);total.append(w+l)
 return {'players':match['players'],'tour':match['tour'],'status':'live','bestOf':best,'finalTiebreakTarget':7,'completedSets':[pair(sets[i]) for i in range(1,current)],'games':games,'points':points,'server':server,'serveWon':won,'serveTotal':total}
def fetch_live(now):
 key=os.environ.get('SPORTRADAR_TENNIS_API_KEY')
 if not key:return None,{'connected':False,'status':'Provider key not configured; manual player picker available'}
 level=os.environ.get('SPORTRADAR_TENNIS_ACCESS_LEVEL','trial')
 if level not in ['trial','production']:raise ValueError('Invalid provider access level')
 url=f'https://api.sportradar.com/tennis/{level}/v3/en/schedules/live/summaries.json'
 req=urllib.request.Request(url,headers={'x-api-key':key,'Accept':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=15) as response:payload=json.load(response)
 except Exception as e:raise RuntimeError('Provider live request failed; check access, quota and coverage') from None
 age=age_seconds(now,payload.get('generated_at'))
 if age is None or not 0<=age<=60:raise ValueError('Provider response timestamp is missing or stale')
 return payload,{'connected':True,'status':'Official live summaries received; per-match coverage gates apply','source':url,'source_generated_at':payload['generated_at'],'captured_at':now}
def calculate(state,root):
 result=subprocess.run(['node',str(pathlib.Path(root)/'tennis-runner.mjs')],input=json.dumps(state),text=True,capture_output=True,timeout=20)
 if result.returncode:raise ValueError('Tennis engine rejected provider state: '+result.stderr.strip()[:200])
 return json.loads(result.stdout)
