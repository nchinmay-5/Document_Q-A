"""Django settings, driven entirely by environment variables (see .env.example)."""
from pathlib import Path

from config import env

BASE_DIR = Path(__file__).resolve().parent.parent
env.load_env_file(BASE_DIR)

# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
SECRET_KEY = env.get_str("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
DEBUG = env.get_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env.get_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]"])

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# `retrieval`, `generation` and `qa` are plain Python packages: they hold no
# models, so they do not need to be Django apps.
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "users",
    "documents",
    "ingestion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Database — Postgres in normal use, SQLite for offline unit tests
# --------------------------------------------------------------------------
if env.get_bool("USE_SQLITE", False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env.get_str("POSTGRES_DB", "rag"),
            "USER": env.get_str("POSTGRES_USER", "rag"),
            "PASSWORD": env.get_str("POSTGRES_PASSWORD", "rag"),
            "HOST": env.get_str("POSTGRES_HOST", "localhost"),
            "PORT": env.get_str("POSTGRES_PORT", "5433"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# --------------------------------------------------------------------------
# API — token auth keeps the Streamlit client trivial
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# --------------------------------------------------------------------------
# Static and uploaded files
# --------------------------------------------------------------------------
STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env.get_str("MEDIA_ROOT", str(BASE_DIR / "media")))

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Celery
# --------------------------------------------------------------------------
CELERY_BROKER_URL = env.get_str("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env.get_str("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TASK_ALWAYS_EAGER = env.get_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_TIME_LIMIT = env.get_int("CELERY_TASK_TIME_LIMIT", 1800)

# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------
ALLOWED_UPLOAD_EXTENSIONS = env.get_list("ALLOWED_UPLOAD_EXTENSIONS", ["pdf", "docx", "txt"])
MAX_UPLOAD_SIZE_MB = env.get_int("MAX_UPLOAD_SIZE_MB", 50)
CHUNK_SIZE_CHARS = env.get_int("CHUNK_SIZE_CHARS", 2400)
CHUNK_OVERLAP_CHARS = env.get_int("CHUNK_OVERLAP_CHARS", 300)

# --------------------------------------------------------------------------
# Embeddings
# --------------------------------------------------------------------------
EMBEDDING_BACKEND = env.get_str("EMBEDDING_BACKEND", "sentence_transformers")
EMBEDDING_MODEL = env.get_str("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIMENSIONS = env.get_int("EMBEDDING_DIMENSIONS", 384)
EMBEDDING_BATCH_SIZE = env.get_int("EMBEDDING_BATCH_SIZE", 32)
EMBEDDING_QUERY_PREFIX = env.get_str(
    "EMBEDDING_QUERY_PREFIX", "Represent this sentence for searching relevant passages: "
)

# --------------------------------------------------------------------------
# Elasticsearch
# --------------------------------------------------------------------------
ELASTICSEARCH_URL = env.get_str("ELASTICSEARCH_URL", "http://localhost:9200")
ELASTICSEARCH_USERNAME = env.get_str("ELASTICSEARCH_USERNAME", "")
ELASTICSEARCH_PASSWORD = env.get_str("ELASTICSEARCH_PASSWORD", "")
ELASTICSEARCH_CHUNK_INDEX = env.get_str("ELASTICSEARCH_CHUNK_INDEX", "rag_chunks")
ELASTICSEARCH_REQUEST_TIMEOUT = env.get_int("ELASTICSEARCH_REQUEST_TIMEOUT", 30)

# --------------------------------------------------------------------------
# Retrieval defaults (overridable per request)
# --------------------------------------------------------------------------
RETRIEVAL_MODE = env.get_str("RETRIEVAL_MODE", "hybrid")
RETRIEVAL_DENSE_K = env.get_int("RETRIEVAL_DENSE_K", 30)
RETRIEVAL_BM25_K = env.get_int("RETRIEVAL_BM25_K", 30)
RETRIEVAL_FINAL_K = env.get_int("RETRIEVAL_FINAL_K", 20)
RETRIEVAL_CONTEXT_K = env.get_int("RETRIEVAL_CONTEXT_K", 5)
RRF_K = env.get_int("RRF_K", 60)

# --------------------------------------------------------------------------
# Reranking — the last ordering stage, applied to the retrieved candidates
# --------------------------------------------------------------------------
RERANK_ENABLED = env.get_bool("RERANK_ENABLED", True)
RERANKER_BACKEND = env.get_str("RERANKER_BACKEND", "cross_encoder")
RERANKER_MODEL = env.get_str("RERANKER_MODEL", "BAAI/bge-reranker-base")
RERANKER_BATCH_SIZE = env.get_int("RERANKER_BATCH_SIZE", 16)
RERANK_TOP_K = env.get_int("RERANK_TOP_K", 5)

# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------
LLM_PROVIDER = env.get_str("LLM_PROVIDER", "ollama")
QUERY_REWRITE_ENABLED = env.get_bool("QUERY_REWRITE_ENABLED", True)
QUERY_REWRITE_HISTORY_TURNS = env.get_int("QUERY_REWRITE_HISTORY_TURNS", 4)
LLM_TEMPERATURE = float(env.get_str("LLM_TEMPERATURE", "0.1"))
LLM_MAX_OUTPUT_TOKENS = env.get_int("LLM_MAX_OUTPUT_TOKENS", 800)
CONTEXT_CHAR_BUDGET = env.get_int("CONTEXT_CHAR_BUDGET", 12000)

GEMINI_API_KEY = env.get_str("GEMINI_API_KEY", "")
GEMINI_MODEL = env.get_str("GEMINI_MODEL", "gemini-2.5-flash")

OLLAMA_BASE_URL = env.get_str("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = env.get_str("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = env.get_int("OLLAMA_TIMEOUT", 120)

# --------------------------------------------------------------------------
# Logging — plain console output is enough for a single-node dev stack
# --------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": env.get_str("LOG_LEVEL", "INFO")},
}
