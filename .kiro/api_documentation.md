# 📡 Documentación de API

## 🔐 Autenticación

### Base URL
```
Development: http://localhost:8000/api/v1
Production: https://api.evoting.example.com/api/v1
```

### Headers de Autenticación
```http
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}
Content-Type: application/json
```

### Flujo de Autenticación
1. **Login** → Obtener tokens de acceso/refresh
2. **Refresh Token** → Renovar access token
3. **MFA Verification** → Verificación de segundo factor
4. **Access Token** → Usar en todas las requests

## 📊 Endpoints Principales

### Autenticación

#### POST /auth/login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password",
  "organization_id": "org_123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900,
  "requires_mfa": true,
  "user": {
    "id": "user_123",
    "email": "user@example.com",
    "roles": ["MEMBER"]
  }
}
```

#### POST /auth/mfa/verify
```http
POST /api/v1/auth/mfa/verify
Authorization: Bearer {temp_token}
Content-Type: application/json

{
  "code": "123456"
}
```

#### POST /auth/refresh
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### Miembros (Members)

#### GET /members
Listar miembros con paginación y filtros.

```http
GET /api/v1/members
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}

Params:
- page: number (default: 1)
- limit: number (default: 20)
- status: string (ACTIVE, INACTIVE, SANCTIONED)
- search: string (search by name or email)
```

**Response:**
```json
{
  "data": [
    {
      "id": "member_123",
      "email": "member@example.com",
      "full_name": "John Doe",
      "dni": "12345678",
      "status": "ACTIVE",
      "membership_months": 24,
      "has_voted": false,
      "created_at": "2026-07-21T10:30:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "total": 150,
    "page_size": 20,
    "total_pages": 8
  }
}
```

#### GET /members/{id}
Obtener miembro específico.

```http
GET /api/v1/members/{member_id}
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}
```

#### PUT /members/{id}
Actualizar miembro.

```http
PUT /api/v1/members/{member_id}
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}
Content-Type: application/json

{
  "full_name": "John Updated",
  "status": "ACTIVE"
}
```

### Elecciones (Elections)

#### GET /elections
Listar elecciones.

```http
GET /api/v1/elections
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}

Params:
- status: string (DRAFT, REGISTRATION, FREEZE, ACTIVE, CLOSED, TALLIED)
- upcoming: boolean (true for future elections)
- active: boolean (true for active elections)
```

#### POST /elections
Crear nueva elección.

```http
POST /api/v1/elections
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}
Content-Type: application/json

{
  "title": "Elección del Comité Directivo 2026",
  "voting_type": "SLATE_PLURALITY",
  "start_time": "2026-09-01T08:00:00Z",
  "end_time": "2026-09-07T20:00:00Z",
  "quorum_threshold_pct": 30.0,
  "positions": [
    {
      "title": "Presidente",
      "code": "PRESIDENT",
      "is_required": true
    },
    {
      "title": "Secretario",
      "code": "SECRETARY",
      "is_required": true
    }
  ]
}
```

#### PUT /elections/{id}/status
Actualizar estado de elección.

```http
PUT /api/v1/elections/{election_id}/status
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}
Content-Type: application/json

{
  "status": "ACTIVE",
  "transition_reason": "Opening election for voting"
}
```

### Planchas (Slates)

#### GET /slates
Listar planchas electorales.

```http
GET /api/v1/slates
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}

Params:
- election_id: string (filter by election)
- status: string (PENDING, UNDER_REVIEW, APPROVED, REJECTED)
```

#### POST /slates
Crear nueva plancha.

```http
POST /api/v1/slates
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}
Content-Type: multipart/form-data

Form Data:
- name: "Plancha Progresista"
- slogan: "Por un futuro mejor"
- election_id: "election_123"
- proxy_member_id: "member_456"
- work_plan_pdf: (file)
- logo: (file, 600x600px)
- video_url: "https://youtube.com/watch?v=..."
- candidates: [
    {
      "position_id": "position_123",
      "member_id": "member_789",
      "bio": "Candidato con experiencia..."
    }
  ]
