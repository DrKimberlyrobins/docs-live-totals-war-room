"""Review immutable forecasts; never change original forecasts or grade records."""
import json,statistics,datetime as dt,pathlib

def read_rows(path):
 return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
def stat_points(s):
 try:
  return 2*float(s['fieldGoalsMade-fieldGoalsAttempted'].split('-')[0])+float(s['threePointFieldGoalsMade-threePointFieldGoalsAttempted'].split('-')[0])+float(s['freeThrowsMade-freeThrowsAttempted'].split('-')[0])
 except (KeyError,ValueError,TypeError,IndexError):return None
def age_seconds(timestamp,capture):
 try:return round((dt.datetime.fromisoformat(timestamp)-dt.datetime.fromisoformat(capture)).total_seconds(),2)
 except (ValueError,TypeError):return None

def analyze(forecasts,grades):
 grades_by_id={g['fingerprint']:g for g in grades};rows=[]
 for f in sorted(forecasts,key=lambda x:x['timestamp']):
  g=f['game'];sim=f['simulation'];grade=grades_by_id.get(f['fingerprint']);age=age_seconds(f['timestamp'],g.get('stats_captured_at'));score_age=age_seconds(f['timestamp'],g.get('score_captured_at'))
  points=[stat_points(s) for s in g.get('stats',[])];mismatch=len(points)==2 and any(p is not None and abs(p-score)>.01 for p,score in zip(points,g['scores']))
  flags=[]
  if age is None:flags.append('Box-score capture time unavailable')
  elif age>90:flags.append('Box score older than 90 seconds at save time')
  if score_age is None:flags.append('Score capture time unavailable')
  elif score_age>90:flags.append('Score capture older than 90 seconds at save time')
  if mismatch:flags.append('Score disagrees with points reconstructed from shooting statistics')
  flags.append('Source-origin latency unverified')
  actual=grade.get('actual_total') if grade else None
  rows.append({'fingerprint':f['fingerprint'],'game_id':g['id'],'name':g['name'],'league':g['league'],'timestamp':f['timestamp'],'status':g['status'],'scores':g['scores'],'forecast':sim['mean'],'p10':sim['p10'],'p90':sim['p90'],'runs':sim['runs'],'actual':actual,'error':round(sim['mean']-actual,2) if actual is not None else None,'interval_covered':sim['p10']<=actual<=sim['p90'] if actual is not None else None,'box_capture_age_seconds':age,'score_capture_age_seconds':score_age,'shooting_points':points,'score_stat_mismatch':mismatch,'quality_flags':flags,'verified_live_eligible':False})
 def metrics(rs):
  graded=[r for r in rs if r['actual'] is not None]
  return {'forecasts':len(rs),'graded':len(graded),'mae':round(statistics.mean(abs(r['error']) for r in graded),2) if graded else None,'bias':round(statistics.mean(r['error'] for r in graded),2) if graded else None,'interval_hits':sum(r['interval_covered'] for r in graded),'interval_count':len(graded)}
 first={}
 for r in rows:first.setdefault(r['game_id'],r)
 first_rows=list(first.values())
 return {'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'policy':'First saved forecast per game. All experimental records remain included in descriptive metrics; stale or inconsistent snapshots are flagged, not erased. No live betting performance is established.','all_snapshots':metrics(rows),'first_per_game':metrics(first_rows),'league_first':{l:metrics([r for r in first_rows if r['league']==l]) for l in ['nba','cbb']},'stale_box_snapshots':sum((r['box_capture_age_seconds'] or 0)>90 for r in rows),'inconsistent_snapshots':sum(r['score_stat_mismatch'] for r in rows),'verified_live_eligible':0,'first_forecasts':first_rows,'rows':rows}

def write_review(directory):
 directory=pathlib.Path(directory);result=analyze(read_rows(directory/'forecasts.jsonl'),read_rows(directory/'grades.jsonl'));(directory/'review.json').write_text(json.dumps(result,separators=(',',':')));return result
if __name__=='__main__':write_review(pathlib.Path(__file__).parent/'data')
