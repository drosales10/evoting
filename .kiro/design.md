# Design & UX/UI Specification (`design.md`)

## 1. Design System & System Architecture Rules

### Visual Identity & Theme
* **Institutional Aesthetics:** Paleta basada en tonos oscuros/azules corporativos (Confianza, Seguridad, Transparencia) con contrastes de alta accesibilidad (WCAG AA / AAA).
* **UI Engine:** TailwindCSS + Lucide Icons + Radix UI / Shadcn UI (componentes accesibles y modulares).
* **Feedback & Notifications:** **`sileo`** como librería exclusiva para toasters, banners de confirmación (ej. *Confirmación de emisión de voto*, *Éxito en carga de plancha*) y modales de advertencia.

### UX Principles for E-Voting
1. **Zero-Ambiguity Voting Wizard:** El flujo de votación no debe presentar más de una acción principal por pantalla.
2. **Defensive Confirmation Pattern:** Antes de cifrar y enviar el voto, se exige un modal de previsualización explícito (*"¿Estás seguro de votar por la Planilla X?"*).
3. **Receipt Transparency:** Al completar el voto, el usuario recibe un código Hash SHA-256 amigable con opción de copia en 1 clic y descarga de comprobante en PDF/PNG.

---

## 2. Design System Components Checklist

- [ ] **`BaseLayout` / `TenantShell`:** Header con marca de la organización activa, conmutador de rol y badge de estado de la elección (Ej: `REVISIÓN`, `EN VIVO`, `CERRADO`).
- [ ] **`MemberGuard` / `AuthCard`:** Pantalla de autenticación limpia con soporte para correo + OTP / MFA y selector de organización.
- [ ] **`SlateCard` / `SlateGrid`:** Tarjetas de presentación de planchas electorales con logo, eslogan, integrantes por cargo, vista previa de Plan de Trabajo (PDF Viewer) y video promocional.
- [ ] **`DynamicBallot`:** Interfaz interactiva de la boleta electrónica por tramos, soporte para selección de planilla completa, voto en blanco o voto nulo.
- [ ] **`EncryptedReceiptModal`:** Modal de éxito tras la emisión del voto que muestra el Hash único, timestamp e inmutabilidad del registro.
- [ ] **`GeoParticipationMap` (Nivel N4):** Mapa vectorial/geoespacial para el monitoreo en tiempo real de la participación por mesa/centro electoral.
- [ ] **`TallySankeyChart` & `ResultsDashboard`:** Tableros con gráficos de barras, distribución de porcentaje de quórum y diagramas de flujo/Sankey para escrutinio.

---

## 3. Implementation Tasks (Design & Frontend Backlog)

### Task Group 1: Public Portal & Slate Showcase (N0 - N5)
- [ ] **TASK-DES-01:** Diseñar la Landing Page pública multitarget por `organization_id` con banners de convocatoria electoral.
- [ ] **TASK-DES-02:** Construir la vista detallada de Planchas (`/slates/[id]`) con modal embebido para lectura del Plan de Trabajo (PDF) y visor MP4 de presentación.
- [ ] **TASK-DES-03:** Implementar el módulo comparador interactivo de propuestas lado a lado entre 2 o más planchas registradas.

### Task Group 2: Voter Wizard & Encryption Flow
- [ ] **TASK-DES-04:** Diseñar el flujo de 4 pasos del sufragio: 
  1. *Autenticación/Elegibilidad* ➔ 2. *Selección de Boleta* ➔ 3. *Previsualización/Confirmación* ➔ 4. *Comprobante Criptográfico*.
- [ ] **TASK-DES-05:** Integrar estados de carga (*Skeletons* & *Loaders*) para la fase de cifrado en cliente con WebCrypto API para evitar dobles clics o interrupciones.
- [ ] **TASK-DES-06:** Configurar las alertas y feedback con `sileo` para manejar errores de sesión expirada, doble intento de voto o errores de red.

### Task Group 3: Electoral Board Dashboard & Live Analytics
- [ ] **TASK-DES-07:** Diseñar el panel de control de la Comisión Electoral con métricas de participación en vivo (porcentaje de quórum, mapa N4, curva temporal de sufragios).
- [ ] **TASK-DES-08:** Diseñar la interfaz del *Sealed Urn & Threshold Decryption* (ingreso de claves parciales $k$-of-$n$ por parte de los miembros de la comisión).
- [ ] **TASK-DES-09:** Desarrollar los componentes de visualización de resultados finales (gráficos de barras, tortas para nulos/blancos y tabla de composición de la junta ganadora).

### Task Group 4: Accessibility, Responsive & PDF Templates
- [ ] **TASK-DES-10:** Garantizar la navegabilidad completa por teclado (Tab/Espacio/Enter) y compatibilidad con lectores de pantalla en la boleta electrónica (Cumplimiento WCAG 2.1 AA).
- [ ] **TASK-DES-11:** Diseñar la plantilla responsive adaptada a dispositivos móviles (smartphones/tablets) para voto remoto sin pérdidas de layout.
- [ ] **TASK-DES-12:** Diseñar el layout del comprobante de sufragio y del Acta Final Escrutada para exportación en PDF (`@react-pdf/renderer`).