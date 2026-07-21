# 🛠️ Configuración de Entorno y Setup

## 📋 Prerrequisitos

### Sistema Operativo
- **Windows 10/11** (64-bit) o **macOS 12+** o **Ubuntu 22.04+**
- **RAM:** Mínimo 8GB, recomendado 16GB
- **Disk:** 10GB espacio libre

### Software Requerido
```bash
# Node.js & pnpm
node --version      # >= 20.0.0
pnpm --version      # >= 8.0.0

# Python
python --version    # >= 3.11.0
pip --version       # >= 23.0.0

# Docker
docker --version    # >= 24.0.0
docker-compose --version  # >= 2.20.0

# Git
git --version       # >= 2.40.0

# PostgreSQL (opcional, Docker recomendado)
psql --version      # >= 15.0.0
```

## 🚀 Setup Rápido

### 1. Clonar Repositorio
```bash
git clone https://github.com/organization/evoting-platform.git
cd evoting-platform
```

### 2. Instalar Dependencias Globales
```bash
# Windows (PowerShell)
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Python.Python.3.11
winget install -e --id Docker.DockerDesktop

# macOS
brew install node@20 pnpm python@3.11 docker docker-compose

# Ubuntu
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs pnpm python3.11 python3-pip docker.io docker-compose
```

### 3. Configurar Variables de Entorno
```bash
# Copiar plantilla de entorno
cp .env.example .env.local

# Editar .env.local con tus valores
notepad .env.local  # Windows
nano .env.local     # Linux/macOS
```

### 4. Iniciar Servicios con Docker
```bash
# Iniciar todos los servicios
docker-compose up -d

# Verificar que todos los servicios estén corriendo
docker-compose ps

# Ver logs
docker-compose logs -f
```

### 5. Setup del Proyecto
```bash
# Instalar dependencias
pnpm install

# Configurar base de datos
pnpm db:setup

# Iniciar modo desarrollo
pnpm dev
```

## 🔧 Configuración Manual (Sin Docker)

### Base de Datos PostgreSQL
```bash
# 1. Instalar PostgreSQL
# Windows: https://www.postgresql.org/download/windows/
# macOS: brew install postgresql@15
# Ubuntu: sudo apt install postgresql-15 postgresql-15-postgis

# 2. Crear base de datos
sudo -u postgres psql
CREATE DATABASE evoting_dev;
CREATE USER evoting_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE evoting_dev TO evoting_user;
\c evoting_dev
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
\q
```

### Backend Python
```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno
# Windows
venv\Scripts\activate
# Unix/macOS
source venv/bin/activate

# Instalar dependencias
pip install -r apps/backend/requirements.txt

# Instalar dependencias de desarrollo
pip install -r apps/backend/requirements-dev.txt
```

### Frontend Node.js
```bash
# Instalar pnpm globalmente
npm install -g pnpm

# Instalar dependencias del workspace
pnpm install

# Generar cliente Prisma
pnpm db:generate
```

## 🐳 Docker Compose Configuration

### docker-compose.yml
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: evoting-postgres
    environment:
      POSTGRES_USER: evoting_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-dev_password}
      POSTGRES_DB: evoting_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/docker/database/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U evoting_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: evoting-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  backend:
    build:
      context: ./apps/backend
      dockerfile: Dockerfile.dev
    container_name: evoting-backend
    environment:
      DATABASE_URL: postgresql://evoting_user:${POSTGRES_PASSWORD:-dev_password}@postgres:5432/evoting_dev
      REDIS_URL: redis://redis:6379
      JWT_SECRET: ${JWT_SECRET:-dev_secret}
    ports:
      - "8000:8000"
    volumes:
      - ./apps/backend:/app
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build:
      context: ./apps/frontend
      dockerfile: Dockerfile.dev
    container_name: evoting-frontend
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    ports:
      - "3000:3000"
    volumes:
      - ./apps/frontend:/app
      - /app/node_modules
    depends_on:
      - backend

  pgadmin:
    image: dpage/pgadmin4
    container_name: evoting-pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@evoting.local
      PGADMIN_DEFAULT_PASSWORD: admin123
    ports:
      - "5050:80"
    depends_on:
      - postgres

volumes:
  postgres_data:
  redis_data:
```

### Inicialización de Base de Datos (init.sql)
```sql
-- Habilitar extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Crear esquemas
CREATE SCHEMA IF NOT EXISTS geo;
CREATE SCHEMA IF NOT EXISTS config;

-- Usuario de solo lectura para reporting
CREATE USER readonly WITH PASSWORD 'readonly_password';
GRANT CONNECT ON DATABASE evoting_dev TO readonly;
GRANT USAGE ON SCHEMA public TO readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;
```

## 🔐 Configuración de Seguridad

### Generación de Claves
```bash
# Generar JWT secret
openssl rand -base64 32

# Generar clave de encriptación
openssl rand -base64 32

# Generar secret para MFA
openssl rand -base64 20
```

### Archivo .env.local
```env
# Database
POSTGRES_PASSWORD=your_secure_password_here
DATABASE_URL=postgresql://evoting_user:${POSTGRES_PASSWORD}@localhost:5432/evoting_dev

