# 📋 Metodología Electoral Digital — Resumen Ejecutivo

## Fase 1: Pre-Electoral (Padrón e Infraestructura)
- **Verificación de Identidad:** Autenticación robusta mediante MFA de dos factores (Correo Institucional + OTP/TOTP) con soporte opcional para WebAuthn/Passkeys (biometría local del dispositivo).
- **Protección de Datos:** Base de datos maestra con hashes cryptographic SHA-256; almacenamiento estricto sin datos sensibles o de identificación en texto plano.
- **Calendario Institucional:**
  - `D-30`: Convocatoria oficial y publicación del padrón preliminar.
  - `D-20 a D-15`: Periodo de subsanación/impugnación de datos del padrón.
  - `D-15`: Cierre definitivo del padrón de miembros activos.
  - `D-7`: Simulacro general de carga, estrés y seguridad.
  - `D-Day`: Apertura de la jornada de votación online.

## Fase 2: Votación Online (Emisión y Seguridad)
- **Flujo del Elector:**
  1. Autenticación MFA / Validación de sesión.
  2. Verificación automática de elegibilidad en padrón activo.
  3. Selección y cifrado del voto en el cliente (*Client-side Encryption*).
  4. Emisión de sufragio y recepción de comprobante con hash único (miga de pan / *tracking code*).
- **5 Capas de Seguridad:**
  1. *Perimetral:* WAF (Web Application Firewall), mitigación DDoS y filtrado de IP/rate limiting.
  2. *Autenticación:* MFA obligatorio y tokens JWT de vida corta (un solo uso para emisión).
  3. *Aplicación:* Protección anti-CSRF, sanitización de entradas y cabeceras de seguridad estrictas.
  4. *Datos:* Desacoplamiento criptográfico total entre la identidad del votante (`members`) y la urna (`encrypted_ballots`).
  5. *Auditoría:* Registro de eventos inmutable (*Audit Trail*) para la trazabilidad del proceso.
- **Principios Democráticos:** Universalidad, secreto absoluto del voto, libre elección y soporte explícito para voto en blanco formalmente validado.

## Fase 3: Escrutinio Criptográfico y Transparencia
- **Técnicas Modernas de Protección:**
  - **Cifrado Homomórfico (ElGamal/Paillier):** Permite sumar y tabular los votos en estado cifrado sin necesidad de descifrar papeletas individuales.
  - **Pruebas de Conocimiento Cero (ZKP):** Garantizan que el voto cifrado contiene una opción válida (incluyendo voto en blanco) sin revelar la preferencia.
  - **Árboles de Merkle (Merkle Trees):** Estructura de datos para la auditoría y verificación individual del sufragio por parte de cada elector.
  - **Mix-Net Criptográfico:** Reordenamiento y cegado aleatorio previo al descifrado para impedir correlación por timestamp.
- **Proceso de Apertura de Urna:**
  1. Cierre automático del sistema con marca de tiempo (*Timestamping*).
  2. Descifrado distribuido mediante esquema de umbral (*Threshold Cryptography*, $k$ de $n$ claves de la Comisión Electoral).
  3. Verificación matemática de integridad del *bulletin board*.
  4. Conteo de resultados respaldado por pruebas ZKP.
  5. Generación e inmutabilización del Acta Digital Criptográfica.

## Fase 4: Resultados, Visualización y Gobernanza
- **Métricas Clave del Proceso:**
  - Participación global (% de Quórum alcanzado).
  - Votos válidos vs. Votos en blanco.
  - Registro de integridad y consistencia del sistema (100% verificado).
- **Visualización:** Tableros interactivos con gráficos de barras, gráficos circulares de distribución y diagramas de flujo/Sankey (para sistemas preferenciales/RCV).
- **Mecanismos de Transparencia:**
  - Registro inmutable (*Public Ledger* de auditoría).
  - Acta Final descargable con firma digital de la Comisión Electoral.
  - Ventana formal de impugnación de 48 horas post-publicación.

---

## 💡 Recomendaciones de Implementación y Gobernanza
1. **Auditoría Externa:** Contratar una evaluación de seguridad (PenTesting y revisión de código/esquema criptográfico) previo a la elección.
2. **Simulacro Participativo:** Ejecutar una prueba piloto con al menos el 20% del padrón activo para medir usabilidad y carga de servidores.
3. **Plan de Contingencia:** Establecer un protocolo claro de alta disponibilidad (failover) o extensión del horario de votación en caso de interrupciones técnicas.
4. **Capacitación:** Entrenar a la Comisión Electoral en la custodia de claves compartidas ($k$-of-$n$) y gestión de incidentes.
5. **Apertura y Auditoría:** Publicar el código fuente del motor de escrutinio y documentación técnica en un repositorio de acceso público (preservando la confidencialidad del padrón).
6. **Mejora Continua:** Revisar y actualizar la metodología electoral de forma anual previa a cada periodo de comicios.

