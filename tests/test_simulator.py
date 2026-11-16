from datetime import datetime, timedelta, timezone

from app import db, simulator
from app.config import DOWNTIME_REASONS, LINES

END = datetime(2026, 10, 26, tzinfo=timezone.utc)
LINE = {line["id"]: line for line in LINES}


def test_generate_covers_every_line_and_hour():
    production, _ = simulator.generate(END - timedelta(hours=23), END, seed=1)
    assert len(production) == 24 * len(LINES)


def test_values_stay_consistent():
    production, _ = simulator.generate(END - timedelta(days=7), END, seed=2)
    for r in production:
        assert r["planned_minutes"] in (0, 60)
        assert 0 <= r["run_minutes"] <= r["planned_minutes"]
        assert 0 <= r["good_count"] <= r["total_count"]
        # never faster than the rated speed
        assert r["total_count"] <= r["run_minutes"] * 60 / LINE[r["line_id"]]["ideal_cycle_s"] + 1


def test_each_shift_has_one_hour_meal_break():
    production, _ = simulator.generate(END - timedelta(hours=23), END, seed=3)
    for line in LINES:
        planned = [r["planned_minutes"] for r in production if r["line_id"] == line["id"]]
        assert planned.count(0) == 3
        assert sum(planned) == 3 * 420


def test_downtime_events_are_valid_and_some_are_long():
    _, downtime = simulator.generate(END - timedelta(days=7), END, seed=4)
    assert downtime
    assert all(e["reason"] in DOWNTIME_REASONS and e["minutes"] > 0 for e in downtime)
    assert any(e["minutes"] > 30 for e in downtime)
    assert {"changeover", "breakdown", "minor_stop"} <= {e["reason"] for e in downtime}


def test_struggling_lines_lose_more_time_than_steady_ones():
    production, _ = simulator.generate(END - timedelta(days=7), END, seed=5)

    def availability(profile):
        rows = [r for r in production if LINE[r["line_id"]]["profile"] == profile]
        return sum(r["run_minutes"] for r in rows) / sum(r["planned_minutes"] for r in rows)

    assert availability("struggling") < availability("steady")


def test_stops_are_deterministic():
    line = LINES[0]
    hours = [END + timedelta(hours=h) for h in range(48)]
    assert [simulator.events_starting(line, h) for h in hours] == [simulator.events_starting(line, h) for h in hours]


def test_backfill_stores_production_and_downtime():
    n = simulator.backfill(hours=6)
    assert n == 6 * len(LINES)
    assert db.count() == n
    assert set(db.latest_by_line()) == {line["id"] for line in LINES}
    assert simulator.catch_up() == 0  # already up to date
