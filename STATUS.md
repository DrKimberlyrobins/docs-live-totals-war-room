# Verification and deployment status

The application is implemented locally, not deployed to GitHub Pages.

- 17 automated tests pass: NBA/college clocks, OT periods, possession fallback, 10,000 samples, probability operators, market-price independence, complementary order-book execution/depth, fees, date-and-league matching, period-market separation, append-only persistence, deduplication, postgame grading without forecast rewriting, summary clock parsing, NBA vs college feed filtering, and versioned official settlement terms.
- Browser verified locally: real-data board renders; Live filter; Forecast archive displays saved UTC records; stale snapshot warning; no verified recommendation appears.
- Mobile CSS is implemented. A phone viewport has not been visually tested.
- No production URL has been verified. GitHub rejected the secure browser sign-in with “Incorrect username or password.” The available GitHub connector has no repository-creation or Pages-configuration tools, so account sign-in remains necessary to create this separate repository.
- API requests retrieve real data. Authorization/licensing and latency guarantees for ESPN's undocumented public website feeds remain unverified. Kalshi's official public read-only market API is connected.
- Forecasts use experimental league priors. Team-specific ratings, lineup verification, period-specific models and held-out calibration remain incomplete.
- Contract overtime treatment must be verified before computing probabilities and EV. The official API-linked PDF was reviewed and is hash-checked by subsequent collections. The first saved collection retained unknown treatment and is not rewritten.
- Scheduled refresh is a best-effort five-minute GitHub Actions workflow, not a continuously running live backend. Production scheduling has not been enabled or tested because deployment is blocked.

The source checkout contains the complete first implementation, source data snapshot, immutable forward experimental forecasts, and deploy workflows. Existing NBA and CBB war rooms were not accessed or modified.

Second real-data collection: 2026-11-05T04:12:45.598597Z. NBA schedule ingestion confirmed. 607 NBA and 537 college scoring contracts matched; 11 saved experimental forecasts, including five NBA. 113 full-game executable YES order-book quotes retrieved. Old snapshots and records remain unchanged when settlement verification is improved.
