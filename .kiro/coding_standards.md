# 📝 Guía de Estilo de Código

## 🎯 Principios Fundamentales

### 1. Claridad sobre Brevedad
```typescript
// ❌ Difícil de leer
const r=(a,b)=>a&&b?a+b:0

// ✅ Claro y explícito
const calculateResult = (valueA: number, valueB: number): number => {
  if (valueA && valueB) {
    return valueA + valueB
  }
  return 0
}
```

### 2. TypeScript Estricto
```typescript
// ❌ Tipo implícito
const user = { name: 'John' }

// ✅ Tipo explícito
interface User {
  name: string
  email?: string
}

const user: User = { name: 'John' }
```

### 3. Funciones Puras cuando sea posible
```typescript
// ❌ Efecto secundario
let counter = 0
function increment() {
  counter++
}

// ✅ Función pura
function increment(current: number): number {
  return current + 1
}
```

## 🏗️ Estructura de Archivos

### Convenciones de Nombres
```
// Componentes React
PascalCase.tsx          // BallotWizard.tsx
// Utilidades y hooks
camelCase.ts           // useBallotEncryption.ts
// Constantes
UPPER_SNAKE_CASE.ts    // VOTING_STATUS.ts
// Tipos e interfaces
PascalCase.ts          // BallotTypes.ts
```

### Organización de Componentes
```
src/
├── components/
│   ├── ui/           # Componentes reutilizables (Shadcn)
│   ├── ballot/       # Componentes específicos de boleta
│   ├── auth/         # Componentes de autenticación
│   └── layout/       # Componentes de layout
├── hooks/            # Custom hooks
├── lib/              # Utilidades y helpers
├── types/            # Tipos TypeScript
└── utils/            # Funciones utilitarias
```

## 📄 Convenciones de TypeScript

### Interfaces vs Types
```typescript
// ✅ Usar interface para objetos
interface Ballot {
  id: string
  encryptedPayload: string
  receiptHash: string
}

// ✅ Usar type para uniones
type VotingStatus = 'DRAFT' | 'ACTIVE' | 'CLOSED' | 'TALLIED'

// ✅ Usar type para mapeos
type StatusColors = {
  [K in VotingStatus]: string
}
```

### Generics
```typescript
// ✅ Generic explícito
function getById<T>(id: string, items: T[]): T | undefined {
  return items.find(item => item.id === id)
}

// ✅ Generic con constraints
function updateItem<T extends { id: string }>(
  id: string,
  update: Partial<T>,
  items: T[]
): T[] {
  return items.map(item => 
    item.id === id ? { ...item, ...update } : item
  )
}
```

## 🎨 Estilo de Código

### Indentación
- **Espacios:** 2 espacios (no tabs)
- **Línea máxima:** 100 caracteres
- **Comillas:** Comillas simples para strings

### Orden de imports
```typescript
// 1. React y librerías externas
import React from 'react'
import { useRouter } from 'next/navigation'

// 2. Componentes internos
import { BallotCard } from '@/components/ballot'
import { useAuth } from '@/hooks/use-auth'

// 3. Utilidades y tipos
import { formatDate } from '@/lib/utils'
import type { Ballot } from '@/types/ballot'

// 4. Estilos
import styles from './Ballot.module.css'
```

### Nombrado de Variables
```typescript
// ✅ Descriptivo
const ballotEncryptionKey = generateKey()
const hasUserVoted = checkVotingStatus(userId)

// ❌ Abreviado
const key = genKey()
const voted = chk(userId)

// ✅ Booleano como pregunta
const isLoading = true
const hasError = false
const isValid = true

// ✅ Arrays plural
const ballots: Ballot[] = []
const users: User[] = []
```

## ⚛️ Convenciones de React

### Componentes Funcionales
```typescriptx
// ✅ Con tipado explícito
interface BallotProps {
  ballot: Ballot
  onVote: (choice: string) => void
}

export function BallotComponent({ ballot, onVote }: BallotProps) {
  const [selected, setSelected] = React.useState<string>('')

  const handleSubmit = React.useCallback(() => {
    onVote(selected)
  }, [onVote, selected])

  return (
    <div className="ballot-container">
      {/* Componente */}
    </div>
  )
}
```

