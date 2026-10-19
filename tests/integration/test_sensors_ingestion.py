from datetime import datetime, timezone
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_single_and_batch_reading_ingestion(client: AsyncClient):
    now = datetime.now(timezone.utc).isoformat()

    # 1. Ingest single reading
    single_reading = {
        "sensorId": "library-floor-2",
        "type": "temperature",
        "value": 24.5,
        "timestamp": now,
    }
    resp = await client.post("/api/v1/readings", json=single_reading)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["success"] is True
    assert res_data["data"]["ingested_count"] == 1

    # 2. Ingest batch reading
    batch_readings = [
        {
            "sensorId": "engineering-lab-1",
            "type": "humidity",
            "value": 45.0,
            "timestamp": now,
        },
        {
            "sensorId": "science-hall-air",
            "type": "air_quality",
            "value": 72.0,
            "timestamp": now,
        },
    ]
    batch_resp = await client.post("/api/v1/readings", json=batch_readings)
    assert batch_resp.status_code == 200
    assert batch_resp.json()["data"]["ingested_count"] == 2

    # 3. Query automatically registered sensors
    sensors_resp = await client.get("/api/v1/sensors")
    assert sensors_resp.status_code == 200
    sensors = sensors_resp.json()["data"]
    sensor_ids = [s["id"] for s in sensors]
    assert "library-floor-2" in sensor_ids
    assert "engineering-lab-1" in sensor_ids
    assert "science-hall-air" in sensor_ids

    # 4. Query historical readings for sensor
    hist_resp = await client.get("/api/v1/sensors/library-floor-2/readings")
    assert hist_resp.status_code == 200
    assert len(hist_resp.json()["data"]) == 1
    assert hist_resp.json()["data"][0]["value"] == 24.5


@pytest.mark.asyncio
async def test_invalid_reading_validation(client: AsyncClient):
    # Missing required field 'value'
    bad_payload = {
        "sensorId": "faulty-sensor",
        "type": "temperature",
        "timestamp": "2026-10-12T10:30:00Z",
    }
    resp = await client.post("/api/v1/readings", json=bad_payload)
    assert resp.status_code == 422
    assert resp.json()["success"] is False
