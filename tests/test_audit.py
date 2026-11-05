import unittest,copy
from audit import analyze
class AuditTests(unittest.TestCase):
 def record(self,key,time,forecast):
  return {'fingerprint':key,'timestamp':time,'game':{'id':'A','name':'A at B','league':'nba','status':'Halftime','scores':[10,10],'stats_captured_at':'2026-11-05T00:00:00+00:00','score_captured_at':'2026-11-05T00:00:00+00:00','stats':[{'fieldGoalsMade-fieldGoalsAttempted':'4-10','threePointFieldGoalsMade-threePointFieldGoalsAttempted':'0-2','freeThrowsMade-freeThrowsAttempted':'2-2'}]*2},'simulation':{'mean':forecast,'p10':30,'p90':50,'runs':10000}}
 def test_repeated_snapshots_are_not_independent_games(self):
  a=self.record('first','2026-11-05T00:00:30+00:00',45);b=self.record('second','2026-11-05T00:01:00+00:00',50);g=[{'fingerprint':k,'actual_total':40} for k in ['first','second']]
  r=analyze([b,a],g);self.assertEqual(r['all_snapshots']['mae'],7.5);self.assertEqual(r['first_per_game']['mae'],5);self.assertEqual(r['first_per_game']['forecasts'],1)
 def test_stale_and_inconsistent_inputs_remain_visible(self):
  a=self.record('bad','2026-11-05T00:03:00+00:00',45);a['game']['scores']=[12,10];before=copy.deepcopy(a);r=analyze([a],[{'fingerprint':'bad','actual_total':40}]);self.assertEqual(a,before);self.assertEqual(r['stale_box_snapshots'],1);self.assertEqual(r['inconsistent_snapshots'],1);self.assertEqual(r['verified_live_eligible'],0);self.assertEqual(r['first_per_game']['graded'],1)
 def test_ungraded_records_do_not_enter_error_metrics(self):
  r=analyze([self.record('new','2026-11-05T00:00:30+00:00',45)],[]);self.assertIsNone(r['all_snapshots']['mae']);self.assertEqual(r['all_snapshots']['graded'],0)
