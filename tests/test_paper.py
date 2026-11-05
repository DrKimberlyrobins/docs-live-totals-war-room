import unittest,copy
from paper import choose,settlement,report,input_errors
class PaperTests(unittest.TestCase):
 def fixtures(self):
  now='2026-11-05T01:00:00+00:00';stat={'fieldGoalsMade-fieldGoalsAttempted':'4-10','threePointFieldGoalsMade-threePointFieldGoalsAttempted':'0-3','freeThrowsMade-freeThrowsAttempted':'2-2'}
  c={'ticker':'KXNBATOTAL-X','type':'full','strike_type':'greater','status':'active','overtime':'included','captured_at':now,'orderbook_captured_at':now,'floor_strike':200.5,'p_yes':.65,'p_no':.35,'yes_execution':{'vwap':.5,'fee':.02,'net_ev':.13,'quantity_at_best':4},'no_execution':{'vwap':.52,'fee':.02,'net_ev':-.19,'quantity_at_best':4}}
  g={'id':'A','name':'A at B','league':'nba','state':'in','scores':[10,10],'stats':[stat,copy.deepcopy(stat)],'stats_captured_at':now,'score_captured_at':now,'period':1,'clock':'4:00','clock_seconds':240,'contracts':[c]};sim={'runs':10000,'model_version':'experimental'};return now,g,sim
 def test_prospective_selection_and_deduplication(self):
  now,g,s=self.fixtures();p=choose(g,s,now,[]);self.assertEqual(p['side'],'yes');self.assertAlmostEqual(p['entry_cost'],.52);self.assertIsNone(choose(g,s,now,[p]));self.assertEqual(g['contracts'][0]['yes_execution']['vwap'],.5)
 def test_stale_inconsistent_suspended_and_scope_blocked(self):
  now,g,s=self.fixtures()
  for change in ['stale','mismatch','suspended','half','unknown','no_depth','no_fee','low_ev']:
   x=copy.deepcopy(g)
   if change=='stale':x['stats_captured_at']='2026-11-05T00:58:00+00:00'
   if change=='mismatch':x['scores'][0]=12
   c=x['contracts'][0]
   if change=='suspended':c['status']='suspended'
   if change=='half':c['type']='1h'
   if change=='unknown':c['overtime']='unverified'
   if change=='no_depth':c['yes_execution']['quantity_at_best']=0
   if change=='no_fee':c['yes_execution']['fee']=None
   if change=='low_ev':c['yes_execution']['net_ev']=.01
   self.assertIsNone(choose(x,s,now,[]),change)
 def test_win_loss_after_fees(self):
  now,g,s=self.fixtures();p=choose(g,s,now,[])
  yes=settlement(p,{'ticker':p['ticker'],'status':'finalized','result':'yes'},now);no=settlement(p,{'ticker':p['ticker'],'status':'finalized','result':'no'},now)
  self.assertEqual(yes['net_profit'],.48);self.assertEqual(no['net_profit'],-.52);self.assertEqual(yes['outcome'],'WIN');self.assertEqual(no['outcome'],'LOSS')
  r=report([p],[yes]);self.assertEqual(r['wins'],1);self.assertEqual(r['pending'],0);self.assertAlmostEqual(r['roi'],.48/.52)
 def test_final_or_retroactive_entry_and_unverified_settlement_rejected(self):
  now,g,s=self.fixtures();g['state']='post';self.assertIsNone(choose(g,s,now,[]));g['state']='in';p=choose(g,s,now,[])
  self.assertIsNone(settlement(p,{'ticker':p['ticker'],'status':'finalized','result':'scalar'},now));self.assertIsNone(settlement(p,{'ticker':p['ticker'],'status':'finalized','result':'yes','settlement_ts':'2026-11-05T00:59:00+00:00'},now))
