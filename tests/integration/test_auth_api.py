import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_registration_and_login_flow(client: AsyncClient):
    # 1. Register new organizer
    reg_payload = {
        "email": "organizer@campus.edu",
        "password": "SecurePassword123!",
        "full_name": "Campus Lead",
        "role": "organizer",
    }
    resp = await client.post("/api/v1/auth/register", json=reg_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["email"] == "organizer@campus.edu"
    assert data["data"]["role"] == "organizer"

    # 2. Register duplicate email -> 409 Conflict
    dup_resp = await client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_resp.status_code == 409
    assert dup_resp.json()["success"] is False

    # 3. Login with correct credentials
    login_payload = {
        "email": "organizer@campus.edu",
        "password": "SecurePassword123!",
    }
    login_resp = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_resp.status_code == 200
    tokens = login_resp.json()["data"]
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # 4. Access protected profile route
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["email"] == "organizer@campus.edu"

    # 5. Refresh token
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()["data"]


@pytest.mark.asyncio
async def test_auth_invalid_credentials(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@test.com", "password": "WrongPassword"},
    )
    assert resp.status_code == 401
    assert resp.json()["success"] is False
