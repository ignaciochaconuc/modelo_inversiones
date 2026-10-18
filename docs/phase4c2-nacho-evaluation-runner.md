# Phase 4C.2.2 — Ejecutor de evaluación Nacho preparado

Estado actual: `nacho_evaluation_runner_p0_integrated_pending_authorization`.
Véase [integración P0](phase4c2-runner-p0-integration.md) y ADR-035. El texto
siguiente registra la preparación original; la corrida histórica posterior
run01 permanece intacta y no se reutiliza. No hay nueva inferencia autorizada.
Phase 4C.3: `not_started`.

## Componentes y alcance

- CLI: `scripts/run_phase4c2_attribution_evaluation.py`.
- Instrumentos: `tools/evaluation/nacho_attribution_runner.py`.
- Perfil explícito: `config/news_interpretation.evaluation.yaml`.
- Tests: `tests/unit/test_nacho_attribution_runner.py`.
- Decisión: ADR-033. No modifica los contratos/prompts/validadores existentes.

Reutiliza el pipeline real etiquetado NewsAgent: NewsInterpretationService,
LLMRouter, OpenAIClient, RunBudget, CostTracker, pricing v2, resolver de citas y
atribución económica v3/runtime v4. El NewsAgent público sigue siendo un stub;
no se conecta su AgentResponse con producción ni se añade Feature Store.

El freeze se acepta solo con SHA-256
`1484dab560f898c71a857c40d3fe9ee3312981cbafdfa2eb4936b1e093fbfb39`.
Se reconstruyen los ocho registros y B04 editorial antes de preparar el plan.
Solo el plano de control lee las referencias; el adaptador y el LLM reciben los
textos originales y la tabla neutral, nunca anotaciones, respuestas esperadas,
strata ocultos o resultados ChatGPT. La herramienta no calcula ni ejecuta scoring.

## Conversión sintética y PIT

Los originales se leen de `evaluation/phase4c2_attribution_v1/prepared/reviewer/`:
`blind_synthetic_evidence.json` y `identity_lookup.synthetic.json`. Se verifican
sus hashes mediante el manifest preparado y los 32 fingerprints de texto.
No se consulta NewsStore, Finnhub ni registry de producción.

El único reloj disponible es `virtual_decision_time=2026-10-13T00:05:00Z`.
Se usa para los campos obligatorios de observación/disponibilidad/ingesta de una
fixture sintética, no como timestamps históricos observados. La política de
adaptación figura en el plan. `published_at` y `event_date` quedan null, sin URL,
target, snapshot, ticker de proveedor ni contexto adicional. La generación y
disponibilidad derivada mantienen timestamps reales posteriores al freeze.

Se conservan nombres/security IDs/tickers FIC originales, effective_from y known_at.
No se añaden aliases ni tickers reales. Nueve entradas son elegibles: Quillan es
futura para ese reloj y se excluye; las dos clases de Seabright conservan una
identidad corporativa compartida y securities distintos, sin resolver ambigüedad.
Los IDs de entidad son identificadores deterministas de fixture, no atribuciones
económicas. El plan registra el mapa entre IDs originales de evidencia y los
digests que exige el contrato de Nacho, sin cambiar textos/fingerprints originales.

## Precio, capacidades y presupuesto

