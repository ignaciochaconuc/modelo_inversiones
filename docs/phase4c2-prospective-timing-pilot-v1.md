# Phase 4C.2 — Calibración temporal prospectiva mínima — v1

## Estado, autoridad y alcance

`prepared_pending_session_authorization`: etiqueta descriptiva de esta preparación,
sin modificación del estado oficial. Autorización real: instrucción del propietario
«Phase 4C.2: Preparación del piloto temporal prospectivo». Implementación aislada
según [ADR-042](decisions/ADR-042-isolated-prospective-timing-pilot.md).
No se inicia ninguna sesión ni se revela contenido de los casos.

El propósito es describir el trabajo de una persona en tres ciclos de desarrollo,
con preparación factual y revisión contractual separadas, no repetir las seis
revisiones cerradas ni medir calidad del NewsAgent. Tres casos es una recomendación
práctica, no un tamaño estadísticamente validado o umbral normativo de éxito.
No se autoriza aquí ningún envío a ChatGPT; una modalidad manual asistida futura
debe quedar expresamente declarada y autorizada antes de comenzar.

## Candidatos y fronteras de evidencia

| `D-5f21ec91317d6943` | `DF-7bee069935c5c291` | pendiente de confirmación por sesión |
| `D-8d5314f2c5c04bdf` | `DF-52324f86ba41ef20` | pendiente de confirmación por sesión |
| `D-bcc9cce8989c97da` | `DF-67d60d0c5faf93b7` | pendiente de confirmación por sesión |

Las tres familias son diferentes. La selección se hizo por metadatos privados
para cubrir situaciones distintas; no se reproducen aquí textos, estratos,
variantes, intención del autor o respuestas esperadas. No abrir las variantes
hermanas. Se debe confirmar exposición previa a texto, variante contrafactual,
propuestas o respuestas antes de cada sesión factual.

El corpus fuente está marcado development_only, fictional=true y sin referencias
semánticas creadas; su manifiesto registra cero reservados y ningún freeze reservado.
El lector exige esas condiciones, pins de corpus/selección/diseño y candidatos
ajenos a los seis históricos. Su sobre de caso no admite expected_answer u otros
campos ajenos al corpus. El material factual se proyecta por allowlist desde
fuente, evidencias y registry; no incluye diseño privado, predicciones o scoring.

Es una comprobación estructural y documental, no prueba de aislamiento cognitivo
del propietario. Tiene acceso al repositorio: debe confirmar que no consultó
material privado o respuestas. Si no puede hacerlo, el candidato permanece
inelegible para primera lectura; no se cambia de caso silenciosamente ni se llama
ciega o independiente a la actividad. Cualquier sustitución requiere otro plan
y autorización vinculada al nuevo fingerprint.

## Archivos y reutilización

- [Instrumento](../tools/evaluation/prospective_timing_pilot.py): no modifica ni
  usa para transiciones los adaptadores históricos.
- [Plan](../evaluation/phase4c2_prospective_timing_pilot_v1/plan.json): tres
  candidatos, seis reservas y administración, con fuentes/código/protocolo fijados
  por hash. No contiene horas, personas asignadas o contenido de noticias.
- Esquemas Plan/Authorization/Event/Attestation en
  `evaluation/phase4c2_prospective_timing_pilot_v1/schemas/`.
- Dos plantillas bajo ese directorio: autorización de la primera sesión y
  elegibilidad posterior, ambas inválidas hasta completar declaraciones reales.
- [Tests](../tests/unit/test_prospective_timing_pilot.py): solo datos y relojes
  ficticios, kind=synthetic_fixture y rutas temporales. No producen mediciones
  reales ni referencias semánticas.

Los modelos temporales históricos aportan convenciones reutilizadas, pero su CLI
exige exactamente seis casos originales; el contractual requiere cierres factuales
históricos concretos. No se amplían sus inventarios, enums o guards.

## Reservas sin actividad

| `D-5f21ec91317d6943` | factual | `pt-7876c40dc93144768f9d1adc19b8b052` |
| `D-5f21ec91317d6943` | contractual | `pt-6b6229bbaf244855961ade9d32008070` |
| `D-8d5314f2c5c04bdf` | factual | `pt-11554b077981407b9e17fc2cd1103405` |
| `D-8d5314f2c5c04bdf` | contractual | `pt-2c281cb582d74a07a6e8cc701809febb` |
| `D-bcc9cce8989c97da` | factual | `pt-433d00de8de542fdb67410a0380e0e30` |
| `D-bcc9cce8989c97da` | contractual | `pt-f1a5b759d7a540299035c5d2b50b95ac` |

