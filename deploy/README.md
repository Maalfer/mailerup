# Despliegue NATIVO (sin Docker)

Desde 2026-06-15 MailerUp se ejecuta de forma nativa sobre la VPS (no con Docker).
Esta carpeta contiene los ficheros de referencia de ese despliegue.

| Fichero | Destino en la VPS | Qué es |
|---|---|---|
| `mailerup.service` | `/etc/systemd/system/mailerup.service` | Servicio systemd que corre la app (uvicorn ASGI, 1 worker, puerto 8100) |
| `newsletter.example.com` | `/etc/nginx/sites-available/newsletter.example.com` | Vhost nginx del host: sirve el SPA (`dist`) y hace proxy a uvicorn |

## Arquitectura

```
Cloudflare (TLS) ──► nginx del HOST (443) ──┬─ /                → /var/www/mailerup/dist (SPA)
                                            └─ /api /admin /static
                                               /u /o /c /oa /ca
                                               /subscribe /verify-subscription
                                               /recurso          ──► 127.0.0.1:8100 (uvicorn)
                                                                       │
                                                          systemd: mailerup.service
                                                                       │
                                                          PostgreSQL 16 nativo (127.0.0.1:5432)
```

- **Python**: venv en `/opt/mailerup/backend/venv` (Python 3.12, Django 6).
- **DB**: PostgreSQL 16 nativo. Conexión por `DATABASE_URL` en `backend/.env`.
- **SMTP**: Postfix del host (`SMTP_HOST=127.0.0.1`).
- **Estáticos**: whitenoise (vía uvicorn). **Media**: `/opt/mailerup/backend/media/`.

## Instalación desde cero (resumen)

```bash
# 1. PostgreSQL
sudo apt-get install -y postgresql postgresql-client
sudo -u postgres psql -c "CREATE ROLE mailerup LOGIN PASSWORD '...';"
sudo -u postgres createdb -O mailerup mailerup
#   (restaurar dump si migras: pg_restore -d mailerup backup.dump)

# 2. App
cd /opt/mailerup/backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
#   backend/.env: DATABASE_URL=postgres://mailerup:...@127.0.0.1:5432/mailerup, SMTP_HOST=127.0.0.1, ...
DJANGO_SETTINGS_MODULE=mailerup.settings.production venv/bin/python manage.py migrate
DJANGO_SETTINGS_MODULE=mailerup.settings.production venv/bin/python manage.py collectstatic --noinput

# 3. Servicio
sudo install -m 644 deploy/mailerup.service /etc/systemd/system/mailerup.service
sudo systemctl daemon-reload && sudo systemctl enable --now mailerup

# 4. Frontend (COMPILAR EN LOCAL, nunca en la VPS)
#   en tu máquina:
cd frontend && npm ci && npm run build
rsync -az --delete frontend/dist/ usuario@vps:/var/www/mailerup/dist/

# 5. nginx
sudo install -m 644 deploy/newsletter.example.com /etc/nginx/sites-available/newsletter.example.com
sudo ln -s ../sites-available/newsletter.example.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## Actualizaciones

- **Backend**: `bash /opt/mailerup/update.sh` (git pull → pip → migrate → collectstatic → restart).
- **Frontend**: build local + `rsync` del `dist/` (ver arriba). **Nunca compilar Vite en la VPS** (1 GB de RAM → OOM).

> ⚠️ La VPS tiene 1 GB de RAM y un swapfile de 2 GB (`/swapfile`). El build del frontend
> se hace fuera de la máquina por eso.
