#!/usr/bin/env bash
# MailerUp — script de actualización (despliegue NATIVO, sin Docker)
#
# Sincroniza el BACKEND con el repo y reinicia el servicio systemd, aplicando
# migraciones y estáticos. NO toca la base de datos (Postgres nativo persiste).
#
# IMPORTANTE: el FRONTEND no se compila aquí. Con 1 GB de RAM el build de Vite
# agota la memoria y cuelga la VPS. Compílalo en tu máquina y sube el dist:
#     cd frontend && npm ci && npm run build
#     rsync -az --delete frontend/dist/ usuario@vps:/opt/mailerup/frontend/dist/
#
# El servidor MCP (mcp/) es tooling de CLIENTE (se ejecuta donde corre Claude,
# no en la VPS): este script NO lo instala ni lo arranca. Ver mcp/README.md.
#
# Uso:  bash update.sh [opciones]
#   --branch NAME   Rama a desplegar (por defecto: la rama actual, o main)
#   --no-backup     No hacer copia (pg_dump) de la base de datos antes de actualizar
#   --no-git        No tocar git (solo pip/migrate/collectstatic/restart)
#   --no-pip        Saltar pip install (úsalo si no cambió requirements.txt)
#   -h | --help     Muestra esta ayuda
#
set -euo pipefail

APP_DIR="/opt/mailerup"
BACKEND_DIR="$APP_DIR/backend"
VENV="$BACKEND_DIR/.venv"
SERVICE="mailerup"
SETTINGS="mailerup.settings.production"
DB_NAME="mailerup"
DB_USER="mailerup"
DB_HOST="127.0.0.1"

BRANCH=""
DO_BACKUP=1
DO_GIT=1
DO_PIP=1

while [ $# -gt 0 ]; do
  case "$1" in
    --branch) BRANCH="$2"; shift 2 ;;
    --no-backup) DO_BACKUP=0; shift ;;
    --no-git) DO_GIT=0; shift ;;
    --no-pip) DO_PIP=0; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Opción desconocida: $1"; exit 1 ;;
  esac
done

cd "$BACKEND_DIR"
export DJANGO_SETTINGS_MODULE="$SETTINGS"

if [ "$DO_BACKUP" -eq 1 ]; then
  mkdir -p "$APP_DIR/backups"
  TS=$(date +%F_%H%M%S)
  echo "[update] Backup de la BD → backups/mailerup_$TS.dump"
  pg_dump -Fc -h "$DB_HOST" -U "$DB_USER" "$DB_NAME" > "$APP_DIR/backups/mailerup_$TS.dump"
fi

if [ "$DO_GIT" -eq 1 ]; then
  cd "$APP_DIR"
  CUR_BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)}"
  echo "[update] git pull (rama $CUR_BRANCH)"
  git fetch origin --quiet
  git checkout "$CUR_BRANCH" --quiet
  git pull --ff-only origin "$CUR_BRANCH"
  cd "$BACKEND_DIR"
fi

if [ "$DO_PIP" -eq 1 ]; then
  echo "[update] pip install -r requirements.txt"
  "$VENV/bin/pip" install -q -r requirements.txt
fi

echo "[update] migrate"
"$VENV/bin/python" manage.py migrate --noinput

echo "[update] collectstatic"
"$VENV/bin/python" manage.py collectstatic --noinput

echo "[update] check"
"$VENV/bin/python" manage.py check

echo "[update] reiniciando servicio $SERVICE"
sudo systemctl restart "$SERVICE"
sleep 2
systemctl is-active "$SERVICE"

echo "[update] health check"
curl -s -o /dev/null -w "  api/analytics/overview -> %{http_code} (401 sin auth = OK)\n" \
  -H 'X-Forwarded-Proto: https' http://127.0.0.1:8100/api/analytics/overview/

echo "[update] Hecho. (Recuerda: el frontend se compila en local y se sube el dist/.)"
