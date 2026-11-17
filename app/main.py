"""REST API (and, once the web/ folder exists, the dashboard).

    uvicorn app.main:app --reload      # then open http://localhost:8000 and /docs

Environment variables:
    OEE_DB             SQLite file (default data/oee.db)
    OEE_SIMULATE       1 (default) to keep adding simulated production for every complete hour
    OEE_SIM_INTERVAL   seconds between checks for a new complete hour (default 60)
    OEE_API_KEY        if set, POST /api/production and /api/downtime require the header X-API-Key
"""
import asyncio
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from . import __version__, db, oee, simulator
from .config import (DOWNTIME_ALERT_MINUTES, DOWNTIME_REASONS, LINE_IDS, LINES, OEE_ALERT, OEE_BANDS,
                     PLANNED_MINUTES_PER_SHIFT, PLANT_IDS, PLANTS, SHIFTS)
from .models import DowntimeIn, ProductionIn

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
PLANT_BY_ID = {p["id"]: p for p in PLANTS}


async def simulate_forever(interval: int) -> None:
    while True:
        await asyncio.sleep(interval)
        simulator.catch_up()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    task = None
    if os.environ.get("OEE_SIMULATE", "1") == "1":
        simulator.catch_up()  # 72 hours on first start, then whatever was missed
        task = asyncio.create_task(simulate_forever(int(os.environ.get("OEE_SIM_INTERVAL", "60"))))
    yield
    if task:
        task.cancel()


app = FastAPI(
    title="Factory Production Monitoring (OEE)",
    description="Production lines in Indonesian industrial estates: output, downtime, quality and OEE.",
    version=__version__,
    lifespan=lifespan,
)


def check_key(x_api_key: str | None) -> None:
    key = os.environ.get("OEE_API_KEY")
    if key and x_api_key != key:
        raise HTTPException(401, "invalid or missing X-API-Key")


def _by_line(rows: list[dict]) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for r in rows:
        out[r["line_id"]].append(r)
    return out


def line_view(line: dict, latest: dict | None, records: list[dict], events: list[dict]) -> dict:
    """A line with its latest hour, current shift, last 24 h and whether it is stopped now."""
    plant = PLANT_BY_ID[line["plant_id"]]
    stopped = None
    if latest:
        last_minute = datetime.fromisoformat(latest["timestamp"]) + timedelta(minutes=59)
        stopped = oee.stopped_at(events, last_minute)
    return {
        **line, "plant": plant["name"], "estate": plant["estate"], "city": plant["city"],
        "latest": oee.score(latest) if latest else None,
        "current_shift": oee.current_shift(records),
        "last_24h": oee.aggregate(records),
        "shifts_24h": oee.by_shift(records),
        "down": stopped,
    }


def all_lines() -> list[dict]:
    latest = db.latest_by_line()
    records = _by_line(db.production(hours=24))
    events = _by_line(db.downtime(hours=8))
    return [line_view(line, latest.get(line["id"]), records[line["id"]], events[line["id"]]) for line in LINES]


def _known_line(line_id: str) -> dict:
    if line_id not in LINE_IDS:
        raise HTTPException(404, f"unknown line '{line_id}'")
    return next(line for line in LINES if line["id"] == line_id)


def _plant_filter(rows: list[dict], plant_id: str | None) -> list[dict]:
    if plant_id is None:
        return rows
    if plant_id not in PLANT_IDS:
        raise HTTPException(404, f"unknown plant '{plant_id}'")
    return [r for r in rows if oee.LINE_BY_ID[r["line_id"]]["plant_id"] == plant_id]


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "records": db.count(), "downtime_events": db.count_downtime()}


@app.get("/api/meta")
def meta() -> dict:
    """Plants, lines, shifts, downtime reasons, bands and alert thresholds, for building a UI."""
    return {"plants": PLANTS, "lines": LINES, "shifts": SHIFTS,
            "planned_minutes_per_shift": PLANNED_MINUTES_PER_SHIFT,
            "downtime_reasons": DOWNTIME_REASONS, "oee_bands": OEE_BANDS,
            "alerts": {"oee_below": OEE_ALERT, "downtime_minutes_over": DOWNTIME_ALERT_MINUTES}}


@app.get("/api/lines")
def lines() -> list[dict]:
    return all_lines()