Perfil `gpt-5.6-luna`, Responses, Structured Outputs estricto, reasoning none,
2048 tokens máximos de salida, un intento por caso. Ventana 1.050.000; límite
de entrada conservador 922.000 (ventana menos máximo de salida del modelo).
Estas capacidades y precios se comprobaron en
[OpenAI Docs del modelo](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

Tarifas estándar de contexto corto, USD/millón: entrada 0,20, caché lectura 0,02,
caché escritura 0,25, salida 1,20. La escritura no es una tarifa adicional a la
entrada: son categorías disjuntas, según
[Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).
Se bloquean solicitudes mayores de 272.000 tokens estimados para no omitir el
recargo de contexto largo. No se habilitan herramientas, tier rápido/regional
ni descuentos de Batch. Ver [tarifas](https://developers.openai.com/api/docs/pricing).

La reserva usa bytes UTF-8 del wire más 256 de framing, como cota de entrada,
multiplicados por la mayor tarifa input/read/write, más toda la salida permitida.
No cuenta con ahorros de caché. Para los 32 wires preparados:

- Cota agregada de entrada: 765.531 tokens estimados, no telemetría medida.
- Salida agregada máxima: 65.536 tokens.
- Reserva agregada: US$0,27002595.
- Límite configurable inicial: US$1,60; por caso: US$0,05.

Una reducción de presupuesto debe seguir cubriendo todas las reservas. La CLI
no puede ampliar el perfil; un cambio de perfil exige plan/autorización nuevos.
No confundir reserva o estimación con garantía de factura. Si la API no informa
alguna categoría, especialmente cache_write_tokens, el coste real es desconocido:
se conserva la reserva completa y se detienen las llamadas siguientes.
Sobreuso o telemetría inválida también detienen la corrida, sin retry.

Comprobación documental: `2026-10-14T20:39:20Z`. Vigencia local:
hasta `2026-10-15T20:39:20Z`, exclusivamente un plazo de revalidación de 24 horas,
no promesa del proveedor. Pasado ese plazo se bloquea incluso el preflight:
revisar fuentes y crear un perfil/plan actualizado antes de pedir autorización.
El alias no fija un snapshot ni prueba acceso de la cuenta.

## Preflight completamente offline

Desde la raíz del repositorio:

```powershell
python scripts/run_phase4c2_attribution_evaluation.py --config config/news_interpretation.evaluation.yaml --budget-usd 1.60 --validate-only
```

Devuelve el plan completo y plan_fingerprint, hashes de freeze, código, perfil,
fuentes, requests y wires, bindings y reservas. No lee/carga `.env`, consulta
claves, crea clientes de red activos, budgets, cache ni resultados de inferencia.
Preparar el wire usa el adapter deshabilitado/puro existente, no su transporte.
No enviar el informe de referencias al modelo. Preflight tampoco exporta
anotaciones ni genera respuestas esperadas.

Plan comprobado durante esta preparación:
`5a2af4a9a266cb27ff8ad9b57e68a652fa79889fc91ed44804b89e2977cf3281`.
Reejecutar el preflight antes de autorizar; si cambian código, perfil o presupuesto,
usar su nuevo fingerprint, no copiar retrospectivamente este identificador.

## Autorización posterior: NO concedida por esta entrega

El propietario debe revisar el preflight final y autorizar por separado hasta
32 llamadas, US$1,60 como límite, un intento por caso, modelo/perfil exactos y
retención. Crear luego un JSON local con esta estructura; esta plantilla
deliberadamente incompleta y no aprobada NO permite ejecución:

```json
{
  "version": "nacho-evaluation-authorization-v1",
  "approved": false,
  "authorized_by": null,
  "authorized_at": null,
  "expires_at": null,
  "plan_fingerprint": null,
  "freeze_sha256": "1484dab560f898c71a857c40d3fe9ee3312981cbafdfa2eb4936b1e093fbfb39",
  "run_id": null,
  "max_provider_calls": 32,
  "budget_usd": 1.60
}
```

Solo tras autorización real: completar responsable, fechas reales con timezone,
approved=true, plan_fingerprint exacto y un run_id nuevo. authorized_at debe ser
posterior al freeze, no futuro; expires_at debe ser posterior a la ejecución.
No inventar timestamps ni afirmar que el JSON es firma criptográfica. El plan
vincula código/configuración/sources/wires/budget; cambios invalidan la autorización.
No incluir API keys. La referencia de autorización es declarativa, no un sistema
de identidad del propietario.

Comando futuro, **no ejecutar ahora**; sustituir placeholders después de aprobar:

```powershell
python scripts/run_phase4c2_attribution_evaluation.py --config config/news_interpretation.evaluation.yaml --budget-usd 1.60 --confirm-real-inference --authorization <autorizacion-local.json> --run-id <id-nuevo-aprobado>
```

Sin flag explícito Y registro aprobado/vigente ligado al plan no se cargan claves.
Ambos modos juntos se rechazan. El loader central carga `.env` de la raíz sin
override solo después de autorización/preflight. No hay lectura de credenciales
en imports o tests normales. Antes de cada llamada se revisan autorización,
freeze/config; el servicio reserva presupuesto y revisa precios vigentes.

## Salidas futuras y comparación

Cada corrida nueva queda en el árbol local ignorado
`data/cache/news_attribution_evaluation/nacho-v1/<run_id>/`: plan.json,
authorization.json, runtime/attempts, ledger SQLite, casos y nacho-outputs.json.
No se permite sobreescribir, reanudar automáticamente o repetir el mismo run ID.
La cache y los smokes anteriores están en árboles separados y no se reutilizan.

Persistir todos los intentos v4 (salida original, resolución, validación,
proveniencia, tokens/cache/output, costes conocidos/desconocidos, timestamps,
TTL, diagnostics y fingerprints), incluso errores/rechazos/abstenciones. El
export registra siempre los 32 casos; los no ejecutados quedan not_run sin
fabricar unidades. Una excepción inesperada conserva el ledger y deja
attempt_may_have_occurred=true con revisión manual obligatoria: no atribuir
cero consumo ni reintentar automáticamente. Las salidas escritas antes del
fallo se conservan. Costes desconocidos detienen la ejecución restante.

Export compatible con la estructura del comparador existente: case_id, outcome,
attempt_started_at posterior al freeze, record_id, output_fingerprint y units
con ocho dimensiones. Preserva native_outcome cuando categoriza códigos de
transporte como transport_error y rechazos como rejected. Los valores semánticos
son datos nativos v3, no respuestas armonizadas con el gold. La comparación
literal puede marcar desigualdades de formato/vocabulario: revisar cada
desacuerdo y alineación, sin editar referencias para maximizar concordancia.
Identidad/ticker se separan de participación e impacto; ningún ticker anidado
es exposición confirmada. operational y confirmed_exposure permanecen false.

No se ejecutó la comparación real. En una futura tarea autorizada se registrará
el hash de nacho-outputs.json, se alinearán eventos/unidades y se usará el SHA-256
congelado en alignment. Referencias siguen chatgpt_assisted_exploratory_review,
sin independencia humana, precisión/recall poblacionales ni certificación causal.

Retención local de contenido: 24 horas. LocalInterpretationStore bloquea replay
expirado; no es borrado físico automático. Cualquier purga debe autorizarse y
seleccionar solo contenido expirado de esta corrida, preservando ledger,
identificadores, hashes y metadata sanitizada. No tocar referencias, smokes ni
artefactos históricos. store=false no equivale a Zero Data Retention remoto;
la configuración de cuenta/proveedor debe revisarse antes de la autorización.

## Validaciones de entrega

Se ejecutan tests con transportes simulados y temporales: preflight puro,
integridad, texto/registry/PIT, separación del wire, budgets/precios, autorización,
abstenciones/rechazos/errores, categorías desconocidas, export y comparación
únicamente con fixtures nuevas fabricadas (no el conjunto de referencias real).
Resultados finales:

- `python -m pytest`: 705 tests aprobados, 77,24 s; 30 pruebas adicionales.
- `python scripts/validate_data.py`: correcto; 905 revisiones, 811 artículos,
  cero hashes inválidos/linaje faltante/duplicados y cuatro snapshots válidos.
- `python -m compileall -q src scripts tools/evaluation`: correcto.
- SHA-256 antes/después: cero cambios en los 3.483 archivos existentes
  inspeccionados de data, src, scripts, tools, config, evaluation, docs y los
  cinco documentos raíz. Se excluyeron cachés de bytecode y únicamente los cinco
  archivos nuevos de implementación/documentación/perfil de esta tarea; el nuevo
  test queda fuera de esos árboles. El freeze original se incluye en el control.
- Preflight CLI final: 32 casos, US$0,27002595 de reserva agregada, cero llamadas
  y cero escrituras de inferencia. No existe árbol de corrida real de evaluación.

No se realizaron inferencias reales, predicciones para la evaluación, consultas
Finnhub, gasto API ni reapertura del TEST oficial. La documentación oficial fue
la única consulta web, sin credenciales ni endpoints de inferencia.
