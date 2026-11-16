# Phase 4C.2 — Expediente para revisión técnica externa — v1

## Autoridad, estado y alcance

Preparación documental solicitada por el propietario en la conversación mediante
«Preparación del expediente para revisión técnica externa». No es la revisión
externa, un dictamen ni una autorización de cierre o transición. Autor de esta
compilación: asistente de desarrollo, con asistencia de ChatGPT; no revisor
independiente. No se inventan timestamp de aprobación, firma o ID de mensaje.

Se solicita determinar si el alcance implementado de 4C.2/4C.2.1/4C.2.2 admite
cierre técnico, qué defectos o evidencia faltante lo impiden y qué condiciones
requiere una eventual 4C.3. No se solicita certificar precisión poblacional,
rentabilidad, exposición económica ni aptitud operativa.

El expediente comprende este documento, la [matriz v1](phase4c2-external-technical-review-matrix-v1.md),
el [inventario con SHA-256](phase4c2-external-technical-review-evidence-v1.json)
y la [plantilla de dictamen](phase4c2-external-technical-review-verdict-template-v1.md).
Estos son documentos nuevos: no superseden las fuentes normativas ni los expedientes.
El inventario fija las versiones de las fuentes; las líneas citadas corresponden
a esas versiones. Un hash es una comprobación de integridad, no una firma.

## Resumen ejecutivo

- Fase oficial y subfases: `implemented_pending_external_review`; 4C.3 `not_started`.
- Hay integración opt-in por router, salida estructurada y validación local,
  presupuestos durables, persistencia versionada, caché, TTL y replay.
- La selección de citas v2 resuelve coincidencias exactas únicas y después aplica
  los validadores originales. El contrato económico v3 separa identidad,
  participación, relación, contexto e impacto potencial. No estima retornos.
- Seis expedientes asistidos tienen cierre factual lateral y contractual:
  74 mappings, 78 dimensiones y 159 apariciones de citas; seis mappings
  `structured` y 68 `faithful_partial_only`. Son descripciones del instrumento,
  no aciertos del NewsAgent ni observaciones independientes.
- La corrida histórica de 32 casos registra una interpretación, dos abstenciones
  y 29 rechazos. El contenido expiró: no permite completar hoy su examen semántico.
- No están demostradas la calidad semántica independiente, la medición temporal
  integral ni la capacidad operativa del experimento v3/v4. Este no fue ejecutado.
- La evidencia permite solicitar revisión, sin anticipar que deba aprobarse.

Se conservan `integral_pilot_completed=false`, `semantic_truth=not_assessed`
y `factual_timing_rehabilitated=false`. Ninguna constatación documental cambia
esos campos o habilita Feature Store, modelos, cartera, riesgo o ejecución.

## Lectura y alcance técnico verificable

Orden recomendado: fuentes normativas y matriz; implementación y tests;
evidencia histórica sanitizada; seis expedientes ficticios cuando su acceso esté
autorizado y vigente; riesgos y plantilla. No empezar mirando una conclusión propuesta.

| Área | Implementación a inspeccionar | Pregunta de control |
| --- | --- | --- |
| Transporte y router | `llm/openai_client.py`, `llm/openai_settings.py`, `llm/router.py`, `agents/news_interpretation/service.py` | ¿Rutas/modelos/capacidades explícitos, JSON estricto seguido de validación, sin herramientas/fallback ni llamadas offline? |
| Configuración y secretos | `core/environment.py`, CLI smoke/evaluación y sus pruebas | ¿Carga de `.env` solo tras autorización real, sin override, sin claves en YAML/logs/errores? |
| Contratos e identidad | `schemas.py`, `grounding.py`, `economic_attribution.py`, `runtime_schemas.py` | ¿Conviven v1/v2/v3 y attempts v1–v4 sin renombrar ni migrar evidencia histórica? |
| Evidencia y semántica | `grounding.resolve_quote_fields`, `replay.validate_payload_evidence`, `economic_attribution.validate_attribution` | ¿Cita única, campo/revisión correctos, etapa/números/negación e identidad separada de participación? |
| PIT | `inputs.py`, validadores de request/replay | ¿Revisión/registry/contexto elegibles al cutoff y disponibilidad derivada honesta, sin backdating? |
| Costes | `budget.py`, `runtime_schemas.py`, `service.py`, `llm/pricing.py`, `llm/cost_tracker.py` | ¿Reserva por solicitud/corrida, cuatro categorías de precio, desconocidos conservados y parada por sobrecoste? |
| Persistencia | `persistence.py`, modelos de intentos y pruebas de replay | ¿Inmutabilidad, claves completas, hashes y TTL antes de entregar contenido? |
| Diagnóstico P0 | `diagnostic_events.py`, `diagnostic_sidecar.py`, runner y overlay | ¿Metadata sanitizada, captura en la rama original, opt-in, manifest y retención independiente sin backfill? |

