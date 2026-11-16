"""Realistic simulated production for every line.

One record per line per hour (`timestamp` = start of the hour) plus the downtime events
behind it. What happens on a line:

- three shifts a day, each with a 60-minute meal break that is not planned production time;
- a changeover at the start of some shifts (15 to 40 minutes);
- breakdowns, material shortages, quality checks and operator absences, now and then long
  ones (over 30 minutes), more often on "struggling" lines;
- power outages from PLN that stop every line of a plant at once;
- short minor stops;
- running below rated speed (more so on the night shift) and scrap, with occasional scrap
  spikes when a process drifts.

Events are derived from a hash of (line, hour), so the same hour always gives the same
stops whichever order hours are generated in, and a long stop carries over into the next
hours.

    python -m app.simulator --hours 72      # fill the database with 3 days of production
"""
import argparse
import random
from datetime import datetime, timedelta, timezone

from . import db
from .config import LINES, PLANTS, SHIFTS, WIB

PROFILES = {
    #             stops per hour, speed vs rated, scrap rate
    "steady":     {"stop": 0.020, "speed": 0.95, "scrap": 0.006},
    "average":    {"stop": 0.045, "speed": 0.89, "scrap": 0.015},
    "struggling": {"stop": 0.100, "speed": 0.76, "scrap": 0.040},
}
STOP_REASONS = ["breakdown", "material", "quality_check", "operator"]
STOP_WEIGHTS = [55, 22, 13, 10]
LONG_STOP_SHARE = 0.3
CHANGEOVER_CHANCE = 0.35       # per shift start
MINOR_STOP_CHANCE = 0.25       # per hour
POWER_OUTAGE_CHANCE = 0.004    # per plant per hour
SCRAP_SPIKE_CHANCE = 0.03      # per line per hour
NIGHT_SPEED = 0.95             # shift 3 runs a little slower
LOOKBACK_HOURS = 4             # the longest stop (150 min from minute 50) ends within 4 hours

SHIFT_STARTS = {s["start"] for s in SHIFTS}
BREAK_HOURS = {s["break_hour"] for s in SHIFTS}


def local_hour(ts: datetime) -> int:
    return ts.astimezone(WIB).hour


def is_break(ts: datetime) -> bool:
    return local_hour(ts) in BREAK_HOURS


def _hour(ts: datetime) -> datetime:
    return ts.replace(minute=0, second=0, microsecond=0)


def events_starting(line: dict, hour: datetime) -> list[dict]:
    """Downtime events of `line` that begin in the hour starting at `hour`."""
    hour = _hour(hour)
    if is_break(hour):
        return []
    rng = random.Random(f"{line['id']}:{hour.isoformat()}")
    profile = PROFILES[line["profile"]]
    events = []

    def add(minute: int, minutes: int, reason: str) -> None:
        events.append({"line_id": line["id"], "start": hour + timedelta(minutes=minute),
                       "minutes": minutes, "reason": reason})

    if local_hour(hour) in SHIFT_STARTS and rng.random() < CHANGEOVER_CHANCE:
        add(0, rng.randint(15, 40), "changeover")
    if rng.random() < profile["stop"]:
        minutes = rng.randint(35, 150) if rng.random() < LONG_STOP_SHARE else rng.randint(8, 28)
        add(rng.randint(5, 50), minutes, rng.choices(STOP_REASONS, STOP_WEIGHTS)[0])
    if rng.random() < MINOR_STOP_CHANCE:
        add(rng.randint(0, 55), rng.randint(2, 5), "minor_stop")

    plant_rng = random.Random(f"{line['plant_id']}:{hour.isoformat()}:pln")
    if plant_rng.random() < POWER_OUTAGE_CHANCE:
        add(plant_rng.randint(0, 45), plant_rng.randint(20, 90), "power")
    return events


def downtime_minutes(line: dict, hour: datetime) -> int:
    """Minutes of the hour starting at `hour` during which the line was stopped."""
    hour = _hour(hour)
    stopped = [False] * 60
    for back in range(LOOKBACK_HOURS):
        for e in events_starting(line, hour - timedelta(hours=back)):
            begin = (e["start"] - hour).total_seconds() / 60
            for m in range(max(0, int(begin)), min(60, int(begin + e["minutes"]))):
                stopped[m] = True
    return sum(stopped)


def record(line: dict, ts: datetime, rng: random.Random) -> dict:
    """The production record of one line for the hour starting at `ts`."""
    ts = _hour(ts)
    row = {"line_id": line["id"], "timestamp": ts, "planned_minutes": 0, "run_minutes": 0,
           "total_count": 0, "good_count": 0}
    if is_break(ts):
        return row
    profile = PROFILES[line["profile"]]
    run = 60 - downtime_minutes(line, ts)
    night = local_hour(ts) >= 23 or local_hour(ts) < 7
    speed = min(1.0, profile["speed"] * (NIGHT_SPEED if night else 1.0) * rng.uniform(0.96, 1.04))
    total = int(run * 60 / line["ideal_cycle_s"] * speed)
    spike = random.Random(f"{line['id']}:{ts.isoformat()}:scrap").random() < SCRAP_SPIKE_CHANCE
    scrap = min(0.6, profile["scrap"] * (6 if spike else 1) * rng.lognormvariate(0, 0.3))
    row.update(planned_minutes=60, run_minutes=run, total_count=total,
               good_count=total - round(total * scrap))
    return row


def generate(start: datetime, end: datetime, seed: int | None = None) -> tuple[list[dict], list[dict]]:
    """Hourly production records and the downtime events that start in [start, end]."""
    rng = random.Random(seed)
    production, downtime = [], []
    ts = _hour(start)
    while ts <= end:
        for line in LINES:
            production.append(record(line, ts, rng))
            downtime.extend(events_starting(line, ts))
        ts += timedelta(hours=1)
    return production, downtime


def store(start: datetime, end: datetime, seed: int | None = None) -> int:
    production, downtime = generate(start, end, seed)
    db.init_db()
    db.insert_downtime(downtime)
    return db.insert_production(production)


def backfill(hours: int = 72, seed: int | None = 42) -> int:
    """Store the last `hours` complete hours of production."""
    last = _hour(datetime.now(timezone.utc)) - timedelta(hours=1)
    return store(last - timedelta(hours=hours - 1), last, seed)


def catch_up(seed: int | None = None) -> int:
    """Add every complete hour since the latest stored record (used by the running server)."""
    latest = db.latest_timestamp()
    if latest is None:
        return backfill()
    start = datetime.fromisoformat(latest) + timedelta(hours=1)
    last = _hour(datetime.now(timezone.utc)) - timedelta(hours=1)
    return store(start, last, seed) if start <= last else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill the database with simulated production.")
    parser.add_argument("--hours", type=int, default=72)
    args = parser.parse_args()
    n = backfill(args.hours)
    print(f"stored {n} production records ({len(PLANTS)} plants, {len(LINES)} lines) in {db.db_path()}")


if __name__ == "__main__":
    main()
