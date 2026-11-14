# ADR-042 — Instrumentación temporal prospectiva aislada

## Estado y autoridad

Implementación aislada de preparación, autorizada por el propietario mediante la
instrucción «Phase 4C.2: Preparación del piloto temporal prospectivo».
No autoriza ejecutar casos, iniciar cronómetros, mostrar material seleccionado,
inferencias, cierre integral o cambios de fase. No se inventan timestamps, firmas
o identificadores de mensaje. No se atribuye revisión técnica independiente.

## Contexto y decisión

ADR-041 reconoce seis cierres asistidos de alcance acotado. Sus factuales no tienen
mediciones completas y siguen excluidos. Los verificadores históricos están
fijados a esos seis paquetes y no ofrecen revisión factual del propietario como
fase temporal separada. Reutilizarlos con otros IDs cambiaría su significado.

Añadir exclusivamente `news-prospective-timing-pilot-v1`, CLI offline, protocolo,
plan fijado por hashes, cuatro esquemas y dos plantillas no autorizadas. Reutilizar
las convenciones de referencias SHA-256, intervalos consecutivos y autorizaciones
explícitas, sin importar ni alterar estados de los flujos históricos.

Reservar seis IDs nuevos para tres pares factual/contractual y un ID administrativo
separado, todos sin participantes, tiempos o eventos. Los candidatos son de
desarrollo, de familias distintas y fuera del piloto anterior; no son elegibles
hasta confirmar familiaridad, material y asistencia en cada sesión.

Cada inicio necesita autorización específica vinculada al fingerprint del plan,
ID de sesión, persona y declaración de familiaridad, más acción explícita con
reloj local real. El CLI no admite fechas inyectadas. Tests técnicos usan relojes
ficticios en temporales con kind=synthetic_fixture, rechazado por el CLI real.

Mantener eventos encadenados por hash, escritura exclusiva y exclusión mutua de
sesiones y administración. Una pausa no permite contabilizar actividad simultánea.
Una sesión contractual requiere factual terminada, fases cubiertas, referencia
al tip y al artefacto factual exacto y declaración real de contenido preparado.
Eso vincula etapas; no certifica el significado del artefacto.

La parada registra fin, sin aprobar ni declarar elegibilidad. La elegibilidad
requiere declaración posterior, separada y vinculada al tip, alcance completo,
trabajo declarado terminado y ausencia declarada de actividad no registrada.
Es elegibilidad por alcance bajo procedencia declarada, no autenticación del humano.

## Límites y compatibilidad

No se preparan anotaciones, mappings o respuestas esperadas. `material` solo puede
mostrar una proyección neutral del caso durante lectura activa autorizada; no se
invoca en esta entrega. Familias y etiquetas privadas no son input del revisor.
El acceso al repositorio no proporciona aislamiento absoluto: la familiaridad
real y la no consulta de respuestas deben confirmarse, no presumirse.

Retención de metadata temporal: 90 días desde su propio stop, sin renovación por
atestación. Expiración, corrupción o persistencia incompleta bloquean el lector;
no hay reparación automática, sobrescritura ni reinicio de sesiones detenidas.
No se copian respuestas de proveedor ni se cambia su TTL de 24 horas.

Solo se escribe en la ubicación nueva fijada por el plan, bajo
`data/cache/news_prospective_timing_pilot/`. No se crea ese directorio real ahora.
Plan, esquemas y plantillas son preparación, no registros de medición.

Conservar `integral_pilot_completed=false`, `semantic_truth=not_assessed`,
`factual_timing_rehabilitated=false`, fases oficiales y Phase 4C.3 `not_started`.
No se usan APIs, secretos, routers, prompts de inferencia o modelos.

## Referencias

[Protocolo del instrumento](../phase4c2-prospective-timing-pilot-v1.md),
[ADR-041](ADR-041-bounded-assisted-development-review-closure.md),
[ADR-037](ADR-037-pilot-semantic-timing-separation.md),
[ADR-038](ADR-038-pilot-contract-review-adapter.md) y
[plan temporal original](../../evaluation/phase4c2_development_corpus_v1/pilot-plan.json).