Los nombres abreviados corresponden a `src/investment_system/agents/news_interpretation/`
salvo prefijos indicados. El inventario incluye rutas completas y hashes.
Una revisión de código debe inspeccionar también las ramas de error, no solo el
camino aceptado. La tabla no constituye una conclusión de corrección exhaustiva.

## Casos críticos y significado de los expedientes

Los seis formularios y sus referencias canónicas están en el manifiesto
`data/cache/news_development_pilot/contract-D-6c6ef03a91cca2a9-attempt01/manifest.json`.
Su inventario derivado aquí solo contiene IDs, conteos y vínculos; no copia
sesiones, citas ni contenido de proveedor. La revisión manual no ejecutó Nacho.

| Caso | Hechos/mappings | Distinción que debe comprobar el revisor |
| --- | ---: | --- |
| D-293a6cbca3479505 | 11 | Publicación no acredita fecha efectiva; ausencia de previsión no es producción cero; identidad nominal no es identidad bursátil resuelta. |
| D-a8db3a0c74d93eb8 | 13 | Magnitud física conjunta frente a ingresos por cada mes; bruto no es neto; intento 02 derivado del 01, no revisión independiente nueva. |
| D-fbf4c5c9e02691b3 | 12 | Un código definido en esa fuente puede describir habilitación operativa sin demostrar producción efectiva, plena capacidad o retorno. |
| D-40e8a2188273506b | 12 | Fecha efectiva del permiso y timestamp de publicación son funciones distintas, aunque compartan día; registry vacío no prueba inexistencia bursátil. |
| D-1211fcda178c57ab | 14 | Importe bruto conjunto de enero–marzo, no mensual; no distribuir las toneladas por mes ni inventar año, contraparte, costes o rentabilidad. |
| D-6c6ef03a91cca2a9 | 12 | R7 no está definido aquí: no trasladar el glosario de otro caso ni inferir cierre, aceptación, puesta en servicio o producción. |

Cada hecho conserva sus evidencias y una de 13 dimensiones. La obligación material
no sustituye la revisión de todos los hechos. Ausencia de documentación no significa
inexistencia, importe cero ni negación del acontecimiento.

`faithful_partial_only` reconoce límites de representación: parte del significado
solo puede conservarse mediante narrativa, unknown/null o limitaciones. No promete
extracción estructurada completa, aceptación del modelo o verdad semántica.
`allowed_outcomes=[interpreted, indeterminate]` pertenece al instrumento manual;
no añade un estado ejecutable al contrato económico v3. Campos no admitidos no se
introducen al DTO para salvar una representación imposible.

Las diferencias documentadas se conservan: criterio/granularidad de identidad en
los casos 1/4; `recorded` frente a `insufficient` en roles/fechas de los casos 2/5;
`event_stage=indeterminate` del sexto frente a una explicación narrativa más
genérica; lenguaje provisional preservado en rationales ya aprobados.
Fuente: [cierre acotado](phase4c2-bounded-assisted-development-review-closure-v1.md),
líneas 196–218. El revisor debe valorar su efecto; esta compilación no adjudica
ni modifica esos juicios.

## Evidencia de evaluación y límites de acceso

El freeze exploratorio de 32 casos conserva SHA-256
`1484dab560f898c71a857c40d3fe9ee3312981cbafdfa2eb4936b1e093fbfb39`.
Sus referencias asistidas no son ground truth humano independiente. El freeze se
verifica por bytes; este expediente no revela anotaciones ni ejecuta comparación.

El [diagnóstico TTL](phase4c2-rejection-diagnosis-ttl-limited.md), líneas 8–66,
documenta 32 contenidos expirados y los diagnósticos primarios agregados:
22 `stage_not_supported`, tres `unknown_evidence_id`, tres `numeric_fidelity`
y uno `negation_lost`. No se conoce por metadata suficiente la causa semántica
de cada respuesta ni se puede certificar la interpretación aceptada. No se
atribuyen los 29 rechazos a un validador defectuoso o al modelo sin evidencia.

