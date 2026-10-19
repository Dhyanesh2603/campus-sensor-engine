import pytest
from app.redis.cooldown import CooldownManager
from tests.conftest import FakeRedis


@pytest.mark.asyncio
async def test_alert_cooldown_deduplication(fake_redis: FakeRedis):
    cm = CooldownManager(fake_redis)  # type: ignore
    rule_id = "test-rule-1"
    sensor_id = "sensor-dorm-3"

    # First attempt: lock acquired -> allow alert
    allowed = await cm.acquire_cooldown_lock(rule_id, sensor_id, cooldown_seconds=300)
    assert allowed is True

    # Immediate second attempt: in cooldown -> suppress alert
    allowed_again = await cm.acquire_cooldown_lock(rule_id, sensor_id, cooldown_seconds=300)
    assert allowed_again is False

    # Check state
    assert await cm.is_in_cooldown(rule_id, sensor_id) is True

    # Clear cooldown manually
    await cm.clear_cooldown(rule_id, sensor_id)
    assert await cm.is_in_cooldown(rule_id, sensor_id) is False

    # Should allow alert once cleared
    assert await cm.acquire_cooldown_lock(rule_id, sensor_id, cooldown_seconds=300) is True
