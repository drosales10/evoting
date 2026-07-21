# 🔄 Adaptación de Skills para Sistema de Votación Electrónica

## 📋 Estado Actual

Las 4 skills existen y están correctamente configuradas en formato Kiro, pero están orientadas a un proyecto SMyEG (sistema forestal). Aquí se explica cómo adaptarlas para el sistema de votación electrónica.

## 🎯 **Skill 1: admin-client-split**

### **Aplicación en eVoting:**
Esta skill es **CRÍTICA** para separar:
- **Área Administrativa:** Comisión Electoral, SUPER_ADMIN, gestión de elecciones
- **Área de Cliente:** Votantes, portal público de votación

### **Adaptaciones necesarias:**
1. **Tablas de usuarios:**
   - `User` → Miembros de la comisión electoral, administradores (RBAC)
   - `ClientUser` → Votantes (sin roles en sesión, solo elegibilidad)

2. **Estructura de rutas:**
   ```
   src/app/
   ├── (auth)/           # Autenticación MFA para votantes
   ├── (electoral-board)/ # Comisión Electoral (dashboard)
   ├── admin/            # Administración general
   ├── voting/           # Portal de votación (público)
   └── welcome/          # Landing pública por organización
   ```

3. **RBAC para eVoting:**
   ```typescript
   type UserRole = 
     | 'SUPER_ADMIN'        # Full system
     | 'ELECTORAL_JUSTICE'  # Comisión electoral
     | 'PARTY_PROXY'        # Apoderados de planchas
     | 'CANDIDATE'          # Candidatos (read-only)
     | 'MEMBER';            # Votantes
   ```

4. **Landing context:** Organización electoral activa para filtrado de datos

### **Checklist adaptación:**
- [ ] Modelos Prisma: `User` (admin) y `Voter` (cliente)
- [ ] NextAuth con providers: `admin-credentials` y `voter-credentials`
- [ ] Route groups para comisión electoral `(electoral-board)/`
- [ ] Proxy guards para rutas administrativas
- [ ] Landing context por organización electoral

## 🗺️ **Skill 2: geovisor-development**

### **Aplicación en eVoting:**
Para visualización **geoespacial de participación electoral**:
- **Admin:** Import de distritos/centros de votación (N1-N3)
- **Cliente:** Mapa de participación en tiempo real (N4 = mesas)

### **Adaptaciones necesarias:**
1. **Jerarquía territorial electoral:**
   - **N1:** Región/Estado
   - **N2:** Distrito/Circuito
   - **N3:** Centro de votación
   - **N4:** Mesa/Urna digital

2. **Mapas:**
   - **Admin:** Leaflet para importar distritos
   - **Cliente:** DeckGL + Mapbox para visualizar participación
   - **Google Earth Engine:** No necesario para votación

3. **Store adaptado:**
   ```typescript
   type ElectionGeoStore = {
     regions: GeoJSON.FeatureCollection;      // N1
     districts: GeoJSON.FeatureCollection;    // N2
     votingCenters: GeoJSON.FeatureCollection; // N3
     votingTables: GeoJSON.FeatureCollection;  // N4
     participationData: Map<string, number>;   // Participación por mesa
   }
   ```

4. **APIs:**
   - `/api/admin/geo/import/` → Import distritos
   - `/api/election/geo/participation` → Datos de participación
   - `/api/election/geo/results` → Resultados geoespaciales

### **Checklist adaptación:**
- [ ] Modelos PostGIS: `election_regions`, `election_districts`, `voting_centers`, `voting_tables`
- [ ] Componente `ElectionMapView` para visualización
- [ ] Store `useElectionGeoStore`
- [ ] APIs de importación territorial
- [ ] Visualización de participación en tiempo real

## 🔄 **Skill 3: git-workflow**

### **Aplicación en eVoting:**
**NO necesita adaptación** - Este workflow es **genérico y aplicable directamente**.

### **Aplicación directa:**
1. **Branching:** `squad/{issue}-{slug}` para features
2. **Commits:** Conventional commits en español
3. **PR Guardrails:** Validación de checklist técnica
4. **Labels:** `squad:*`, `area:`, `needs:*`
5. **Reviewers:** Iris (QA), Vera (seguridad), Dario (datos)

