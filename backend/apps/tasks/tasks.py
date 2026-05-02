from celery import shared_task


@shared_task(name="tasks.debug_echo")
def debug_echo(value="pong"):
    """
    Minimal Celery task used to verify broker, worker, and result backend wiring.
    """
    return {
        "echo": value,
    }
