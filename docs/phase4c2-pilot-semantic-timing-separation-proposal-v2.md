# Separación de aprobación, cierre y medición del piloto — propuesta v2

Estado: `proposed_pending_owner_approval`; implementación: `not_implemented`.
Alcance: seis revisiones factuales del piloto de desarrollo. No cambia estados,
contratos, validadores ni requisitos del experimento reservado. Complementa la
propuesta v1 sin reescribirla. Sus descripciones de casos pendientes son snapshots
anteriores; el balance y las seis decisiones posteriores documentan la aprobación.

## Decisión recomendada

Reconocer cuatro ejes mediante un registro metodológico lateral versionado,
conservando las anotaciones aprobadas byte por byte. Permitir, después de aprobar
e implementar esta adaptación, un cierre explícito de contenido sin medición
temporal. Ese cierre no se traduciría a `completed` del formulario histórico ni
a piloto integral completado. No se aplica ninguna transición en esta entrega.

| Eje | Qué acredita | Condiciones propuestas | Situación de los seis casos |
| --- | --- | --- | --- |
| Contenido factual aprobado | Decisión sobre una versión exacta | Caso, fingerprint del paquete, hash literal de anotación y de aprobación, alcance, persona que decide, fuente de su decisión, origen ChatGPT y límites de independencia | Seis aprobados documentalmente; no repetir lectura ni aprobación del mismo contenido |
| Formulario factual cerrado | Finalización explícita de un proceso bajo un modo identificado | Integridad, 13 dimensiones evaluadas, citas válidas, cobertura material justificada, observaciones resueltas o incertidumbres expresas, aprobación vinculada al hash y decisión de cierre separada | Los seis siguen `in_progress`; sin cierre formal aplicado |
| Cronometraje válido | Mediciones de tareas y períodos identificados | Procedencia real, reloj/método, intervalos reales y zona, coherencia de sumas, cobertura de tarea, vigencia y revisión de calidad | Ninguno tiene medición completa; conservar declaraciones parciales |
| Elegibilidad para estimar esfuerzo humano | Uso de una medición válida para una población y tarea determinadas | Cronometraje válido para ese alcance, tarea y asistencia declaradas, familiaridad documentada, tiempo humano separado de espera/IA y exclusiones explícitas | Los seis intentos se excluyen de estadísticas medidas de esfuerzo/capacidad; no se excluyen de historia cualitativa |

La aprobación del contenido no acredita independencia, verdad exhaustiva ni
adjudicación. Un cronometraje coherente tampoco demuestra independencia ni
representatividad. Una incertidumbre explícita no impide por sí sola cerrar el
contenido: cierre no significa que todas las dimensiones deban ser concluyentes.

## Hallazgos en el protocolo y el código actuales

Fuentes: balance v1; propuesta metodológica v1; guía del operador; protocolo v3/v4;
`tools/evaluation/development_pilot_review.py` y sus esquemas generados.

- `Factual` admite `unfilled/in_progress/completed`; no tiene aprobación, autoría
  o elegibilidad temporal. `validate_factual` valida IDs, dimensiones, enlaces,
  citas y offsets. Para `completed` prohíbe dimensiones sin evaluar. No comprueba
  aprobación, entailment, materialidad semántica ni cronometraje.
- La guía exige revisar evidencia, conservar incertidumbre y cerrar la fase en
  el registro de tiempos antes de marcar `completed`. Es una obligación operativa
  más fuerte que la función factual aislada. No usar esa diferencia como atajo.
- `validate_timing` admite `owner_declared`: no exige origen de plataforma.
  Una declaración de 20/30 segundos sin inicio ni intervalos no satisface el flujo.
  Para registros no vacíos exige identidad/procedencia e inicio; contrasta
  intervalos consecutivos, pausas y totales. Para `completed` exige fin, totales,
  fases, intervalos y estados de discrepancia/adjudicación. No certifica el reloj.
- `validate_forms` exige exactamente seis casos con factual, contractual y timing;
  rechaza anotación con timing vacío (`annotation_without_provenance`). No define
  un éxito parcial de aprobación semántica sin tiempos. `--allow-incomplete` no
  omite ese control. Los directorios documentales con archivos extra no son ese
  inventario integral y no deben presentarse como si lo hubieran aprobado.
- `validate_contract` rechaza anotaciones si el factual no está `completed`
  (`factual_must_close_before_contract`). El agregado exige cierre factual temporal
  y un intervalo contractual (`contract_without_separate_timing`). La función
  temporal también rechaza revisión contractual anterior al cierre. Ningún
  sidecar actual satisface automáticamente esas condiciones.
