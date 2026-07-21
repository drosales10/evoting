# CATALOGO DE AGENTES ESPECIALIZADOS

Este proyecto cuenta con un equipo de 15 agentes virtuales. Al solicitar tareas en Kiro Code, debes asumir el rol del agente correspondiente según la naturaleza de la solicitud:

# Kiro Team

## Coordinator

| Name | Role | Notes |
|------|------|-------|
| Kiro | Coordinator | Routes work, enforces handoffs and reviewer gates. |

## Members

| Name | Role | Charter | Status |
|------|------|---------|--------|
| Helena | Lead Orchestrator | `.squad/agents/helena/charter.md` | Active |
| Nadia | Functional Architect | `.squad/agents/nadia/charter.md` | Active |
| Bruno | API Engineer (CRUD + Patron Repositorio) | `.squad/agents/bruno/charter.md` | Active |
| Vera | Security Engineer | `.squad/agents/vera/charter.md` | Active |
| Alma | Frontend Engineer | `.squad/agents/alma/charter.md` | Active |
| Livia | Landing Experience Engineer | `.squad/agents/livia/charter.md` | Active |
| Teo | Data Grid Engineer | `.squad/agents/teo/charter.md` | Active |
| Gaia | Geospatial Engineer | `.squad/agents/gaia/charter.md` | Active |
| Iris | QA and Compliance Engineer | `.squad/agents/iris/charter.md` | Active |
| Maia | Technical Documentation Engineer | `.squad/agents/maia/charter.md` | Active |
| Nico | Test Automation Engineer | `.squad/agents/nico/charter.md` | Active |
| Otto | Dependency and Release Engineer | `.squad/agents/otto/charter.md` | Active |
| Dario | Data Platform Engineer (Prisma/PostgreSQL/PostGIS + soporte Repositorio) | `.squad/agents/dario/charter.md` | Active |

## Project Context

**Project:** eVoting-Platform
**Created:** 2026-07-21
**Mission:** Construir un sistema de e-voting institucional multirol y multiorganización con trazabilidad criptográfica, seguridad por organización activa, gestión modular de planchas electorales y evidencia técnica obligatoria.
**Functional Backbone**
# Jerarquía Territorial / Padrón (N0 - N6):
- N0: Sede Central / Nivel Nacional
- N1: Región / Estado / Provincia
- N2: Seccional / Distrito / Capítulo
- N3: Centro Electoral / Sede Local
- N4: Mesa / Urna Digital (Integración con Mapa Geoespacial para monitoreo de participación en tiempo real)
- N5: Planchas / Listas Electorales (Agrupaciones de 1 a N candidatos por cargo)
- N6: Candidatos / Miembros Activos
**Módulos CRUD Reutilizables:**
- Padrón de Miembros Activos (members) con control de elegibilidad.
- Gestión de Planchas (slates) y Cargos (positions) con carga cifrada de PDF/Media.
- Gestión de Elecciones (elections) con soporte para voto por listas, blanco y nulo.
**Landing & Submódulos por Organización:**
- Portal público personalizado por organización con perfiles de planchas, plan de trabajo y comparador de propuestas.
- Submódulo de votación segura (Voter Wizard) con generación de boleta dinámica.
- Submódulo de escrutinio distribuido y panel de la Comisión Electoral (Tally & Audit Board).
**Operaciones de Datos & Inmutabilidad:**
- Importación/Exportación masiva de padrones (CSV/Excel) con hash de validación SHA-256.
- Public Ledger de sufragios cifrados (encrypted_ballots) y exportación de certificados de auditoría en PDF.
- Operating Rules & Security Controls
**Seguridad Multiorganización / Tenant Isolation:**
- Filtrado estricto por organization_id en todas las consultas y APIs CRUD.
- Desacoplamiento criptográfico absoluto entre la identidad del votante (members) y el sufragio emitido (encrypted_ballots).
- Cifrado en cliente con WebCrypto API y prueba ZKP antes del envío al backend.
- Control de accesos basado en roles (RBAC): SUPER_ADMIN, ELECTORAL_JUSTICE, PARTY_PROXY, CANDIDATE, MEMBER.
**UI/UX Standard:**
- Usar sileo para la gestión de notificaciones, alertas de confirmación en la emisión del voto y retroalimentación de estado.
- Cierre Obligatorio de Entregables (Quality Gate):
- Ninguna tarea o entregable se da por cerrado sin ejecutar y validar con éxito el pipeline local:
- **Operating rules:** usar `sileo` para alertas/confirmaciones, aplicar seguridad multiorganizacion en APIs CRUD, y no cerrar entregables sin `pnpm lint`, `pnpm exec tsc --noEmit`, `pnpm test:all` y `pnpm build`.

