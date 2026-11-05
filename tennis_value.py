"""Conditional normal-completion contract values, using executable depth and actual fees."""
import math
from decimal import Decimal,ROUND_CEILING
from collect import API,get,utc

def quotes(book,side):
 raw=book.get('orderbook_fp',{}).get(('no' if side=='yes' else 'yes')+'_dollars')
 if raw is None:return []
 result=[]
 for price,size in raw:
  p,q=1-float(price),float(size)
  if 0<p<1 and q>0:result.append((p,q))
 return sorted(result)
def quote_cost(book,side,quantity=1):
 levels=quotes(book,side);left=quantity;cost=0
 for price,size in levels:
  take=min(left,size);cost+=take*price;left-=take
  if left<=1e-9:break
 if left>1e-9 or not levels:return None
 return {'price':levels[0][0],'quantity_at_best':levels[0][1],'vwap':cost/quantity,'slippage':cost/quantity-levels[0][0]}
def fee(price,multiplier):
 # July 7, 2026 schedule: round fee + position cost up to one centicent ($0.0001).
 cost=Decimal(str(price)).quantize(Decimal('.0001'))
 raw=Decimal('.07')*cost*(1-cost)*Decimal(str(multiplier))
 return float(((cost+raw)*10000).to_integral_value(rounding=ROUND_CEILING)/10000-cost)
def evaluate(contract,p,book,series):
 out={'basis':'Conditional on normal match completion; retirement/fair-price outcomes not priced','captured_at':utc(),'sides':[],'recommendation':'NO VERIFIED EDGE'}
 multiplier=series.get('fee_multiplier');fee_type=series.get('fee_type')
 fee_known=fee_type in ['quadratic','quadratic_with_maker_fees'] and multiplier is not None and math.isfinite(float(multiplier)) and float(multiplier)>=0
 for side,prob in [('yes',p),('no',1-p)]:
  q=quote_cost(book,side)
  if q is None:continue
  f=fee(q['vwap'],multiplier) if fee_known else None
  out['sides'].append(dict(q,side=side,probability=prob,difference=prob-q['price'],fee=f,net_ev=None if f is None else prob-q['vwap']-f))
 priced=[s for s in out['sides'] if s['net_ev'] is not None]
 best=max(priced,key=lambda s:s['net_ev']) if priced else None
 out['best_side']=best
 out['model_price_preference']=('OVER' if best['side']=='yes' else 'UNDER') if best and best['net_ev']>0 and contract['scope']=='match_completed_games' else (best['side'].upper() if best and best['net_ev']>0 else 'NO POSITIVE MODEL VALUE')
 out['fee_status']='Series quadratic taker fee; July 2026 centicent cost rounding' if fee_known else 'Applicable fee not verified; net EV unavailable'
 out['depth_status']='One-contract executable depth received' if out['sides'] else 'No one-contract executable depth'
 return out
