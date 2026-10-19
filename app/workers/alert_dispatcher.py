import asyncio
from typing import Any
from app.core.logging import get_logger

logger = get_logger("workers.alert_dispatcher")


class AlertDispatcherWorker:
    """
    Asynchronous worker responsible for broadcasting generated alerts to external
    channels (e.g. Webhooks, PagerDuty, Slack, Email) without blocking the ingestion path.
    """

    def __init__(self) -> None:
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._process_queue())
        logger.info("alert_dispatcher_worker_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("alert_dispatcher_worker_stopped")

    async def dispatch_alert(self, alert_data: dict[str, Any]) -> None:
        await self.queue.put(alert_data)

    async def _process_queue(self) -> None:
        while self._running:
            try:
                alert_data = await self.queue.get()
                logger.info(
                    "dispatching_alert_notification",
                    alert_id=str(alert_data.get("id")),
                    sensor_id=alert_data.get("sensor_id"),
                    severity=alert_data.get("severity"),
                )
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("alert_dispatch_failed", error=str(exc))