- No existe una garantía única de cierre: poner `completed` en el factual y pasar
  su validador aislado no cumple la guía. El agregado tampoco valida la decisión
  del propietario ni la correspondencia semántica material. Hace falta un gate
  explícito; no cambiar silenciosamente el significado de los estados existentes.

No se cambian endpoints, umbrales, independencia exigida para determinadas
afirmaciones ni criterios de adopción del experimento. El ensayo asistido de
desarrollo no satisface automáticamente sus requisitos de referencia o capacidad.

## Cambio mínimo propuesto, todavía sin implementar

1. Añadir un instrumento externo, `news-pilot-review-disposition-v1`, con los
   cuatro ejes separados. Un registro por caso enlazaría la anotación y la decisión
   existentes; sin copiar textos, reescribir aprobaciones ni asignar nuevos tiempos.
   Campo de estado histórico solo de lectura: `legacy_factual_status`.
2. Proponer para cierre `open`, `closed_content_only_untimed` y
   `closed_under_legacy_protocol`. El segundo exige una decisión explícita de cierre
   bajo la adaptación aprobada; no se deduce de la aprobación del contenido ni de
   esta solicitud de propuesta. `closed_under_legacy_protocol` requiere cumplir
   la guía y validar la sesión factual real, incluido `factual_closed_at` y ausencia
   de ediciones posteriores. No exige que ya haya terminado la revisión contractual.
   El cierre integral sigue separado y exige los tres formularios completos.
3. Separar estado temporal (`unknown`, `estimate_only`,
   `declared_duration_unvalidated`, `valid_measured_scope`,
   `valid_complete_measurement`, `invalid_or_expired`) de elegibilidad
   (`excluded`, `eligible_for_named_scope`). Todo uso exige alcance y motivos;
   una lectura medida no habilita estimar todo el trabajo factual/contractual.
   Estados y campos son diseño propuesto, no enums añadidos a los contratos v1.
4. Incorporar después un verificador offline específico, opt-in, que compruebe
   vínculos, decisiones y compatibilidad sin interpretar la aprobación como tiempo
   o verdad. Sus resultados no sustituirían el éxito del validador integral v1.
5. Para avanzar posteriormente a contractual sin medir retrospectivamente el factual,
   diseñar un adaptador de revisión del piloto v2: consumiría la disposición de
   cierre y el SHA del factual v1 sin cambiar su `status`. Exigiría aprobación de
   la adaptación, cierre explícito válido y autorización separada de apertura.
   La futura sesión contractual tendría identidad y reloj propios; no utilizaría
   su inicio como fin ficticio de la revisión factual anterior. Si necesita otro
   formulario, versionarlo como instrumento del piloto, sin tocar el contrato
   económico productivo v3. Mantener intacto el camino v1 y sus bloqueos.

No bastaría añadir una excepción al guard del contrato actual: también deben
versionarse la procedencia y el agregado, que hoy enlazan cierre y tiempos. La
alternativa de repetir o inventar tiempos para conseguir `completed` se descarta.
No se recomienda sustituir todos los esquemas del piloto; el adaptador separado
limita el cambio al modo exploratorio explícito y mantiene el replay v1.

Superficie concreta de una implementación posterior: un nuevo módulo offline
`tools/evaluation/pilot_review_disposition.py`, su esquema generado en un directorio
versionado nuevo y tests dedicados en `tests/unit/`. El mismo módulo puede alojar
el gate del adaptador v2, sin otro servicio o repositorio. Las disposiciones se
guardarían fuera de los directorios de formularios v1 (su inventario es exacto).
Una guía adicional describiría el modo nuevo; no reescribir la guía histórica
fijada por manifiesto. No modificar el importador ChatGPT, el runner de inferencia,
los validadores económicos o las anotaciones. No se crea ninguno de estos módulos
en esta entrega.

## Contenido mínimo del futuro registro

- Identidad: `case_id`, fingerprint del paquete, ruta/versión/hash exactos del
  factual y ruta/hash de la decisión documental ya existente.
- Procedencia: persona que aprobó y fuente real de decisión; asistencia ChatGPT,
  propietario no independiente, adjudicación no atribuida; datos desconocidos null.
- Cierre: modo, decisión separada, fuente, versión de política y vínculo al mismo
  hash aprobado. Una fecha de registro futuro es fecha de ese nuevo acto, nunca
  hora recuperada de la revisión previa. Una actualización crea otro registro;
  una edición del factual invalida el vínculo anterior hasta nueva revisión.
- Tiempos: referencia a mediciones reales si existen; declaraciones y estimaciones
  conservadas con su naturaleza; alcance, faltantes, motivo de exclusión y origen.
  No obtener tiempos de nombres de carpetas, filesystem, noticias o aprobación.
- Elegibilidad: alcance humano/tarea/población, inclusión o exclusión motivada,
  asistencia, familiaridad y evidencia del reloj. No deducir tiempo humano de
  latencia de IA ni atribuirle esperas. La independencia se mantiene en otro eje.