### Hooks Personalizados
```typescript
// ✅ Prefijo 'use'
export function useBallotEncryption() {
  const [encrypted, setEncrypted] = React.useState<string>('')
  
  const encryptBallot = React.useCallback(async (data: BallotData) => {
    const result = await encrypt(data)
    setEncrypted(result)
  }, [])

  return { encrypted, encryptBallot }
}

// ✅ Retornar objeto, no array (mejor DX)
// ❌ return [encrypted, encryptBallot]
// ✅ return { encrypted, encryptBallot }
```

### Manejo de Estado
```typescript
// ✅ Estado complejo con useReducer
type VotingState = {
  ballot: Ballot | null
  status: VotingStatus
  error: string | null
}

type VotingAction = 
  | { type: 'SET_BALLOT'; payload: Ballot }
  | { type: 'SET_STATUS'; payload: VotingStatus }
  | { type: 'SET_ERROR'; payload: string }

function votingReducer(state: VotingState, action: VotingAction): VotingState {
  switch (action.type) {
    case 'SET_BALLOT':
      return { ...state, ballot: action.payload }
    case 'SET_STATUS':
      return { ...state, status: action.payload }
    case 'SET_ERROR':
      return { ...state, error: action.payload }
    default:
      return state
  }
}
```

## 🔐 Seguridad y Criptografía

### Cifrado en Cliente
```typescript
// ✅ Web Crypto API con manejo de errores
export async function encryptBallot(
  ballotData: BallotData,
  publicKey: CryptoKey
): Promise<string> {
  try {
    const encoder = new TextEncoder()
    const data = encoder.encode(JSON.stringify(ballotData))
    
    const encrypted = await window.crypto.subtle.encrypt(
      {
        name: 'RSA-OAEP',
      },
      publicKey,
      data
    )
    
    return arrayBufferToBase64(encrypted)
  } catch (error) {
    throw new Error(`Failed to encrypt ballot: ${error.message}`)
  }
}
```

### Validación de Entrada
```typescript
// ✅ Zod para validación
import { z } from 'zod'

const ballotSchema = z.object({
  electionId: z.string().uuid(),
  encryptedPayload: z.string().min(1),
  receiptHash: z.string().length(64), // SHA-256
  zkpProof: z.string().optional(),
})

export function validateBallot(data: unknown): Ballot {
  return ballotSchema.parse(data)
}
```

## 🧪 Testing

### Backend Testing (Python/pytest)
```python
# test_ballot_encryption.py
import pytest
from app.services.ballot import encrypt_ballot
from app.exceptions import EncryptionError

class TestBallotEncryption:
    @pytest.fixture
    def ballot_data(self):
        return {
            "election_id": "election_123",
            "slate_id": "slate_456",
            "positions": [...]
        }

    def test_encrypt_ballot_success(self, ballot_data):
        """Test successful ballot encryption."""
        result = encrypt_ballot(ballot_data)
        
        assert "encrypted_payload" in result
        assert "receipt_hash" in result
        assert len(result["receipt_hash"]) == 64  # SHA-256
        
    def test_encrypt_ballot_invalid_data(self):
        """Test encryption with invalid data raises error."""
        with pytest.raises(EncryptionError, match="Invalid ballot data"):
            encrypt_ballot({})
            
    @pytest.mark.asyncio
    async def test_async_ballot_processing(self):
        """Test async ballot processing."""
        result = await process_ballot_async()
        assert result["status"] == "processed"
```

### Test Naming (Python)
```python
# ✅ Describe comportamiento
def test_encrypt_ballot_success():
    """Test successful ballot encryption."""
    pass
    
def test_encrypt_ballot_invalid_public_key():
    """Test encryption fails with invalid public key."""
    pass
    
def test_handle_large_ballot_data():
    """Test encryption handles large ballot data."""
    pass

# ❌ Describe implementación
def test_calls_crypto_subtle_encrypt():
    """Test calls crypto.subtle.encrypt."""
    pass
```

