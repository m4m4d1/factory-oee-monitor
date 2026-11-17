"""Overall Equipment Effectiveness (OEE), downtime Pareto and alerts.

OEE (Nakajima, Total Productive Maintenance) splits the planned production time into
three losses:

    Availability = run time / planned production time            (stops)
    Performance  = ideal cycle time x total count / run time      (slow running, capped at 100%)
    Quality      = good count / total count                       (scrap and rework)
    OEE          = Availability x Performance x Quality

Over several records (or lines) the sums are combined first, so OEE always equals
"fully productive time / planned production time". 85% is the commonly cited world-class
level and 65% a common floor; both are industry conventions, not a regulation.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from .config import (DOWNTIME_ALERT_MINUTES, DOWNTIME_REASONS, LINES, MIN_ALERT_PLANNED_MINUTES,
                     OEE_ALERT, OEE_BANDS, SHIFTS, WIB)

LINE_BY_ID = {line["id"]: line for line in LINES}
SHIFT_BY_KEY = {s["key"]: s for s in SHIFTS}


def _dt(ts) -> datetime:
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat(timespec="seconds")


def shift_of(ts) -> tuple[str, str]:
    """(shift key, shift date) of a moment. The night shift belongs to the day it started."""
    local = _dt(ts).astimezone(WIB)
    if 7 <= local.hour < 15:
        return "1", local.date().isoformat()
    if 15 <= local.hour < 23:
        return "2", local.date().isoformat()
    day = local.date() if local.hour >= 23 else local.date() - timedelta(days=1)
    return "3", day.isoformat()


def shift_start(key: str, shift_date: str) -> str:
    """UTC start of a shift, as ISO text."""
    local = datetime.combine(date.fromisoformat(shift_date), datetime.min.time(), WIB)
    return _iso(local + timedelta(hours=SHIFT_BY_KEY[key]["start"]))


def ratios(planned: float, run: float, total: int, good: int, ideal_minutes: float) -> dict:
    """Availability, performance, quality and OEE as fractions (None when undefined).

    `ideal_minutes` is the time the output would have taken at rated speed:
    sum of ideal cycle time x total count, in minutes.
    """
    if not planned:
        return {"availability": None, "performance": None, "quality": None, "oee": None}
    a = run / planned
    p = min(1.0, ideal_minutes / run) if run else 0.0
    q = good / total if total else None
    oee = a * p * (q if q is not None else 1.0)
    return {"availability": round(a, 4), "performance": round(p, 4),
            "quality": None if q is None else round(q, 4), "oee": round(oee, 4)}


def band(oee: float | None) -> dict | None:
    if oee is None:
        return None
    return next(b for b in OEE_BANDS if oee >= b["min"])


def _with_band(values: dict) -> dict:
    b = band(values["oee"])
    return {**values, "band": b["key"] if b else None,
            "band_label": {"en": b["en"], "id": b["id"]} if b else None}


def ideal_minutes(record: dict) -> float:
    return LINE_BY_ID[record["line_id"]]["ideal_cycle_s"] * record["total_count"] / 60


def aggregate(records: list[dict]) -> dict:
    """OEE over any set of records (one line or many, one hour or many)."""
    planned = sum(r["planned_minutes"] for r in records)
    run = sum(r["run_minutes"] for r in records)
    total = sum(r["total_count"] for r in records)
    good = sum(r["good_count"] for r in records)
    values = ratios(planned, run, total, good, sum(ideal_minutes(r) for r in records))
    return {"planned_minutes": planned, "run_minutes": run, "downtime_minutes": planned - run,
            "total_count": total, "good_count": good, "reject_count": total - good,
            **_with_band(values)}


def score(record: dict) -> dict:
    """A production record with its OEE, band and shift attached."""
    values = ratios(record["planned_minutes"], record["run_minutes"], record["total_count"],
                    record["good_count"], ideal_minutes(record))
    key, shift_date = shift_of(record["timestamp"])
    return {**record, **_with_band(values), "shift": key, "shift_date": shift_date}


def by_shift(records: list[dict]) -> list[dict]:
    """OEE per shift (1, 2, 3) over the given records."""
    groups = defaultdict(list)
    for r in records:
        groups[shift_of(r["timestamp"])[0]].append(r)
    return [{"shift": s["key"], "label": {"en": s["en"], "id": s["id"]}, **aggregate(groups[s["key"]])}
            for s in SHIFTS]


def line_shifts(records: list[dict]) -> list[dict]:
    """OEE of every (line, shift) worked in the records, oldest first."""
    groups = defaultdict(list)
    for r in records:
        groups[(r["line_id"], *shift_of(r["timestamp"]))].append(r)
    out = [{"line_id": line_id, "shift": key, "shift_date": shift_date,
            "start": shift_start(key, shift_date), **aggregate(rows)}
           for (line_id, key, shift_date), rows in groups.items()]
    return sorted(out, key=lambda x: (x["start"], x["line_id"]))


def current_shift(records: list[dict]) -> dict | None:
    """OEE of the shift of the latest record of one line (records of that line only)."""
    if not records:
        return None
    latest = max(records, key=lambda r: r["timestamp"])
    key, shift_date = shift_of(latest["timestamp"])
    rows = [r for r in records if shift_of(r["timestamp"]) == (key, shift_date)]
    return {"shift": key, "shift_date": shift_date, "start": shift_start(key, shift_date), **aggregate(rows)}


def event_view(event: dict) -> dict:
    """A downtime event with its end time and reason label."""
    end = _dt(event["start"]) + timedelta(minutes=event["minutes"])
    return {**event, "end": _iso(end), "reason_label": DOWNTIME_REASONS[event["reason"]],
            "long": event["minutes"] > DOWNTIME_ALERT_MINUTES}


def stopped_at(events: list[dict], moment) -> dict | None:
    """The event that keeps a line stopped at `moment`, if any."""
    t = _dt(moment)
    active = [e for e in events
              if _dt(e["start"]) <= t < _dt(e["start"]) + timedelta(minutes=e["minutes"])]
    return event_view(max(active, key=lambda e: e["start"])) if active else None


def pareto(events: list[dict]) -> list[dict]:
    """Downtime minutes per reason, largest first, with cumulative share (Pareto chart)."""
    minutes, counts = defaultdict(float), defaultdict(int)
    for e in events:
        minutes[e["reason"]] += e["minutes"]
        counts[e["reason"]] += 1
    total = sum(minutes.values())
    out, running = [], 0.0
    for reason, m in sorted(minutes.items(), key=lambda kv: kv[1], reverse=True):
        running += m
        out.append({"reason": reason, "label": DOWNTIME_REASONS[reason], "minutes": round(m, 1),
                    "events": counts[reason], "share": round(m / total, 4),
                    "cumulative": round(running / total, 4)})
    return out


def alerts(records: list[dict], events: list[dict]) -> list[dict]:
    """Line shifts with OEE below the alert level and stops longer than the limit, newest first."""
    out = []
    for ls in line_shifts(records):
        if ls["planned_minutes"] >= MIN_ALERT_PLANNED_MINUTES and ls["oee"] < OEE_ALERT:
            out.append({"type": "low_oee", "line_id": ls["line_id"],
                        "plant_id": LINE_BY_ID[ls["line_id"]]["plant_id"], "timestamp": ls["start"],
                        "shift": ls["shift"], "shift_date": ls["shift_date"], "oee": ls["oee"],
                        "availability": ls["availability"], "performance": ls["performance"],
                        "quality": ls["quality"]})
    for e in events:
        if e["minutes"] > DOWNTIME_ALERT_MINUTES:
            ev = event_view(e)
            out.append({"type": "long_downtime", "line_id": e["line_id"],
                        "plant_id": LINE_BY_ID[e["line_id"]]["plant_id"], "timestamp": _iso(_dt(e["start"])),
                        "minutes": e["minutes"], "reason": e["reason"], "reason_label": ev["reason_label"],
                        "end": ev["end"]})
    return sorted(out, key=lambda a: a["timestamp"], reverse=True)
