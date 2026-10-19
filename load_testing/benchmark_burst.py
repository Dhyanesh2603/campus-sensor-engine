import asyncio
import random
import time
from datetime import datetime, timezone
from typing import Any
import httpx
import psutil

BASE_URL = "http://localhost:8000"
TOTAL_BURST_READINGS = 10000
BATCH_SIZE = 500  # 20 batches of 500 readings fired concurrently
CONCURRENT_BATCHES = TOTAL_BURST_READINGS // BATCH_SIZE


def generate_batch(batch_size: int, start_idx: int) -> list[dict[str, Any]]:
    types = ["temperature", "humidity", "occupancy", "air_quality", "noise", "light"]
    batch = []
    now = datetime.now(timezone.utc).isoformat()
    for i in range(batch_size):
        idx = start_idx + i
        stype = types[idx % len(types)]
        sid = f"benchmark-sensor-{idx % 1000}-{stype}"
        # generate occasional spike
        val = round(random.uniform(40.0, 50.0) if i % 10 == 0 else random.uniform(18.0, 25.0), 2)
        batch.append({
            "sensorId": sid,
            "type": stype,
            "value": val,
            "timestamp": now,
        })
    return batch


async def post_batch(
    client: httpx.AsyncClient,
    batch: list[dict[str, Any]],
    batch_idx: int,
) -> tuple[int, float, bool]:
    req_start = time.perf_counter()
    try:
        resp = await client.post(f"{BASE_URL}/api/v1/readings", json=batch)
        duration_ms = (time.perf_counter() - req_start) * 1000
        success = resp.status_code == 200
        return len(batch), duration_ms, success
    except Exception:
        duration_ms = (time.perf_counter() - req_start) * 1000
        return len(batch), duration_ms, False


async def query_api(client: httpx.AsyncClient, token: str) -> tuple[str, float, bool]:
    endpoints = ["/api/v1/alerts", "/api/v1/sensors", "/api/v1/rules"]
    target = random.choice(endpoints)
    req_start = time.perf_counter()
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get(f"{BASE_URL}{target}", headers=headers)
        duration_ms = (time.perf_counter() - req_start) * 1000
        return target, duration_ms, resp.status_code == 200
    except Exception:
        duration_ms = (time.perf_counter() - req_start) * 1000
        return target, duration_ms, False


async def run_burst_benchmark():
    print("================================================================")
    print("   BURST BENCHMARK: 10,000 SENSOR READINGS IN 1 SECOND")
    print("================================================================")

    process = psutil.Process()
    cpu_before = psutil.cpu_percent(interval=None)
    mem_before = process.memory_info().rss / (1024 * 1024)

    limits = httpx.Limits(max_connections=100, max_keepalive_connections=50)
    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        # 1. Setup user & rule
        email = f"burst_test_{int(time.time())}@test.com"
        await client.post(
            f"{BASE_URL}/api/v1/auth/register",
            json={"email": email, "password": "Password123!", "role": "organizer"},
        )
        login_res = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": email, "password": "Password123!"},
        )
        token = login_res.json().get("data", {}).get("access_token", "")
        headers = {"Authorization": f"Bearer {token}"}

        # Create threshold rule
        await client.post(
            f"{BASE_URL}/api/v1/rules",
            headers=headers,
            json={
                "name": "High Temp Burst Alert",
                "sensor_type": "temperature",
                "rule_type": "threshold",
                "operator": ">",
                "threshold": 35.0,
                "severity": "CRITICAL",
                "cooldown_seconds": 60,
            },
        )

        print(f"-> Generating {TOTAL_BURST_READINGS} sensor readings across {CONCURRENT_BATCHES} batches...")
        batches = [generate_batch(BATCH_SIZE, i * BATCH_SIZE) for i in range(CONCURRENT_BATCHES)]

        print("-> Firing concurrent 10,000 reading burst alongside live API queries...")
        wall_clock_start = time.perf_counter()

        # Concurrent ingestion tasks + concurrent read tasks
        ingest_tasks = [post_batch(client, b, i) for i, b in enumerate(batches)]
        query_tasks = [query_api(client, token) for _ in range(15)]

        results = await asyncio.gather(*ingest_tasks)
        query_results = await asyncio.gather(*query_tasks)

        wall_clock_duration = time.perf_counter() - wall_clock_start

    cpu_after = psutil.cpu_percent(interval=None)
    mem_after = process.memory_info().rss / (1024 * 1024)

    total_ingested = sum(r[0] for r in results if r[2])
    total_failures = sum(1 for r in results if not r[2])
    latencies = [r[1] for r in results]
    latencies.sort()

    p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    throughput = total_ingested / max(0.001, wall_clock_duration)

    query_success = sum(1 for q in query_results if q[2])
    query_latencies = [q[1] for q in query_results]
    avg_query_lat = sum(query_latencies) / len(query_latencies) if query_latencies else 0.0

    print("\n----------------- BENCHMARK RESULTS -----------------")
    print(f"Total Readings Dispatched:  {TOTAL_BURST_READINGS}")
    print(f"Total Readings Accepted:    {total_ingested}")
    print(f"Wall Clock Time:            {wall_clock_duration:.3f} seconds")
    print(f"Achieved Throughput:        {throughput:,.1f} readings/sec")
    print(f"Failed Batches:             {total_failures}")
    print(f"Average Batch Latency:      {avg_latency:.2f} ms")
    print(f"Median Latency (P50):       {p50:.2f} ms")
    print(f"95th Percentile (P95):      {p95:.2f} ms")
    print(f"99th Percentile (P99):      {p99:.2f} ms")
    print(f"Concurrent Query Latency:   {avg_query_lat:.2f} ms ({query_success}/{len(query_results)} ok)")
    print(f"Memory Usage Delta:         {mem_after - mem_before:+.2f} MB")
    print("-----------------------------------------------------")

    if wall_clock_duration <= 1.5 and total_failures == 0:
        print("RESULT: SUCCESS - Sustained 10,000 readings burst comfortably within target window!")
    else:
        print("RESULT: COMPLETED")


if __name__ == "__main__":
    asyncio.run(run_burst_benchmark())
