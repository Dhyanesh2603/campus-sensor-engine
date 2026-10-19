import uuid
from datetime import datetime, timezone
import pytest
from app.models.alert_rule import AlertRule
from app.redis.cooldown import CooldownManager
from app.redis.sliding_window import SlidingWindowManager
from app.services.rule_evaluation_engine import RuleEvaluationEngine
from tests.conftest import FakeRedis


@pytest.fixture
def rule_engine(fake_redis: FakeRedis):
    sw = SlidingWindowManager(fake_redis)  # type: ignore
    cm = CooldownManager(fake_redis)  # type: ignore
    return RuleEvaluationEngine(sw, cm)


def test_operator_evaluations(rule_engine: RuleEvaluationEngine):
    assert rule_engine.evaluate_condition(35.5, ">", 35.0) is True
    assert rule_engine.evaluate_condition(35.0, ">", 35.0) is False
    assert rule_engine.evaluate_condition(35.0, ">=", 35.0) is True
    assert rule_engine.evaluate_condition(19.9, "<", 20.0) is True
    assert rule_engine.evaluate_condition(20.0, "<=", 20.0) is True
    assert rule_engine.evaluate_condition(42.0, "==", 42.0) is True
    assert rule_engine.evaluate_condition(42.0001, "!=", 42.0) is True


@pytest.mark.asyncio
async def test_threshold_rule_triggers_alert(rule_engine: RuleEvaluationEngine):
    rule = AlertRule(
        id=uuid.uuid4(),
        name="High Temperature Alert",
        sensor_type="temperature",
        rule_type="threshold",
        operator=">",
        threshold=35.0,
        enabled=True,
        severity="HIGH",
        cooldown_seconds=300,
    )

    now = datetime.now(timezone.utc)

    # Reading below threshold -> no alert
    alerts = await rule_engine.evaluate_reading(
        sensor_id="sensor-1",
        sensor_type="temperature",
        value=32.0,
        timestamp=now,
        rules=[rule],
    )
    assert len(alerts) == 0

    # Reading above threshold -> triggers alert
    alerts = await rule_engine.evaluate_reading(
        sensor_id="sensor-1",
        sensor_type="temperature",
        value=36.5,
        timestamp=now,
        rules=[rule],
    )
    assert len(alerts) == 1
    assert alerts[0]["trigger_value"] == 36.5
    assert alerts[0]["threshold"] == 35.0
    assert alerts[0]["severity"] == "HIGH"
