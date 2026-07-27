# Arquitectura eVoting (para jurado)

## 1. Vista de contexto

```mermaid
flowchart LR
  subgraph Usuarios
    A[Admin / Comisión]
    V[Elector]
    P[Público / Ciudadanía]
  end

  subgraph App["eVoting — mismo origen HTTPS"]
    WEB[Next.js 15<br/>UI ADMIN · VOTER · Pública]
    API[FastAPI<br/>Realms · CSRF · Rate limit]
    WEB --> API
  end

  DB[(PostgreSQL + PostGIS)]
  OFF[Escrutinio offline<br/>clave privada fuera de la API]
  PUB[Verificación pública<br/>artefacto + firma RSA-PSS]

  A --> WEB
  V --> WEB
  P --> WEB
  API --> DB
  OFF --> DB
  OFF --> PUB
  P --> PUB
```

## 2. Separación de realms (seguridad)

```mermaid
flowchart TB
  U[Usuario] --> NGX[nginx :443]
  NGX -->|/api/*| API[FastAPI]
  NGX -->|/*| WEB[Next.js]

  API --> RA[Cookie ADMIN HttpOnly]
  API --> RV[Cookie VOTER HttpOnly]

  RA --> ADM[Rutas /api/v1/admin/*]
  RV --> VOT[Rutas /api/v1/voter/*]
  API --> PUB[Rutas /api/v1/public/*]
```

**Idea clave:** cookies por realm, `SameSite=strict`, sin mezclar privilegios ADMIN y VOTER.

## 3. Flujo de voto (impacto + innovación)

```mermaid
sequenceDiagram
  autonumber
  actor E as Elector
  participant UI as Frontend (WebCrypto)
  participant API as FastAPI
  participant DB as PostgreSQL

  E->>UI: Login OTP (realm VOTER)
  UI->>API: Autenticación
  API->>DB: Valida elegibilidad (snapshot)
  E->>UI: Selecciona plancha
  UI->>UI: Cifra boleta RSA-OAEP + AES-GCM
  UI->>UI: Genera commitment / integrity proof
  UI->>API: POST boleta cifrada (sin preferencia en claro)
  API->>DB: Guarda encrypted_ballots (sin member_id)
  API->>DB: Marca has_voted en member_election_status
  API-->>UI: receipt_hash + QR
  UI-->>E: Recibo (existencia, no contenido)
```

## 4. Ciclo electoral

```mermaid
stateDiagram-v2
  [*] --> DRAFT
  DRAFT --> REGISTRATION: Abrir registro / snapshot
  REGISTRATION --> FREEZE: Congelar padrón
  FREEZE --> ACTIVE: Activar + clave pública urna
  ACTIVE --> CLOSED: Cerrar votación
  CLOSED --> TALLIED: Escrutinio offline firmado
  TALLIED --> [*]
```

## 5. Mapa de despliegue actual → AWS

```mermaid
flowchart TB
  subgraph Hoy["Piloto actual"]
    DO[Droplet DigitalOcean]
    NG[nginx]
    PM2[PM2: Next + Uvicorn]
    PG[(PostgreSQL/PostGIS local)]
    DO --> NG --> PM2
    PM2 --> PG
  end

  subgraph AWS["Arquitectura objetivo AWS"]
    ALB[ALB / CloudFront]
    EC2[EC2 o ECS Fargate]
    RDS[(Amazon RDS PostgreSQL)]
    S3[S3 medios / actas]
    BR[Bedrock asistente electoral opcional]
    ALB --> EC2
    EC2 --> RDS
    EC2 --> S3
    EC2 --> BR
  end

  Hoy -.->|migración natural| AWS
```

## 6. Componentes principales (para el vídeo)

| Componente | Qué demuestra |
|------------|---------------|
| Portal público `/elections` | Transparencia sin padrón |
| Área cliente `/cliente` | UX ciudadana + geovisor |
| Voto `/vote` | Cifrado en cliente + recibo |
| Admin `/admin` | Ciclo electoral y padrón |
| Verify `/verify/...` | Auditabilidad independiente |
| Recibo `/recibo/...` | Existencia sin filtrar preferencia |

## 7. Principios de seguridad (slide único)

1. Clave privada de urna **nunca** en API, DB, frontend ni logs  
2. Urna sin `member_id`  
3. Escrutinio offline + firma del acta  
4. MFA / OTP, CSRF, rate limiting, cookies Secure en producción  
5. Resultados de piloto no se publican como oficiales  
