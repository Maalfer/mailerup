#!/usr/bin/env bash
# Instala el servidor MCP de MailerUp en un venv local.
# Uso:  bash setup.sh
set -euo pipefail

cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
echo "==> Creando venv en .venv (con $($PY --version))"
"$PY" -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
echo "==> Instalando dependencias (mcp, httpx)"
./.venv/bin/pip install --quiet -r requirements.txt

echo
echo "Listo. Binario del servidor:"
echo "  $(pwd)/.venv/bin/python -m mailerup_mcp"
echo
echo "Prueba de humo (lista de herramientas):"
./.venv/bin/python -c "from mailerup_mcp.server import mcp; import asyncio; print(len(asyncio.run(mcp.list_tools())), 'herramientas registradas')"
