"""Expose the Celery app so `celery -A config` and shared_task both find it."""
from config.celery import app as celery_app

__all__ = ["celery_app"]
