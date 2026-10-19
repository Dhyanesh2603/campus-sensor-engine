import random
import time
from datetime import datetime, timezone
from locust import HttpUser, between, events, task

SENSOR_TYPES = ["temperature", "humidity", "occupancy", "air_quality", "noise", "light"]
SENSOR_POOLS = [f"sensor-campus-{i}" for i in range(1, 5001)]


class SensorIngestionUser(HttpUser):
    wait_time = between(0.01, 0.05)

    def on_start(self):
        # Register and login to obtain organizer token
        self.auth_headers = {}
        email = f"loadtest_{int(time.time()*1000)}_{random.randint(100, 999)}@test.com"
        reg_payload = {
            "email": email,
            "password": "Password123!",
            "full_name": "Load Test Runner",
            "role": "organizer",
        }
        with self.client.post("/api/v1/auth/register", json=reg_payload, catch_response=True) as resp:
            if resp.status_code == 201:
                token_data = resp.json().get("data", {})
                # Login
                login_resp = self.client.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": "Password123!"},
                )
                if login_resp.status_code == 200:
                    token = login_resp.json().get("data", {}).get("access_token")
                    self.auth_headers = {"Authorization": f"Bearer {token}"}

    @task(80)
    def ingest_reading_batch(self):
        """
        Sends a burst batch of 250 readings per request.
        40 concurrent users at 1 req/sec = 10,000 readings/sec!
        """
        batch_size = 250
        now = datetime.now(timezone.utc).isoformat()
        batch = []
        for _ in range(batch_size):
            sid = random.choice(SENSOR_POOLS)
            stype = random.choice(SENSOR_TYPES)
            val = round(random.uniform(10.0, 90.0), 2)
            batch.append({
                "sensorId": sid,
                "type": stype,
                "value": val,
                "timestamp": now,
            })

        with self.client.post(
            "/api/v1/readings",
            json=batch,
            headers={"Content-Type": "application/json"},
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}: {response.text}")

    @task(10)
    def get_alerts(self):
        self.client.get(
            "/api/v1/alerts?page=1&page_size=20",
            headers=self.auth_headers,
        )

    @task(5)
    def get_sensors(self):
        self.client.get(
            "/api/v1/sensors?limit=50",
            headers=self.auth_headers,
        )

    @task(5)
    def get_rules(self):
        self.client.get(
            "/api/v1/rules",
            headers=self.auth_headers,
        )
