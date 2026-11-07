# ADR-040 — Reintento contractual por cronometraje incompleto

## Estado

Extensión administrativa implementada por instrucción del propietario. No
autoriza preparar el segundo workspace real, abrirlo ni iniciar sus actividades.

## Contexto

Bravqulin tiene 13 mappings técnicamente válidos, formulario `in_progress` y
sesión `completed`, sin intervalo activo de `contract_mapping`. El bloqueo es
correcto: una sesión terminada no se reabre y los tiempos no se reclasifican.
El flujo ordinario de ADR-039 tampoco permite preparar desde una selección con
un caso en progreso. No se debe eludir ese control usando un manifiesto viejo.

## Decisión

Añadir exclusivamente `prepare-retry`, con motivo enumerado y verificado:
`contract_mapping_not_timed` u `owner_review_not_timed`. El origen debe ser un
workspace validable del mismo caso, sin aprobación contractual, con formulario
`in_progress`, todos sus mappings y sesión terminada. El motivo debe corresponder
a una fase realmente no registrada. Otros casos solo pueden estar `completed`
o `unfilled`. No cambia la elegibilidad de `prepare` ordinario.

Usar `news-pilot-contract-workflow-v2` solo para reintentos y
`news-pilot-contract-retry-lineage-v1` para su linaje. Los contratos económicos,
formularios v2, sesiones v1, autorizaciones v1, decisiones v1 y validadores de
ADR-038 permanecen intactos. El workflow-v1 sigue leyéndose como antes.

El nuevo manifiesto selecciona una copia vacía del formulario del caso y una
sesión completamente nueva, manteniendo referencias originales de los otros
cinco. El intento anterior conserva su selección, estado y todos sus archivos.
El linaje fija por hash su workflow, manifiesto, formulario, sesión e inventario
completo, además de ambos review_id y el motivo. Se verifica en cada operación
del nuevo flujo. No hay reemplazo o suma de sesiones ni `supersedes` que cambie
un estado histórico.

Conservar los mappings, resultados propuestos y rationale exactos en una entrega
derivada con nuevo review_id. No importarlos al formulario ni marcarlos aprobados.
La procedencia indica explícitamente que no es evaluación independiente y que
no se transfirieron tiempos. Generar plantillas nuevas de apertura y aprobación
con aprobación/autorización null; el fingerprint final solo se calcula después
de una sesión nueva completada. Se requiere nueva autorización real por review_id.

## Límites y consecuencias

La revisión nueva debe medir trabajo humano real de verificación contractual y
revisión del propietario, no solo un contador o el procesamiento del importador.
Pausas y espera de ChatGPT se mantienen separadas. Si es fiel, el contenido puede
reutilizarse como propuesta; no se repite automáticamente la revisión factual.

El lector anterior aplica su TTL antes de auditar inventario o resolver linaje.
No se revive un intento vencido. El reintento tampoco renueva la retención de su
predecesor: si vence, se bloquea la reverificación de la cadena mediante este
instrumento. Resolver ese escenario necesitaría otra decisión metodológica;
no se ofrece una vía alternativa de lectura.

Los recibos, aprobación de contenido y autorización de cierre del nuevo intento
siguen siendo actos separados. Los fingerprints incluyen la nueva referencia de
sesión, por lo que no se hereda una aprobación del intento anterior. No hay
recuperación automática ante I/O parcial ni permisos implícitos para modificar
el predecesor. No se alteran estados oficiales ni se autoriza inferencia.

Guía: [reintento contractual](../phase4c2-contract-retry-v1.md).