```

#### PUT /slates/{id}/status
Actualizar estado de revisión de plancha.

```http
PUT /api/v1/slates/{slate_id}/status
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}
Content-Type: application/json

{
  "status": "APPROVED",
  "review_notes": "Documentación completa y válida",
  "validation_hash": "sha256_hash_of_documents"
}
```

### Votación (Ballots)

#### POST /ballots/eligibility
Verificar elegibilidad para votar.

```http
POST /api/v1/ballots/eligibility
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}
Content-Type: application/json

{
  "election_id": "election_123"
}
```

**Response:**
```json
{
  "eligible": true,
  "reason": "ACTIVE_MEMBER",
  "has_voted": false,
  "election": {
    "id": "election_123",
    "title": "Elección del Comité Directivo 2026",
    "status": "ACTIVE",
    "positions": [...]
  },
  "slates": [...]
}
```

#### POST /ballots/vote
Emitir voto cifrado.

```http
POST /api/v1/ballots/vote
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}
Content-Type: application/json

{
  "election_id": "election_123",
  "encrypted_payload": "base64_encrypted_data",
  "zkp_proof": "base64_zkp_proof",
  "client_public_key": "base64_public_key"
}
```

**Response:**
```json
{
  "success": true,
  "receipt_hash": "a1b2c3d4e5f6...",
  "timestamp": "2026-07-21T14:30:45Z",
  "ballot_id": "ballot_123"
}
```

#### GET /ballots/receipt/{hash}
Obtener comprobante de voto.

```http
GET /api/v1/ballots/receipt/{receipt_hash}
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}
```

### Escrutinio (Tally)

#### POST /tally/start
Iniciar proceso de escrutinio.

```http
POST /api/v1/tally/start
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}
Content-Type: application/json

{
  "election_id": "election_123",
  "decryption_threshold": 3,
  "commission_members": ["member_1", "member_2", "member_3", "member_4", "member_5"]
}
```

#### POST /tally/decrypt
Proporcionar clave parcial para descifrado.

```http
POST /api/v1/tally/decrypt
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}
Content-Type: application/json

{
  "election_id": "election_123",
  "partial_key": "base64_partial_decryption_key",
  "member_id": "member_456",
  "signature": "base64_signature"
}
```

#### GET /tally/results/{election_id}
Obtener resultados del escrutinio.

```http
GET /api/v1/tally/results/{election_id}
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}
```

### Geoespacial

#### GET /geo/regions
Listar regiones (N1).

```http
GET /api/v1/geo/regions
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}

Params:
- bbox: string (min_lon,min_lat,max_lon,max_lat)
- level: number (1-4)
```

#### GET /geo/participation
Obtener participación por región.

```http
GET /api/v1/geo/participation
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}

Params:
- election_id: string
- level: number (1-4)
- format: string (geojson, csv)
```

### Auditoría (Audit)

#### GET /audit/logs
Obtener logs de auditoría.

```http
GET /api/v1/audit/logs
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}

Params:
- event_type: string
- actor_id: string
- start_date: string (ISO date)
- end_date: string (ISO date)
- page: number
- limit: number
```

#### GET /audit/export
Exportar ledger público.

```http
GET /api/v1/audit/export
Authorization: Bearer {access_token}
X-Organization-ID: {organization_id}

