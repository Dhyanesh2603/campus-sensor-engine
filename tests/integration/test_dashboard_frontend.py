import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_dashboard_served_successfully(client: AsyncClient):
    resp = await client.get("/dashboard/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Campus Sensor Engine" in resp.text
    assert "Real-Time Telemetry Stream" in resp.text


@pytest.mark.asyncio
async def test_root_endpoint_includes_dashboard_link(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["dashboard"] == "/dashboard"
