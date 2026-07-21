# 🚀 Configuración Técnica del Proyecto

## Stack Tecnológico Principal

### Frontend
- **Framework:** Next.js 16.2.62+ (App Router)
- **Lenguaje:** TypeScript 5+
- **Estilos:** TailwindCSS + CSS Modules
- **UI Components:** Shadcn UI + Radix UI primitives
- **Iconos:** Lucide React Icons
- **Notificaciones:** `sileo` (librería personalizada)
- **Mapas:** Leaflet + React-Leaflet
- **PDFs:** `@react-pdf/renderer`
- **Cifrado:** Web Crypto API (nativo del navegador)

### Backend
- **Framework:** FastAPI (Python 3.11+)
- **Base de datos:** PostgreSQL 15+ con PostGIS
- **ORM:** Prisma Client (TypeScript)
- **Autenticación:** JWT tokens + MFA (OTP/TOTP)
- **Cifrado:** PyCryptodome / cryptography
- **Validación:** Pydantic v2

### Infraestructura
- **Contenedores:** Docker + Docker Compose
- **Orquestación:** Kubernetes (producción)
- **CI/CD:** GitHub Actions
- **Monitoreo:** Prometheus + Grafana
- **Logs:** ELK Stack (Elasticsearch, Logstash, Kibana)

### Herramientas de Desarrollo
- **Package Manager:** pnpm (frontend) + pip/uv (backend)
- **Linting:** ESLint + Prettier (frontend) + Ruff + Black (backend)
- **Testing:** pytest + pytest-cov + pytest-asyncio (backend) + Playwright (E2E frontend)
- **Type Checking:** TypeScript strict mode (frontend) + mypy (backend)
- **Build Tool:** Turbopack (dev frontend) + Webpack (prod frontend) + uvicorn (backend)

## Versiones Específicas

```json
{
  "node": ">=20.0.0",
  "python": ">=3.12.0",
  "postgresql": ">=15.0.0",
  "docker": ">=24.0.0"
}
```

## Dependencias Clave

### Frontend (package.json)
```json
{
  "dependencies": {
    "next": "^16.6.62",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "tailwindcss": "^3.4.0",
    "@radix-ui/react-*": "latest",
    "lucide-react": "^0.344.0",
    "leaflet": "^1.9.0",
    "react-leaflet": "^4.10.0",
    "@react-pdf/renderer": "^3.0.0",
    "zod": "^3.22.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/react": "^19.0.0",
    "typescript": "^5.0.0",
    "eslint": "^9.0.0",
    "prettier": "^3.0.0",
    "@playwright/test": "^1.40.0"
  }
}
```

### Backend (requirements.txt)
```txt
# Core
fastapi==0.104.0
uvicorn[standard]==0.24.0
pydantic==2.5.0
sqlalchemy==2.0.0
psycopg2-binary==2.9.0

# Security
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
cryptography==41.0.0

# Utilities
python-multipart==0.0.6
redis==5.0.0
celery==5.3.0

# Testing
pytest==7.4.0
pytest-cov==4.1.0
pytest-asyncio==0.21.0
httpx==0.25.0
factory-boy==3.3.0
freezegun==1.2.2

# Development
ruff==0.1.0
black==23.9.0
mypy==1.5.0
pre-commit==3.5.0
```

## Configuración de Base de Datos

### PostgreSQL Extensions
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
```

### Connection Pool
```yaml
database:
  max_connections: 20
  pool_size: 10
  timeout: 30
  statement_timeout: 10000
```

## Variables de Entorno

### Desarrollo (.env.local)
```env
# Database
DATABASE_URL="postgresql://user:password@localhost:5432/evoting"
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="Pal095ckX,."
POSTGRES_DB="evoting"

# Security
JWT_SECRET="dev_jwt_secret_key_here"
ENCRYPTION_KEY="dev_encryption_key_32_bytes"
MFA_SECRET="dev_mfa_secret"

# Application
NEXT_PUBLIC_API_URL="http://localhost:3000/api"
API_PORT=8000
NODE_ENV="development"

# Features
ENABLE_MFA=true
ENABLE_GEO_SPATIAL=true
ENABLE_PDF_EXPORT=true
```

### Producción (.env.production)
```env
# Database
DATABASE_URL=${PRODUCTION_DB_URL}
POSTGRES_USER=${PRODUCTION_DB_USER}
POSTGRES_PASSWORD=${PRODUCTION_DB_PASSWORD}
POSTGRES_DB="evoting_prod"