La mejora P0 es observabilidad para futuras corridas, no reparación retrospectiva.
V4 draft2 es candidato no activado; fixtures offline no prueban adherencia del LLM.
No recuperar intentos, exportaciones, backups o conversaciones para sortear el
TTL de respuestas de 24 horas. El inventario excluye esos cuerpos expirados.

Los seis expedientes ficticios pueden consultarse mediante sus lectores vigentes;
la metadata temporal contractual tiene TTL de 90 días desde su propio final.
Los hashes de metadata caducada no autorizan leerla. No copiar intervalos a un
informe para conservarlos después del vencimiento. La documentación es un
snapshot de comprobaciones, no una renovación de retención.

No se incluye contenido Finnhub. Sigue bloqueada su entrega externa hasta
verificar derechos y obtener autorización. El requisito de positivos reales de
la revisión de atribución no queda satisfecho por cambiarles el nombre a
positivos sintéticos ni por invocar una revisión de código.

## Pruebas: evidencia histórica y comprobaciones de preparación

| Registro histórico | Resultado registrado | Fuente exacta |
| --- | --- | --- |
| Integración 4C.2 | 468 passed; subconjunto 75 | `docs/phase4c2-review.md:204–219` |
| Grounding 4C.2.1 | 548 passed; 36 regresiones nuevas | `docs/phase4c2-1-grounding-review.md:153–166` |
| Atribución 4C.2.2 | 586 passed; 38 nuevas | `docs/phase4c2-2-economic-attribution-review.md:99–108,135–153` |
| P0 | 753 passed; 32 nuevas | `docs/phase4c2-p0-diagnostic-sidecars.md:144–157` |
| Integración P0 | 770 passed; 17 dedicadas | `docs/phase4c2-runner-p0-integration.md:109–116` |

No sumar estos resultados como muestras independientes ni atribuirlos a esta tarea.
El inventario enumera tests de runtime, PIT, grounding, atribución, costes, secretos,
sidecars, compatibilidad, relojes y disposiciones. Una prueba contra una simulación
comprueba infraestructura/contrato; no precisión, recall o seguridad de un LLM real.

Comprobaciones ejecutadas durante esta preparación:

- Lectores offline de contrato, disposiciones y plan temporal: correctos; seis
  contratos completos, seis cierres factuales laterales, cero elegibles medidos,
  seis reservas temporales `unfilled` y ninguna inferencia o llamada de proveedor.
- `python -B scripts/validate_data.py`: correcto; 905 capturas/revisiones,
  811 artículos, cero hashes inválidos, linaje faltante o duplicados; cuatro snapshots.
- Resultado de la suite actual y conservación del inventario previo: registrados
  en la sección `preparation_checks` del inventario, sin confundirlos con los históricos.

Reproducción posterior explícita, sin ejecutar transiciones: usar los tres comandos
`--validate` del inventario. Los tests normales bloquean red/DNS y aíslan `.env`
en temporales (`tests/conftest.py:6–29`). No ejecutar smoke, runner real, comparación,
comandos de apertura/cierre, limpieza o renovación de perfiles. No se compila con
`compileall` en esta preparación: crearía bytecode innecesario para documentación.

## Riesgos y posibles bloqueantes, por prioridad

La prioridad siguiente es una recomendación de triage para el revisor, no nuevos
umbrales de aceptación aprobados. Ninguna brecha se convierte aquí en defecto
técnico demostrado sin un test, reproducción o evidencia que lo sustente.

1. **Alta — condición normativa no demostrada:** ADR-032:68–70 exige política
   congelada y casos nuevos adjudicados externamente antes del cierre técnico o
   integración. La revisión de atribución:127–133 añade positivos reales y revisión
   ciega por dimensiones. Debe dictaminarse cumplimiento o la necesidad de una
   decisión metodológica explícita distinta; no dar por satisfecha con desarrollo.
2. **Alta — evidencia semántica incompleta:** los 32 resultados históricos no pueden
   revisarse plenamente tras su TTL; rechazos abundantes, recall desconocido,
   atribución y falsas confirmaciones pendientes. No hay garantía de que un caso
   estructuralmente aceptado sea semánticamente correcto.
3. **Alta para integración — límites económicos:** identidad/registry no demuestra
   participación ni exposición; una relación citada no prueba causalidad o retorno.
   Los consumidores deben respetar `confirmed_exposure=false` y `operational=false`.
   Cualquier integración que lea tickers anidados como exposición debe bloquearse.
