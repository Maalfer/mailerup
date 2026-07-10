from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "django_celery_beat",
    "django_celery_results",
    # local
    "apps.accounts",
    "apps.subscribers",
    "apps.campaigns",
    "apps.analytics",
    "apps.forms",
    "apps.automations",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mailerup.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "mailerup.wsgi.application"
ASGI_APPLICATION = "mailerup.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3")
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-es"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.CookieJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    # Throttling por ámbito: solo afecta a las vistas que declaran `throttle_scope`
    # (login y alta pública). No limita el resto de la API autenticada, donde hay
    # operaciones masivas legítimas (import/export de suscriptores, etc.).
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",            # frena fuerza bruta / credential stuffing
        "subscribe": "30/min",        # frena abuso del formulario público de alta
        "api_subscribe": "60/min",    # alta vía API key externa, por key
        "api_subscribe_ip": "120/min",  # tope por IP (pre-auth) del endpoint por-key
    },
}

# JWT
from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# Security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Celery
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Europe/Madrid"

# URL pública para enlaces que se incrustan en los emails (baja, tracking, etc.)
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", default="http://localhost:8000")

# --- Envío progresivo de campañas -------------------------------------------
# El scheduler in-process envía como mucho CAMPAIGN_SEND_BATCH_SIZE correos cada
# CAMPAIGN_SEND_INTERVAL_SECONDS segundos, repartiendo listas grandes en el
# tiempo para no saturar al proveedor SMTP/API ni provocar bloqueos.
# Por defecto conservador: 5 correos / 60s = 300/hora. El SMTP de hosting
# compartido (Raiola, IONOS, Gmail…) suele tener límites bajos; mantenlo lento.
# Súbelo solo si tu proveedor permite más volumen por hora.
CAMPAIGN_SEND_BATCH_SIZE = env.int("CAMPAIGN_SEND_BATCH_SIZE", default=5)
CAMPAIGN_SEND_INTERVAL_SECONDS = env.int("CAMPAIGN_SEND_INTERVAL_SECONDS", default=60)
# Pon a "1" en los procesos web para que NO arranquen el scheduler (útil al
# escalar a varios workers: deja un único proceso dedicado al scheduler).
DISABLE_SCHEDULER = env.bool("MAILERUP_DISABLE_SCHEDULER", default=False)

# Email provider (Brevo or SendGrid)
EMAIL_PROVIDER = env("EMAIL_PROVIDER", default="brevo")
BREVO_API_KEY = env("BREVO_API_KEY", default="")
SENDGRID_API_KEY = env("SENDGRID_API_KEY", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@mailerup.com")
DEFAULT_FROM_NAME = env("DEFAULT_FROM_NAME", default="MailerUp")

# CORS
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:5173"])

# CSRF trusted origins (needed for the Django admin login behind HTTPS/proxy).
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Spectacular (OpenAPI)
SPECTACULAR_SETTINGS = {
    "TITLE": "MailerUp API",
    "DESCRIPTION": "Email marketing platform API",
    "VERSION": "1.1.1",
}
