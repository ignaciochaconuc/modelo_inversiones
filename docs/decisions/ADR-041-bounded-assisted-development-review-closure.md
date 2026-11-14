# ADR-041 — Cierre documental acotado de la revisión factual/contractual asistida

## Estado, versión y autoridad

Registro metodológico documental autorizado, versión 1. Fuente: instrucción expresa
del propietario en la conversación, titulada «Phase 4C.2 — Formalización documental
del cierre acotado». La instrucción autoriza exclusivamente preparar y registrar
esta documentación; no autoriza cambios técnicos, cierre integral o avance de fase.
No se atribuye aprobación independiente del documento ni una evaluación externa.

La identidad de autoridad conserva la etiqueta de los expedientes:
`Project owner, current conversation participant`. Es una identidad declarada,
no una identidad legal autenticada. No constan identificador de mensaje, firma
ni timestamp verificable de esta autorización; no se inventan.

## Contexto

ADR-037 separó aprobación factual, cierre, medición y elegibilidad. ADR-038 añadió
el formulario contractual separado; ADR-039 y ADR-040 conservaron autorizaciones
por operación y linaje de reintentos. Los seis expedientes seleccionados ahora
tienen cierre factual lateral y cierre contractual, pero los factuales históricos
siguen `in_progress` y carecen de cronometraje integral elegible.

El agregado contractual mantiene deliberadamente `integral_pilot_completed=false`.
El agregado histórico exige sus tres formularios completos. No hay equivalencia
que permita convertir los cierres laterales en un éxito integral v1.

## Decisión documental y alcance

Reconocer como concluido el procedimiento asistido de revisión de contenido factual
y representabilidad contractual de los seis casos identificados en el
[inventario v1](../phase4c2-bounded-assisted-development-review-closure-v1.md).
Este reconocimiento se limita a las versiones y evidencias allí fijadas por hash.
Documenta cierres ya autorizados: no emite nuevas aprobaciones de hechos o mappings.

Se reconocen seis cierres factuales `closed_content_only_untimed`, seis contratos
`completed`, 74 mappings, 78 evaluaciones dimensionales y 159 apariciones de citas.
Los modos registrados son seis `structured` y 68 `faithful_partial_only`.
Son resultados descriptivos del instrumento, no exactitud semántica del NewsAgent.

Las diferencias de clasificación detectadas se conservan como limitaciones
metodológicas explícitas. No se cambian juicios, rationale, evidencias o hashes,
ni se afirma una adjudicación independiente de esas diferencias.

## Exclusiones y compatibilidad

Mantener `integral_pilot_completed=false`, `semantic_truth=not_assessed` y
`factual_timing_rehabilitated=false`. No crear un agregado o un nuevo enum técnico.
La expresión «cierre documental acotado» es una descripción metodológica, no un
estado de producción. No supersede ADR-037 a ADR-040, sus controles o el flujo v1.

Conservar los seis factuales históricos `in_progress`, sus aprobaciones y cierres
laterales, el reintento anterior de Bravqulin y toda la procedencia asistida por
ChatGPT. No declarar independencia humana ni adjudicación. Los tiempos factuales
siguen excluidos; las sesiones contractuales no acreditan esfuerzo integral.

No se renueva la retención: metadata temporal contractual, 90 días desde su propio
fin; contenido de proveedor, 24 horas conforme a su política. No copiar intervalos,
duraciones o respuestas a esta documentación para eludir su vencimiento. El linaje
de Bravqulin conserva también las restricciones de lectura del predecesor.

## Pendientes y consecuencias

Permanecen pendientes la definición de alcance temporal y elegibilidad, la
calibración prospectiva del trabajo faltante, la evaluación semántica independiente,
el experimento v3/v4 y los criterios/autorizaciones de transición de fase.
No se repiten revisiones aprobadas para reconstruir tiempos desconocidos.

El siguiente trabajo recomendable es diseñar, con autorización separada, un plan
temporal por tarea y población, con asistencia, familiaridad, fases y exclusiones
declaradas. Diseñar ese plan no autoriza ejecutarlo ni iniciar inferencias.

Los estados oficiales de Phase 4C.2 y sus subfases permanecen
`implemented_pending_external_review`; Phase 4C.3 permanece `not_started`.
Este ADR no autoriza modelos, llamadas API, experimentos o interpretaciones operativas.

## Fuentes normativas

- [ADR-037](ADR-037-pilot-semantic-timing-separation.md),
  [ADR-038](ADR-038-pilot-contract-review-adapter.md),
  [ADR-039](ADR-039-opt-in-contract-review-workflow.md) y
  [ADR-040](ADR-040-traceable-contract-retry.md).
- [Disposiciones del piloto](../phase4c2-pilot-review-dispositions.md) y
  [propuesta de separación v2](../phase4c2-pilot-semantic-timing-separation-proposal-v2.md).
- [Protocolo 4C.1](../phase4c1-evaluation.md) y
  [protocolo experimental v3/v4](../phase4c2-v3-v4-experimental-protocol.md):
  evaluación, denominadores y gates propios del experimento.
- [ROADMAP](../../ROADMAP.md), [PROJECT_SPEC](../../PROJECT_SPEC.md) y
  [ARCHITECTURE](../../ARCHITECTURE.md): estado de fase y límites operativos.

