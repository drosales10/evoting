# Pitch por criterios de evaluación

## Elevator pitch (30 s)

> eVoting es una plataforma de votación electrónica institucional donde el voto se cifra en el navegador, la urna no guarda quién votó, y cualquiera puede verificar el acta firmada. Diseñada con Kiro (steering multiagente) para organizaciones que necesitan elecciones digitales confiables, no solo “formularios online”.

---

## a) Impacto tecnológico — 30%

### Problema real

Las organizaciones (colegios profesionales, sindicatos, cooperativas, asociaciones civiles, gremios) realizan elecciones internas con:

- Excel + Zoom + “confianza en el comité”
- Plataformas genéricas de encuestas (sin secreto del voto ni auditabilidad)
- Costos altos de urna física o proveedores cerrados

Riesgos: doble voto, fuga de preferencias, resultados no verificables, dependencia de un administrador omnisciente.

### A quién aportamos valor

| Entorno | Valor |
|---------|-------|
| **Empresas / gremios** | Elecciones de junta, comités, planchas con padrón y alcance territorial |
| **Educación** | Laboratorios de democracia digital, criptografía aplicada, gobernanza |
| **Desarrollo** | Arquitectura de referencia: realms ADMIN/VOTER, crypto en cliente, PostGIS |

### Por qué eVoting responde

1. **Secreto del voto:** cifrado RSA-OAEP + AES-256-GCM en el navegador; la API solo recibe ciphertext.  
2. **Separación urna ↔ identidad:** `encrypted_ballots` sin `member_id`; la participación vive en `member_election_status`.  
3. **Ciclo electoral controlado:** `DRAFT → REGISTRATION → FREEZE → ACTIVE → CLOSED → TALLIED`.  
4. **Transparencia:** recibo con hash + verificación pública del artefacto de escrutinio (firma RSA-PSS).  
5. **Territorio:** jerarquía N2–N5 + geovisores (admin/cliente) para participación y alcance.

### Frase para el jurado

> No resolvemos “hacer una encuesta”. Resolvemos **confianza democrática digital**: emitir sin revelar, contar sin improvisar, verificar sin pedir permiso.

---

## b) Innovación — 30%

### Frente a alternativas del mercado

| Alternativa | Limitación típica | Ventaja eVoting |
|-------------|-------------------|-----------------|
| Google Forms / Typeform | Identidad ligada a respuesta | Urna desacoplada de identidad |
| ElectionBuddy / Simply Voting | Caja negra SaaS | Código abierto + verificación independiente |
| Blockchain voting | Costo, complejidad, privacidad débil | Crypto clásica auditable + escrutinio offline |
| Apps internas ad-hoc | Sin ciclo ni ceremonia de claves | Runbooks, MFA, CSRF, rate limits, realms |

### Ventajas técnicas (lo que mide el criterio)

- **Rendimiento / recursos:** cifrado en cliente (CPU del elector); urna solo almacena ciphertext; escrutinio offline fuera del path caliente.  
- **Escalabilidad:** API async (FastAPI + SQLAlchemy), snapshot de elegibilidad por territorio, mismo origen nginx (cookies `SameSite=strict`).  
- **Mantenibilidad:** monorepo pnpm, migraciones Alembic, scripts de seed/export, docs operativas, CI.  
- **Integridad:** compromiso `ballot-integrity-v1` (camino hacia ZKP completo); actas firmadas verificables por CLI/UI.

### Diferenciadores “wow” en demo

1. Emitir voto → recibo con QR (solo confirma existencia, no la plancha).  
2. Mostrar que la urna no tiene `member_id`.  
3. Verificar artefacto en `/verify/[hash]` o CLI.  
4. Geovisor de participación / territorio.

---

## c) Software funcional y entregables — 30%

### Estado operativo

- Demo: `https://evoting.dennyrosales.com`  
- Superficies: pública, cliente, elector, admin  
- Stack: Next.js 15 + FastAPI + PostgreSQL/PostGIS  

### Entregables

- [x] Repo público + README  
- [ ] Vídeo ≤ 5 min (usar `02_GUION_VIDEO.md`)  
- [x] Demo online  
- [x] Diagramas / casos de uso (este paquete)  

### Qué NO decir en el vídeo

- Secretos, `.env`, claves privadas, tokens SMTP  
- Datos reales del padrón (usar demo / datos de prueba)  
- Promesas de “elecciones oficiales” sin auditoría externa  

---

## d) Uso de AWS y Kiro — 10%

### Kiro (fortaleza actual)

El proyecto nació y se aceleró con **Kiro**:

- Steering completo (visión electoral, diseño UX, standards, API docs)  
- Catálogo de **15 agentes** especializados (security, geo, API, QA…)  
- Skills: admin/cliente split, geovisores, git workflow, migraciones PostgreSQL  
- Rules de routing y ceremonias  

Mensaje: *Kiro no fue un autocomplete; fue el sistema de orquestación del producto.*

### AWS / IA (criterio 10% y demo IA)

- **Kiro:** steering + skills (evidencia principal del criterio tooling)
- **Google Gemini 3.5 Flash:** asistente FAQ en `/cliente/asistente` (fuera de la urna)
- Health: `/health/ai`

> Nota: se intentó cablear Amazon S3/Bedrock; la cuenta AWS quedó bloqueada por verificación de pago. La IA operativa quedó en Gemini.
---

## Estructura narrativa recomendada (orden de persuasión)

1. Problema humano (30 s)  
2. Demo del flujo elector (90 s)  
3. Innovación criptográfica + verificación (90 s)  
4. Admin / territorio / ciclo (45 s)  
5. Kiro + AWS + cierre (45 s)  

Total ≈ 5:00  
