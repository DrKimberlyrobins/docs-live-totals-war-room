import unittest
from unittest.mock import patch
import api_tennis
class ApiTennisTests(unittest.TestCase):
 def test_unique_identity_and_order(self):
  row={'event_live':'1','event_type_type':'ATP Singles','event_date':'2026-11-05','event_first_player':'J. Sinner','event_second_player':'C. Alcaraz','event_serve':'First Player','scores':[{'score_set':'1','score_first':'3','score_second':'2'}]}
  match={'tour':'atp','date':'2026-11-05T12:00:00Z','players':['Carlos Alcaraz','Jannik Sinner']}
  r,order=api_tennis.find([row],match);ev=api_tennis.evidence(r,order,'now')
  self.assertEqual(ev['server_index'],1);self.assertEqual(ev['set_scores'],[[2],[3]]);self.assertIsNone(ev['source_updated_at'])
  with self.assertRaises(ValueError):api_tennis.find([row,row],match)
 def test_missing_key(self):
  with patch.dict('os.environ',{},clear=True):self.assertFalse(api_tennis.fetch()[1]['connected'])
 def test_errors_do_not_expose_key(self):
  with patch.dict('os.environ',{'API_TENNIS_KEY':'private-test-key'}),patch('urllib.request.urlopen',side_effect=Exception('private-test-key')):
   with self.assertRaises(RuntimeError) as ctx:api_tennis.fetch()
   self.assertNotIn('private-test-key',str(ctx.exception))
