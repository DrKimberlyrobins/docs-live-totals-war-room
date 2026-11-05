import copy,datetime as dt,json,pathlib,tempfile,unittest
from unittest.mock import patch
from api_tennis import state_from_evidence,format_rules
from tennis_value import evaluate,quote_cost
import tennis

def row():
 return {'event_key':123,'event_date':'2026-11-05','event_time':'12:00','event_live':'1','event_type_type':'Wta Singles','event_status':'Set 2','event_first_player':'A. Alpha','event_second_player':'B. Beta','first_player_key':1,'second_player_key':2,'event_serve':'Second Player','event_game_result':'15 - 30','tournament_name':'Chennai Open','scores':[{'score_set':'1','score_first':'6','score_second':'4'},{'score_set':'2','score_first':'2','score_second':'3'}],'statistics':[{'player_key':i,'stat_period':'match','stat_name':'Service Points Won','stat_won':w,'stat_total':40} for i,w in [(1,26),(2,22)]]}
class AutomaticTennisTests(unittest.TestCase):
 def test_normalization_and_prior(self):
  from api_tennis import evidence
  m={'players':['Bea Beta','Amy Alpha'],'tour':'wta','tournament':'Chennai Open'}
  ev=evidence(row(),[1,0],'2026-11-05T12:00Z');s,r=state_from_evidence(ev,m)
  self.assertEqual(s['points'],[2,1]);self.assertEqual(s['server'],0);self.assertEqual(s['serveWon'],[22,26]);self.assertEqual(s['completedSets'],[[4,6]])
  ev['statistics']=[];s,r=state_from_evidence(ev,m);self.assertEqual(s['serveTotal'],[0,0]);self.assertTrue(any('prior used' in x for x in r['notes']))
 def test_transition_and_suspension(self):
  from api_tennis import evidence
  m={'players':['Amy Alpha','Bea Beta'],'tour':'wta','tournament':'Chennai Open'}
  ev=evidence(row(),[0,1],'now');ev['status']='Suspended'
  with self.assertRaises(ValueError):state_from_evidence(ev,m)
  ev['status']='Set 2';ev['set_scores']=[[6,6],[4,4]]
  with self.assertRaises(ValueError):state_from_evidence(ev,m)
 def test_rule_presets(self):
  self.assertEqual(format_rules({'tour':'atp','tournament':'US Open'})['bestOf'],5)
  self.assertEqual(format_rules({'tour':'wta','tournament':'US Open'})['finalTiebreakTarget'],10)
  with self.assertRaises(ValueError):format_rules({'tour':'atp','tournament':'Next Gen Finals'})
 def test_executable_depth_fees_and_no_invented_value(self):
  book={'orderbook_fp':{'no_dollars':[['0.60','0.5'],['0.55','2']],'yes_dollars':[['0.50','4']]}}
  q=quote_cost(book,'yes');self.assertAlmostEqual(q['vwap'],.425);self.assertAlmostEqual(q['slippage'],.025)
  c={'scope':'match_completed_games'};v=evaluate(c,.7,book,{'fee_type':'quadratic','fee_multiplier':1})
  self.assertAlmostEqual(v['sides'][0]['fee'],.02);self.assertAlmostEqual(v['sides'][0]['net_ev'],.255)
  self.assertEqual(v['model_price_preference'],'OVER');self.assertEqual(v['recommendation'],'NO VERIFIED EDGE')
  self.assertIsNone(evaluate(c,.7,book,{})['sides'][0]['net_ev']);self.assertEqual(evaluate(c,.7,{}, {})['sides'],[])
 def test_forward_archive_then_grading_no_rewrite(self):
  live=row();final=copy.deepcopy(live);final.update(event_live='0',event_status='Finished');final['scores'][1].update(score_first='6',score_second='4')
  def api(method='get_livescore',**kwargs):return ([live] if method=='get_livescore' else [live]),{'connected':True,'status':'fixture'}
  with tempfile.TemporaryDirectory() as tmp,patch.object(tennis,'ROOT',pathlib.Path(tmp)),patch.object(tennis,'get',return_value={}),patch.object(tennis,'paged',return_value=[]),patch('api_tennis.fetch',side_effect=api):
   # Invoke the actual Node engine using its repository path while writing evidence in a temp directory.
   from tennis_live import calculate
   engine_root=pathlib.Path(tennis.__file__).parent
   with patch('tennis_live.calculate',side_effect=lambda s,r:calculate(s,engine_root)):
    first=tennis.run(dt.date(2026,11,5));self.assertEqual(first['simulations_completed'],10000)
    archive=pathlib.Path(tmp)/'data/tennis_forecasts.jsonl';before=archive.read_bytes();self.assertEqual(first['forecast_count'],1)
    def ended(method='get_livescore',**kw):return ([] if method=='get_livescore' else [final]),{'connected':True,'status':'fixture'}
    with patch('api_tennis.fetch',side_effect=ended):second=tennis.run(dt.date(2026,11,5))
    self.assertEqual(second['grading']['count'],1);self.assertEqual(archive.read_bytes(),before);self.assertIsNone(second['grading']['rows'][0]['paper_profit'])
