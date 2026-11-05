# DOC'S LIVE TOTALS WAR ROOM

Separate read-only NBA and NCAA men's basketball totals research application.

## Current status

**Published:** https://drkimberlyrobins.github.io/docs-live-totals-war-room/ — verified in the browser on November 5, 2026. GitHub Pages deployment and the hosted collector succeeded; all 17 hosted tests passed. The first hosted run graded all 11 saved experimental forecasts (MAE 12.3 points across correlated snapshots; not held-out validation). Remaining model limitations below still apply.

Implemented: automatic three-day ESPN schedule board; live scores and clocks; box-score statistics; estimated possessions and pace; separate NBA / college game rules; actual 10,000-run independent simulations; official Kalshi series discovery, conservative date-and-team matching, market-type separation, exact rule display, order books, one-contract VWAP and fee calculation; immutable deduplicated forward experimental forecast records; separate final-score grading and contract settlement checks; responsive dashboard and archive; GitHub Actions collector and Pages deployment workflows.

**Not a validated betting model. No verified recommendations are emitted.** No real money orders or credentials are used. Unknown overtime settlement rules block contract probabilities and EV. A model distribution can still be inspected as experimental game analysis. The first collection did not yet include linked PDF-term verification and retained unknown overtime treatment; those immutable records remain unchanged. Subsequent collections verify the exact official PDF hash before using its overtime defaults.

Not implemented/verified: licensed low-latency score feed, guaranteed source freshness, exact play-by-play possession counts, verified team pregame efficiencies, injuries/lineups/rotation adjustments, current-period fouls and bonus, separate quarter/half distributions, dedicated final-five-minute validation, held-out calibration, continuous backend service, production deployment and phone-viewport QA . No paper positions have been opened, so no returns are claimed. Live contract matching is implemented; team and period markets are shown but never substituted for full-game markets.

## Run locally

Python 3.11+; no third-party packages or keys required.

```sh
python -m unittest discover -s tests -v
python collect.py --date 2026-11-04
python -m http.server 8000
```

Serve the repository and open index.html. The UI checks the saved snapshot every 30 seconds; this does not cause new source ingestion. Snapshot age >90 seconds is marked stale. Source-origin latency remains unknown at every age and blocks all recommendations.

## GitHub deployment (already completed)

Create a new repository named `docs-live-totals-war-room` under `DrKimberlyrobins` and push this checkout's main branch. In repository Settings → Pages select **GitHub Actions** as the source. Run **Deploy GitHub Pages**, then **Collect live basketball evidence**. The expected Pages address is not considered verified until deployment succeeds.

Collector runs on GitHub's best-effort five-minute schedule. This is snapshot collection, not a guaranteed low-latency live backend. The browser retrieves the latest committed data from the repository's main branch so data commits do not require another Pages deployment. Collector commits preserve JSONL evidence. Archive records are experimental forward forecasts, not backtests. Settlement/grade updates are appended separately; forecasts are never rewritten by the collector. Protect the main branch and retain repository history for durable auditing.

## Data and rights

- ESPN website scoreboard/summary JSON: actual public endpoints successfully retrieved. No published API contract, redistribution license, rate guarantee, or latency SLA has been established. Public accessibility does not establish authorization for commercial redistribution. Treat as a personal research prototype pending provider approval.
- Kalshi public API: https://external-api.kalshi.com/trade-api/v2. Official unauthenticated endpoints are documented at https://docs.kalshi.com/getting_started/quick_start_market_data and https://docs.kalshi.com/getting_started/orderbook_responses. Bounded concurrency, retries and incomplete-pagination detection are implemented. Public unauthenticated rate limits are not assumed from authenticated tiers. Rate-limit errors appear on the board.
- Kalshi fees: current series fee metadata is required. Quadratic fees are ceil-to-cent(.07 × C × P × (1-P) × multiplier). Standard fee schedule: https://kalshi.com/fee-schedule. VWAP includes crossing the spread and book-depth slippage for one contract; no adequate depth means no executable price. Displayed quotes are observations, never guaranteed fills.
- Sportradar investigated, not connected: official NBA provider with authenticated NBA v8 API; NCAA men's API has coverage tiers and requires commercial account/access. https://developer.sportradar.com/basketball/reference/nba-overview and https://developer.sportradar.com/basketball/reference/ncaamb-overview. No provider key or license supplied.

## Model assumptions

See engine.py and the dashboard for full explicit priors. Market prices never enter the simulation. Stable input-derived seeds avoid turning unchanged input into a new forecast. Simulated scores are nonnegative integer remaining points plus actual points; repeated five-minute OT is conditional on a simulated tie (20-period numerical guard). Uncalibrated uncertainty parameters are heuristic and not a reliability claim.

Official BASKETBALLTOTALS contract terms were reviewed at https://assets.kalshi.com/contract_terms/BASKETBALLTOTALS.pdf (SHA-256 c48fb1f6bd54fa6a2298e9f6c75b4c0ce31009ad609719ef119e179429652217). A changed or unavailable document blocks its default rules. Full-game defaults include overtime; quarter/half defaults exclude it. Explicit market wording overrides defaults.

Order-book depth retrieval is bounded to eight nearest full-game thresholds per active game. Other matched contracts retain quote metadata but unavailable depth/EV is labeled explicitly.

A regulation-only rule is priced against regulation samples; an explicitly overtime-inclusive rule against total samples. Unknown semantics are blocked. YES/NO complementary probabilities are not labeled over/under unless settlement rules match. Other operators and scopes remain unsupported.

## First live collection

Completed at 2026-11-05T04:02:54.928551Z (November 4, 10:02:54 PM Central). 120 schedule events in the three-day window, 1,589 open scoring contracts retrieved, 552 matched college scoring contracts, zero open NBA matches in that collection. Three active college forecasts completed 10,000 runs each. All are experimental and no paper positions were taken. See data/forecasts.jsonl for exact timestamps, input states, assumptions and source capture times.

## Corrected second collection

Completed 2026-11-05T04:12:45.598597Z (November 4, 10:12:45 PM Central): 136 events across the three-day window, including 16 NBA events and 120 college events. Retrieved 1,419 open scoring contracts and conservatively matched 607 NBA plus 537 college contracts. Retrieved executable YES book quotes for 113 matched active full-game contracts. Archive now contains 11 experimental forward forecasts, including five NBA forecasts, with 10,000 runs each. This collection predates the linked-PDF semantic verifier, so those contracts still show unknown overtime treatment. No verified edge or paper position was issued. Source capture times may precede collection completion by several minutes; do not treat this snapshot as an executable live recommendation.

Browser checks confirmed real scores, projected totals, stale warnings, Live filtering, the NBA selector, and immutable UTC forecast rows in the archive. Phone viewport QA remains pending.
