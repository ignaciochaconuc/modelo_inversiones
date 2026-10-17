# Phase 4C.2.2 — Diagnóstico histórico limitado por TTL

Corrida exclusiva: `nacho-synthetic-20261014-run01`.
Fecha de auditoría: 2026-10-17, America/Santiago.
Estado: **`diagnosis_limited_by_expired_content`**.
No es una nueva evaluación ni un cierre semántico. Phase 4C.3: `not_started`.

## 1. Alcance permitido y acceso denegado

El contenido venció entre `2026-10-15T20:59:49.280297+00:00` y
`2026-10-15T21:04:30.612437+00:00`. Se llamó al lector tipado
`LocalInterpretationStore.read` con la hora actual real de esta auditoría,
`2026-10-17T16:41:52.459079+00:00`: **32 bloqueos por TTL, cero contenidos
devueltos**. No se retrasó el reloj, cambió expires_at, extendió retención ni
utilizó directamente ATTEMPT_ADAPTER para sortear el bloqueo.

No se decodificaron nacho-outputs.json, los archivos cases/*.json ni los
intentos mediante vías alternativas. Tampoco se reconstruyeron citas desde
los fixtures originales, backups, mensajes anteriores o referencias ChatGPT.
El lector implementado carga y valida internamente antes de aplicar su guardia
TTL; se respetó esa interfaz existente y no se extrajeron sus objetos rechazados.

Se calcularon SHA-256 sobre bytes opacos, sin interpretar contenido vencido.
Se leyeron exclusivamente metadata de plan.json, audit.json previamente
sanitizado, ledger SQLite en modo read-only e índices de cache que solo guardan
IDs, fingerprints, modelo y timestamps. No se llamó cache_get para recuperar
interpretaciones. Un puntero de éxito no autoriza leer el contenido apuntado.

Consecuencia: no es posible cumplir honestamente la revisión textual completa
de cada respuesta histórica. Etapa propuesta concreta, citas, magnitudes,
identificadores emitidos y alcance semántico de negaciones quedan
`indeterminate` donde no existe metadata independiente suficiente.

## 2. Integridad y evidencia verificable

- nacho-outputs.json SHA-256 correcto:
  `c9181bee95769a0d13928d768a3490c83de2377ba93aa9f60eb4252d14479fa4`.
- audit.json histórico SHA-256:
  `241d4d13cd18b671a987cc629c6f4168aac4b33e2cd0dfa992cd48ea94d378e9`.
- Los 71 hashes del manifiesto histórico coinciden, sin decodificar sus archivos
  de contenido. El freeze conserva
  `1484dab560f898c71a857c40d3fe9ee3312981cbafdfa2eb4936b1e093fbfb39`.
- 32 case_id únicos y sus fingerprints están en el plan; cada cache_key enlaza
  una reserva/attempt_id de ledger. SQLite integrity_check=ok.
- Código de producción, runner, CLI y configuración coinciden con los
  fingerprints del plan original. Las reglas inspeccionadas son las utilizadas
  por esa corrida, no revisiones posteriores.
- Según el informe sanitizado producido antes del vencimiento: 29
  invalid_response, una interpreted, dos abstained; cero errores técnicos,
  costes desconocidos o casos no ejecutados. Son hechos históricos de metadata,
  no una revalidación semántica realizada hoy.

La metadata agregada conserva estos diagnósticos primarios:

| Etapa | Regla | Casos | Campo sanitizado |
| --- | --- | ---: | --- |
| evidence_resolution | unknown_evidence_id | 3 | identity_evidence dos veces y evidence una |
| semantic_validation | stage_not_supported | 22 | events.state_evidence |
| internal_schema | numeric_fidelity | 3 | events.0.numbers.0 dos veces; events.1.numbers.0 una |
| semantic_validation | negation_lost | 1 | events.negated |

No se conserva en audit.json la asociación de cada diagnóstico con su case_id.
La ruta events.state_evidence tampoco conserva el índice concreto del evento.
No se adivina esa asociación a partir del orden, el coste o la longitud del
archivo. Los diagnósticos son primeros fallos observados, no inventarios
exhaustivos de todos los problemas que pudiera contener cada respuesta.

## 3. Etapas: qué causó el bloqueo y qué no puede concluirse

Código exacto: `replay.py:99–106`, función validate_payload_evidence;
mapeo a diagnóstico genérico: `grounding.py:99–100`.

Para stage=completed se exige que state_evidence.quote, tras casefold, contenga
una palabra completa de este conjunto: completed, closed, finalized.
Si no ocurre, se lanza "completion not supported by state evidence".
Para announced o proposed se exige la propia palabra completa de la etapa;
de lo contrario se lanza "event stage not explicitly supported".
Ambos errores se convierten en stage_not_supported y events.state_evidence.

Por tanto, los 22 casos activaron alguna de esas dos condiciones. La etapa
necesariamente era completed, announced o proposed; la metadata no permite
determinar cuál, ni la cita exacta o qué evento falló. No puede decidirse por
caso si hubo contradicción real, cita insuficiente, cita equivocada o un
falso positivo léxico. Confianza alta en el mecanismo de rechazo y
`indeterminate` en su corrección semántica histórica.

El prompt exige preservar anuncio/cierre pero no enumera estas condiciones
léxicas del validador. Existe un posible desajuste entre selección semántica del
modelo y contrato léxico efectivo. Esto es una hipótesis general sustentada
por código, no prueba de que los 22 fueran errores del modelo o del validador.

En texto ficticio nuevo se comprobó que una formulación como "has acquired"
no satisface completed; las variantes announces/plans tampoco satisfacen
announced/proposed. Las formas literales sí pasan y unknown permanece permitido.
Esto demuestra una limitación de recall/morfología; no certifica que toda
expresión adquisitiva implique cierre legal ni justifica aceptar estas 22
respuestas retrospectivamente.

**Tratamiento propuesto:** primero aclarar en un prompt futuro/versionado cuándo
elegir unknown bajo la política vigente. Si se pretende admitir equivalencias
semánticas, diseñar una nueva política con casos independientes de anuncios,
cierre efectivo, hipótesis y negación. No eliminar el control ni convertir
automáticamente proposed/announced en completed. Mantener estos rechazos.

## 4. Identificadores, números y negaciones

### Tres unknown_evidence_id

`grounding.py:161–172`: el resolver busca el ID propuesto en el mapa de evidencia
elegible del request. Si no existe, rechaza antes de buscar la cita. Un ID
existente de otra revisión usa wrong_revision; una cita ausente con ID conocido
usa otra regla. Por eso el fallo observado es de identidad/resolución o
vinculación de evidencia, no una prueba de JSON inválido ni de texto inventado.

Campos históricos agregados: events.0.entities.2.identity_evidence,
events.0.entities.1.evidence y events.0.entities.1.identity_evidence.
No se conocen hoy los valores emitidos. Posibilidades: ID fabricado/truncado,
ID de otro campo/revisión, confusión de namespace o defecto de mapeo. No puede
elegirse una causa. El código preparador incorpora explícitamente los digests
al envelope; el plan registra el mapa case_id:field → digest. No hay evidencia
positiva de un bug de mapeo, pero tampoco se inspeccionó hoy el valor vencido.

Confianza alta en el tipo de guardia activada; causa concreta `indeterminate`.
Mantener el rechazo. En una versión futura, considerar enums/referencias de
evidencia válidas por request y tests de namespaces, sin reparación automática,
lookup difuso ni reutilización de IDs entre revisiones.

### Tres numeric_fidelity

`schemas.py:180–198` agrupa seis posibilidades:
lexema no parseable; valor transformado/no coincidente con Decimal del lexema;
número no presente en el contexto; unidad inexistente; escala no literal;
período no literal. El diagnóstico actual no conserva cuál de ellas ocurrió.
El parseo elimina comas; las comprobaciones restantes exigen literalidad.

La etapa internal_schema indica que la validación interna de NumericClaim falló
después de la selección/resolución, no que el transporte fuera inválido.
No puede atribuirse a "alucinación numérica" sin conocer value/value_text,
unidad/escala/período y contexto. También podrían existir ambigüedades de
formato o desajustes de representación; quedan `indeterminate`.

Se reprodujeron las seis ramas con ejemplos nuevos, sin leer números originales.
Mantener el rechazo; priorizar subcódigos sanitizados distintos en una futura
versión y ejemplos de representación literal, sin normalizaciones financieras
silenciosas. Cualquier cambio de parsing/unidades requiere contrato versionado,
pruebas de locale/signos/escalas y revisión independiente.

### Un negation_lost

`replay.py:104–106`: si state_evidence.quote contiene una palabra completa entre
not, never, no, denied, denies y event.negated es false, rechaza. No determina
a qué proposición se aplica la negación.

Un test nuevo con dos proposiciones —cierre afirmado y precio no divulgado—
activa el rechazo. Demuestra un posible falso positivo de alcance; un segundo
test comprueba que la negación real del cierre tampoco puede perderse.
Nada permite saber si el caso histórico tenía negación de evento o de una
afirmación incidental. Confianza alta en el riesgo general, histórica
`indeterminate`. No marcar negated=true solo para atravesar el validador.
Proponer citas más locales y, separadamente, diseño versionado de alcance de
negación con controles contra confirmaciones falsas. Mantener el rechazo histórico.

## 5. Interpretación aceptada y abstenciones

No pueden revisarse sus afirmaciones ni motivos por caso sin usar contenido
vencido. La metadata agregada conserva una interpretación y dos abstenciones,
con tres motivos de abstención en total: unattributed_rumor una vez e
insufficient_evidence dos veces. No hay asociación retenida a los tres casos.

Se localizaron tres índices de éxito metadata-only, vinculados al plan y al
ledger. El código solo escribe esos índices tras interpreted/abstained.
Sus fingerprints coinciden con el manifiesto anterior al vencimiento.
Esto distingue el conjunto de tres éxitos técnicos, no su subtipo ni su
corrección semántica. Los otros 29 se infieren como rechazados apoyándose en
el informe histórico sin fallos de persistencia y los 32 intentos completos.
No se está usando el índice como cache/replay de interpretaciones.

No puede descartarse falso vínculo corporativo, rol incorrecto, impacto no
sustentado, omisión, abstención excesiva o falsa abstención. El estado operativo
permanece falso. No se promueve ninguno a "semánticamente correcto".

## 6. Matriz de los 32 casos

La matriz completa con fingerprints originales, request/cache/attempt UUID,
hash de archivo de caso y coste liquidado está en
`data/reports/news/phase4c2_rejection_diagnosis_ttl_limited.json`.
No contiene citas, textos de noticia, respuestas o referencias esperadas.

Leyenda:
- **R**: rechazado inferido desde metadata verificada, no relectura del resultado.
- **S**: interpreted o abstained por índice metadata-only; subtipo indeterminate.
- **M**: confianza alta en la clasificación metadata, condicionada al audit
  histórico sin fallos y a la semántica del índice; confianza causal indeterminate.
- **K1**: preservar rechazo, no reparar; falta contenido para adjudicar causa.
- **K2**: no certificar éxito semántico ni distinguir subtipo; revisión bloqueada.
- Para todas las filas, etapa propuesta y evidencia textual: no disponibles por
  TTL. La regla individual y causa raíz no pueden asignarse desde los agregados.

| case_id | Estado por metadata | Causa observada por caso | Confianza metadata / causal | Tratamiento |
| --- | --- | --- | --- | --- |
| `S-08ab6f2771fbf4a6` | R | indeterminate | M / indeterminate | K1 |
| `S-0b348ae4d5f9db5b` | R | indeterminate | M / indeterminate | K1 |
| `S-0dfb4b77b037b9da` | R | indeterminate | M / indeterminate | K1 |
| `S-101a16357b30a7ab` | R | indeterminate | M / indeterminate | K1 |
| `S-17c18cde08a18186` | R | indeterminate | M / indeterminate | K1 |
| `S-21369de6ca9529c4` | R | indeterminate | M / indeterminate | K1 |
| `S-250bf0fb27a44ef6` | S | indeterminate | M / indeterminate | K2 |
| `S-261f5495206977cc` | R | indeterminate | M / indeterminate | K1 |
| `S-2a6f842eeab8cddb` | S | indeterminate | M / indeterminate | K2 |
| `S-337b4818cb47ae90` | R | indeterminate | M / indeterminate | K1 |
| `S-35a0c5b8faaa5741` | R | indeterminate | M / indeterminate | K1 |
| `S-3735adaf106afa39` | R | indeterminate | M / indeterminate | K1 |
| `S-3c30cb40dd71e6ca` | R | indeterminate | M / indeterminate | K1 |
| `S-40501aee7851586a` | R | indeterminate | M / indeterminate | K1 |
| `S-4a310ed5f76719a3` | S | indeterminate | M / indeterminate | K2 |
| `S-4e663c72421c23f0` | R | indeterminate | M / indeterminate | K1 |
| `S-52efc69a6674d077` | R | indeterminate | M / indeterminate | K1 |
| `S-5cd02bc28bc2405b` | R | indeterminate | M / indeterminate | K1 |
| `S-5e06c61a620d1290` | R | indeterminate | M / indeterminate | K1 |
| `S-5e1d0147e0529b8c` | R | indeterminate | M / indeterminate | K1 |
| `S-5e4223789f2cdc0f` | R | indeterminate | M / indeterminate | K1 |
| `S-69a88ea765d353b5` | R | indeterminate | M / indeterminate | K1 |
| `S-6c4db24e38ef94dc` | R | indeterminate | M / indeterminate | K1 |
| `S-7394579424f4d7e8` | R | indeterminate | M / indeterminate | K1 |
| `S-8640db367d8f2e35` | R | indeterminate | M / indeterminate | K1 |
| `S-91e5c93f0cf4ece5` | R | indeterminate | M / indeterminate | K1 |
| `S-aa6dc0bc8f72b6b1` | R | indeterminate | M / indeterminate | K1 |
| `S-bd80c0631533bf42` | R | indeterminate | M / indeterminate | K1 |
| `S-c0e6d5edb8735e03` | R | indeterminate | M / indeterminate | K1 |
| `S-c2c94e2676dcb74e` | R | indeterminate | M / indeterminate | K1 |
| `S-c2f36114546f9be5` | R | indeterminate | M / indeterminate | K1 |
| `S-d73a2bcb6f94338a` | R | indeterminate | M / indeterminate | K1 |

Los 22 casos stage_not_supported, los tres unknown_evidence_id, los tres
numeric_fidelity y el caso negation_lost están incluidos entre las 29 filas R,
pero no pueden repartirse responsablemente entre ellas con la metadata retenida.

## 7. Priorización — propuestas, no cambios implementados

| Prioridad | Capa | Propuesta | Salvaguarda |
| --- | --- | --- | --- |
| P0 | Observabilidad/retención | En futuras corridas, guardar antes del TTL un sidecar sanitizado por caso con outcome, record_id, rama precisa de regla, enums de etapa y rutas, con política propia explícita | Sin citas/respuestas; no extender TTL histórico ni atribuir retrospectivamente subcódigos |
| P1 | Prompt | Explicar unknown frente a equivalencias no admitidas de etapa; evidencia local de evento; cifras tal como están impresas | Nueva versión, sin aceptar por decreto los 29 ni ajustar contra este conjunto como holdout |
| P1 | Esquema/mapeo | Restringir IDs seleccionables a los del request; tests de namespace/revisión y vínculo exacto | No aliases automáticos, ningún fuzzy match ni mapeo de identidad inventado |
| P1 | Validador de negación | Investigar alcance proposicional con positivos y negativos nuevos | No quitar guardias ni marcar negaciones artificiales; aprobación/versionado posterior |
| P2 | Validador de etapa | Definir si equivalencias morfológicas/semánticas deben admitirse y qué constituye cierre | No confundir anuncio y cierre; evaluación nueva independiente, no reparaciones históricas |
| P2 | Contrato numérico | Separar subcódigos y evaluar reglas explícitas de formatos/unidades/escala | Nunca aceptar valores transformados o unidades/períodos no respaldados |

Se mantienen los rechazos bajo los contratos históricos. No se estima cuántos
deberían aceptarse con otra política, ni precisión/recall. Las demostraciones
sintéticas son desarrollo diagnóstico, no validación independiente de mejoras.
No se ejecuta una segunda evaluación ni una comparación contra ChatGPT.

## 8. Validaciones y conservación

- Export y 71 hashes históricos verificados sobre bytes opacos.
- 32 intentos bloqueados por el lector tipado con reloj actual; cero contenidos
  devueltos y ninguna copia alternativa de respuestas recuperada.
- Producción, runner, CLI y perfil coinciden con el plan histórico.
- Tests diagnósticos nuevos: 16 aprobados, únicamente validadores y texto nuevo,
  sin modelos, prompts, APIs, cache, registro histórico o referencias congeladas.
- Suite completa: 721 aprobados, 87,96 s; fixtures simuladas, no reevaluación LLM.
- No se purgó ni alteró nada. Informe/matriz/tests nuevos se guardan por separado.
- Control final SHA-256: cero cambios en 3.631 archivos existentes de data,
  src, scripts, tools, config, evaluation, docs y tests. Se excluyen únicamente
  los tres archivos nuevos de esta tarea y bytecode. Export, metadata histórica,
  ledger, índices, intentos y referencias permanecen intactos.

No hay llamadas API, inferencias nuevas, cambios de contrato/prompt/validador,
comparación ChatGPT, Feature Store, TEST oficial ni inicio de Phase 4C.3.
