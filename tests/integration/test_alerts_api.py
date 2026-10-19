from datetime import datetime, timezone
import pytest
from httpx import AsyncClient


async def get_organizer_token(client: AsyncClient) -> str:
    email = "organizer_alerts@campus.edu"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "role": "organizer"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_alert_generation_lifecycle_and_deduplication(client: AsyncClient):
    token = await get_organizer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a threshold rule: temperature > 35.0 with 300s cooldown
    rule_payload = {
        "name": "Server Room Overheat",
        "sensor_type": "temperature",
        "rule_type": "threshold",
        "operator": ">",
        "threshold": 35.0,
        "severity": "CRITICAL",
        "cooldown_seconds": 300,
    }
    rule_res = await client.post("/api/v1/rules", json=rule_payload, headers=headers)
    assert rule_res.status_code == 201

    now = datetime.now(timezone.utc).isoformat()

    # 2. Ingest reading that triggers the rule (value 38.5 > 35.0)
    trigger_reading = {
        "sensorId": "server-room-sensor-1",
        "type": "temperature",
        "value": 38.5,
        "timestamp": now,
    }
    ingest_res1 = await client.post("/api/v1/readings", json=trigger_reading)
    assert ingest_res1.status_code == 200
    assert ingest_res1.json()["data"]["alerts_triggered"] == 1

    # 3. Ingest identical triggering reading immediately: should be suppressed by cooldown!
    trigger_reading_dup = {
        "sensorId": "server-room-sensor-1",
        "type": "temperature",
        "value": 39.0,
        "timestamp": now,
    }
    ingest_res2 = await client.post("/api/v1/readings", json=trigger_reading_dup)
    assert ingest_res2.status_code == 200
    assert ingest_res2.json()["data"]["alerts_triggered"] == 0

    # 4. List alerts: should contain exactly 1 alert
    alerts_list_res = await client.get("/api/v1/alerts", headers=headers)
    assert alerts_list_res.status_code == 200
    alerts_data = alerts_list_res.json()["data"]
    assert alerts_data["total"] == 1
    alert_item = alerts_data["items"][0]
    alert_id = alert_item["id"]
    assert alert_item["sensor_id"] == "server-room-sensor-1"
    assert alert_item["severity"] == "CRITICAL"
    assert alert_item["status"] == "OPEN"
    assert alert_item["trigger_value"] == 38.5

    # 5. Acknowledge alert
    ack_res = await client.patch(f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers)
    assert ack_res.status_code == 200
    assert ack_res.json()["data"]["status"] == "ACKNOWLEDGED"

    # 6. Resolve alert
    resolve_res = await client.patch(f"/api/v1/alerts/{alert_id}/resolve", headers=headers)
    assert resolve_res.status_code == 200
    assert resolve_res.json()["data"]["status"] == "RESOLVED"

    # 7. Filter alerts by status
    resolved_query = await client.get("/api/v1/alerts?status=RESOLVED", headers=headers)
    assert resolved_query.status_code == 200
    assert resolved_query.json()["data"]["total"] == 1

    open_query = await client.get("/api/v1/alerts?status=OPEN", headers=headers)
    assert open_query.status_code == 200
    assert open_query.json()["data"]["total"] == 0

    # 8. Delete alert
    del_res = await client.delete(f"/api/v1/alerts/{alert_id}", headers=headers)
    assert del_res.status_code == 200

    # 9. Verify list is now empty
    empty_list = await client.get("/api/v1/alerts", headers=headers)
    assert empty_list.json()["data"]["total"] == 0