4. **Alta para experimento — capacidad y versiones:** faltan mediciones pertinentes
   de revisión de salidas/adjudicación, responsables/calendario TTL, freeze reservado,
   runtime de v4 y perfiles/autorizaciones vigentes. No usar el runner de 32 como
   sustituto silencioso del experimento de 96 casos por brazo.
5. **Media — heterogeneidad del instrumento manual:** las diferencias de clasificación
   de los seis casos impiden tratarlos como una referencia homogénea calibrada.
6. **Media — tiempo y exposición:** el piloto temporal está sin iniciar; no hay
   evidencia suficiente de primera exposición de los candidatos anteriores ni
   custodia resuelta para materiales nuevos. Es brecha de medición, no por sí sola
   un defecto del transporte, presupuesto o resolver.
7. **Media — documentación histórica:** algunas entregas narran estados de su propia
   fecha; PROJECT_SPEC:207 aún describe clientes como stubs frente a la integración
   posterior de :147–174. No corregirlo silenciosamente aquí. La procedencia y el
   código fijado deben resolver qué afirmación es histórica; registrar el hallazgo.
8. **Operacional pendiente:** limpieza física, derechos de contenido, acceso local,
   vigencia de precios/capacidades y cuenta real no se certifican con fixtures.
   Serán requisitos antes de las operaciones reales correspondientes, no una
   autorización implícita por el mero dictamen documental.

## Frontera con calibración y Phase 4C.3

ADR-041 reconoce solo el cierre asistido. ADR-042 añade preparación temporal;
no establece tres mediciones como gate universal de fase. Estas no deben bloquear
solicitar el dictamen, pero tampoco se declara resuelta su finalidad temporal.
El diseño v3/v4 sí exige capacidad medida y calendario antes del freeze reservado
(`docs/phase4c2-v3-v4-methodology-readiness.md:161–201`). Tres ciclos manuales no
demostrarían capacidad para 192 salidas ni adjudicación independiente.

No existe en las fuentes examinadas un checklist único ejecutable que autorice
4C.3 automáticamente. Antes de iniciarla deben existir: dictamen de alcance
explícito; resolución de defectos bloqueantes y de las condiciones normativas;
decisión del propietario sobre un eventual cierre limitado y pendientes;
definición concreta del trabajo siguiente, sus dependencias y autorización nueva.
La ausencia de un gate temporal universal no equivale a permiso para integrar.

La preferencia por dos humanos/otra familia de IA no se convierte en obligación
universal. La alternativa IA admite recomendar cierre técnico limitado tras
revisar evidencia/casos críticos (`phase4c2-2-ai-assisted-exploratory-evaluation.md:162–175`);
no satisface verdad humana independiente ni concede 4C.3. Si se propone diferir
una condición explícita de ADR-032, se debe exponer para decisión metodológica
versionada del propietario: ni el compilador ni un resultado favorable la eliminan.

## Entrega a una instancia separada y decisión pendiente

Esta tarea prepara; no envía archivos ni ejecuta un revisor. El propietario debe
autorizar el procedimiento/revisor y el acceso a materiales. Para una segunda IA,
usar conversación separada sin historial de desarrollo ni conclusión deseada;
entregar el expediente y fuentes permitidas fijadas por hash, no credenciales,
`.env`, árboles completos de caché, Finnhub, respuestas expiradas o casos reservados.
No atribuir independencia humana a esa IA ni inferir snapshot/parámetros desconocidos.

Solicitar que el revisor declare identidad/etiqueta real, asistencia, exposición,
alcance, archivos efectivamente consultados y limitaciones. Debe separar revisión
técnica de adjudicación semántica externa y dar evidencia archivo/línea para
hallazgos. Si no tiene acceso a una fuente local, marcar no demostrado; no reemplazarla
con la afirmación de este expediente. Revalidar TTL y hashes antes de acceso futuro.

El conjunto es autocontenido para entender la solicitud, criterios, evidencia y
limitaciones; la inspección técnica completa requiere las fuentes referenciadas.
No se crea un archivo exportable que duplique evidencia protegida. El inventario
permite una entrega selectiva posterior, no autoriza distribuir todos sus archivos.

Responder las diez preguntas de la plantilla sin veredicto preseleccionado.
Después, el propietario deberá decidir expresamente si acepta el dictamen,
qué condiciones debe resolver y qué alcance de cierre/transición autoriza.
No se cambia ninguna fase o estado agregado durante esta preparación.
