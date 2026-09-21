# RealGasCostCalc

A physics-based road-trip gas cost calculator. Enter a route and your vehicle (1998+),
and get a per-segment fuel-cost breakdown using real road data, speed limits, EPA
ratings, and live gas prices — with a manual price override (e.g. Costco).

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens in your browser immediately. No build step.

## How it works

1. **Route** — OSRM (OpenStreetMap, free, no key) computes distance, duration, and
   per-step speeds; Overpass fetches posted speed limits along the route.
2. **Vehicle** — fueleconomy.gov API (free, no key) provides EPA city/highway MPG
   for any year/make/model 1998+.
3. **Fuel model** — per-segment effective MPG: speed-weighted interpolation between
   city and highway ratings, v² aerodynamic penalty above ~65 mph, elevation-grade
   correction, and idle/congestion blending toward city MPG.
4. **Gas price** — live EIA state-average prices, or your own price per gallon.

Built with Google Antigravity. See `GEMINI.md` for the full build prompt.
