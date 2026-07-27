# Estrategia AWS + Kiro (criterio 10%)

El reglamento indica que Kiro/AWS **se sugieren** (no son obligatorios), pero el criterio **d)** vale 10% y se evidencia en arquitectura y herramientas.

## 1. Kiro — cómo contarlo (fortaleza)

Durante el hackathon el desarrollo se guió con **Kiro** como IDE agente:

| Artefacto Kiro | Rol en eVoting |
|----------------|----------------|
| `steering.md` | Especificación electoral (privacidad, E2E, RBAC) |
| `design.md` | UX de boleta, recibo, confirmación defensiva |
| Skills | Admin/cliente split, geovisores, migraciones PG, git |
| 15 agentes | Seguridad (Vera), API (Bruno), geo (Gaia), QA (Iris)… |
| Rules / routing | Ownership y ceremonias de equipo |

**Frase útil:**

> Kiro nos permitió pasar de metodología electoral a software operable en días: no solo generó código, orquestó arquitectura, seguridad y UX bajo un mismo steering.

**Acción recomendada (30–60 min):** incluir en el README una sección “Desarrollado con Kiro” y, si es posible, versionar un subconjunto no sensible de `.kiro/` (hoy está en `.gitignore`). Ejemplo a commitear:

- `.kiro/steering.md` (sanitizado)
- `.kiro/RESUMEN_STEERING_COMPLETO.md`
- listado de skills usadas

---

## 2. AWS — estado y opciones antes del cierre

### Estado actual

Piloto en **DigitalOcean Droplet** (nginx + PM2 + PostgreSQL/PostGIS), equivalente conceptual a EC2 + RDS self-managed.

### Opción A — Roadmap documentado (rápido, 0 infra nueva)

Publicar en README/vídeo el mapa:

| Capa eVoting | Servicio AWS objetivo |
|--------------|----------------------|
| App Next + FastAPI | **EC2** o **ECS Fargate** / **Elastic Beanstalk** |
| PostgreSQL + PostGIS | **Amazon RDS** (PostgreSQL) |
| Fotos candidatos / actas / exports | **Amazon S3** |
| Front estático / hosting | **AWS Amplify** o CloudFront + S3 |
| Asistente “explica la boleta / reglamento” | **Amazon Bedrock** |
| Jobs de seed/tally helpers | **AWS Lambda** |

Ventaja: cumple narrativa de arquitectura.  
Riesgo: el jurado puede preferir evidencia viva.

### Opción B — Quick win real (recomendado si hay 2–4 h)

**B1. S3 para medios (más simple y alineado al producto)**

- Bucket privado/público controlado para fotos de candidatos  
- Upload desde ADMIN vía URL prefirmada  
- En el vídeo: consola S3 + imagen sirviendo en la boleta  

**B2. Bedrock (muy “on brand” para hackathon IA)**

- Endpoint/Lambda que resume plan de trabajo de una plancha o responde FAQ electoral  
- Deja claro que **no** interviene en el cifrado ni en el conteo  

**B3. Amplify / EC2**

- Redeploy del frontend o de un staging en Amplify Hosting  
- Evidencia fuerte, más trabajo de DNS/SSL  

### Opción C — Híbrido (mejor ROI)

1. Documentar arquitectura AWS (Opción A)  
2. Implementar **un** servicio real (S3 o Bedrock)  
3. Mostrarlo 20 s en el vídeo  

---

## 3. Límites de seguridad al usar AWS

Nunca subir a S3/Secrets Manager de demo:

- `encryption-private.pem` / shares Shamir  
- JWT secrets de producción  
- dumps del padrón real  

La clave privada de urna permanece **offline** (cumplimiento del modelo de amenaza).

---

## 4. Slide “AWS + Kiro” (texto listo)

**Título:** Construido con Kiro, listo para AWS  

**Bullets:**

- Kiro: steering multiagente + skills de geo, auth dual y datos  
- Cómputo: EC2/ECS (hoy: droplet equivalente)  
- Datos: RDS PostgreSQL + PostGIS  
- Objetos: S3 para medios y artefactos públicos  
- IA opcional: Bedrock fuera del path de urna  
- Secreto electoral: privadas fuera de la nube de aplicación  

---

## 5. Prioridad hoy (día de cierre)

| Prioridad | Acción | Tiempo |
|-----------|--------|--------|
| P0 | README + links demo/repo + guion vídeo | 1–2 h |
| P0 | Grabar vídeo | 1–2 h |
| P1 | Sección Kiro en README (+ screenshots) | 30 min |
| P1 | Diagrama AWS en vídeo | 20 min |
| P2 | S3 o Bedrock real | 2–4 h |
| P3 | Migrar todo a AWS | no intentar hoy |
