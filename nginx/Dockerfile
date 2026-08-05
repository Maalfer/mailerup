# ⚠️ LEGADO / REFERENCIA — NO es el despliegue actual.
# Desde 2026-06-15 el despliegue es NATIVO: el frontend se compila EN LOCAL y su
# `dist/` se sube por rsync; lo sirve el nginx del host (ver `deploy/README.md`).
# Este Dockerfile se conserva solo como referencia histórica.
#
# MailerUp edge interno: compila el frontend (Vite) y lo sirve con nginx,
# haciendo de proxy hacia el contenedor `web` para la API y endpoints públicos.
# Contexto de build = raíz del repo.

# --- Etapa 1: build del frontend React/Vite ---
FROM node:20-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Etapa 2: nginx sirviendo el dist + proxy ---
FROM nginx:1.27-alpine
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend /app/dist /usr/share/nginx/html