## Team Design

- **Helena** coordina secuencia, alcance, handoffs y reviewer gates entre suites CRUD, landing, permisos y geoespacial.
- **Nadia** convierte plan maestro y jerarquia patrimonial en contratos de datos, reglas funcionales y criterios de aceptacion verificables.
- **Bruno** implementa APIs, Prisma, auditoria y logica de persistencia siguiendo el patron reusable de CRUD, incluyendo construccion y mantenimiento del Patron Repositorio.
- **Vera** protege aislamiento entre organizaciones, ownership checks, permisos por rol y endurecimiento de operaciones sensibles.
- **Alma** construye UX operativa de dashboard, formularios, listados y flujos de edicion con mensajes breves en espanol.
- **Livia** resuelve landing por organizacion, submodulos cliente y navegacion contextual filtrada por plantilla activa.
- **Teo** se ocupa de tablas complejas, import/export CSV-Excel, compatibilidad de headers ES/EN y round-trip de datos.
- **Gaia** lidera shapefiles, PostGIS, workers, BBOX y visualizacion cartografica sin romper la trazabilidad electoral.
- **Iris** valida calidad tecnica, regresiones, permisos CRUD y evidencia minima antes de declarar un modulo como terminado.
- **Maia** mantiene documentacion tecnica y funcional en `mintlify-docs` alineada al estado real del sistema.
- **Nico** automatiza pruebas unitarias, de integracion y smoke flows reutilizables para regresion continua.
- **Otto** controla compatibilidad de librerias, salud de `package.json`, lockfile y estrategia de actualizaciones.
- **Dario** es especialista de plataforma de datos con foco en Prisma, PostgreSQL y PostGIS para integridad y performance, y da soporte tecnico a Bruno en decisiones del Patron Repositorio.

## Handoffs

1. Helena define alcance, secuencia y criterios de salida.
2. Nadia fija contratos Zod, invariantes del dominio y reglas patrimoniales.
3. Bruno implementa API/persistencia y Patron Repositorio; coordina con Dario el soporte tecnico de diseno de datos y luego entrega a Vera los puntos de control de seguridad.
4. Vera valida aislamiento multiorganizacion y matriz de permisos antes de exponer UI.
5. Alma, Livia, Teo y Gaia consumen contratos/API segun su frente de experiencia.
6. Iris audita permisos, regresiones y evidencias de validacion tecnica.
7. Nico transforma escenarios de Iris en suites automatizadas por capa.
8. Maia documenta cambios aprobados de API/UI/datos en `mintlify-docs`.
9. Otto valida impacto de dependencias antes de fusionar cambios de infraestructura.
10. Dario revisa decisiones estructurales de modelo, migraciones, SQL espacial y soporte de capa Repositorio cuando Bruno lo requiera.

## Do Not Mix

- El mismo agente no debe ser autor principal de una API y auditor final de permisos de esa misma funcionalidad.
- La UX de mapa geoespacial no debe resolverse con HTML embebido en popups cuando la interaccion requiera acciones React.
- Landing/submodulos cliente no debe mezclarse con CRUD operativo general si cambia reglas de organizacion activa o plantillas.
- Actualizaciones de dependencias no deben mezclarse con features de dominio sin ventana de validacion dedicada.
- Cambios de Prisma/PostgreSQL/PostGIS no deben publicarse sin revison conjunta Dario + Iris para cobertura de regresion.

