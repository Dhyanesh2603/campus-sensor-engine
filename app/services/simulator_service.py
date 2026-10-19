import asyncio
import random
import time
from datetime import datetime, timezone
from typing import Any
import httpx
from app.config.settings import get_settings
from app.core.logging import get_logger
from app.schemas.sensor import SensorReadingIn
from app.schemas.simulator import SimulatorStartRequest, SimulatorStatusResponse

logger = get_logger("services.simulator")
settings = get_settings()

SENSOR_TYPES_META = {
    "temperature": {"min": 15.0, "max": 45.0, "spike_min": 36.0, "spike_prob": 0.08},
    "humidity": {"min": 10.0, "max": 95.0, "spike_min": 15.0, "spike_prob": 0.08},
    "occupancy": {"min": 0.0, "max": 400.0, "spike_min": 260.0, "spike_prob": 0.08},
    "air_quality": {"min": 10.0, "max": 300.0, "spike_min": 190.0, "spike_prob": 0.08},
    "noise": {"min": 20.0, "max": 105.0, "spike_min": 85.0, "spike_prob": 0.08},
    "light": {"min": 50.0, "max": 1500.0, "spike_min": 1100.0, "spike_prob": 0.08},
}


class SimulatorManager:
    _instance: "SimulatorManager | None" = None

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._is_running: bool = False
        self._start_time: float = 0.0
        self._sensors_configured: int = 0
        self._duration_seconds: int = 0
        self._readings_generated: int = 0
        self._readings_ingested: int = 0
        self._batches_sent: int = 0
        self._sensor_pool: list[dict[str, str]] = []

    @classmethod
    def get_instance(cls) -> "SimulatorManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _generate_sensor_pool(self, count: int) -> list[dict[str, str]]:
        types = list(SENSOR_TYPES_META.keys())
        locations = ["library", "engineering", "student-center", "science-lab", "dorm-a", "dorm-b", "cafeteria"]
        pool = []
        for i in range(count):
            loc = locations[i % len(locations)]
            stype = types[i % len(types)]
            floor = (i % 5) + 1
            sensor_id = f"{loc}-floor-{floor}-{stype}-{i+1}"
            pool.append({"id": sensor_id, "type": stype})
        return pool

    def _generate_batch_readings(self, batch_size: int) -> list[dict[str, Any]]:
        batch: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()
        for _ in range(batch_size):
            sensor = random.choice(self._sensor_pool)
            meta = SENSOR_TYPES_META[sensor["type"]]

            # Occasionally generate anomalous/spike readings to trigger alert rules
            if random.random() < meta["spike_prob"]:
                val = round(random.uniform(meta["spike_min"], meta["max"]), 2)
            else:
                val = round(random.uniform(meta["min"], meta["spike_min"]), 2)

            batch.append({
                "sensorId": sensor["id"],
                "type": sensor["type"],
                "value": val,
                "timestamp": now,
            })
        return batch

    async def start(
        self,
        config: SimulatorStartRequest,
        target_api_url: str = "http://localhost:8000/api/v1/readings",
        auth_token: str | None = None,
    ) -> None:
        if self._is_running:
            logger.warning("simulator_already_running")
            return

        self._sensors_configured = config.number_of_sensors
        self._duration_seconds = config.duration_seconds
        self._sensor_pool = self._generate_sensor_pool(config.number_of_sensors)
        self._readings_generated = 0
        self._readings_ingested = 0
        self._batches_sent = 0
        self._is_running = True
        self._start_time = time.time()

        self._task = asyncio.create_task(
            self._run_loop(config, target_api_url, auth_token)
        )
        logger.info(
            "simulator_started",
            sensors=config.number_of_sensors,
            duration=config.duration_seconds,
            batch_size=config.batch_size,
            frequency=config.frequency_per_second,
        )

    async def _run_loop(
        self,
        config: SimulatorStartRequest,
        target_api_url: str,
        auth_token: str | None,
    ) -> None:
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        client = httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_connections=100))
        interval = 1.0 / max(1, config.frequency_per_second)

        try:
            while self._is_running:
                now = time.time()
                if now - self._start_time >= config.duration_seconds:
                    logger.info("simulator_duration_elapsed")
                    break

                batch_data = self._generate_batch_readings(config.batch_size)
                self._readings_generated += len(batch_data)

                try:
                    resp = await client.post(target_api_url, json=batch_data, headers=headers)
                    if resp.status_code == 200:
                        self._readings_ingested += len(batch_data)
                        self._batches_sent += 1
                    else:
                        logger.warning("simulator_batch_ingest_failed", status=resp.status_code, body=resp.text)
                except Exception as exc:
                    logger.warning("simulator_post_error", error=str(exc))

                await asyncio.sleep(interval)
        finally:
            self._is_running = False
            await client.aclose()
            logger.info(
                "simulator_completed",
                total_generated=self._readings_generated,
                total_ingested=self._readings_ingested,
                batches=self._batches_sent,
            )

    async def stop(self) -> None:
        if self._is_running:
            self._is_running = False
            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("simulator_stopped_manually")

    def get_status(self) -> SimulatorStatusResponse:
        elapsed = time.time() - self._start_time if self._start_time > 0 else 0.0
        if not self._is_running and elapsed > self._duration_seconds:
            elapsed = float(self._duration_seconds)

        rate = (self._readings_ingested / elapsed) if elapsed > 0 else 0.0

        return SimulatorStatusResponse(
            is_running=self._is_running,
            sensors_configured=self._sensors_configured,
            duration_seconds=self._duration_seconds,
            elapsed_seconds=round(elapsed, 2),
            readings_generated=self._readings_generated,
            readings_ingested=self._readings_ingested,
            batches_sent=self._batches_sent,
            current_rate_per_sec=round(rate, 2),
        )
