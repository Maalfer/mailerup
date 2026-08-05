# ⚠️ LEGADO / REFERENCIA — NO es el despliegue actual.
# Desde 2026-06-15 MailerUp se despliega de forma NATIVA (systemd + uvicorn +
# PostgreSQL + nginx del host); ver `deploy/README.md`. Este Dockerfile y el
# resto de ficheros Docker (docker-compose.yml, nginx/Dockerfile, DOCKER.md) se
# conservan solo como referencia histórica.
#
# MailerUp backend — Django + uvicorn (ASGI)
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=mailerup.settings.production

WORKDIR /app

# Dependencias del sistema mínimas (psycopg[binary] y Pillow traen wheels;
# postgresql-client aporta pg_isready/psql para diagnóstico).
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

EXPOSE 8100
ENTRYPOINT ["/app/entrypoint.sh"]
