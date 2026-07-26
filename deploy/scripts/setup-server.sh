#!/usr/bin/env bash
# Preparación del droplet (Ubuntu 22.04/24.04). Ejecutar como root o con sudo.
# Uso: sudo bash deploy/scripts/setup-server.sh
set -euo pipefail

echo "==> Node.js 20 + pnpm"
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
corepack enable
corepack prepare pnpm@10.4.1 --activate

echo "==> Python 3.12 + venv + build deps"
apt-get update
apt-get install -y software-properties-common
# En Ubuntu 24.04 python3.12 suele venir por defecto; en 22.04 puede hacer falta deadsnakes.
if ! command -v python3.12 >/dev/null 2>&1; then
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update
  apt-get install -y python3.12 python3.12-venv python3.12-dev
fi
apt-get install -y build-essential libpq-dev

echo "==> PostGIS (extensión para migraciones geo)"
PG_VER="$(psql --version 2>/dev/null | grep -oE '[0-9]+' | head -1 || true)"
if [[ -n "${PG_VER}" ]]; then
  apt-get install -y "postgresql-${PG_VER}-postgis-3" || apt-get install -y postgresql-postgis || true
else
  apt-get install -y postgresql-postgis || true
fi

echo "==> Certbot (Let's Encrypt)"
apt-get install -y certbot python3-certbot-nginx

echo "==> Directorio de la app"
mkdir -p /var/www/html/evoting
chown -R "${SUDO_USER:-root}:${SUDO_USER:-root}" /var/www/html/evoting

echo "Listo. Siguiente: clonar repo en /var/www/html/evoting y seguir deploy/README.md"
