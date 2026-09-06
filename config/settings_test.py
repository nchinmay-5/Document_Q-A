"""Settings for the test suite: no Postgres, no Redis, no Elasticsearch, no LLM.

pytest.ini points DJANGO_SETTINGS_MODULE here so the overrides are in place
before Django loads.
"""
from config.settings import *  # noqa: F401,F403
from config.settings import BASE_DIR

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Uploads land in a project-local directory instead of the system temp dir.
MEDIA_ROOT = BASE_DIR / ".test_media"

LLM_PROVIDER = "stub"
RERANKER_BACKEND = "identity"
QUERY_REWRITE_ENABLED = True
CELERY_TASK_ALWAYS_EAGER = True
