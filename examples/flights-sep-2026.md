# Historical illustrative case: picking flight dates with Jev (September 2026)

This is a historical example transcribed from an earlier run; it is not
independently verified, a benchmark, or proof of a live integration in this
repository. The route is anonymized. Prices are a snapshot from 2026-09-22 and
are not guaranteed fares. Treat every decision as a recommendation only; no
booking or other external side effect is authorized or demonstrated here.

## Run 1 — one-way on a transatlantic route, Oct–Dec 2026

- **Collected:** one-way, 1 adult, economy, USD, all 92 days 2026-10-01 → 2026-12-31.
- **Range:** $698–$895, median $851, mean $816.7.
- **Cheapest days ($698):** Oct 5, 9, 12, 16, 17, 19, 23, 24.

Jev questions (one parallel call over the price table):
- `choice` "Best month to fly?" → **October**, confidence **1.0**
- `choice` "Best single day?" → **October 5**, confidence **0.67**
- `noul` "Should we book an October fare now?" → yes, **0.82**

Policy read (illustrative only): month at 1.0 → act (focus October); day at 0.67 → surface as recommendation; book-now at 0.82 → recommendation to verify October fares, not authorization to start a booking flow.

**What the historical run reported:** instead of investigating 92 days × airlines × connections, the agent narrowed to ~8 October days first. This is not a measured savings claim for this repository.

## Run 2 — round trip on the same route, Jan–Aug 2027 (3–4 day trips)

- **Collected:** round trip, 1 adult, economy, USD; return 3 and 4 calendar days after departure. Google Flights only showed departures through 2027-08-17 (booking horizon ~330 days).
- **3-day trip:** min **$1030**, max $1931, median $1216, mean $1232.5.
- **4-day trip:** min **$1030**, max $1480, median $1200, mean $1189.2.

Jev verdict:
- Best month for the 3-day trip: **April 2027**, confidence **1.0**
- Best month for the 4-day trip: **April 2027**, confidence **1.0**
- `noul` "Take the $1030 April fare now?" → yes, **0.79** → surface (just under the 0.80 act bar, so shown to the user with the numbers)

Cheapest windows at $1030: Apr 1→4, Apr 17→20, May 29→Jun 1 (3-day); Apr 6→10, Apr 15→19, Apr 17→21, Apr 24→28, Apr 25→29, May 29→Jun 2 (4-day).

## Honest notes

- This is one local run with proxy metrics (fares fetched, options narrowed), not a benchmark.
- Jev didn't find the fares — the agent's browser did. Jev ranked and gated.
- The 0.79 book-now signal landed in the "surface, don't auto-act" band in the historical account; that is an illustration, not a live-policy result.
- Fares move; every number above was true on 2026-09-22 and needs re-verification before purchase.