# Security (managed by secrets manager)
JWT_SECRET=${JWT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
MFA_SECRET=${MFA_SECRET}

# Application
NEXT_PUBLIC_API_URL="https://api.evoting.example.com"
API_PORT=8080
NODE_ENV="production"

# Features
ENABLE_MFA=true
ENABLE_GEO_SPATIAL=true
ENABLE_PDF_EXPORT=true
```

## Configuración de Seguridad

### JWT Tokens
```yaml
jwt:
  algorithm: "HS256"
  access_token_expire_minutes: 15
  refresh_token_expire_days: 7
  issuer: "evoting-system"
  audience: "evoting-clients"
```

### Rate Limiting
```yaml
rate_limit:
  requests_per_minute: 60
  voting_requests_per_hour: 1
  auth_requests_per_minute: 10
```

### CORS Configuration
```yaml
cors:
  origins:
    - "http://localhost:3000"
    - "https://evoting.example.com"
  methods: ["GET", "POST", "PUT", "DELETE", "PATCH"]
  headers: ["Content-Type", "Authorization"]
  credentials: true
```

## Estructura de Monorepo

```
evoting-platform/
├── apps/
│   ├── frontend/          # Next.js application
│   └── backend/           # FastAPI application
├── packages/
│   ├── shared/            # Shared types and utilities
│   ├── database/          # Prisma schema and client
│   └── crypto/            # Cryptographic utilities
├── infra/
│   ├── docker/
│   ├── kubernetes/
│   └── terraform/
└── docs/
    ├── api/
    └── architecture/
```

## Scripts de Desarrollo

### Frontend
```bash
pnpm dev              # Development server
pnpm build            # Production build
pnpm lint             # Lint code
pnpm test:e2e         # Run E2E tests con Playwright
```

### Backend
```bash
python -m uvicorn main:app --reload  # Development server
pytest                                # Run tests unitarios/integración
pytest --cov                          # Tests con cobertura
pytest tests/ -xvs                    # Tests verbosos con stop on failure
black .                               # Formatear código Python
ruff check .                          # Linting Python
ruff format .                         # Formatear con ruff
mypy .                                # Type checking Python
pre-commit run --all-files            # Ejecutar pre-commit hooks
```

### Database
```bash
pnpm db:generate      # Generate Prisma client
pnpm db:migrate       # Run migrations
pnpm db:seed          # Seed database
pnpm db:studio        # Open Prisma Studio
```

### Testing Completo
```bash
# Backend testing
pytest tests/unit/                   # Tests unitarios
pytest tests/integration/            # Tests de integración
pytest tests/ --cov --cov-report=html # Tests con reporte HTML

# Frontend E2E testing
pnpm test:e2e                         # Playwright E2E tests
pnpm test:e2e:ui                      # Playwright con UI
pnpm test:e2e:debug                   # Playwright en modo debug

# Testing completo del sistema
pnpm test:all                         # Ejecuta todos los tests
```

## Convenciones de Git

### Branch Naming
```
feature/description    # New features
bugfix/description     # Bug fixes
hotfix/description     # Critical fixes
release/x.y.z         # Release branches
```

### Commit Messages
```
feat: add voting wizard
fix: resolve auth token expiration
chore: update dependencies
docs: update API documentation
test: add unit tests for ballot encryption
```

## 🧪 Estrategia de Testing

### Backend (Python)
- **pytest**: Framework principal de testing
- **pytest-cov**: Cobertura de código
- **pytest-asyncio**: Testing de código asíncrono
- **httpx**: Cliente HTTP para testing de APIs
- **factory-boy**: Factories para crear datos de prueba
- **freezegun**: Congelar tiempo para testing

### Frontend
- **Playwright**: Testing E2E y de integración
- **ESLint**: Linting y validación de código
- **TypeScript**: Type checking en tiempo de compilación

### Quality Gates

Cada PR debe pasar:
1. ✅ **Lint**: ESLint/Prettier (frontend) + Ruff/Black (backend)
2. ✅ **Type checking**: TypeScript strict (frontend) + mypy (backend)
3. ✅ **Unit tests**: 90%+ cobertura con pytest-cov (backend)
4. ✅ **Integration tests**: Tests de integración y API
5. ✅ **E2E tests**: Playwright tests para flujos críticos
6. ✅ **Build success**: Compilación sin errores
7. ✅ **Security scan**: Análisis de seguridad
8. ✅ **Performance budget**: Cumplir métricas de performance

---

**Última actualización:** 2026-07-21  
**Responsable de mantenimiento:** Otto (Dependency Engineer)
