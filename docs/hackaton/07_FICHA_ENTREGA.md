# Ficha lista para el formulario de entrega

Copia y pega. Completa solo los campos marcados con `_`.

---

## Nombre del proyecto

eVoting — Plataforma de votación electrónica verificable

## Tagline

Elecciones digitales con voto cifrado en el navegador, urna sin identidad y verificación pública del escrutinio.

## Resumen (≤ 500 caracteres)

eVoting permite a organizaciones realizar elecciones institucionales con secreto del voto y auditabilidad. El elector cifra la boleta en el cliente (RSA-OAEP + AES-256-GCM); la urna almacena ciphertext sin member_id; el escrutinio se firma offline (RSA-PSS) y se verifica públicamente. Incluye ciclo electoral controlado, padrón territorial, geovisores PostGIS y superficies ADMIN / VOTER / pública. Construido con Kiro; arquitectura alineada a AWS (EC2/RDS/S3/Bedrock).

## Resumen largo (si el form lo pide)

Problema: las votaciones internas suelen depender de encuestas o proveedores opacos, sin separación real entre identidad y preferencia, ni verificación independiente.

Solución: plataforma full-stack (Next.js 15 + FastAPI + PostgreSQL/PostGIS) con cifrado en cliente, realms de autenticación, ciclo DRAFT→TALLIED, recibos por hash, verificación de actas y operación territorial.

Impacto: gremios, cooperativas, asociaciones y entornos educativos que necesitan democracia digital confiable.

Innovación: desacoplamiento criptográfico urna/padrón, integridad de boleta verificable, escrutinio offline firmado y docs operativas (ceremonia de claves, runbooks).

## Enlaces

- **Repositorio:** https://github.com/drosales10/evoting  
- **Demo:** https://evoting.dennyrosales.com  
- **Vídeo:** _PEGAR_URL_DEL_VIDEO_  
- **Arquitectura / material:** carpeta `docs/hackaton/` en el repo  

## Stack

- Frontend: Next.js 15, React 19, TypeScript  
- Backend: FastAPI, SQLAlchemy async, Alembic  
- DB: PostgreSQL + PostGIS  
- Auth: cookies HttpOnly por realm (ADMIN / VOTER), OTP/MFA  
- Crypto: Web Crypto (RSA-OAEP, AES-GCM), RSA-PSS en actas  
- Tooling IA: Kiro (steering, agentes, skills)  
- Cloud: piloto en VPS; mapa AWS EC2/ECS + RDS + S3 (+ Bedrock opcional)  

## Servicios AWS (declarar con honestidad)

_Opción 1 — si ya hay servicio real:_  
`Amazon S3 (medios de candidatos) + arquitectura RDS/EC2 documentada`

_Opción 2 — si solo hay roadmap:_  
`Arquitectura diseñada para Amazon EC2/ECS, Amazon RDS (PostgreSQL), Amazon S3 y Amazon Bedrock; piloto demostrable en producción equivalente.`

## Uso de Kiro

Steering de producto electoral, design system UX de boleta, skills de separación admin/cliente y geovisores, catálogo multiagente (seguridad, API, datos, QA). Kiro aceleró la convergencia de requisitos criptográficos y UX en una demo operable.

## Equipo

| Nombre | Rol | Correo registro |
|--------|-----|-----------------|
| _ | _ | _ |
| _ | _ | _ |

## Credenciales demo (solo si el form lo pide; no las pongas en el README público si son sensibles)

- URL: https://evoting.dennyrosales.com  
- Elector demo: _  
- Admin demo: _  

## Hashtags / keywords

`#evoting #cryptography #fastapi #nextjs #postgis #kiro #aws #hackathon`
