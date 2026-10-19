import pytest
from httpx import AsyncClient


async def get_organizer_token(client: AsyncClient) -> str:
    email = "admin@campus.edu"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "role": "organizer"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return resp.json()["data"]["access_token"]


async def get_viewer_token(client: AsyncClient) -> str:
    email = "viewer@campus.edu"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "role": "viewer"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_rule_crud_and_role_enforcement(client: AsyncClient):
    org_token = await get_organizer_token(client)
    view_token = await get_viewer_token(client)

    org_headers = {"Authorization": f"Bearer {org_token}"}
    view_headers = {"Authorization": f"Bearer {view_token}"}

    # 1. Non-organizer attempts to create rule -> 403 Forbidden
    rule_payload = {
        "name": "High Temperature Warning",
        "sensor_type": "temperature",
        "rule_type": "threshold",
        "operator": ">",
        "threshold": 35.0,
        "severity": "CRITICAL",
    }
    forbidden_resp = await client.post("/api/v1/rules", json=rule_payload, headers=view_headers)
    assert forbidden_resp.status_code == 403

    # 2. Organizer creates threshold rule
    create_resp = await client.post("/api/v1/rules", json=rule_payload, headers=org_headers)
    assert create_resp.status_code == 201
    rule_data = create_resp.json()["data"]
    rule_id = rule_data["id"]
    assert rule_data["name"] == "High Temperature Warning"
    assert rule_data["threshold"] == 35.0

    # 3. Create sliding-window rule
    window_rule_payload = {
        "name": "Average 10m High Occupancy",
        "sensor_type": "occupancy",
        "rule_type": "window",
        "operator": ">",
        "threshold": 250.0,
        "aggregation": "AVG",
        "window": "10m",
        "severity": "HIGH",
    }
    w_resp = await client.post("/api/v1/rules", json=window_rule_payload, headers=org_headers)
    assert w_resp.status_code == 201
    assert w_resp.json()["data"]["window_seconds"] == 600

    # 4. List rules
    list_resp = await client.get("/api/v1/rules", headers=org_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) == 2

    # 5. Disable rule
    disable_resp = await client.patch(f"/api/v1/rules/{rule_id}/disable", headers=org_headers)
    assert disable_resp.status_code == 200
    assert disable_resp.json()["data"]["enabled"] is False

    # 6. Enable rule
    enable_resp = await client.patch(f"/api/v1/rules/{rule_id}/enable", headers=org_headers)
    assert enable_resp.status_code == 200
    assert enable_resp.json()["data"]["enabled"] is True

    # 7. Delete rule
    del_resp = await client.delete(f"/api/v1/rules/{rule_id}", headers=org_headers)
    assert del_resp.status_code == 200
