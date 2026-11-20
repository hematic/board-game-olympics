import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name: str) -> list[str]:
    return [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()]


SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = ["127.0.0.1", *env_list("DJANGO_ALLOWED_HOSTS")]
POCKET_ID_ISSUER = os.environ["POCKET_ID_ISSUER"]
ORGANIZER_SUBJECTS = frozenset(env_list("OLYMPICS_ORGANIZER_SUBJECTS"))
BGG_API_TOKEN = os.environ.get("BGG_API_TOKEN", "")

INSTALLED_APPS = ["olympics"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "olympics.identity.ProxyIdentityMiddleware",
]
ROOT_URLCONF = "olympics.urls"
WSGI_APPLICATION = "olympics.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("OLYMPICS_DB_PATH", BASE_DIR / "olympics.sqlite3"),
        "OPTIONS": {"timeout": 10, "transaction_mode": "IMMEDIATE"},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
CSRF_COOKIE_SECURE = True
SECURE_REFERRER_POLICY = "same-origin"
