import operator
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from app.core.logging import get_logger
from app.models.alert_rule import AlertRule
from app.redis.cooldown import CooldownManager
from app.redis.sliding_window import SlidingWindowManager

logger = get_logger("services.rule_engine")

OPERATORS: dict[str, Callable[[float, float], bool]] = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": lambda a, b: abs(a - b) < 1e-5,
    "!=": lambda a, b: abs(a - b) >= 1e-5,
}


class RuleEvaluationEngine:
    def __init__(
        self,
        sliding_window: SlidingWindowManager,
        cooldown_manager: CooldownManager,
    ) -> None:
        self.sliding_window = sliding_window
        self.cooldown_manager = cooldown_manager

    def evaluate_condition(self, value: float, op_str: str, threshold: float) -> bool:
        func = OPERATORS.get(op_str)
        if not func:
            logger.error("invalid_rule_operator", operator=op_str)
            return False
        return func(value, threshold)

    async def evaluate_reading(
        self,
        sensor_id: str,
        sensor_type: str,
        value: float,
        timestamp: datetime,
        rules: list[AlertRule],
    ) -> list[dict[str, Any]]:
        """
        Evaluates a single reading against a list of active rules for that sensor type.
        """
        generated_alerts: list[dict[str, Any]] = []
        epoch_ts = timestamp.timestamp()

        for rule in rules:
            if not rule.enabled or rule.sensor_type != sensor_type:
                continue

            matched = False
            trigger_val = value

            if rule.rule_type == "threshold":
                matched = self.evaluate_condition(value, rule.operator, rule.threshold)

            elif rule.rule_type == "window":
                window_sec = rule.window_seconds or 300
                agg_type = rule.aggregation or "AVG"
                agg_val = await self.sliding_window.get_window_aggregation(
                    sensor_id=sensor_id,
                    sensor_type=sensor_type,
                    window_seconds=window_sec,
                    aggregation=agg_type,
                    now_timestamp=epoch_ts,
                )
                if agg_val is not None:
                    trigger_val = agg_val
                    matched = self.evaluate_condition(agg_val, rule.operator, rule.threshold)

            if matched:
                # Check atomic cooldown to prevent duplicate alert storms
                acquired = await self.cooldown_manager.acquire_cooldown_lock(
                    rule_id=str(rule.id),
                    sensor_id=sensor_id,
                    cooldown_seconds=rule.cooldown_seconds,
                )
                if acquired:
                    logger.info(
                        "alert_triggered",
                        rule_id=str(rule.id),
                        rule_name=rule.name,
                        sensor_id=sensor_id,
                        trigger_value=trigger_val,
                        threshold=rule.threshold,
                        severity=rule.severity,
                    )
                    alert_dict = {
                        "id": uuid.uuid4(),
                        "rule_id": rule.id,
                        "sensor_id": sensor_id,
                        "trigger_value": float(trigger_val),
                        "threshold": float(rule.threshold),
                        "severity": rule.severity,
                        "status": "OPEN",
                        "triggered_at": timestamp,
                    }
                    generated_alerts.append(alert_dict)
                else:
                    logger.debug(
                        "alert_suppressed_by_cooldown",
                        rule_id=str(rule.id),
                        sensor_id=sensor_id,
                    )

        return generated_alerts
