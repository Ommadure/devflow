"""The Taskiq broker and scheduler (ADR 0003).

Run the worker:     taskiq worker app.workers.broker:broker app.workers.tasks
Run the scheduler:  taskiq scheduler app.workers.broker:scheduler app.workers.tasks

Exactly ONE scheduler may run: two would fire every scheduled job twice.

RedisStreamBroker uses Redis Streams with a consumer group: a message is acknowledged only
after its task finishes, and one left unacknowledged (the worker died mid-task) is handed
to another worker after `idle_timeout`. That is at-least-once delivery, so every task must
be safe to run twice — ours are (content hashes, conditional updates).
"""

from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import RedisStreamBroker

from app.core.config import get_settings

broker = RedisStreamBroker(
    url=get_settings().redis_url or "redis://localhost:6379/0",
    queue_name="devflow:jobs",
    consumer_group_name="devflow-workers",
    idle_timeout=10 * 60 * 1000,  # ms: longer than any job, or a slow job gets redelivered
)

# Cron schedules are declared on the tasks themselves (`schedule=[...]`).
scheduler = TaskiqScheduler(broker, sources=[LabelScheduleSource(broker)])
