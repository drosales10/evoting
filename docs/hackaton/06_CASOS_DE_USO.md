# Casos de uso — eVoting

## UC-01 — Emitir voto secreto

**Actor:** Elector elegible  
**Precondición:** Elección en `ACTIVE`; miembro en snapshot con `eligible=true` y `has_voted=false`  
**Flujo:**

1. Inicia sesión (OTP) en realm VOTER  
2. El sistema confirma elegibilidad  
3. Visualiza planchas/candidatos  
4. Confirma selección  
5. El cliente cifra la boleta y envía ciphertext + prueba de integridad  
6. Recibe `receipt_hash` y QR  

**Postcondición:** Existe boleta cifrada sin `member_id`; participación marcada; preferencia no legible en servidor.

---

## UC-02 — Congelar padrón y abrir urna

**Actor:** Admin (SUPER_ADMIN / ELECTORAL_JUSTICE)  
**Flujo:**

1. Configura elección en `DRAFT` (cargos, alcance territorial)  
2. Abre `REGISTRATION` → snapshot de elegibilidad  
3. Congela (`FREEZE`)  
4. Activa (`ACTIVE`) entregando **solo** la clave pública de urna  

**Postcondición:** No se pueden alterar padrón ni estructura de cargos; la privada nunca entra a la API.

---

## UC-03 — Verificar resultado sin confiar en la UI

**Actor:** Auditor / ciudadanía técnica  
**Flujo:**

1. Descarga artefacto de escrutinio y firma  
2. Usa `/verify/{artifactHash}` o CLI `evoting_verify.py`  
3. Valida hash canónico, firma RSA-PSS y consistencia de conteos  

**Postcondición:** Veredicto OK/FAIL independiente del frontend.

---

## UC-04 — Consultar recibo sin filtrar el voto

**Actor:** Elector u observador con el hash  
**Flujo:**

1. Abre `/recibo/{receiptHash}`  
2. Ve metadatos de existencia (elección, timestamp, estado ACEPTADO)  

**Postcondición:** No se revela plancha ni payload cifrado.

---

## UC-05 — Explorar territorio y participación

**Actor:** Comisión / ciudadanía  
**Flujo:**

1. Admin gestiona capas N2–N5 en geovisor  
2. Cliente consulta mapa / resultados agregados  

**Postcondición:** Lectura geoespacial sin exponer padrón nominativo.

---

## UC-06 — (Roadmap) Asistente electoral con Bedrock

**Actor:** Elector indeciso  
**Flujo:** pregunta FAQ (“¿qué es el voto en blanco?”, “¿cómo verifico mi recibo?”)  
**Restricción:** el asistente **no** ve boletas ni puede alterar la urna.
