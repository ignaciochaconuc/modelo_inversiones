# Phase 4C.2 — Plantilla de dictamen externo — v1

**Plantilla vacía. No es dictamen ni aprobación.** No rellenar por el propietario
o asistente en nombre de un revisor. Documento base: expediente v1 y su inventario.
No usar esta plantilla como autorización ejecutable o transición automática.

## Procedencia real de la revisión

- Revisor / identidad declarada: pendiente.
- Tipo de revisión (humana, IA, asistida, otra): pendiente.
- Si IA: etiqueta observada, snapshot cuando se conozca, asistencia y limitaciones: pendiente.
- Relación con desarrollo, acceso previo/historial, conflictos e independencia realmente sustentada: pendiente.
- Inicio/fin y fuente real de tiempos si se registran: pendiente; desconocidos `null`.
- Versión y SHA-256 del inventario recibido: pendiente.
- Alcance efectivamente revisado, archivos y líneas consultados: pendiente.
- Fuentes no disponibles, expiradas o no autorizadas: pendiente.
- Pruebas ejecutadas por el revisor y resultados, separados de históricos: pendiente.

No atribuir una identidad humana a IA, snapshots inferidos, cegamiento completo,
firmas, IDs o timestamps que no existan. Si el revisor solo inspeccionó documentos,
no declarar que auditó íntegramente código, ejecuciones o semántica del modelo.

## Diez preguntas obligatorias

Para cada respuesta indicar evidencia con archivo/línea, alcance y lo no demostrado.

1. ¿El alcance técnico implementado cumple sus contratos y requisitos verificables?
   Respuesta: pendiente.
2. ¿Existen defectos técnicos demostrados que impidan el cierre?
   Respuesta y reproducción: pendiente.
3. ¿Qué requisitos de ADR-032 siguen sin satisfacerse, incluidos adjudicación externa
   y positivos reales de la revisión de atribución?
   Respuesta: pendiente.
4. ¿Qué evidencia semántica independiente falta?
   Respuesta: pendiente.
5. ¿Es metodológicamente defendible un cierre técnico limitado y bajo qué alcance?
   Respuesta: pendiente.
6. ¿Qué limitaciones deberían mantenerse explícitas después de ese cierre?
   Respuesta: pendiente.
7. ¿Qué capacidades podrían considerarse aptas para iniciar Phase 4C.3 y con qué condiciones?
   Respuesta: pendiente.
8. ¿Qué integración o uso operativo debe continuar prohibido?
   Respuesta: pendiente.
9. ¿Qué evidencia adicional sería imprescindible antes de cualquier integración?
   Respuesta: pendiente.
10. ¿Qué decisión concreta debe adoptar el propietario, sin atribuirla anticipadamente?
    Respuesta: pendiente.

Registrar hallazgos por ID de matriz, distinguiendo defecto demostrado, evidencia
insuficiente, criterio propuesto y recomendación. Para cada uno: severidad razonada,
reproducción o fuente, efecto sobre cierre y 4C.3, condición de resolución y
limitación residual. No modificar referencias para producir un resultado favorable.

## Resultado — elegir solo al emitir el dictamen

- [ ] Aprobado para el alcance revisado.
- [ ] Aprobado con condiciones.
- [ ] No aprobado.
- [ ] Evidencia insuficiente.

Justificación y alcance exacto del resultado: pendiente.
No confundir aceptación de arquitectura/contratos con calidad semántica,
aptitud operativa o autorización de Phase 4C.3.

## Preguntas obligatorias

| Nº | Pregunta | Respuesta y evidencia archivo/línea |
| --- | --- | --- |
| 1 | ¿El alcance técnico implementado cumple sus contratos y requisitos verificables? | Pendiente |
| 2 | ¿Existen defectos técnicos demostrados que impidan el cierre? | Pendiente |
| 3 | ¿Qué requisitos de ADR-032 siguen sin satisfacerse, incluidos casos nuevos adjudicados externamente y positivos reales? | Pendiente |
| 4 | ¿Qué evidencia semántica independiente falta? | Pendiente |
| 5 | ¿Es metodológicamente defendible un cierre técnico limitado y qué condiciones documentadas admitiría o dejaría abiertas? | Pendiente |
| 6 | ¿Qué limitaciones deben mantenerse después de ese cierre? | Pendiente |
| 7 | ¿Qué capacidades podrían considerarse aptas para iniciar un alcance específico de Phase 4C.3 y con qué evidencia? | Pendiente |
| 8 | ¿Qué integración o uso operativo debe continuar prohibido? | Pendiente |
| 9 | ¿Qué evidencia adicional sería imprescindible antes de cualquier integración? | Pendiente |
| 10 | ¿Qué decisión concreta debe adoptar el propietario? | Pendiente |

## Hallazgos y condiciones

Por cada hallazgo completar sin alterar las fuentes:

- ID y requisito(s) de la matriz: pendiente.
- Naturaleza: defecto técnico demostrado / requisito no demostrado / limitación /
  discrepancia documental / recomendación. Pendiente de elegir.
- Fuente normativa exacta; si es propuesta o recomendación, declararlo: pendiente.
- Evidencia verificable, versión/hash, reproducción permitida y contraejemplo: pendiente.
- Estado (Cumplido / Cumplido con limitaciones / No demostrado / Incumplido / No aplicable): pendiente.
- Severidad justificada, efecto sobre cierre y sobre 4C.3 por separado: pendiente.
- Tratamiento requerido, responsable y evidencia para considerarlo resuelto: pendiente.
- Incertidumbres y alternativas descartadas: pendiente.

Debe pronunciarse expresamente sobre identidad/participación/exposición,
falsas confirmaciones, negaciones, cifras/períodos, fechas/PIT, parciales fieles,
omisiones, fallos/rechazos y las diferencias de clasificación del piloto.
No recuperar respuestas expiradas para completar la evaluación histórica.

## Alcance de continuidad recomendado, sin autorizarlo

- Condiciones previas al eventual cierre técnico: pendiente.
- Condiciones previas al eventual inicio de 4C.3: pendiente.
- Trabajo que puede permanecer pendiente y fundamento: pendiente.
- Calibración temporal y experimento v3/v4, sin declararlos realizados: pendiente.
- Prohibiciones que deben conservarse: pendiente.
- Necesidad de decisión metodológica nueva ante condiciones existentes diferidas: pendiente.
- Decisión posterior del propietario: **no registrada por esta plantilla**.

Conservar los estados existentes hasta una autorización posterior válida:
`integral_pilot_completed=false`, `semantic_truth=not_assessed`,
`factual_timing_rehabilitated=false`, Phase 4C.2 `implemented_pending_external_review`
y Phase 4C.3 `not_started`.
