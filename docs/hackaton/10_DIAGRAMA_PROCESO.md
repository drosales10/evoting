# Diagrama del proceso electoral — eVoting

Usa este Mermaid (más legible que FigJam para narrar). Ábrelo en [mermaid.live](https://mermaid.live), exporta PNG y muéstralo en Snagit.

## Versión corta (recomendada para el vídeo)

```mermaid
flowchart LR
  subgraph prep [Preparacion]
    A[DRAFT] --> B[REGISTRATION]
    B --> C[FREEZE]
    C --> D[ACTIVE]
  end

  subgraph voto [Emision del voto]
    E[Login OTP] --> F{Elegible?}
    F -->|Si| G[Elige plancha]
    G --> H[Cifra en navegador]
    H --> I[Urna: solo ciphertext]
    I --> J[Recibo hash + QR]
  end

  subgraph cierre [Cierre y auditoria]
    K[CLOSED] --> L[Escrutinio offline]
    L --> M[Acta firmada]
    M --> N[TALLIED]
    N --> O[Verificar /verify]
  end

  D --> E
  J --> K
```

## Versión detallada (si quieres más pasos)

```mermaid
flowchart TD
  A([Inicio]) --> B[1. DRAFT: cargos, planchas, territorio]
  B --> C[2. REGISTRATION: snapshot del padron]
  C --> D[3. FREEZE: congelar padron]
  D --> E[4. ACTIVE: clave publica de urna]
  E --> F[5. Elector: login OTP]
  F --> G{Elegible y sin voto?}
  G -->|No| X([Acceso denegado])
  G -->|Si| H[6. Elige plancha]
  H --> I[7. Cifrado en navegador]
  I --> J[8. API recibe ciphertext]
  J --> K[(9. Urna sin member_id)]
  J --> L[(9. Marca has_voted)]
  K --> M[10. Recibo hash + QR]
  L --> M
  M --> N[11. CLOSED]
  N --> O[12. Escrutinio offline]
  O --> P[13. Acta firmada RSA-PSS]
  P --> Q[14. TALLIED]
  Q --> R[15. Verificacion publica]
  R --> S([Fin])
```

## Qué decir en el vídeo (20 s)

> El proceso tiene cuatro actos: preparación del padrón, emisión del voto cifrado en el navegador, cierre con escrutinio firmado, y verificación pública. El padrón sabe quién puede votar; la urna solo guarda ciphertext. Nunca viajan juntos.
