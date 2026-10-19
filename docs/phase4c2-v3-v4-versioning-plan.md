# Plan propuesto de versionamiento: comparación v3 / v4 draft2

Estado: `phase4c2_v3_v4_experiment_design_pending_review`.
No implementación, activación ni sustitución de contratos. ADR-036 sigue Proposed.
Preserva ADR-031–035 y el historial. Este diseño no otorga autorización.

## Identidad exacta y frontera de la comparación

V3 no es un archivo independiente: prepare_economic_request concatena el encabezado
económico y las instrucciones v2 heredadas. El SHA-256 UTF-8 del encabezado efectivo
(incluido newline final, antes del JSON envelope), medido offline con una request
ficticia de diseño, es:

`60cfccd2a2fbf0e5134e2cd0e4beba72112bd10765522d981d9e4925e18fa83b`

Son 2.929 bytes; no contiene evidencia de evaluación ni anotaciones. La captura
solo prepara texto, no cliente/wire de inferencia. Antes del experimento verificar
ese hash y cada wire completo, no usar el SHA de todo economic_attribution.py
como sustituto de la identidad del prompt.

Candidato seleccionado: news-interpretation-prompt-v4, **draft2**, bytes exactos
del archivo existente (8.028 bytes), SHA-256:

`7ed068f02f0f99769af7b83072d265745ffb7f6941fa9528d98fb87ae7182d34`

No normalizar line endings o espacios al cargarlo; distinguir hash de bytes del
artefacto del hash del texto efectivo que se envía. Ambos se registran, más versión,
revisión, renderer y código. Si difieren de la identidad preregistrada, bloquear.
El esquema económico de selección v3 es común: fingerprint canónico
`928e28c7a9572c983065026832d715d3080f77ee947743137c6c571bf017055d`.
No cambiar el esquema bajo un brazo ni añadir una ayuda de extracción solo a v4.

Además se debe fijar el hash del esquema **strict de transporte**, derivado por
el mismo adaptador en ambos brazos; no confundirlo con el schema Pydantic previo
a esa transformación. El candidato tiene más instrucciones que el v3 efectivo
(8.028 frente a 2.929 bytes): la reducción frente a draft1 no implica ahorro
frente al baseline de este experimento.

## Propuesta mínima, a implementar en otra tarea

| Componente | V3 preservado | V4 / experimento propuesto, no implementado |
| --- | --- | --- |
| Prompt | prepare_economic_request y texto efectivo v3 intactos | Descriptor news-prompt-artifact-v1: version v4, draft2, raw/text SHA-256 y renderer. No insertar v4 bajo etiqueta v3. |
| Settings | news-inference-settings-v4, prompt literal v3 | Tipo adicional news-inference-settings-v5, prompt literal v4 y digest/revisión obligatorios. Compartir adapter, parámetros, precios y cotas del experimento sin ampliar el enum v4 histórico. |
| Runtime/selección | Ruta histórica y validación v3 intactas | Selección explícita de renderer, mismo esquema económico v3 y mismas funciones puras de validación/resolución. No reemplazar globalmente constantes ni monkey-patchear prepare_economic_request. |
| Resultado | news-economic-result-v3 y su proveniencia intactos | Nuevo envelope de resultado versionado, propuesto news-economic-result-v4, con prompt descriptor exacto. La versión semántica sigue news-economic-validation-v3; un resultado no debe atribuirse a v3 si el prompt fue v4. |
| Replay/resolución | EconomicReplayEnvelope y rutas v1/v2/v3 históricas | Envelope nuevo, propuesto news-economic-replay-v4, conserva respuesta original, selección/resolución y resultado; resolver v1/atribución v1 compartidos. Fingerprint de invocación usa el renderer real, no el hardcode v3 actual. |
| Persistencia | StoredEconomicAttempt v4 e IDs/hashes intactos | Tipo news-inference-attempt-v5 para settings v5 y nuevo envelope; extender discriminated union con rama nueva. Mantener pares schema/settings, verificaciones de wire, costes y reproducción. Nunca migrar registros antiguos. |
| Caché | Claves históricas sin modificación | Request/evidence + settings completos + prompt descriptor + wire + validation/renderer fingerprints. Ambos brazos aislados; force_new, sin recovery. Caching del proveedor se mide, no se finge desactivado. |
| Wire/Structured Outputs | V3 efectivo reproducible, strict schema v3 | Solo instrucciones y metadata de versión inevitablemente distintas; mismo esquema strict, parámetros, evidencia y orden canónico del envelope. El diff permitido se congela y prueba; no ocultar identidad v4 para lograr wires iguales. |
| P0 | news-evaluation-diagnostics-v1, 90 días | Sidecar sin campo arm añadido; run_id distinto por brazo y manifest experimental lo vincula. Extender wrapper a settings/result nuevos mediante dispatch explícito y captura original, sin reconstruir diagnósticos desde excepciones. |
| Runner/manifests | Runner de 32 casos y manifest v1 intactos | Ejecutor experimental nuevo, news-prompt-comparison-runner-v1; manifests por brazo para 96 y manifest de pares. IDs de casos opacos, family/arm solo en control; pin de sidecar por (run,case). Sin duplicar casos para fingir 32. |
| Autorización | Registros existentes no editados ni reutilizados | Contrato nuevo de autorización experimental, ligado a ambos planes, experimento/corpus/ref freezes, prompts/código, P0/retención, modelo, orden, presupuesto agregado y 192 llamadas. No ampliar silenciosamente el límite 32 del contrato anterior. |

