from fastapi.testclient import TestClient

from app import simulator
from app.config import LINES, PLANTS
from app.main import app


def client() -> TestClient:
    simulator.backfill(hours=24)
    return TestClient(app)


def test_health():
    with client() as c:
        body = c.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["records"] == 24 * len(LINES)


def test_lines_have_oee():
    with client() as c:
        lines = c.get("/api/lines").json()
        assert len(lines) == len(LINES)
        for line in lines:
            assert 0 <= line["last_24h"]["oee"] <= 1
            assert line["last_24h"]["band"] in {"world_class", "acceptable", "low"}
            assert [s["shift"] for s in line["shifts_24h"]] == ["1", "2", "3"]
            assert line["current_shift"]["planned_minutes"] <= 420


def test_line_detail_history_and_unknown_line():
    with client() as c:
        assert c.get("/api/lines/btm-smt-1").json()["plant"] == "PT Selat Elektronika Presisi"
        rows = c.get("/api/lines/btm-smt-1/history?hours=12").json()
        assert 11 <= len(rows) <= 12
        assert all(r["line_id"] == "btm-smt-1" for r in rows)
        assert c.get("/api/lines/nowhere/history").status_code == 404
        assert c.get("/api/lines/nowhere").status_code == 404


def test_summary_and_plants():
    with client() as c:
        body = c.get("/api/summary").json()
        assert body["reporting"] == len(LINES)
        assert sum(body["band_counts"].values()) == len(LINES)
        assert body["worst"]["oee"] <= body["last_24h"]["oee"]
        plants = c.get("/api/plants").json()
        assert len(plants) == len(PLANTS)
        assert sum(p["lines"] for p in plants) == len(LINES)


def test_shifts_and_pareto():
    with client() as c:
        shifts = c.get("/api/shifts?hours=24").json()
        assert [s["shift"] for s in shifts] == ["1", "2", "3"]
        pareto = c.get("/api/downtime/pareto?hours=24").json()
        minutes = [p["minutes"] for p in pareto]
        assert minutes == sorted(minutes, reverse=True)
        assert c.get("/api/downtime/pareto?plant_id=kiic").status_code == 200
        assert c.get("/api/downtime/pareto?plant_id=nowhere").status_code == 404


def test_alerts_endpoint():
    with client() as c:
        alerts = c.get("/api/alerts?hours=24").json()
        assert all(a["type"] in {"low_oee", "long_downtime"} for a in alerts)
        for a in c.get("/api/alerts?hours=24&type=long_downtime").json():
            assert a["minutes"] > 30
        assert c.get("/api/alerts?type=bogus").status_code == 422
