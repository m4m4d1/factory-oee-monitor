import pytest

from app import oee

LINE = "kiic-weld"  # ideal cycle time 40 s


def rec(planned, run, total, good, ts="2026-10-26T01:00:00+00:00", line=LINE):
    return {"line_id": line, "timestamp": ts, "planned_minutes": planned, "run_minutes": run,
            "total_count": total, "good_count": good}


def test_textbook_example():
    # 420 min planned, 47 min down, ideal cycle 1.0 s, 19 271 made, 18 848 good
    r = oee.ratios(420, 373, 19271, 18848, ideal_minutes=19271 / 60)
    assert r["availability"] == pytest.approx(0.8881, abs=1e-4)
    assert r["performance"] == pytest.approx(0.8611, abs=1e-4)
    assert r["quality"] == pytest.approx(0.9780, abs=1e-4)
    assert r["oee"] == pytest.approx(0.7479, abs=1e-3)


@pytest.mark.parametrize("value,key", [(0.92, "world_class"), (0.85, "world_class"), (0.849, "acceptable"),
                                       (0.65, "acceptable"), (0.649, "low"), (0.0, "low")])
def test_bands(value, key):
    assert oee.band(value)["key"] == key


def test_performance_is_capped_and_edge_cases():
    assert oee.ratios(60, 60, 200, 200, ideal_minutes=200)["performance"] == 1.0
    assert oee.ratios(0, 0, 0, 0, 0)["oee"] is None          # meal break: nothing planned
    assert oee.ratios(60, 0, 0, 0, 0)["oee"] == 0.0          # down for the whole hour


def test_score_attaches_oee_band_and_shift():
    # 01:00 UTC is 08:00 WIB: shift 1. 54 min run, 72 units x 40 s = 48 min ideal, 70 good
    s = oee.score(rec(60, 54, 72, 70))
    assert s["availability"] == 0.9
    assert s["performance"] == pytest.approx(48 / 54, abs=1e-4)
    assert s["oee"] == pytest.approx(0.9 * 48 / 54 * 70 / 72, abs=1e-4)
    assert s["band"] == "acceptable"
    assert (s["shift"], s["shift_date"]) == ("1", "2026-10-26")


@pytest.mark.parametrize("utc,expected", [
    ("2026-10-26T00:00:00+00:00", ("1", "2026-10-26")),   # 07:00 WIB
    ("2026-10-26T08:00:00+00:00", ("2", "2026-10-26")),   # 15:00 WIB
    ("2026-10-26T16:30:00+00:00", ("3", "2026-10-26")),   # 23:30 WIB
    ("2026-10-26T20:00:00+00:00", ("3", "2026-10-26")),   # 03:00 WIB next day, same night shift
])
def test_shift_of(utc, expected):
    assert oee.shift_of(utc) == expected


def test_aggregate_combines_sums_not_averages():
    rows = [rec(60, 60, 90, 90), rec(60, 30, 45, 45, ts="2026-10-26T02:00:00+00:00")]
    agg = oee.aggregate(rows)
    assert agg["availability"] == 0.75
    assert agg["downtime_minutes"] == 30
    assert agg["oee"] == pytest.approx(135 * 40 / 60 / 120, abs=1e-4)


def test_pareto_is_sorted_and_cumulative():
    events = [{"line_id": LINE, "start": "2026-10-26T01:00:00+00:00", "minutes": m, "reason": r}
              for m, r in [(10, "minor_stop"), (90, "breakdown"), (30, "changeover"), (20, "breakdown")]]
    p = oee.pareto(events)
    assert [x["reason"] for x in p] == ["breakdown", "changeover", "minor_stop"]
    assert p[0]["minutes"] == 110 and p[0]["events"] == 2
    assert p[-1]["cumulative"] == 1.0


def test_alerts_for_low_oee_and_long_stops():
    good = [rec(60, 58, 85, 85, ts=f"2026-10-26T0{h}:00:00+00:00") for h in range(1, 4)]
    bad = [rec(60, 30, 40, 35, ts=f"2026-10-26T0{h}:00:00+00:00", line="kiic-press-b") for h in range(1, 4)]
    events = [{"line_id": "kiic-press-b", "start": "2026-10-26T02:10:00+00:00", "minutes": 45, "reason": "breakdown"},
              {"line_id": LINE, "start": "2026-10-26T02:00:00+00:00", "minutes": 12, "reason": "minor_stop"}]
    hits = oee.alerts(good + bad, events)
    assert [(h["type"], h["line_id"]) for h in hits] == [("long_downtime", "kiic-press-b"), ("low_oee", "kiic-press-b")]


def test_stopped_at():
    events = [{"line_id": LINE, "start": "2026-10-26T01:10:00+00:00", "minutes": 40, "reason": "breakdown"}]
    assert oee.stopped_at(events, "2026-10-26T01:30:00+00:00")["reason"] == "breakdown"
    assert oee.stopped_at(events, "2026-10-26T01:55:00+00:00") is None