### Frontend E2E Testing (Playwright)
```typescript
// ballot.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Ballot Voting Flow', () => {
  test('should complete voting wizard successfully', async ({ page }) => {
    // 1. Navigate to voting page
    await page.goto('/vote/election-123');
    
    // 2. Select slate
    await page.click('[data-testid="slate-card-456"]');
    
    // 3. Confirm selection
    await page.click('[data-testid="confirm-vote"]');
    
    // 4. Verify receipt
    await expect(page.locator('[data-testid="receipt-hash"]')).toBeVisible();
    
    // 5. Verify receipt hash format
    const receiptHash = await page.locator('[data-testid="receipt-hash"]').textContent();
    expect(receiptHash).toMatch(/^[a-f0-9]{64}$/); // SHA-256 format
  });
});
```

## 📊 Performance

### Optimización de Re-renders
```typescript
// ✅ React.memo para componentes pesados
export const HeavyComponent = React.memo(function HeavyComponent({
  data,
  onAction,
}: HeavyComponentProps) {
  return <div>{/* Renderizado pesado */}</div>
})

// ✅ useMemo para cálculos costosos
export function ResultsComponent({ ballots }: ResultsProps) {
  const totalVotes = React.useMemo(() => {
    return ballots.reduce((sum, ballot) => sum + ballot.votes, 0)
  }, [ballots])

  return <div>Total: {totalVotes}</div>
}
```

### Lazy Loading
```typescript
// ✅ Componentes pesados con lazy loading
const BallotPDF = React.lazy(() => import('./BallotPDF'))

export function ResultsPage() {
  return (
    <React.Suspense fallback={<LoadingSpinner />}>
      <BallotPDF ballots={ballots} />
    </React.Suspense>
  )
}
```

## 🗂️ Estructura de APIs

### Endpoints RESTful
```typescript
// ✅ Nombrado consistente
// GET    /api/ballots           - Listar boletas
// GET    /api/ballots/:id       - Obtener boleta específica
// POST   /api/ballots           - Crear nueva boleta
// PUT    /api/ballots/:id       - Actualizar boleta
// DELETE /api/ballots/:id       - Eliminar boleta

// ✅ Responses estandarizadas
interface ApiResponse<T> {
  data: T
  meta?: {
    page: number
    total: number
    pageSize: number
  }
  error?: string
}
```

### Manejo de Errores
```typescript
// ✅ Error handling consistente
export class VotingError extends Error {
  constructor(
    message: string,
    public code: string,
    public statusCode: number = 400
  ) {
    super(message)
    this.name = 'VotingError'
  }
}

export class BallotNotFoundError extends VotingError {
  constructor(ballotId: string) {
    super(`Ballot ${ballotId} not found`, 'BALLOT_NOT_FOUND', 404)
  }
}
```

## 🎯 Checklist de Revisión

### Antes de Commit
- [ ] Código pasa lint (`pnpm lint` frontend, `ruff check` backend)
- [ ] TypeScript sin errores (`pnpm exec tsc --noEmit`)
- [ ] Python type checking pasa (`mypy .`)
- [ ] Tests pasan (`pytest` backend, `pnpm test:e2e` frontend)
- [ ] Convenciones de nombrado seguidas
- [ ] Documentación actualizada
- [ ] Sin console.logs de debug
- [ ] Manejo de errores apropiado
- [ ] Performance considerada

### Revisión de PR
- [ ] Responsabilidades de agente respetadas
- [ ] Seguridad multiorganización aplicada
- [ ] Filtros por organization_id incluidos
- [ ] Tests unitarios e integración (pytest)
- [ ] Build exitoso (`pnpm build` frontend)
- [ ] Cobertura de código mantenida (pytest-cov)
- [ ] Pre-commit hooks pasan (`pre-commit run --all-files`)

---

**Responsable:** Iris (QA and Compliance Engineer)  
**Última revisión:** 2026-07-21  
**Aplicable a:** Todo el código del proyecto eVoting-Platform