Params:
- election_id: string
- format: string (json, csv, pdf)
```

## 🔧 Schemas de Datos

### Miembro (Member)
```typescript
interface Member {
  id: string;
  email: string;
  full_name: string;
  dni: string;
  status: 'ACTIVE' | 'INACTIVE' | 'SANCTIONED';
  membership_months: number;
  has_voted: boolean;
  voted_at?: string;
  created_at: string;
  organization_id: string;
}
```

### Elección (Election)
```typescript
interface Election {
  id: string;
  title: string;
  voting_type: 'SLATE_PLURALITY' | 'RANKED_CHOICE' | 'APPROVAL';
  start_time: string;
  end_time: string;
  quorum_threshold_pct: number;
  status: 'DRAFT' | 'REGISTRATION' | 'FREEZE' | 'ACTIVE' | 'CLOSED' | 'TALLIED';
  created_at: string;
  organization_id: string;
}
```

### Plancha (Slate)
```typescript
interface Slate {
  id: string;
  election_id: string;
  name: string;
  slogan?: string;
  logo_base64?: string;
  work_plan_pdf_url?: string;
  video_url?: string;
  proxy_member_id: string;
  status: 'PENDING' | 'UNDER_REVIEW' | 'APPROVED' | 'REJECTED';
  validation_hash?: string;
  created_at: string;
  candidates: Candidate[];
}
```

### Boleta Cifrada (EncryptedBallot)
```typescript
interface EncryptedBallot {
  id: string;
  election_id: string;
  encrypted_payload: string;  // Base64 encrypted data
  receipt_hash: string;       // SHA-256 hash
  zkp_proof?: string;         // Zero-knowledge proof
  created_at: string;
}
```

## 🔐 Seguridad y Permisos

### RBAC (Role-Based Access Control)
```typescript
type UserRole = 
  | 'SUPER_ADMIN'      // Full system access
  | 'ELECTORAL_JUSTICE' // Electoral board
  | 'PARTY_PROXY'      // Slate manager
  | 'CANDIDATE'        // Candidate read-only
  | 'MEMBER';          // Regular voter
```

### Permisos por Endpoint
| Endpoint | SUPER_ADMIN | ELECTORAL_JUSTICE | PARTY_PROXY | CANDIDATE | MEMBER |
|----------|-------------|-------------------|-------------|-----------|--------|
| GET /members | ✅ | ✅ | ❌ | ❌ | ❌ |
| POST /members | ✅ | ✅ | ❌ | ❌ | ❌ |
| GET /elections | ✅ | ✅ | ✅ | ✅ | ✅ |
| POST /elections | ✅ | ✅ | ❌ | ❌ | ❌ |
| GET /slates | ✅ | ✅ | ✅ | ✅ | ✅ |
| POST /slates | ✅ | ❌ | ✅* | ❌ | ❌ |
| POST /ballots/vote | ❌ | ❌ | ❌ | ❌ | ✅ |
| POST /tally/start | ✅ | ✅ | ❌ | ❌ | ❌ |

*PARTY_PROXY solo puede crear/modificar sus propias planchas

### Validaciones de Ownership
- Todas las queries incluyen filtro por `organization_id`
- Los usuarios solo pueden acceder a datos de su organización
- Los audit logs registran todas las operaciones
- Validación de MFA para operaciones sensibles

## 🧪 Ejemplos de Uso

### 1. Flujo Completo de Votación
```javascript
// 1. Autenticación
const authResponse = await fetch('/api/v1/auth/login', {
  method: 'POST',
  body: JSON.stringify({
    email: 'voter@example.com',
    password: 'password',
    organization_id: 'org_123'
  })
});

// 2. Verificar elegibilidad
const eligibility = await fetch('/api/v1/ballots/eligibility', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${authResponse.access_token}`,
    'X-Organization-ID': 'org_123'
  },
  body: JSON.stringify({
    election_id: 'election_123'
  })
});

// 3. Cifrar voto en cliente
const encryptedBallot = await encryptBallot({
  election_id: 'election_123',
  slate_id: 'slate_456',
  positions: [...]
});

// 4. Enviar voto cifrado
const voteResponse = await fetch('/api/v1/ballots/vote', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${authResponse.access_token}`,
    'X-Organization-ID': 'org_123',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    election_id: 'election_123',
    encrypted_payload: encryptedBallot.payload,
    zkp_proof: encryptedBallot.proof,
    client_public_key: encryptedBallot.publicKey
  })
});