No cambiar retenciones mediante el sidecar: timing sigue 90 días desde
`completed_at` conforme al instrumento existente; no se usa un cierre nuevo para
renovar el plazo. La política y el lector del nuevo registro deben distinguir
aprobación documental de referencias a timing y bloquear uso de metadata temporal
vencida. Una aprobación sin reloj no inicia una medición perpetua. Las respuestas
de proveedor siguen 24 horas; no se copian aquí. La retención de anotaciones
sintéticas propias permanece separada, sin atribuirles contenido de proveedor.

## Aplicación propuesta a la historia existente

Reutilizar las seis decisiones y el inventario del balance, verificando sus hashes;
no volver a juzgar los hechos. Los seis pueden conservar `owner_approved_content`.
El cierre nuevo permanecería abierto hasta aprobar la adaptación y emitir su acto
de cierre; ningún `in_progress` cambiaría automáticamente.

Caso 1: tiempo desconocido. Caso 2: aproximadamente un minuto estimado. Casos 3–6:
30, 20, 30 y 20 segundos declarados, respectivamente, no validados como sesiones.
Los seis se excluyen de estimaciones medidas. Se puede informar literalmente esas
declaraciones, sin sumar, promediar, imputar ceros o proyectar capacidad. Una futura
sesión cronometrada tendría otro ID, declararía familiaridad y mediría solo trabajo
nuevo; no rehabilita ni reemplaza los tiempos de estos seis intentos.

## Riesgos y pruebas requeridas antes de implementar o consumir

| Riesgo | Prueba offline necesaria |
| --- | --- |
| Convertir aprobación en cierre o en medición | Fixture con contenido aprobado, timing desconocido: conservar aprobación, bloquear cierre automático, métricas e inicio contractual |
| Falso vínculo de versión | Cambiar un byte, case_id, fingerprint, hash de aprobación o destino: rechazo; detectar duplicados y cadena de supersesión incoherente |
| Alterar replay histórico | Cargar seis formularios y aprobaciones existentes sin reescritura; mantener hashes y fallos v1; camino nuevo solo opt-in |
| Forzar incertidumbre a certeza | Permitir cierre con dimensiones insuficientes/indeterminadas justificadas; bloquear dimensiones sin evaluar, citas incorrectas y cobertura material sin decisión |
| Confundir validación y verdad | Salida siempre declara alcance estructural; no generar afirmaciones de entailment, independencia o adjudicación a partir del éxito técnico |
| Inflar esfuerzo o capacidad | Excluir estimaciones y declaraciones sin evidencia de intervalos; rechazar duraciones negativas, huecos, solapes, sumas incorrectas y tiempos futuros/sin zona; ninguna imputación de cero |
| Tratar un fragmento como sesión completa | Lectura prospectiva válida solo elegible para lectura; tiempo humano separado de IA/esperas; actividad familiar no presentada como primera lectura |
| Cambiar el gate contractual por un bypass | Cierre faltante, adaptación no aceptada, autorización de apertura ausente o hash distinto: bloqueo; modo v1 conserva sus guards |
| Eludir retención | Fronteras antes/en vencimiento de timing; no renovar TTL con nueva disposición, no leer respuestas expiradas; aprobar contenido no habilita mediciones vencidas |
| Promover el piloto al experimento | Cierre sin tiempo no satisface capacidad TTL, freeze reservado, adopción de prompt o permiso de inferencia; pruebas de no efectos laterales |

Las pruebas futuras usarán fixtures mínimas en temporales, no nuevos casos de
evaluación ni predicciones. No se escriben todavía código, esquemas o fixtures
de la adaptación: primero se solicita decidir sobre esta propuesta concreta.
Después correspondería implementar el instrumento/gate y su compatibilidad,
ejecutar pytest completo y verificaciones de paquetes, hashes y ausencia de red.

## Secuencia para resolver el bloqueo

Primero aprobar o corregir la adaptación y su alcance sin reaprobar los hechos.
Después implementar y verificar offline el registro y el adaptador explícitos.
Solo entonces registrar el acto de cierre de contenido por caso, preservando
hashes y exclusión temporal. Abrir contractual requerirá una instrucción posterior;
no constituye permiso para inferencias ni cambios de fase. Calibrar esfuerzo
seguirá siendo una tarea prospectiva separada, no un requisito para conservar
las seis aprobaciones y no una medición reconstruida.

Esta entrega contiene únicamente propuesta y manifiesto documental de dependencias.
No modifica la propuesta v1, formularios, aprobaciones, cronometraje, corpus,
prompts, validadores, perfiles ni estados oficiales. No inicia Phase 4C.3.
