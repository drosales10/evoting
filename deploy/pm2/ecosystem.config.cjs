/**
 * PM2 — eVoting (API FastAPI + frontend Next.js)
 *
 * Uso (desde la raíz del repo en el servidor):
 *   pm2 start deploy/pm2/ecosystem.config.cjs
 *   pm2 save
 *   pm2 startup
 *
 * Ajusta APP_ROOT si el clone no está en /var/www/html/evoting.
 */
const APP_ROOT = process.env.EVOTING_APP_ROOT || "/var/www/html/evoting";

module.exports = {
  apps: [
    {
      name: "evoting-api",
      cwd: `${APP_ROOT}/apps/backend`,
      script: `${APP_ROOT}/apps/backend/.venv/bin/uvicorn`,
      args: "app.main:app --host 127.0.0.1 --port 8000 --workers 2",
      interpreter: "none",
      env: {
        NODE_ENV: "production",
      },
      max_memory_restart: "512M",
      time: true,
      autorestart: true,
    },
    {
      name: "evoting-web",
      cwd: `${APP_ROOT}/apps/frontend`,
      script: "node_modules/next/dist/bin/next",
      args: "start -H 127.0.0.1 -p 3000",
      interpreter: "node",
      env: {
        NODE_ENV: "production",
        PORT: "3000",
      },
      max_memory_restart: "512M",
      time: true,
      autorestart: true,
    },
  ],
};