Los identificadores nuevos son **propuestos**, no garantías de API disponible.
Antes de implementar deben aprobarse y comprobar colisiones/versiones vigentes.
No cambia la taxonomía de salida ni la política factual; si compartir validación
requiere extraer una función pura, tests de equivalencia deben probar los mismos
resultados/diagnósticos y todos los IDs de replay históricos sintéticos, sin
abrir respuestas reales expiradas. El resultado v3 actual reconstruye su invocación
con prepare_economic_request; no sirve copiarlo y cambiar solo prompt_version.

## Fairness, verificación y autorización futura

La comparación causal propuesta es de instrucciones, no de dos pipelines con
reglas distintas. Settings v4/v5 necesariamente difieren en identidad de prompt;
congelar una whitelist de diferencias de metadata. Verificar offline que output
schema, entrada primaria/registry/cutoff, política factual y parámetros efectivos
son idénticos, y que cada brazo reproduce su propio wire y cache key. Los prompts
pueden generar entradas de distinta longitud: presupuesto de inferencia con igual
capacidad por solicitud, reserva calculada separadamente y cap global suficiente.

Tests previos a autorización: v3 byte-equivalente; replay v1–v4 compatible;
v4 no legible como v3; igualdad semántica de validación para payloads sintéticos
idénticos; IDs/wires/cache diferenciados; P0 correcto en ambos; fallo de escritura
detiene ambos sin retry; no recuperación cruzada ni backfill; ambas versiones
rechazan referencias/targets/instrucciones esperadas en el input. Dry-run no carga
credenciales, no crea ledger/resultados y no transmite nada.

Referencias quedan fuera del proceso/input del intérprete. El control congela sus
hashes/procedencia; un worker recibe únicamente el subconjunto sintético autorizado.
La implementación futura deberá demostrar esta separación, no solo declararla.

Reservar presupuestos antes de cada intento y todo el alcance antes de iniciar.
La autorización experimental futura requiere owner approval real y timestamps
con zona horaria, expiración vigente y límites por brazo + agregado. Retención
24h/90d y política P0 forman parte del fingerprint. La modalidad desarrollo
opcional tiene autorización/cupo independiente. Ningún comando de ejecución o
registro approved=true se entrega en esta fase de diseño.

Para diseño estadístico, revisión ciega, métricas y presupuesto ilustrativo, véase
[protocolo experimental](phase4c2-v3-v4-experimental-protocol.md).
