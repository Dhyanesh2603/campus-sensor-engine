import argparse
import asyncio
import random
import time
from datetime import datetime, timezone
from typing import Any
import httpx

SENSOR_TYPES_META = {
    "temperature": {"min": 15.0, "max": 45.0, "spike_min": 36.0, "spike_prob": 0.08},
    "humidity": {"min": 10.0, "max": 95.0, "spike_min": 15.0, "spike_prob": 0.08},
    "occupancy": {"min": 0.0, "max": 400.0, "spike_min": 260.0, "spike_prob": 0.08},
    "air_quality": {"min": 10.0, "max": 300.0, "spike_min": 190.0, "spike_prob": 0.08},
    "noise": {"min": 20.0, "max": 105.0, "spike_min": 85.0, "spike_prob": 0.08},
    "light": {"min": 50.0, "max": 1500.0, "spike_min": 1100.0, "spike_prob": 0.08},
}


def generate_sensor_pool(count: int) -> list[dict[str, str]]:
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


def generate_batch(sensor_pool: list[dict[str, str]], batch_size: int) -> list[dict[str, Any]]:
    batch = []
    now = datetime.now(timezone.utc).isoformat()
    for _ in range(batch_size):
        sensor = random.choice(sensor_pool)
        meta = SENSOR_TYPES_META[sensor["type"]]

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


async def run_simulation(
    sensors_count: int,
    duration: int,
    batch_size: int,
    frequency: int,
    url: str,
    token: str | None = None,
) -> None:
    print(f"=== Campus Sensor Simulator ===")
    print(f"Target URL:       {url}")
    print(f"Sensors count:    {sensors_count}")
    print(f"Duration:         {duration}s")
    print(f"Batch size:       {batch_size}")
    print(f"Frequency:        {frequency} batches/sec")
    print(f"Target Throughput:{batch_size * frequency} readings/sec")
    print(f"================================")

    sensor_pool = generate_sensor_pool(sensors_count)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    total_readings_sent = 0
    total_readings_success = 0
    total_batches_sent = 0
    failed_requests = 0
    latencies: list[float] = []

    start_time = time.time()
    interval = 1.0 / max(1, frequency)

    limits = httpx.Limits(max_connections=200, max_keepalive_connections=50)
    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        while time.time() - start_time < duration:
            batch_data = generate_batch(sensor_pool, batch_size)
            req_start = time.perf_counter()

            try:
                resp = await client.post(url, json=batch_data, headers=headers)
                latency_ms = (time.perf_counter() - req_start) * 1000
                latencies.append(latency_ms)
                total_batches_sent += 1
                total_readings_sent += len(batch_data)

                if resp.status_code == 200:
                    total_readings_success += len(batch_data)
                else:
                    failed_requests += 1
            except Exception as exc:
                failed_requests += 1
                total_batches_sent += 1
                total_readings_sent += len(batch_data)

            elapsed = time.time() - start_time
            if total_batches_sent % 10 == 0:
                cur_rate = total_readings_success / max(1.0, elapsed)
                print(f"[{elapsed:6.1f}s] Sent: {total_readings_sent:8d} | Success: {total_readings_success:8d} | Rate: {cur_rate:8.1f} readings/sec | Failures: {failed_requests}")

            await asyncio.sleep(interval)

    total_elapsed = time.time() - start_time
    avg_rate = total_readings_success / max(0.1, total_elapsed)
    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0

    print("\n=== Simulation Summary ===")
    print(f"Total Elapsed Time: {total_elapsed:.2f} s")
    print(f"Total Batches Sent: {total_batches_sent}")
    print(f"Total Readings:     {total_readings_sent}")
    print(f"Success Readings:   {total_readings_success}")
    print(f"Failed Batches:     {failed_requests}")
    print(f"Avg Throughput:     {avg_rate:.2f} readings/sec")
    print(f"Latency P50:        {p50:.2f} ms")
    print(f"Latency P95:        {p95:.2f} ms")
    print(f"Latency P99:        {p99:.2f} ms")
    print("==========================")


def main() -> None:
    parser = argparse.ArgumentParser(description="Campus Sensor Real-time Simulator CLI")
    parser.add_argument("--sensors", type=int, default=1000, help="Number of sensors (e.g. 100, 500, 1000, 5000)")
    parser.add_argument("--duration", type=int, default=60, help="Duration of simulation in seconds")
    parser.add_argument("--batch-size", type=int, default=500, help="Number of readings per batch")
    parser.add_argument("--frequency", type=int, default=20, help="Number of batches per second")
    parser.add_argument("--url", type=str, default="http://localhost:8000/api/v1/readings", help="Target endpoint")
    parser.add_argument("--token", type=str, default=None, help="Bearer authorization token")

    args = parser.parse_args()
    asyncio.run(
        run_simulation(
            sensors_count=args.sensors,
            duration=args.duration,
            batch_size=args.batch_size,
            frequency=args.frequency,
            url=args.url,
            token=args.token,
        )
    )


if __name__ == "__main__":
    main()