# Security
JWT_SECRET=your_jwt_secret_base64_here
ENCRYPTION_KEY=your_encryption_key_base64_here
MFA_SECRET=your_mfa_secret_base64_here

# Application
NEXT_PUBLIC_API_URL=http://localhost:8000
API_PORT=8000
NODE_ENV=development

# Features
ENABLE_MFA=true
ENABLE_GEO_SPATIAL=true
ENABLE_PDF_EXPORT=true
ENABLE_AUDIT_LOG=true

# External Services
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM=noreply@evoting.example.com

# Redis
REDIS_URL=redis://localhost:6379

# File Storage
STORAGE_BUCKET=evoting-files
STORAGE_REGION=us-east-1
STORAGE_ENDPOINT=https://storage.example.com
```

## 🧪 Desarrollo

### Comandos de Desarrollo
```bash
# Desarrollo completo
pnpm dev

# Solo frontend
pnpm dev:frontend

# Solo backend
pnpm dev:backend

# Con Docker
docker-compose up -d
pnpm dev:local
```

### Database Migrations
```bash
# Crear nueva migración
pnpm db:migrate:create add_voting_timestamps

# Ejecutar migraciones
pnpm db:migrate

# Revertir última migración
pnpm db:migrate:down

# Estado de migraciones
pnpm db:migrate:status

# Resetear base de datos
pnpm db:reset
```

### Testing
```bash
# Backend tests (Python)
pytest tests/unit/                   # Tests unitarios
pytest tests/integration/            # Tests de integración
pytest tests/ --cov                  # Tests con cobertura
pytest tests/ --cov --cov-report=html # Reporte HTML de cobertura

# Frontend E2E tests
pnpm test:e2e                        # Playwright E2E tests
pnpm test:e2e:ui                     # Playwright con UI
pnpm test:e2e:debug                  # Playwright en modo debug

# Testing completo
pnpm test:all                        # Todos los tests
```

### Linting y Formato
```bash
# Lint completo
pnpm lint

# Lint específico
pnpm lint:frontend
pnpm lint:backend

# Auto-fix lint issues
pnpm lint:fix

# Formatear código
pnpm format

# Verificar formato
pnpm format:check
```

## 🚀 Producción

### Build de Producción
```bash
# Build completo
pnpm build

# Build frontend
pnpm build:frontend

# Build backend
pnpm build:backend

# Docker production build
docker-compose -f docker-compose.prod.yml build
```

### Deployment
```bash
# Kubernetes
kubectl apply -k infra/kubernetes/

# Docker Swarm
docker stack deploy -c docker-compose.prod.yml evoting

# Manual
pnpm start:production
```

### Health Checks
```bash
# API health
curl http://localhost:8000/health

# Frontend health
curl http://localhost:3000/api/health

# Database connection
psql -h localhost -U evoting_user -d evoting_dev -c "SELECT 1"

# Redis connection
redis-cli ping
```

## 🔧 Troubleshooting

### Problemas Comunes

#### 1. PostgreSQL no inicia
```bash
# Verificar que el puerto 5432 esté libre
netstat -ano | findstr :5432  # Windows
lsof -i :5432                 # Unix

# Reiniciar servicio PostgreSQL
sudo service postgresql restart

# Ver logs de PostgreSQL
sudo journalctl -u postgresql -f
```

#### 2. Docker Compose issues
```bash
# Limpiar containers
docker-compose down -v

# Reconstruir imágenes
docker-compose build --no-cache

# Ver logs detallados
docker-compose logs --tail=100 -f
```

#### 3. Dependencias Node.js
```bash
# Limpiar cache de pnpm
pnpm store prune

# Reinstalar dependencias
rm -rf node_modules
pnpm install
```

#### 4. Python virtual env
```bash
# Recrear entorno virtual
rm -rf venv
python -m venv venv
source venv/bin/activate  # Unix
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### Monitoreo de Recursos
```bash
# Uso de memoria
docker stats

# Logs en tiempo real
docker-compose logs -f --tail=50

# Estado de servicios
docker-compose ps
docker-compose top
```

## 📚 Recursos Adicionales

### Documentación Oficial
- [Next.js Documentation](https://nextjs.org/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Prisma Documentation](https://www.prisma.io/docs/)
- [PostGIS Documentation](https://postgis.net/documentation/)
- [Docker Documentation](https://docs.docker.com/)

### Herramientas Recomendadas
- **VS Code Extensions:**
  - ESLint
  - Prettier
  - Python
  - Docker
  - PostgreSQL
- **Database Clients:**
  - pgAdmin (Docker)
  - DBeaver
  - TablePlus
- **API Testing:**
  - Postman
  - Insomnia
  - Thunder Client (VS Code)

### Soporte
- **Issues:** GitHub Issues
- **Discusión:** GitHub Discussions
- **Chat:** Slack/Discord (canal #evoting-platform)
- **Documentación:** `/docs` folder

---

**Responsable:** Otto (Dependency and Release Engineer)  
**Última actualización:** 2026-07-21  
**Próxima revisión:** 2026-08-21
