# GEMINI.md — RealGasCostCalc build prompt

You are building **RealGasCostCalc**: a physics-based road-trip gas cost calculator.
The user runs it instantly in a browser with Streamlit — no build step, no deployment.

## One-line goal
Given origin, destination, a vehicle (1998 or newer), and a gas price (live or manual),
tell the user exactly how much a trip will cost in gas — modeled per route segment using
real road data, speed limits, and the vehicle's EPA ratings.

## Tech stack (do not change)
- **Streamlit** — the whole UI. User runs `streamlit run app.py` and it opens in their browser.
- **OSRM (OpenStreetMap routing)** — free, no API key: `https://router.project-osrm.org`
  for route distance, duration, per-step speeds, and route geometry.
- **Overpass API (OpenStreetMap)** — free, no API key: fetch `maxspeed` tags along the
  route so per-segment fuel modeling uses posted speed limits, not averages.
- **fueleconomy.gov API** — free, no key: vehicle lookup back to 1984 (we support 1998+),
  returns city/highway/combined MPG per exact year/make/model/trim.
- **EIA (U.S. Energy Information Administration) API** — free key from eia.gov; weekly
  retail gasoline prices by state. Primary live-price source.
- Manual gas-price override always available (e.g. enter the Costco price yourself —
  there is no reliable free API for station-level prices, so do not pretend otherwise).

## Features
1. **Trip input**: origin, destination (text addresses → geocode via OSRM/Nominatim),
   optional waypoints, round-trip toggle.
2. **Vehicle picker**: year (1998–current) → make → model → trim, pulled from fueleconomy.gov.
   Show its EPA city/highway MPG. Allow manual MPG override.
3. **Route analysis**: OSRM returns legs/steps with distance + duration → per-step average
   speed. Query Overpass for `maxspeed` on the route corridor; fall back to OSRM step
   speeds where tags are missing. Flag segments with no data instead of silently guessing.
4. **Physics model** (per segment, then summed):
   - Effective MPG = interpolation between city and highway MPG based on segment speed
     (economy peaks ~45–55 mph; city rating ≈ stop-and-go, highway rating ≈ 55–65 mph cruise).
   - Aerodynamic + rolling-resistance penalty above ~65 mph (drag grows with v² — model it).
   - Grade correction: sample elevation along route geometry (OpenTopoData, free);
     uphill costs extra, downhill gives partial credit, never below zero.
   - Idle/congestion penalty: when segment speed << speed limit, blend toward city MPG.
   - Output: gallons per segment, total gallons, total cost, cost per mile, and a
     per-segment table + map of the route colored by cost.
5. **Gas price**: live EIA state-average prices along the route (use each state's price
   for its segments, or the origin state's price as default), with a manual override box
   that takes precedence. Show both the live-price total and the manual-price total
   when they differ.
6. **Results page**: total cost (big), total gallons, miles, effective MPG for the trip,
   price source used, segment breakdown table, route map.

## Data-source honesty rules
- If a source is unreachable or returns no data, say so in the UI and fall back
  gracefully — never fabricate speed limits, prices, or MPG values.
- Cache fueleconomy.gov vehicle data and EIA prices locally (24h TTL) to avoid
  hammering free APIs.

## Suggested files
- `app.py` — Streamlit UI (inputs, results, map)
- `routing.py` — OSRM + Overpass helpers
- `vehicles.py` — fueleconomy.gov lookup + caching
- `prices.py` — EIA live prices + manual override
- `physics.py` — the per-segment fuel model (keep it pure functions, well-commented,
  unit-testable)
- `requirements.txt` — streamlit, requests, pandas, pydeck

## Acceptance criteria
- `pip install -r requirements.txt && streamlit run app.py` works on a fresh Mac
  with Python 3.11+.
- Entering two addresses and picking a vehicle yields a cost breakdown in under ~30s.
- Every number shown traces back to a stated source (OSRM, OSM maxspeed, EPA, EIA, or user input).

## How to run (for the user)
```bash
pip install -r requirements.txt
streamlit run app.py
```