### **Configuraciones específicas:**
- **Quality gates:** `pytest` (backend) + Playwright (frontend E2E)
- **Checklist PR:** Incluir validación criptográfica
- **Labels específicos:** `area:voting`, `area:crypto`, `area:audit`

### **Checklist:**
- [ ] Configurar `.github/workflows/pr-guardrails.yml`
- [ ] Crear templates de issues para votación
- [ ] Definir labels específicos de eVoting
- [ ] Configurar reviewers obligatorios

## 🗄️ **Skill 4: postgresql-migrations**

### **Aplicación en eVoting:**
**CRÍTICA** para migraciones seguras de esquema electoral.

### **Adaptaciones necesarias:**
1. **Esquema Prisma específico:**
   ```prisma
   // Tablas principales
   model Election {
     id        String   @id @default(uuid())
     title     String
     status    ElectionStatus
     // ... campos específicos de votación
   }
   
   model Ballot {
     id               String   @id @default(uuid())
     encryptedPayload String   // Voto cifrado
     receiptHash      String   @unique // SHA-256
     electionId       String
     // Desacoplamiento de identidad del votante
   }
   ```

2. **Migraciones seguras:**
   - **NUNCA** `DROP TABLE` en producción
   - **SIEMPRE** `db:migrate:safe` en entornos con datos
   - Backfill para campos nuevos

3. **PostGIS para datos geoespaciales:**
   ```sql
   CREATE TABLE election_regions (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     geom geometry(MultiPolygon, 4326),
     name VARCHAR(255),
     code VARCHAR(50)
   );
   ```

4. **Seed idempotente:**
   - Roles del sistema: `SUPER_ADMIN`, `ELECTORAL_JUSTICE`, etc.
   - Configuración electoral base
   - Organizaciones de prueba

### **Checklist adaptación:**
- [ ] Esquema Prisma completo para eVoting
- [ ] Migraciones iniciales
- [ ] Seed con datos de prueba electorales
- [ ] Scripts `db:migrate:safe` configurados
- [ ] Validación de PostGIS para datos territoriales

## 🚀 **Plan de Implementación**

### **Fase 1: Skills críticas inmediatas**
1. **admin-client-split** - Configurar separación admin/cliente
2. **postgresql-migrations** - Crear esquema inicial seguro

### **Fase 2: Skills para desarrollo**
3. **git-workflow** - Configurar CI/CD y PR gates
4. **geovisor-development** - Adaptar para visualización electoral

### **Fase 3: Integración completa**
- Integrar las 4 skills en el flujo de desarrollo
- Crear documentación específica para eVoting
- Entrenar al equipo en el uso de las skills

## 📊 **Matriz de Aplicabilidad**

| Skill | Aplicabilidad | Esfuerzo Adaptación | Prioridad |
|-------|---------------|---------------------|-----------|
| **admin-client-split** | Alta (crítica) | Media | 🔴 ALTA |
| **geovisor-development** | Media (visualización) | Alta | 🟡 MEDIA |
| **git-workflow** | Alta (genérica) | Baja | 🟢 ALTA |
| **postgresql-migrations** | Alta (crítica) | Media | 🔴 ALTA |

## 🎯 **Beneficios de la Adaptación**

1. **Consistencia:** Mismos patrones en todo el proyecto
2. **Seguridad:** Migraciones seguras, separación de concerns
3. **Productividad:** Workflow colaborativo establecido
4. **Calidad:** Gates de validación automáticos
5. **Mantenibilidad:** Código estructurado y documentado

## 📝 **Siguientes Pasos**

1. **Activar skills** en el proyecto eVoting
2. **Adaptar** `admin-client-split` y `postgresql-migrations`
3. **Configurar** `git-workflow` para el equipo
4. **Planificar** adaptación de `geovisor-development`

**Las skills están listas para usar** - Solo requieren adaptación de contenido específico para el dominio de votación electrónica.

---

**Responsable:** Helena (Lead Orchestrator)  
**Fecha:** 2026-07-21  
**Estado:** ✅ Skills configuradas, 🔄 Necesitan adaptación de dominio