// 5. Mostrar comprobante
console.log('Receipt Hash:', voteResponse.receipt_hash);
```

### 2. Crear Nueva Elección (Admin)
```javascript
const createElection = async () => {
  const response = await fetch('/api/v1/elections', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${adminToken}`,
      'X-Organization-ID': 'org_123',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      title: 'Elección del Comité Directivo 2026',
      voting_type: 'SLATE_PLURALITY',
      start_time: '2026-09-01T08:00:00Z',
      end_time: '2026-09-07T20:00:00Z',
      quorum_threshold_pct: 30.0,
      positions: [
        {
          title: 'Presidente',
          code: 'PRESIDENT',
          is_required: true
        },
        {
          title: 'Secretario',
          code: 'SECRETARY',
          is_required: true
        }
      ]
    })
  });
  
  return response.json();
};
```

## 🚨 Manejo de Errores

### Códigos de Error HTTP
| Código | Descripción |
|--------|-------------|
| 400 | Bad Request - Datos inválidos |
| 401 | Unauthorized - Token inválido o expirado |
| 403 | Forbidden - Sin permisos suficientes |
| 404 | Not Found - Recurso no existe |
| 409 | Conflict - Recurso en estado incompatible |
| 422 | Unprocessable Entity - Validación fallida |
| 429 | Too Many Requests - Rate limit excedido |
| 500 | Internal Server Error - Error del servidor |

### Response de Error
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid election data",
    "details": {
      "title": ["Field is required"],
      "start_time": ["Must be a future date"]
    },
    "timestamp": "2026-07-21T14:30:45Z",
    "request_id": "req_123456"
  }
}
```

### Códigos de Error Comunes
- `AUTH_INVALID_TOKEN` - Token inválido o expirado
- `AUTH_MFA_REQUIRED` - Se requiere verificación MFA
- `PERMISSION_DENIED` - Usuario no tiene permisos
- `ELECTION_NOT_ACTIVE` - Elección no está activa
- `MEMBER_NOT_ELIGIBLE` - Miembro no es elegible
- `ALREADY_VOTED` - Usuario ya votó
- `SLATE_NOT_APPROVED` - Plancha no aprobada

## 📊 Rate Limiting

### Límites por Endpoint
| Endpoint | Límite | Ventana |
|----------|--------|---------|
| /auth/login | 10 | 1 minuto |
| /auth/mfa/verify | 5 | 1 minuto |
| /ballots/vote | 1 | 1 hora |
| /members (POST) | 100 | 1 hora |
| API General | 1000 | 1 hora |

### Headers de Rate Limit
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 997
X-RateLimit-Reset: 1665
Retry-After: 65
```

## 🔄 Webhooks

### Eventos Disponibles
```typescript
type WebhookEvent =
  | 'election.created'
  | 'election.status_changed'
  | 'slate.submitted'
  | 'slate.reviewed'
  | 'ballot.cast'
  | 'tally.started'
  | 'tally.completed'
  | 'audit.event'
```

### Configurar Webhook
```http
POST /api/v1/webhooks
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "url": "https://your-server.com/webhooks/evoting",
  "events": ["ballot.cast", "tally.completed"],
  "secret": "your_webhook_secret"
}
```

### Payload de Webhook
```json
{
  "event": "ballot.cast",
  "data": {
    "election_id": "election_123",
    "ballot_id": "ballot_456",
    "receipt_hash": "a1b2c3...",
    "timestamp": "2026-07-21T14:30:45Z"
  },
  "signature": "sha256_signature",
  "timestamp": "2026-07-21T14:30:45Z"
}
```

## 📈 Métricas y Monitoreo

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-07-21T14:30:45Z",
  "services": {
    "database": "connected",
    "redis": "connected",
    "storage": "connected"
  },
  "metrics": {
    "uptime": "7d 3h 45m",
    "memory_usage": "45%",
    "active_connections": 127
  }
}
```

### Métricas Disponibles
- `GET /metrics` - Métricas Prometheus
- `GET /stats` - Estadísticas de uso
- `GET /audit/summary` - Resumen de auditoría

---

**Responsable:** Bruno (API Engineer)  
**Última actualización:** 2026-07-21  
**Especificación OpenAPI:** `/docs/openapi.yaml`
