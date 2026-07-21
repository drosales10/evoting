# Tasks & Execution Roadmap (`tasks.md`)

## Phase 0: Environment, Architecture & Quality Assurance Setup
- [ ] **TASK-CORE-01:** Configurar la estructura base del repositorio monorepo / Next.js + FastAPI con soporte para `pnpm`.
- [ ] **TASK-CORE-02:** Configurar el pipeline de Calidad Local obligatorio (`pnpm lint`, `pnpm exec tsc --noEmit`, `pnpm test:all`, `pnpm build`).
- [ ] **TASK-CORE-03:** Configurar middleware de aislamiento multiorganización (*Tenant Isolation*) por `organization_id` en peticiones API.
- [ ] **TASK-CORE-04:** Configurar integración de la libreróa `sileo` para el manejo centralizado de notificaciones, alertas y modales de confirmación.

---

## Phase 1: Database Architecture & Multitenant Models (N0 - N6)
- [ ] **TASK-DB-01:** Implementar esquema PostgreSQL de Miembros (`members`) y Padrones con soporte para control de elegibilidad y jerarquóa N0-N6.
- [ ] **TASK-DB-02:** Diseóar e implementar las tablas de Elecciones (`elections`), Cargos (`positions`) y Planchas Electorales (`slates`).
- [ ] **TASK-DB-03:** Crear las tablas de Candidatos (`candidates`) y restricciones de unicidad de postulaciones por elección.
- [ ] **TASK-DB-04:** Diseóar la tabla de Urna Cifrada (`encrypted_ballots`) con desacoplamiento estricto de la identidad del votante y soporte para recibos SHA-256.
- [ ] **TASK-DB-05:** Implementar la tabla inmutable de auditoróa (`audit_logs`) y triggers para el registro de eventos clave.

---

## Phase 2: Slate Management & Validation Engine (N5 - N6)
- [ ] **TASK-SLATE-01:** Desarrollar endpoints CRUD para la creación y gestión de planchas por el Apoderado (`PARTY_PROXY`).
- [ ] **TASK-SLATE-02:** Implementar motor de validaciones automóticas: comprobación de antigóedad (mónimo 6 meses), estatus activo y ausencia de sanciones.
- [ ] **TASK-SLATE-03:** Construir la carga cifrada y almacenamiento de documentos (PDF de Plan de Trabajo, Fotos 600x600px y Video MP4).
- [ ] **TASK-SLATE-04:** Desarrollar el flujo de revisión documental, subsanación de observaciones y dictamen de habilitación por la Justicia Electoral (`ELECTORAL_JUSTICE`).
- [ ] **TASK-SLATE-05:** Implementar el mecanismo de congelamiento inmutable (*Freeze Trigger*) a $D-1$ de las tablas de planchas y candidatos.

---

## Phase 3: Portal Póblico & Comparador de Propuestas
- [ ] **TASK-PUB-01:** Desarrollar Landing Page póblica por `organization_id` con banners de la convocatoria e indicadores de tiempo.
- [ ] **TASK-PUB-02:** Implementar vista detallada de planchas habilitadas (`/slates/[id]`) con visor PDF de Plan de Trabajo y reproductor MP4.
- [ ] **TASK-PUB-03:** Construir el módulo interactivo de comparación de propuestas lado a lado entre planchas participantes.
- [ ] **TASK-PUB-04:** Implementar foro de preguntas y respuestas moderado con autenticación de miembros activos.

---

## Phase 4: Voter Wizard & Client-Side Cryptography (WebCrypto API)
- [ ] **TASK-VOTE-01:** Desarrollar flujo de autenticación de dos factores (MFA/OTP) y verificación automótica de elegibilidad en padrón.
- [ ] **TASK-VOTE-02:** Implementar el módulo de Boleta Dinómica (`DynamicBallot`) con soporte para plancha completa, voto en blanco y voto nulo.
- [ ] **TASK-VOTE-03:** Desarrollar la lógica de cifrado en cliente mediante WebCrypto API y generación de pruebas de validez ZKP.
- [ ] **TASK-VOTE-04:** Crear el endpoint atómico de recepción de sufragio cifrado, marcado de `has_voted = true` y emisión del comprobante SHA-256.
- [ ] **TASK-VOTE-05:** Diseóar el modal de confirmación con `sileo` y la descarga del comprobante de votación en PDF/PNG.

---

## Phase 5: Tally Engine, Threshold Decryption & Analytics
- [ ] **TASK-TALLY-01:** Implementar el motor de agregación cifrada mediante suma homomórfica por identificador de planilla.
- [ ] **TASK-TALLY-02:** Desarrollar la interfaz y protocolo de descifrado distribuido ($k$-of-$n$ claves parciales) para la apertura de la urna.
- [ ] **TASK-TALLY-03:** Implementar las reglas de resolución de resultados (Mayoróa Simple, Mayoróa Absoluta y regla de desempate determinista).
- [ ] **TASK-TALLY-04:** Construir el Dashboard de la Comisión Electoral con mótricas de quórum en vivo y mapa geoespacial de participación (Nivel N4).
- [ ] **TASK-TALLY-05:** Diseóar la visualización interactiva de resultados finales (gróficos de barras, tortas de distribución y composición de la directiva electa).

---

## Phase 6: Audit, Export & Quality Gates
- [ ] **TASK-AUDIT-01:** Implementar la exportación del *Public Ledger* de sufragios cifrados para verificación independiente.
- [ ] **TASK-AUDIT-02:** Construir el generador de Actas Digitales Escrutadas en PDF firmadas criptogróficamente (`@react-pdf/renderer`).
- [ ] **TASK-AUDIT-03:** Implementar pruebas unitarias e integración para los flujos criptogróficos, validación de planchas y cólculo de escrutinio.
- [ ] **TASK-AUDIT-04:** Ejecución y validación final del pipeline de cierre de entregables (`pnpm lint`, `pnpm exec tsc --noEmit`, `pnpm test:all`, `pnpm build`).