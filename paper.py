"""Prospective experimental paper ledger. No orders or trading credentials."""
import datetime as dt,hashlib,json,pathlib,statistics
from audit import read_rows,stat_points,age_seconds
from engine import minutes
POLICY={'id':'paper-v1','quantity':1,'max_positions_per_game':1,'minimum_probability':.55,'minimum_net_ev':.03,'max_game_capture_age_seconds':60,'max_quote_capture_age_seconds':30,'scope':'full','label':'Experimental forward paper test; not a verified betting recommendation'}
def input_errors(game,now):
 errors=[]
 if game.get('state')!='in':errors.append('Game is not active')
 for field in ['stats_captured_at','score_captured_at']:
  age=age_seconds(now,game.get(field))
  if age is None or not 0<=age<=POLICY['max_game_capture_age_seconds']:errors.append('Missing or stale '+field)
 stats=game.get('stats',[]);scores=game.get('scores',[])
 if len(stats)!=2 or len(scores)!=2:errors.append('Missing team statistics')
 else:
  for s,score in zip(stats,scores):
   p=stat_points(s)
   if p is None or abs(p-score)>.01:errors.append('Score and shooting statistics disagree')
 return errors

def choose(game,simulation,now,positions):
 if input_errors(game,now) or not simulation or simulation.get('runs')!=10000:return None
 try:
  _,remaining=minutes(game['league'],game['period'],game['clock_seconds'],game['state'])
  capture_age=max(age_seconds(now,game['stats_captured_at']),age_seconds(now,game['score_captured_at']))
  if remaining*60<=capture_age+10:return None
 except (KeyError,TypeError,ValueError):return None
 if any(p['game_id']==game['id'] for p in positions):return None
 candidates=[]
 for c in game.get('contracts',[]):
  age=age_seconds(now,c.get('orderbook_captured_at'));meta_age=age_seconds(now,c.get('captured_at'))
  if c.get('type')!='full' or c.get('strike_type')!='greater' or c.get('overtime')=='unverified' or c.get('status') not in ['active','open']:continue
  if age is None or meta_age is None or not 0<=age<=30 or not 0<=meta_age<=30:continue
  for side in ['yes','no']:
   q=c.get(side+'_execution',{});p=c.get('p_'+side)
   if p is None or p<POLICY['minimum_probability'] or q.get('fee') is None or q.get('net_ev') is None:continue
   if not 0<q.get('vwap',0)<1 or q.get('quantity_at_best',0)<1 or q['net_ev']<POLICY['minimum_net_ev']:continue
   candidates.append((q['net_ev'],c['ticker'],side,c,q,p))
 if not candidates:return None
 _,_,side,c,q,p=max(candidates,key=lambda x:(x[0],x[1],x[2]))
 position_id=hashlib.sha256((POLICY['id']+':'+game['id']).encode()).hexdigest()
 return {'position_id':position_id,'timestamp':now,'kind':'forward_experimental_paper','policy':dict(POLICY),'game_id':game['id'],'game_name':game['name'],'league':game['league'],'scores':game['scores'],'clock':game.get('clock'),'period':game.get('period'),'game_capture_timestamp':game['score_captured_at'],'stats_capture_timestamp':game['stats_captured_at'],'contract':c,'ticker':c['ticker'],'threshold':c['floor_strike'],'side':side,'selection':('OVER' if side=='yes' else 'AT OR BELOW')+' '+str(c['floor_strike']),'quantity':1,'entry_price':q['vwap'],'entry_fee':q['fee'],'entry_cost':q['vwap']+q['fee'],'model_probability':p,'expected_net_profit':q['net_ev'],'simulation':simulation,'model_version':simulation['model_version'],'inputs':game,'limitations':['Source-origin latency is unverified','League priors and strategy assumptions are uncalibrated','Quoted depth is observed, not an actual fill; no real order was placed']}

def settlement(position,market,now):
 if market.get('ticker')!=position['ticker'] or market.get('status')!='finalized' or market.get('result') not in ['yes','no']:return None
 # Reject a settlement timestamp predating the saved position.
 stamp=market.get('settlement_ts')
 if stamp and age_seconds(stamp,position['timestamp']) is not None and age_seconds(stamp,position['timestamp'])<0:return None
 win=market['result']==position['side'];payout=float(position['quantity']) if win else 0.
 return {'position_id':position['position_id'],'graded_at':now,'ticker':position['ticker'],'official_result':market['result'],'settlement_timestamp':stamp,'outcome':'WIN' if win else 'LOSS','payout':payout,'net_profit':round(payout-position['entry_cost'],6),'model_probability':position['model_probability'],'brier':round((position['model_probability']-int(win))**2,6),'expected_net_profit':position['expected_net_profit'],'settlement_source':'https://external-api.kalshi.com/trade-api/v2/markets/'+position['ticker']}

def report(positions,results):
 by_id={r['position_id']:r for r in results};closed=[p for p in positions if p['position_id'] in by_id];wins=sum(by_id[p['position_id']]['outcome']=='WIN' for p in closed);cost=sum(p['entry_cost'] for p in closed);profit=sum(by_id[p['position_id']]['net_profit'] for p in closed)
 return {'policy':POLICY,'positions':len(positions),'settled':len(closed),'pending':len(positions)-len(closed),'wins':wins,'losses':len(closed)-wins,'win_rate':wins/len(closed) if closed else None,'net_profit':round(profit,6) if closed else None,'settled_entry_cost':round(cost,6),'roi':profit/cost if cost else None,'expected_profit_settled':sum(p['expected_net_profit'] for p in closed) if closed else None,'brier':statistics.mean(by_id[p['position_id']]['brier'] for p in closed) if closed else None,'rows':[dict(p,grade=by_id.get(p['position_id'])) for p in positions]}

def save_report(directory):
 directory=pathlib.Path(directory);r=report(read_rows(directory/'paper_positions.jsonl'),read_rows(directory/'paper_results.jsonl'));(directory/'paper.json').write_text(json.dumps(r,separators=(',',':')));return r
