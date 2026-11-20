from fastapi.testclient import TestClient

from app.main import app

HOUR = {"line_id": "btm-smt-1", "timestamp": "2026-10-26T02:00:00+00:00", "planned_minutes": 60,
        "run_minutes": 57, "total_count": 148, "good_count": 147}
STOP = {"line_id": "kiic-press-b", "minutes": 12, "reason": "minor_stop"}


def test_ingest_production_scores_and_stores_it():
    with TestClient(app) as c:
        res = c.post("/api/production", json=HOUR)
        assert res.status_code == 201
        body = res.json()
        # 57/60 x (148 x 22 s / 57 min) x 147/148 = 0.8983
        assert abs(body["oee"] - 0.8983) < 1e-3
        assert body["band"] == "world_class"
        assert body["shift"] == "1"
        assert c.get("/api/health").json()["records"] == 1


def test_ingest_downtime_flags_long_stops():
    with TestClient(app) as c:
        short = c.post("/api/downtime", json=STOP)
        assert short.status_code == 201 and short.json()["long"] is False
        long = c.post("/api/downtime", json={**STOP, "minutes": 45, "reason": "breakdown"}).json()
        assert long["long"] is True
        assert long["reason_label"]["id"] == "Kerusakan mesin"
        alerts = c.get("/api/alerts?type=long_downtime").json()
        assert [a["minutes"] for a in alerts] == [45]
        assert c.get("/api/lines/kiic-press-b/downtime").json()[0]["line_id"] == "kiic-press-b"


def test_ingest_validates_input():
    with TestClient(app) as c:
        assert c.post("/api/production", json={**HOUR, "line_id": "nowhere"}).status_code == 422
        assert c.post("/api/production", json={**HOUR, "run_minutes": 61}).status_code == 422
        assert c.post("/api/production", json={**HOUR, "run_minutes": 50, "planned_minutes": 40}).status_code == 422
        assert c.post("/api/production", json={**HOUR, "good_count": 200}).status_code == 422
        assert c.post("/api/downtime", json={**STOP, "reason": "lunch"}).status_code == 422
        assert c.post("/api/downtime", json={**STOP, "minutes": 0}).status_code == 422


def test_api_key_is_enforced_when_set(monkeypatch):
    monkeypatch.setenv("OEE_API_KEY", "secret")
    with TestClient(app) as c:
        assert c.post("/api/production", json=HOUR).status_code == 401
        assert c.post("/api/downtime", json=STOP).status_code == 401
        assert c.post("/api/production", json=HOUR, headers={"X-API-Key": "secret"}).status_code == 201
        assert c.post("/api/downtime", json=STOP, headers={"X-API-Key": "secret"}).status_code == 201
