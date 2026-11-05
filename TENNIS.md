# Tennis discovery board

The Tennis tab retrieves ATP/WTA singles schedules and set scores from ESPN website JSON, and open Kalshi KXATPGTOTAL / KXWTAGTOTAL full-match completed-games contracts. Tennis collection runs separately after basketball collection in the scheduled workflow. Matching requires both normalized player names, the tour, and the contract's scheduled day; ambiguous matches remain unassigned. Doubles are excluded. A tournament feed can include a whole draw, so competition-level dates are filtered to a three-day window.

Initial collection 2026-11-05T09:55:42.492899Z: 53 open total-games contracts, 45 matched. No invented prices, model probabilities, simulated runs or paper positions are displayed. Quoted market bid/ask fields are not verified executable depth.

This is not a completed tennis prediction engine. The inspected live responses lack current point scores and verified serve statistics. Some include generic possession/situation fields whose tennis meaning is unverified. The feed reports five regulation periods for some ATP Paris matches despite completed two-set matches, so that field is not accepted as verified format. Set-only state does not establish current server, point score, injury/retirement status, surface-adjusted serve probabilities or tiebreak format.

ESPN's undocumented website endpoints have no established redistribution license, latency SLA, or published rate contract here. Sportradar Tennis v3 Live Summaries/Timelines were investigated and provide richer state by coverage level, but no authenticated provider access has been supplied or connected. See https://developer.sportradar.com/tennis/docs/tennis-ig-live-match-retrieval and https://developer.sportradar.com/tennis/docs/tennis-ig-update-frequencies.

Kalshi's inspected total-games rules distinguish completed games from points and sets. Injury, retirement, walkover and postponement treatment is shown verbatim per contract. Some retirement outcomes resolve at fair price rather than a simple binary settlement. No tennis paper entries are made until a separate tennis scoring model, trustworthy inputs and applicable settlement handling are verified. Existing basketball forecasts/ledgers remain unchanged.

Esports is explained in the tab, but no esports model or live gameplay feed is connected. A total-maps series market is a different quantity from kills, rounds, points or duration. No claim is made that all esports titles score slowly.
