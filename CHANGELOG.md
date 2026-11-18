# Changelog

## Unreleased

- Bilingual (EN/ID) dashboard: KPIs, line table, line detail with 72-hour OEE chart and stops,
  downtime Pareto and OEE by shift.
- REST API: lines, plants, history, shifts, downtime Pareto, alerts, and ingest endpoints for
  production and downtime (`/docs` for details).
- OEE (availability × performance × quality) per hour, shift, line and plant, with bands and alerts
  (OEE below 65%, stops over 30 minutes).
- Production simulator with shifts, meal breaks, changeovers, breakdowns, PLN outages and scrap
  spikes, and SQLite storage (`python -m app.simulator --hours 72`).
- Project scaffold, 7 fictional plants in real industrial estates, 19 production lines, three shifts
  and the production and downtime data model.
