# Guion del vídeo de presentación (máx. 5:00)

**Formato sugerido:** pantalla compartida + cámara (picture-in-picture)  
**Idioma:** español  
**1 vídeo por equipo**  
**No mostrar:** `.env`, claves PEM, tokens, datos personales reales del padrón  

---

## Minuto 0:00 – 0:30 | Hook + objetivo

**Pantalla:** landing `https://evoting.dennyrosales.com`

**Narración:**

> En muchas organizaciones las elecciones digitales terminan siendo encuestas con poca privacidad y cero auditabilidad.  
> Nuestro proyecto, **eVoting**, construye una urna digital donde el voto se cifra en el navegador, la identidad no viaja con la boleta, y el resultado se puede verificar de forma independiente.  
> Objetivo: elecciones institucionales confiables para gremios, cooperativas y asociaciones.

**Overlay texto (opcional):**  
`eVoting — Voto secreto · Urna cifrada · Verificación pública`

---

## Minuto 0:30 – 2:00 | Demo elector (componente principal)

**Pantalla:** `/vote/login` → OTP → boleta → confirmación → recibo

**Narración:**

> El elector se autentica en el realm VOTER. El sistema valida elegibilidad contra el snapshot del padrón.  
> Al elegir una plancha, el cifrado ocurre **en el cliente** con Web Crypto: RSA-OAEP y AES-256-GCM.  
> La API solo recibe la boleta cifrada. No guarda la preferencia en claro.  
> Al final, el elector obtiene un recibo con hash y código QR. Ese recibo confirma que la boleta existe… sin revelar por quién votó.

**Checklist visual:**

- [ ] Login OTP  
- [ ] Selección de plancha (fotos/candidatos si aplica)  
- [ ] Modal de confirmación  
- [ ] Recibo + QR (`/recibo/...`)  

**Si no hay elección ACTIVE en prod:** grabar en staging/local o reactivar una elección piloto *sin* publicar resultados como oficiales.

---

## Minuto 2:00 – 3:20 | Innovación: separación urna + verificación

**Pantalla A (10 s):** diagrama de arquitectura (exportar desde `03_ARQUITECTURA.md`)  
**Pantalla B:** `/verify/[artifactHash]` o CLI `evoting_verify.py`  
**Pantalla C (opcional):** snippet de cifrado en frontend (sin secretos)

**Narración:**

> Innovamos en tres capas. Primero: desacoplamiento criptográfico entre el padrón y la urna.  
> Segundo: ciclo electoral estricto — borrador, registro, congelamiento, activación, cierre y escrutinio.  
> Tercero: escrutinio offline firmado con RSA-PSS. Cualquier tercero puede verificar el artefacto sin confiar ciegamente en la interfaz.  
> Eso nos diferencia de formularios genéricos y de cajas negras SaaS.

**Snippet seguro a mostrar (idea):** generación de commitment / WebCrypto encrypt — nunca claves privadas.

---

## Minuto 3:20 – 4:15 | Admin, territorio y valor organizacional

**Pantalla:** `/admin` (ciclo electoral) + geovisor `/admin/geovisor` o `/cliente/geovisor` + resultados públicos

**Narración:**

> Del lado ADMIN, la comisión configura cargos, planchas y alcance territorial — nacional, regional o estatal.  
> El padrón se congela antes de abrir la urna.  
> Con PostGIS y geovisores, la organización ve el territorio y la participación.  
> El área cliente permite consulta ciudadana sin exponer el padrón.

---

## Minuto 4:15 – 4:50 | Kiro + Gemini + stack

**Pantalla:** `/cliente/asistente` (Gemini) + `/health/ai`

**Narración:**

> Construimos el sistema acelerado por **Kiro**: steering de producto y skills de arquitectura.  
> El asistente ciudadano corre con **Google Gemini 3.5 Flash** — fuera de la urna, sin acceso a boletas ni claves.  
> Stack: Next.js 15, FastAPI, PostgreSQL con PostGIS.

---

## Minuto 4:50 – 5:00 | Cierre

**Pantalla:** landing + links

**Narración:**

> eVoting: secreto del voto, urna verificable y operación electoral real.  
> Demo en evoting.dennyrosales.com — código en GitHub. Gracias.

**Overlay final:**

```
Repo: github.com/drosales10/evoting
Demo: evoting.dennyrosales.com
Hackathon: Código Facilito × Kiro × AWS
```

---

## Plan B si algo falla en vivo (30 s de backup)

Tener clips precargados:

1. Emisión de voto + recibo  
2. Verificación de artefacto  
3. Panel admin freeze → activate  

Si la demo cae: “mientras recuperamos el servicio, mostramos la grabación del flujo completo” y continúa el guion.

---

## Producción práctica

| Paso | Tip |
|------|-----|
| Resolución | 1080p, 16:9 |
| Audio | micrófono claro; recortar silencios |
| Ritmo | cortes cada 8–15 s; no leer párrafos largos |
| Textos en pantalla | tipografía grande; pocas palabras |
| Subtítulos | recomendados (jurado en YouTube/async) |
| Duración | exportar y verificar **≤ 4:55** (margen de seguridad) |
| Privacidad | cuenta demo; sin padrón real en pantalla |

## Título sugerido del vídeo (YouTube / Drive)

`eVoting — Urna digital cifrada y verificable | Hackathon Kiro Código Facilito`
