import unittest,datetime as dt
from tennis import parse_matches,market_matches
class TennisTests(unittest.TestCase):
 def fixture(self):
  return {'events':[{'name':'Test Open','groupings':[{'grouping':{'slug':'womens-singles'},'competitions':[{'id':'A','date':'2026-11-05T09:00Z','status':{'type':{'state':'in','detail':'2nd Set'}},'format':{'regulation':{'periods':3}},'competitors':[{'type':'athlete','athlete':{'displayName':'Player One'},'linescores':[{'value':6},{'value':1}]},{'type':'athlete','athlete':{'displayName':'Player Two'},'linescores':[{'value':4},{'value':2}]}]}]}]}]}
 def test_actual_game_counts_not_set_wins_or_tiebreak_points(self):
  g=parse_matches(self.fixture(),'wta',dt.date(2026,11,5),'now','fixture')[0];self.assertEqual(g['completed_games'],13);self.assertEqual(g['simulations_completed'],0);self.assertIn('Verified current server',g['missing'])
 def test_exact_players_tour_and_date_required(self):
  g=parse_matches(self.fixture(),'wta',dt.date(2026,11,5),'now','fixture')[0];m={'ticker':'KXWTAGTOTAL-26NOV05ONEtwo-20','event_ticker':'KXWTAGTOTAL-26NOV05ONEtwo','rules_primary':'Player One vs Player Two'};self.assertTrue(market_matches(g,m));m['ticker']='KXATPGTOTAL-26NOV05ONEtwo-20';self.assertFalse(market_matches(g,m));m['ticker']='KXWTAGTOTAL-26NOV05ONEtwo-20';m['event_ticker']='KXWTAGTOTAL-26NOV06ONEtwo';self.assertFalse(market_matches(g,m))
 def test_doubles_not_silently_treated_as_singles(self):
  d=self.fixture();d['events'][0]['groupings'][0]['grouping']['slug']='womens-doubles';self.assertEqual(parse_matches(d,'wta',dt.date(2026,11,5),'now','fixture'),[])
