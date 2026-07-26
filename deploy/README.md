# Despliegue DigitalOcean — eVoting (`evoting.dennyrosales.com`)

Droplet ya preparado: **nginx**, **PostgreSQL**, **firewall**, **PM2**.  
Cloudflare se configura **al final** (DNS/proxy naranja después de validar SSL en origen).

Arquitectura (mismo origen, obligatorio por cookies `SameSite=strict`):

```
Internet → nginx :443
            ├─ /api/*, /health*  → 127.0.0.1:8000  (uvicorn / FastAPI)
            └─ /*                → 127.0.0.1:3000  (Next.js)
```

Archivos de este directorio:

| Archivo | Uso |
|---------|-----|
| `nginx/evoting.dennyrosales.com.conf` | Virtual host HTTP (Certbot añade TLS) |
| `pm2/ecosystem.config.cjs` | Procesos `evoting-api` + `evoting-web` |
| `env.production.example` | Plantilla de `.env` |
| `scripts/setup-server.sh` | Python 3.12, pnpm, PostGIS, Certbot |
| `scripts/deploy-app.sh` | Install, build, migrate, reload PM2 |

---

## 0. DNS (antes de Certbot)

En el panel DNS (o temporalmente en el registrador, **sin** proxy Cloudflare aún):

| Tipo | Nombre | Valor |
|------|--------|--------|
| A | `evoting` | IP pública del droplet |

Espera propagación (`dig +short evoting.dennyrosales.com`).  
**Importante:** deja el registro en **DNS only** (nube gris) hasta tener el certificado y la app respondiendo; luego activas Cloudflare.

---

## 1. Preparar el servidor

```bash
ssh root@TU_IP_DROPLET
# o usuario con sudo

cd /tmp
# Si el repo aún no está en el servidor, clónalo primero en /var/www/html/evoting
git clone TU_REPO_URL /var/www/html/evoting
cd /var/www/html/evoting
sudo bash deploy/scripts/setup-server.sh
```

---

## 2. PostgreSQL + PostGIS

```bash
sudo -u postgres psql <<'SQL'
CREATE USER evoting WITH PASSWORD 'CAMBIAR_PASSWORD_FUERTE';
CREATE DATABASE evoting OWNER evoting;
\c evoting
CREATE EXTENSION IF NOT EXISTS postgis;
GRANT ALL ON SCHEMA public TO evoting;
SQL
```

Verifica:

```bash
sudo -u postgres psql -d evoting -c "SELECT PostGIS_Version();"
```

---

## 3. Variables de entorno

```bash
cd /var/www/html/evoting
cp deploy/env.production.example .env
nano .env
```

Generar secretos:

```bash
openssl rand -hex 32   # JWT_SECRET
python3.12 -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"  # MFA_ENCRYPTION_KEY
```

Valores críticos:

- `DATABASE_URL=postgresql+asyncpg://evoting:...@127.0.0.1:5432/evoting`
- `ENVIRONMENT=production`
- `SECURE_COOKIES=true`
- `VOTER_TEST_MODE=false`
- `CORS_ORIGINS=["https://evoting.dennyrosales.com"]`
- `NEXT_PUBLIC_API_URL=https://evoting.dennyrosales.com`
- `APP_PUBLIC_URL=https://evoting.dennyrosales.com`

---

## 4. Nginx (HTTP primero)

```bash
sudo cp /var/www/html/evoting/deploy/nginx/evoting.dennyrosales.com.conf \
  /etc/nginx/sites-available/evoting.dennyrosales.com.conf
sudo ln -sf /etc/nginx/sites-available/evoting.dennyrosales.com.conf \
  /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Firewall (si UFW):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw status
```

---

## 5. Primera build + PM2

```bash
cd /var/www/html/evoting
bash deploy/scripts/deploy-app.sh
pm2 status
curl -fsS http://127.0.0.1:8000/health
curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000/
```

Seed del primer admin (opcional, con `SEED_ADMIN_*` en `.env`):

```bash
cd /var/www/html/evoting/apps/backend
source .venv/bin/activate
set -a && source ../../.env && set +a
python -m scripts.seed_admin
# Luego vacía SEED_ADMIN_PASSWORD del .env
```

---

## 6. Certificado SSL (Let's Encrypt)

Con el DNS A apuntando al droplet y el puerto 80 abierto:

```bash
sudo certbot --nginx -d evoting.dennyrosales.com
```

Renovación automática (systemd timer de certbot suele quedar activo):

```bash
sudo certbot renew --dry-run
```

Comprueba:

```bash
curl -fsS https://evoting.dennyrosales.com/health
curl -fsS -o /dev/null -w "%{http_code}\n" https://evoting.dennyrosales.com/
```

---

## 7. Cloudflare (al final)

1. Añade el dominio / subdominio si aún no está.
2. Registro **A** `evoting` → IP del droplet.
3. Activa proxy (nube naranja) cuando HTTPS en origen ya funcione.
4. SSL/TLS mode: **Full (strict)** (origen con certificado válido de Let's Encrypt).
5. No uses “Flexible”.
6. Opcional: regla de caché *Bypass* para `/api/*` y rutas de login/voto.

---

## Redeploy

```bash
cd /var/www/html/evoting
git pull
bash deploy/scripts/deploy-app.sh
```

Si cambias `NEXT_PUBLIC_*`, el script ya hace `pnpm build:frontend` (necesario: esas vars se embeben en el build).

---

## Checklist rápido post-deploy

- [ ] `https://evoting.dennyrosales.com/health` → `ok`
- [ ] `https://evoting.dennyrosales.com/health/ready` → DB reachable
- [ ] Login admin / OTP (correo real, no test mode)
- [ ] Cookies `Secure` en DevTools
- [ ] PostGIS OK (geovisor / territorio si aplica)
- [ ] Backup DB programado (`docs/Production_Ops.md`)