@app.get("/api/lines/{line_id}")
def line(line_id: str) -> dict:
    _known_line(line_id)
    return next(v for v in all_lines() if v["id"] == line_id)


@app.get("/api/lines/{line_id}/history")
def line_history(line_id: str, hours: int = Query(72, ge=1, le=24 * 30)) -> list[dict]:
    """Hourly records of one line with their OEE."""
    _known_line(line_id)
    return [oee.score(r) for r in db.production(line_id, hours)]


@app.get("/api/lines/{line_id}/downtime")
def line_downtime(line_id: str, hours: int = Query(24, ge=1, le=24 * 30)) -> list[dict]:
    """Stops of one line, newest first."""
    _known_line(line_id)
    return [oee.event_view(e) for e in reversed(db.downtime(line_id, hours))]


@app.get("/api/plants")
def plants() -> list[dict]:
    views = all_lines()
    records = db.production(hours=24)
    out = []
    for p in PLANTS:
        mine = [v for v in views if v["plant_id"] == p["id"]]
        worst = min((v for v in mine if v["last_24h"]["oee"] is not None),
                    key=lambda v: v["last_24h"]["oee"], default=None)
        out.append({**p, "lines": len(mine), "lines_down": sum(1 for v in mine if v["down"]),
                    "last_24h": oee.aggregate(_plant_filter(records, p["id"])),
                    "worst_line": {"line_id": worst["id"], "name": worst["name"],
                                   "oee": worst["last_24h"]["oee"]} if worst else None})
    return out


@app.get("/api/summary")
def summary() -> dict:
    """All plants over the last 24 hours."""
    views = all_lines()
    records = db.production(hours=24)
    counts = {b["key"]: 0 for b in OEE_BANDS}
    for v in views:
        if v["last_24h"]["band"]:
            counts[v["last_24h"]["band"]] += 1
    scored = [v for v in views if v["last_24h"]["oee"] is not None]
    worst = min(scored, key=lambda v: v["last_24h"]["oee"], default=None)
    return {
        "plants": len(PLANTS), "lines": len(LINES), "reporting": sum(1 for v in views if v["latest"]),
        "last_24h": oee.aggregate(records),
        "band_counts": counts,
        "lines_down": sum(1 for v in views if v["down"]),
        "worst": {"line_id": worst["id"], "oee": worst["last_24h"]["oee"]} if worst else None,
        "alerts_24h": len(oee.alerts(records, db.downtime(hours=24))),
        "latest": db.latest_timestamp(),
    }


@app.get("/api/shifts")
def shifts(hours: int = Query(24, ge=1, le=24 * 30), plant_id: str | None = None) -> list[dict]:
    """OEE per shift over all lines (or one plant)."""
    return oee.by_shift(_plant_filter(db.production(hours=hours), plant_id))


@app.get("/api/downtime/pareto")
def downtime_pareto(hours: int = Query(24, ge=1, le=24 * 30), plant_id: str | None = None) -> list[dict]:
    """Downtime minutes per reason, largest first, with cumulative share."""
    return oee.pareto(_plant_filter(db.downtime(hours=hours), plant_id))


@app.get("/api/alerts")
def alerts(hours: int = Query(24, ge=1, le=24 * 30),
           type: str | None = Query(None, pattern="^(low_oee|long_downtime)$")) -> list[dict]:
    hits = oee.alerts(db.production(hours=hours), db.downtime(hours=hours))
    return [a for a in hits if type is None or a["type"] == type][:200]


@app.post("/api/production", status_code=201)
def ingest_production(record: ProductionIn, x_api_key: str | None = Header(None)) -> dict:
    """Store a production record from a PLC, MES or line leader and return its OEE."""
    check_key(x_api_key)
    row = record.model_dump()
    row["timestamp"] = row["timestamp"] or datetime.now(timezone.utc)
    db.insert_production([row])
    return oee.score({**row, "timestamp": db.to_iso(row["timestamp"])})


@app.post("/api/downtime", status_code=201)
def ingest_downtime(event: DowntimeIn, x_api_key: str | None = Header(None)) -> dict:
    """Store a stop of a line. `long` is true when it breaks the downtime alert limit."""
    check_key(x_api_key)
    row = event.model_dump()
    row["start"] = row["start"] or datetime.now(timezone.utc)
    db.insert_downtime([row])
    return oee.event_view({**row, "start": db.to_iso(row["start"])})


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