Administración del lote: `pt-7703596798234aa4aae9e3b45653abb5`, registro distinto de las
seis sesiones por caso. Una reserva no es una apertura ni una medición iniciada.
Los IDs no usan fechas ni identidades históricas.

## Fases y separación de actividades

| Etapa | Fase exacta | Alcance |
| --- | --- | --- |
| Factual | factual_reading | Primera lectura del paquete factual neutral |
| Factual | factual_annotation | Preparar/verificar el contenido factual, con asistencia declarada |
| Factual | citation_check | Comprobar texto literal, evidencia, campo y offsets |
| Factual | factual_owner_review | Revisión y decisión factual de la persona, sin llamarla independiente |
| Contractual | contract_reading | Leer factual fijado y referencia técnica exacta v3 |
| Contractual | contract_mapping | Examinar representabilidad de todos los fact_id |
| Contractual | contract_check | Comprobar cobertura, evidencia, límites y coherencia |
| Contractual | contract_owner_review | Revisión final del contenido contractual |
| Lote | batch_administration | Preparación operativa y comprobaciones administrativas del lote |

Preparar una consulta o leer una respuesta es activo en su tarea; esperar una
respuesta es pausa ai_wait. Break/interruption/other se declaran como pausas.
La modalidad se fija por sesión: manual_human o manual_chatgpt_owner. Modelo
visible desconocido queda null; no se infieren snapshot, parámetros o tokens.

No contabilizar simultáneamente fases, casos o administración. Incluso una sesión
pausada bloquea empezar otra: para cambiar a administración hay que terminar
honestamente el alcance actual o dejar el lote pendiente, no reclasificar espera
como trabajo. Preparar autorizaciones antes de una sesión se registra como
administración si se quiere medirlo; no se añade retrospectivamente al caso.

No hay mínimo o máximo objetivo de duración. Las fases exigibles deben tener
intervalos realmente observados para ser elegibles. Detener sin cubrir una fase
conserva el registro, pero no permite atestar cobertura completa. Un cero registrado
no prueba que una actividad humana no haya existido fuera del reloj.

## Autorización y familiaridad

Cada inicio exige un archivo Authorization oficial completo, explicitamente
autorizado por el propietario, vinculado al fingerprint y session_id. Se conserva
null para authorized_at/source_message_id desconocidos. La autorización no es un
timestamp de inicio; el CLI captura UTC real al recibir clock start, sin --at.

En factual: first_reading=true, unseen_counterfactual=true y
familiarity_confirmed=true deben ser declaraciones reales. No usarlas por defecto.
En contractual: first_reading=false; declarar que el material ya fue conocido
en la sesión factual. Se exige su tip final, hash de artefacto factual y
factual_content_ready=true. No copiar tiempos ni confundir esa declaración
con validación semántica del artefacto.

Los artefactos factuales/contractuales se elaborarán solo durante una futura
ejecución autorizada. Este instrumento mide y vincula: no adjudica hechos, exige
una verdad de referencia ni aprueba mappings. El propietario debe cumplir la
rúbrica factual (13 dimensiones y citas) y la revisión de todos los hechos.
La referencia a un artefacto con case_id correcto no certifica esa completitud.

## Lectura, validación y estados

El preflight validate es offline, de lectura, sin .env, credenciales o proveedores.
Con cero eventos informa seis unfilled, administración unfilled y cero elegibles.
No crea la carpeta de mediciones. No usar los CLI históricos para este plan.

Los eventos son inmutables, secuenciales y encadenados por SHA-256, con vínculos
a plan y autorización. El lector rechaza tiempos sin zona/futuros, orden inválido,
cambios de autorización, etapas superpuestas y corrupción. Una parada no puede
reabrirse o recibir eventos. El directorio de registros está fijado por el plan;
no se reutiliza la autorización en otra ubicación.

Stop termina el reloj sin aprobar contenido ni asignar elegibilidad. Attest exige
otra declaración real vinculada al tip: tarea terminada, registro completo,
familiaridad y asistencia declaradas, sin multitarea no registrada y alcance exacto.
Se puede registrar exclusión explícita con scope vacío. Ni siquiera una atestación
aceptada autentica el trabajo humano: la salida declara structural_validation_only.
La persona atestante conserva su identidad y fuente; no se inventa independencia.

Un lock obsoleto, archivo parcial o escritura fallida bloquea nuevas operaciones;
no hay reparación automática, sobrescritura o retries. Conservar los registros e
inspeccionar el error. El uso es secuencial por un operador.

## Retención y métricas

