#!/usr/bin/env bash
# Despliegue / redeploy de la app (ejecutar como el usuario dueño del repo).
# Uso desde la raíz del clone:
#   bash deploy/scripts/deploy-app.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Falta .env en $ROOT — copia deploy/env.production.example y completa secretos."
  exit 1
fi

# Cargar .env para el build (NEXT_PUBLIC_*) y para Alembic.
# Requiere valores JSON entre comillas simples (ver env.production.example).
set -a
# shellcheck disable=SC1091
source ./.env
set +a

echo "==> Dependencias Node"
corepack enable
pnpm install --frozen-lockfile

echo "==> Build frontend"
pnpm build:frontend

echo "==> venv Python + dependencias"
cd apps/backend
# Si un intento anterior falló (sin ensurepip), limpia el venv roto.
if [[ -d .venv ]] && [[ ! -x .venv/bin/pip ]]; then
  echo "venv incompleto detectado; recreando..."
  rm -rf .venv
fi
if [[ ! -d .venv ]]; then
  if ! python3.12 -m venv .venv; then
    echo "ERROR: no se pudo crear el venv."
    echo "En el servidor ejecuta: sudo apt-get install -y python3.12-venv python3.12-dev"
    echo "Luego: rm -rf apps/backend/.venv && bash deploy/scripts/deploy-app.sh"
    exit 1
  fi
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -e .

echo "==> Migraciones Alembic"
alembic upgrade head
deactivate
cd "$ROOT"

echo "==> Reiniciar PM2"
if pm2 describe evoting-api >/dev/null 2>&1; then
  pm2 reload deploy/pm2/ecosystem.config.cjs --update-env
else
  pm2 start deploy/pm2/ecosystem.config.cjs
fi
pm2 save

echo "OK. Health: curl -fsS https://evoting.dennyrosales.com/health"
