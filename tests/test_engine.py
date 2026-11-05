import unittest,tempfile,pathlib,json,copy
from engine import *
from collect import append
class EngineTests(unittest.TestCase):
 def game(self):
  return {'id':'test','league':'nba','period':2,'clock_seconds':0,'state':'in','scores':[55,52],'stats':[{'fieldGoalsMade-fieldGoalsAttempted':'20-44','freeThrowsMade-freeThrowsAttempted':'10-12','offensiveRebounds':'5','turnovers':'6'}]*2}
 def test_clocks(self):
  self.assertEqual(minutes('nba',2,0,'in'),(24,24));self.assertEqual(minutes('cbb',1,0,'in'),(20,20));self.assertEqual(minutes('nba',5,150,'in'),(50.5,2.5));self.assertEqual(minutes('cbb',3,300,'in'),(40,5));self.assertEqual(minutes('nba',4,720,'post')[1],0)
 def test_invalid_clock(self):
  with self.assertRaises(ValueError):minutes('cbb',1,1300,'in')
 def test_possession(self):
  self.assertAlmostEqual(possession(self.game()['stats'][0],'nba'),50.28);self.assertIsNone(possession({},'cbb'))
 def test_real_simulation(self):
  s=simulate(self.game());self.assertEqual(s['runs'],10000);self.assertEqual(len(s['samples']),10000);self.assertTrue(s['p10']<s['median']<s['p90']);self.assertGreater(s['remaining_points'],0);self.assertGreater(len(set(s['samples'])),50);self.assertEqual(s['samples'],simulate(self.game())['samples'])
 def test_no_market_input(self):
  g=self.game();a=simulate(g);g['kalshi_price']=.99;self.assertEqual(a['samples'],simulate(g)['samples'])
 def test_college(self):
  g=self.game();g.update(league='cbb',period=1);s=simulate(g);self.assertEqual(s['runs'],10000);self.assertGreater(s['mean'],107)
 def test_terminal(self):
  g=self.game();g['state']='post';self.assertIsNone(simulate(g));g['state']='in';g['period']=4;self.assertIsNone(simulate(g))
 def test_probabilities(self):
  self.assertEqual(probability([100,101,102,103],101),.5);self.assertEqual(probability([100,101,102,103],101,'greater_or_equal'),.75)
 def test_quote(self):
  b={'orderbook_fp':{'no_dollars':[['0.60','2'],['0.50','4']]}}
  q=quote(b,'yes',3);self.assertAlmostEqual(q['vwap'],1.3/3);self.assertEqual(q['quantity_at_best'],2);self.assertIsNone(quote(b,'yes',7));self.assertIsNone(quote(b,'no'))
 def test_fee(self):self.assertEqual(fee(.5),.02);self.assertEqual(fee(.5,100),1.75)
 def test_matching(self):
  g={'league':'nba','date':'2026-11-05T01:00Z','aliases':[['Indiana','Indiana Pacers'],['Memphis','Memphis Grizzlies']]};m={'ticker':'KXNBATOTAL-26NOV04INDMEM-201','event_ticker':'KXNBATOTAL-26NOV04INDMEM','rules_primary':'If over 200.5 total points are scored in the Indiana vs Memphis Pro Basketball game'}
  self.assertTrue(matches(g,m));m['event_ticker']='KXNBATOTAL-26NOV05INDMEM';self.assertFalse(matches(g,m));m['event_ticker']='KXNBATOTAL-26NOV04INDMEM';g['league']='cbb';self.assertFalse(matches(g,m))
 def test_scope_separation(self):
  self.assertEqual(contract_type('KXNBA1HTOTAL-XX'),'1h');self.assertEqual(contract_type('KXNCAAMBTEAMTOTAL-XX'),'team');self.assertEqual(contract_type('KXNBA3QTOTAL-XX'),'q3');self.assertEqual(contract_type('KXNBATOTAL-XX'),'full')
 def test_append_only(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'forecast.jsonl';append(p,{'a':1});original=p.read_bytes();append(p,{'a':2});self.assertTrue(p.read_bytes().startswith(original));self.assertEqual(len(p.read_text().splitlines()),2)
if __name__=='__main__':unittest.main()

class CollectionTests(unittest.TestCase):
 def test_forward_persistence_and_grading_without_rewrite(self):
  import collect,datetime as dt
  from unittest.mock import patch
  g={'id':'integration','league':'nba','name':'A at B','date':'2026-11-05T01:00Z','state':'in','period':2,'clock_seconds':0,'clock':'0:00','scores':[10,10],'stats':[{'fieldGoalsMade-fieldGoalsAttempted':'4-10','threePointFieldGoalsMade-threePointFieldGoalsAttempted':'0-2','freeThrowsMade-freeThrowsAttempted':'2-2'}]*2,'aliases':[['Alpha'],['Bravo']],'contracts':[],'missing':[],'source':'fixture://scoreboard','status':'Halftime'}
  with tempfile.TemporaryDirectory() as d:
   def board(l,date):return [copy.deepcopy(g)] if l=='nba' and date=='20261104' else []
   with patch.object(collect.urllib.request,'urlopen',side_effect=RuntimeError('fixture: terms unavailable')),patch.object(collect,'ROOT',pathlib.Path(d)),patch.object(collect,'scoreboard',side_effect=board),patch.object(collect,'summary',side_effect=lambda x:(x.update(score_captured_at=collect.utc(),stats_captured_at=collect.utc()) or x)),patch.object(collect,'get',return_value={'series':[]}):
    collect.run(dt.date(2026,11,4));p=pathlib.Path(d)/'data/forecasts.jsonl';first=p.read_bytes()
    collect.run(dt.date(2026,11,4));self.assertEqual(first,p.read_bytes())
    g.update(state='post',period=4,scores=[110,105]);collect.run(dt.date(2026,11,4));self.assertEqual(first,p.read_bytes())
    grades=[json.loads(x) for x in (pathlib.Path(d)/'data/grades.jsonl').read_text().splitlines()];self.assertEqual(len(grades),1);self.assertEqual(grades[0]['actual_total'],215)
    collect.run(dt.date(2026,11,4));self.assertEqual(len((pathlib.Path(d)/'data/grades.jsonl').read_text().splitlines()),1)

class FeedTests(unittest.TestCase):
 def test_summary_display_clock(self):
  from collect import clock_seconds
  self.assertEqual(clock_seconds({'displayClock':'5:30'}),330)
  self.assertEqual(clock_seconds({'displayClock':'0:00'}),0)
  with self.assertRaises(ValueError):clock_seconds({})
 def test_nba_filter_does_not_include_college_group(self):
  from unittest.mock import patch
  import collect
  with patch.object(collect,'get',return_value={'events':[]}) as mocked:
   collect.scoreboard('nba','20261104');self.assertNotIn('groups=',mocked.call_args.args[0])
   collect.scoreboard('cbb','20261104');self.assertIn('groups=50',mocked.call_args.args[0])

class SettlementTests(unittest.TestCase):
 def test_versioned_official_terms(self):
  self.assertEqual(overtime_rule('Full Game: Over 200.5','full',True),'included')
  self.assertEqual(overtime_rule('First half','1h',True),'excluded')
  self.assertEqual(overtime_rule('Full Game','full',False),'unverified')
  self.assertEqual(overtime_rule('Entire game excluding overtime','full',True),'excluded')
