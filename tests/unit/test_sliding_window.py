import time
import pytest
from app.redis.sliding_window import SlidingWindowManager
from tests.conftest import FakeRedis


@pytest.mark.asyncio
async def test_sliding_window_aggregations(fake_redis: FakeRedis):
    sw = SlidingWindowManager(fake_redis)  # type: ignore
    sensor_id = "test-sensor-window"
    sensor_type = "temperature"

    now = 1000.0
    # Add 4 readings at now-40, now-30, now-20, now-10
    values = [20.0, 24.0, 28.0, 32.0]
    for idx, val in enumerate(values):
        ts = now - (40 - idx * 10)
        await sw.add_reading(sensor_id, sensor_type, ts, val)

    # 1. COUNT aggregation over 60s
    count_val = await sw.get_window_aggregation(
        sensor_id, sensor_type, window_seconds=60, aggregation="COUNT", now_timestamp=now
    )
    assert count_val == 4.0

    # 2. AVG aggregation over 60s (20 + 24 + 28 + 32) / 4 = 26.0
    avg_val = await sw.get_window_aggregation(
        sensor_id, sensor_type, window_seconds=60, aggregation="AVG", now_timestamp=now
    )
    assert avg_val == 26.0

    # 3. MIN aggregation over 60s
    min_val = await sw.get_window_aggregation(
        sensor_id, sensor_type, window_seconds=60, aggregation="MIN", now_timestamp=now
    )
    assert min_val == 20.0

    # 4. MAX aggregation over 60s
    max_val = await sw.get_window_aggregation(
        sensor_id, sensor_type, window_seconds=60, aggregation="MAX", now_timestamp=now
    )
    assert max_val == 32.0

    # 5. Window boundary test: window of 15s should only capture the last reading (now-10)
    count_15s = await sw.get_window_aggregation(
        sensor_id, sensor_type, window_seconds=15, aggregation="COUNT", now_timestamp=now
    )
    assert count_15s == 1.0


@pytest.mark.asyncio
async def test_sliding_window_batch_add(fake_redis: FakeRedis):
    sw = SlidingWindowManager(fake_redis)  # type: ignore
    sensor_id = "test-sensor-batch"
    sensor_type = "humidity"

    now = time.time()
    batch = [
        {"sensor_id": sensor_id, "sensor_type": sensor_type, "timestamp": now - 10, "value": 45.0},
        {"sensor_id": sensor_id, "sensor_type": sensor_type, "timestamp": now - 5, "value": 55.0},
    ]
    await sw.add_readings_batch(batch)

    avg_val = await sw.get_window_aggregation(
        sensor_id, sensor_type, window_seconds=60, aggregation="AVG", now_timestamp=now
    )
    assert avg_val == 50.0