# SYSTEM SPECIFICATION: E-VOTING & SLATE MANAGEMENT SYSTEM (E-COMMISSION)

## 1. PROJECT OVERVIEW
Core Goal: Build a secure, privacy-preserving, end-to-end verifiable online voting platform supporting Slate/List Registration (Planchas Electorales), dynamic ballot generation, threshold cryptography tallying, and public auditability.

## 2. CORE DEMOCRATIC & SECURITY PRINCIPLES
- **One Member, One Vote:** Strict identity verification against active membership roster.
- **Vote Privacy & Anonymity:** Complete decoupling of Voter Identity (`members` table) from Cast Ballots (`encrypted_ballots` table) using blind tokens and cryptographic separation.
- **End-to-End Verifiability (E2E):** Issue a unique SHA-256 receipt code to the voter upon ballot submission.
- **Sealed Urn & Threshold Decryption:** Ballots remain encrypted until election closure, requiring $k$-of-$n$ private key shares to decrypt the tally.
- **Immutable Candidate Freeze:** Once voting starts, all candidate and slate structures are strictly locked from editing.

## 3. RBAC (ROLE-BASED ACCESS CONTROL)
1. `SUPER_ADMIN / ELECTORAL_JUSTICE`: Full system audit, board management, roster approval, final tally trigger.
2. `PARTY_PROXY (Apoderado)`: Manages slate details, candidate rosters, media uploads, and document submissions for their specific party/slate.
3. `CANDIDATE`: View-only access to their profile and campaign status.
4. `MEMBER (Voter)`: MFA authentication, eligibility check, ballot access, receipt tracking.

## 4. DATABASE SCHEMA DESIGN (PostgreSQL / PostGIS compatible)

```sql
-- Members / Active Roster
CREATE TABLE members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    dni VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'ACTIVE', -- ACTIVE, INACTIVE, SANCTIONED
    membership_months INT DEFAULT 0,
    has_voted BOOLEAN DEFAULT FALSE,
    voted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Elections
CREATE TABLE elections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    voting_type VARCHAR(50) DEFAULT 'SLATE_PLURALITY', -- SLATE_PLURALITY, RANKED_CHOICE, APPROVAL
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    quorum_threshold_pct DECIMAL(5,2) DEFAULT 30.00,
    status VARCHAR(50) DEFAULT 'DRAFT' -- DRAFT, REGISTRATION, FREEZE, ACTIVE, CLOSED, TALLIED
);

-- Positions / Cargo Definitions
CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    election_id UUID REFERENCES elections(id),
    title VARCHAR(100) NOT NULL, -- e.g., Presidente, Secretario, Tesorero, Vocal
    code VARCHAR(50) NOT NULL,
    is_required BOOLEAN DEFAULT TRUE,
    display_order INT DEFAULT 0
);

-- Slates / Partidos / Planchas (Supports 1 or N candidates)
CREATE TABLE slates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    election_id UUID REFERENCES elections(id),
    name VARCHAR(150) NOT NULL,
    slogan VARCHAR(255),
    logo_base64 TEXT,
    work_plan_pdf_url TEXT,
    video_url TEXT,
    proxy_member_id UUID REFERENCES members(id),
    status VARCHAR(50) DEFAULT 'PENDING', -- PENDING, UNDER_REVIEW, APPROVED, REJECTED
    validation_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Candidates linked to Slates and Positions
CREATE TABLE candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slate_id UUID REFERENCES slates(id) ON DELETE CASCADE,
    position_id UUID REFERENCES positions(id),
    member_id UUID REFERENCES members(id),
    bio TEXT,
    photo_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_candidate_per_election UNIQUE (slate_id, position_id)
);

-- Encrypted Ballots Storage (Anonymous Urn)
CREATE TABLE encrypted_ballots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    election_id UUID REFERENCES elections(id),
    encrypted_payload TEXT NOT NULL, -- Homomorphic / Asymmetric encrypted choice
    receipt_hash VARCHAR(64) UNIQUE NOT NULL,
    zkp_proof TEXT, -- Zero-Knowledge Proof of valid vote choice
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Immutable Audit Log
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    actor_id_hash VARCHAR(64),
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);