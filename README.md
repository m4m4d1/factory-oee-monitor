# Factory Production Monitoring (OEE)

**Pemantauan Produksi Pabrik (OEE)** for Indonesian industrial estates.

Monitors production lines in Indonesian industrial estates: output, downtime, quality and Overall
Equipment Effectiveness (OEE) per line and shift, with a downtime Pareto and alerts when a line's
shift falls below 65% OEE or a line stops for more than 30 minutes.

> Week 4 of Nusantara Intel: one new open-source
> information system for Indonesia every week, built in public one step per day.

**Live demo:** https://m4m4d1.github.io/factory-oee-monitor/ (simulated data)

## Features

- **7 plants, 19 lines** in KIIC and Suryacipta (Karawang), Jababeka and MM2100 (Cikarang),
  Batamindo (Batam), JIIPE (Gresik) and Kawasan Industri Terpadu Batang. Estates are real;
  companies are fictional.
- **OEE** (availability × performance × quality) per hour, shift, line and plant, with three bands:
  world class (85% and up), acceptable (65-85%) and low (below 65%).
- **Downtime Pareto**: stop minutes per reason (breakdown, changeover, material shortage, quality
  check, PLN power outage, operator absence, minor stops), largest first, with cumulative share.
- **Alerts** when a line's shift falls below 65% OEE or a single stop lasts more than 30 minutes.
- **Bilingual dashboard** (English / Bahasa Indonesia): KPIs, line table, line detail with 72-hour
  OEE chart and recent stops, downtime Pareto, OEE by shift, plant map and alerts.
- **REST API** with interactive docs at `/docs`, including endpoints for a PLC, MES or line leader
  to report production and stops.
- **Simulator** that produces realistic shifts (meal breaks, changeovers, breakdowns, power outages
  that stop a whole plant, slower night shifts, scrap spikes) so the system runs out of the box.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000 for the dashboard and http://localhost:8000/docs for the API.
On first start the database is filled with 72 hours of simulated production, and every complete
hour after that is added while the server runs.

With Docker:

```bash
docker build -t factory-oee-monitor .
docker run -p 8000:8000 -v oee-data:/data factory-oee-monitor
```

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `OEE_DB` | `data/oee.db` | SQLite database file |
| `OEE_SIMULATE` | `1` | `0` turns the simulator off (use with real data) |
| `OEE_SIM_INTERVAL` | `60` | Seconds between checks for a new complete hour to simulate |
| `OEE_API_KEY` | not set | If set, `POST /api/production` and `POST /api/downtime` need the header `X-API-Key` |

Plants, lines (with their ideal cycle times), shifts and alert thresholds are in `app/config.py`.

## API

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/lines` | All lines: latest hour, current shift, last 24 h, OEE per shift, stopped now |
| GET | `/api/lines/{id}` | One line |
| GET | `/api/lines/{id}/history?hours=72` | Hourly records of one line with OEE |
| GET | `/api/lines/{id}/downtime?hours=24` | Stops of one line, newest first |
| GET | `/api/plants` | Plants with 24-hour OEE, lowest line and lines stopped |
| GET | `/api/summary` | OEE of all lines (24 h), lines per band, lines stopped, alert count |
| GET | `/api/shifts?hours=24&plant_id=` | OEE per shift |
| GET | `/api/downtime/pareto?hours=24&plant_id=` | Downtime minutes per reason, with cumulative share |
| GET | `/api/alerts?hours=24&type=` | Low-OEE shifts (`low_oee`) and long stops (`long_downtime`) |
| GET | `/api/meta` | Plants, lines, shifts, reasons, bands and thresholds |
| POST | `/api/production` | Store one period of output from a line; returns its OEE |
| POST | `/api/downtime` | Store a stop of a line; returns it with `long` set if over 30 minutes |

Report an hour of production and a stop:

```bash
curl -X POST http://localhost:8000/api/production \
  -H "Content-Type: application/json" \
  -d '{"line_id": "btm-smt-1", "planned_minutes": 60, "run_minutes": 52, "total_count": 131, "good_count": 129}'

curl -X POST http://localhost:8000/api/downtime \
  -H "Content-Type: application/json" \
  -d '{"line_id": "btm-smt-1", "minutes": 8, "reason": "material"}'
```

## How OEE is calculated

| Factor | Formula |
|--------|---------|
| Availability | run time / planned production time |
| Performance | ideal cycle time × total count / run time (at most 100%) |
| Quality | good count / total count |
| **OEE** | availability × performance × quality |

Planned production time excludes the 60-minute meal break of each 8-hour shift (420 minutes per
shift). Every stop inside planned time, including changeovers and minor stops, counts against
availability. Over several hours or lines the minutes and counts are summed first, so OEE always
equals fully productive time divided by planned production time.

| OEE | Band |
|-----|------|
| 85% and up | World class (*kelas dunia*) |
| 65% to 85% | Acceptable (*cukup*) |
| below 65% | Low (*rendah*); a line's shift here raises an alert |

OEE comes from Seiichi Nakajima's Total Productive Maintenance (TPM). The 85% and 65% levels are
common industry rules of thumb, not a standard or regulation: set targets per line and product.

## Tests

```bash
pytest -q
```

## Notes

The demo data is simulated: the industrial estates and their locations are real, the companies and
all production figures are not.

## Built this week

- [x] Mon: scaffold, plants, lines and data model
- [x] Tue: production simulator and storage
- [x] Wed: REST API, OEE calculation and alerts
- [x] Thu: dashboard
- [x] Fri: plant map and alerts panel
- [x] Sat: Docker, tests and documentation
- [x] Sun: live demo and v1.0 release

## License

MIT