Metadata temporal y elegibilidad derivada: 90 días desde el stop de la propia
sesión, sin renovación por una atestación posterior. Al vencer, se bloquea su
consulta, exportación o uso en el lector; tampoco material puede eludir ese gate.
No se implementa purga ni se extiende retención histórica. Sesiones sin stop
son incompletas y no producen un resultado elegible.

No se copian respuestas de proveedor. Si en otro trabajo existieran, conservarían
TTL de 24h. No persistir aquí prompts, respuestas o información restringida.

Mediciones futuras: tiempo activo y pausa por sesión, fases y total pareado por
caso; administración del lote separada. Revisiones del propietario están incluidas
en activo, no se suman otra vez. Totales de sesiones abiertas son provisionales:
solo suman intervalos ya cerrados. Tres casos no sustentan p95, capacidad poblacional
o forecast validado para 192 respuestas.

La familiaridad y elegibilidad actuales siguen pendientes. La evaluación de
salidas, desacuerdos auténticos y adjudicación independiente no están medidas.

## Procedimiento futuro de la primera sesión — no ejecutar todavía

Primero: autorización posterior de ejecución; confirmar candidato no visto,
modalidad, responsable y capacidad real. El propietario debe completar una copia
de AUTHORIZATION-TEMPLATE.json, sin convertir null en declaraciones no confirmadas.
Guardar la copia fuera del directorio de eventos, por ejemplo en
`data/cache/news_prospective_timing_pilot/authorizations/first-factual-v1.json`.
No modificar la plantilla fijada ni usar una autorización histórica.

Preflight que sí es seguro ejecutar ahora:

```powershell
$p = 'evaluation/phase4c2_prospective_timing_pilot_v1/plan.json'
$r = 'data/cache/news_prospective_timing_pilot/calibration-v1'
python -B tools/evaluation/prospective_timing_pilot.py --plan $p --records $r validate
```

Solo al comenzar efectivamente la lectura, después de autorización específica:

```powershell
python -B tools/evaluation/prospective_timing_pilot.py --plan $p --records $r clock start --session pt-7876c40dc93144768f9d1adc19b8b052 --authorization data/cache/news_prospective_timing_pilot/authorizations/first-factual-v1.json --phase factual_reading --confirm-start
python -B tools/evaluation/prospective_timing_pilot.py --plan $p --records $r material --session pt-7876c40dc93144768f9d1adc19b8b052
```

El segundo comando muestra material local solo durante lectura activa autorizada.
No se ejecutó contra los candidatos en esta entrega. Para fases posteriores usar
clock phase --session ID --phase FASE; pausas clock pause --session ID --reason
ai_wait/break/interruption/other; reanudación clock resume --session ID --phase FASE;
parada real clock stop --session ID. Esos comandos no aprueban contenido.

No usar stop como sustituto de pausas ni inventar actividades para completar fases.
No ejecutar contractual antes de fijar el factual y autorizar su nueva sesión.
Attest --decision ARCHIVO solo después de revisión real del registro, no
automáticamente al detener. Las plantillas no representan decisiones del propietario.

## Validaciones y alcance pendiente

Pruebas locales ficticias:
`python -B -m pytest -p no:cacheprovider tests/unit/test_prospective_timing_pilot.py`.
Deben cubrir autorización, seis sesiones simuladas, administración, no duplicación,
retención, cadenas, familiaridad, separación del material y protección histórica.

Los seis expedientes históricos, sus factuales, cronómetros y cierres no cambian.
Conservar integral_pilot_completed=false, semantic_truth=not_assessed,
factual_timing_rehabilitated=false y fase oficial implemented_pending_external_review;
Phase 4C.3 permanece not_started. La CLI devuelve esas limitaciones, nunca un gate
de cierre integral.

El experimento v3/v4 sigue requiriendo referencias/procedencia, revisión de salidas,
capacidad y calendario TTL, desacuerdos/adjudicación pertinentes, freeze reservado,
runtime probado, perfiles y presupuestos vigentes y autorizaciones nuevas.
No genera ni ejecuta aquí ninguno de esos trabajos.

Fuentes: [ADR-041](decisions/ADR-041-bounded-assisted-development-review-closure.md),
[plan original](../evaluation/phase4c2_development_corpus_v1/pilot-plan.json),
[instrumento](../evaluation/phase4c2_semantic_review_workshop_v1/instrument.json),
[capacidad](../evaluation/phase4c2_semantic_review_workshop_v1/capacity.json),
[disposiciones](phase4c2-pilot-review-dispositions.md),
[adaptador contractual](phase4c2-pilot-contract-adapter-v1.md) y
[protocolo v3/v4](phase4c2-v3-v4-experimental-protocol.md).

