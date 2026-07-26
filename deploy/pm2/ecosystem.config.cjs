/**
 * PM2 — eVoting (API FastAPI + frontend Next.js)
 *
 * Uso (desde la raíz del repo en el servidor):
 *   pm2 start deploy/pm2/ecosystem.config.cjs
 *   pm2 save
 *   pm2 startup
 *
 * La API carga variables desde `$APP_ROOT/.env` en cada start/restart
 * (SMTP_FROM, MAILTRAP_*, DATABASE_URL, etc.). Edita solo ese archivo
 * y luego: `pm2 restart evoting-api --update-env` + `pm2 save`.
 *
 * Ajusta APP_ROOT si el clone no está en /var/www/html/evoting.
 */
const fs = require("fs");
const path = require("path");

const APP_ROOT = process.env.EVOTING_APP_ROOT || "/var/www/html/evoting";

function loadEnvFile(filePath) {
  const env = {};
  if (!fs.existsSync(filePath)) {
    return env;
  }
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) {
      continue;
    }
    const eq = line.indexOf("=");
    if (eq <= 0) {
      continue;
    }
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

const rootEnv = loadEnvFile(path.join(APP_ROOT, ".env"));

module.exports = {
  apps: [
    {
      name: "evoting-api",
      cwd: `${APP_ROOT}/apps/backend`,
      script: `${APP_ROOT}/apps/backend/.venv/bin/uvicorn`,
      args: "app.main:app --host 127.0.0.1 --port 8000 --workers 2",
      interpreter: "none",
      env: {
        ...rootEnv,
        NODE_ENV: "production",
        // Temporal: poner "true" cuando MFA esté operativo de nuevo
        ADMIN_MFA_REQUIRED: "false",
      },
      max_memory_restart: "512M",
      time: true,
      autorestart: true,
    },
    {
      name: "evoting-web",
      cwd: `${APP_ROOT}/apps/frontend`,
      script: "node_modules/next/dist/bin/next",
      // 3000 suele estar ocupado por otras apps del droplet (p. ej. denny-nextjs)
      args: "start -H 127.0.0.1 -p 3001",
      interpreter: "node",
      env: {
        NODE_ENV: "production",
        PORT: "3001",
      },
      max_memory_restart: "512M",
      time: true,
      autorestart: true,
    },
  ],
};
