# Phase 4C.2.2 — Primera corrida real controlada de Nacho

Corrida: `nacho-synthetic-20261014-run01`. Ejecución finalizada; revisión técnica
conjunta pendiente. No se declara cierre técnico de Phase 4C.2 ni se modifica su
metodología. Phase 4C.3 permanece `not_started`; ninguna interpretación es operativa.

## Autorización y preflight

El propietario Nacho autorizó expresamente este único plan: 32 llamadas como
máximo, `gpt-5.6-luna`, perfil `config/news_interpretation.evaluation.yaml`,
presupuesto de aplicación US$1,60, un intento por caso y cero reintentos.

Preflight ejecutado nuevamente y correcto: 32 casos/fingerprints originales,
freeze pinned, configuración/código/prompt v3 intactos, registry neutral PIT,
modo estricto, referencias excluidas del wire y run ID previamente inexistente.
La documentación oficial del modelo se reconsultó antes de ejecutar:
[GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna).
Mantiene las capacidades/precios usados por el perfil; no se cambió configuración.
El perfil seguía vigente hasta `2026-10-15T20:39:20Z`.

Plan fingerprint:
`5a2af4a9a266cb27ff8ad9b57e68a652fa79889fc91ed44804b89e2977cf3281`.

Reserva conservadora de los 32 wires: US$0,27002595. Reserva máxima individual:
US$0,00845135, dentro del límite de US$0,05 por caso. Las cotas incluyen la
salida máxima y la tarifa más cara de entrada/lectura/escritura, sin presumir
descuentos de caché. Son controles de aplicación, no garantía de factura.

Registro de autorización local:
`data/cache/news_attribution_evaluation/authorizations/nacho-synthetic-20261014-run01.json`.
Versión `nacho-evaluation-authorization-v1`, approved=true, authorized_by=Nacho,
max_provider_calls=32 y budget_usd=1.60, ligado al plan y freeze exactos.
authorized_at=`2026-10-14T20:59:15+00:00` y
expires_at=`2026-10-14T21:59:15+00:00`. El primero registra el momento local de
registro de la instrucción expresa recibida, no un timestamp de mensaje de
plataforma verificado independientemente; el vencimiento de una hora limita su
uso. Este registro no es una firma criptográfica y no autoriza otra corrida.

El original se conserva íntegro. La copia de autorización dentro de la corrida
es igual como objeto JSON, con serialización propia del CLI; por eso sus hashes
de bytes son distintos, sin modificación de valores o alcance.

Comando efectivamente ejecutado, **no repetir ni reutilizar esta autorización**:

```powershell
python scripts/run_phase4c2_attribution_evaluation.py --config config/news_interpretation.evaluation.yaml --budget-usd 1.60 --confirm-real-inference --authorization data/cache/news_attribution_evaluation/authorizations/nacho-synthetic-20261014-run01.json --run-id nacho-synthetic-20261014-run01
```

La CLI carga credenciales únicamente tras autorización/preflight. No se muestran
ni copian claves en este informe, YAML, wire, metadata o excepciones.

## Resultados técnicos y consumo

Inicio del primer intento: `2026-10-14T20:59:38.840391+00:00`.
Última persistencia: `2026-10-14T21:04:30.612437+00:00`.
32 intentos con respuesta del proveedor y 32 reservas enlazadas, una por caso.
Sin retries, sustituciones, cache recovery o casos omitidos.

| Categoría de informe | Casos |
| --- | ---: |
| interpreted | 1 |
| abstained | 2 |
| rejected (export nativo: invalid_response) | 29 |
| technical_error | 0 |
| not_run | 0 |

El export conserva literalmente `invalid_response`, conforme al comparador:
`rejected` aquí es la agrupación de informe, no una reescritura del resultado.
Las 29 respuestas inválidas conservan `invalid_structured_evidence`; ninguna
se reparó, descartó o sustituyó. Dos abstenciones incluyen tres motivos en total:
unattributed_rumor una vez e insufficient_evidence dos veces (pueden coexistir).

| Categoría de tokens informada | Total |
| --- | ---: |
| Entrada total | 187.704 |
| Lectura de caché (incluida en entrada) | 53.816 |
| Escritura de caché (incluida en entrada) | 133.792 |
| Entrada ordinaria restante | 96 |
| Salida | 34.794 |

Las tres categorías de entrada son disjuntas y suman el total; no se suman de
nuevo las escrituras a la entrada. Con el perfil 0,20/0,02/0,25/1,20 USD/millón,
la estimación por uso y el consumo contabilizado del ledger son
**US$0,07629632**, dentro de US$1,60. No es comprobación de factura del proveedor.
La suma Decimal de los floats persistidos es `0.0762963199999999961`; la cifra
mostrada es su representación redondeada, no una discrepancia presupuestaria.
Cero costes desconocidos, reservas pendientes, sobreusos o pérdidas de persistencia.

## Diagnósticos conservados

| Etapa / regla | Casos |
| --- | ---: |
| evidence_resolution / unknown_evidence_id | 3 |
| semantic_validation / stage_not_supported | 22 |
| internal_schema / numeric_fidelity | 3 |
| semantic_validation / negation_lost | 1 |

Ubicaciones sanitizadas: los IDs desconocidos están en
events.0.entities.2.identity_evidence, events.0.entities.1.evidence y
events.0.entities.1.identity_evidence (una vez cada una). Stage usa el código
events.state_evidence (22); numeric_fidelity aparece en events.1.numbers.0 (una)
y events.0.numbers.0 (dos); negation_lost en events.negated (una).

Son diagnósticos primarios de rechazo, no un inventario exhaustivo de errores
semánticos. No hubo rechazo primario con etapa economic_attribution/identity;
esto no prueba que todas las atribuciones sean correctas: la validación puede
detenerse antes y solo una interpretación fue aceptada. Tampoco se ha determinado
si los rechazos provienen del modelo o de restricciones excesivas del validador.
La tasa elevada de invalid_response exige revisión técnica posterior, no ajuste
automático de prompts/reglas ni selección retrospectiva de respuestas.

## Integridad, hashes y trazabilidad

Directorio local: `data/cache/news_attribution_evaluation/nacho-v1/nacho-synthetic-20261014-run01/`.
Contiene plan, autorización, 32 casos, 32 intentos v4, índices de cache de éxitos,
ledger, nacho-outputs.json y el informe sanitizado audit.json.

Se verificaron registros con el lector tipado/TTL, identidad canónica y hash,
settings v4, output v3, modelo real solicitado, request/bindings/fingerprints,
wire exacto, cadena de resolución/validación, timestamps y coste a cuatro tarifas.
Se reconstruyó cada fila del export desde su intento mediante el exportador
original y se comprobó igualdad exacta con la fila y archivo de caso persistidos.
El wire de cada intento coincide con el preflight y no contiene referencias,
anotaciones ChatGPT o resultados esperados. Los 32 intentos son posteriores al
freeze y a la autorización, y terminaron antes de vencer esta.

SQLite: PRAGMA integrity_check=ok; 32 attempt_id/cache_key únicos enlazados con
sus registros y costes/reservas exactos; cero reservas sin liquidación.
No se modificó el ledger para auditarlo. audit.json conserva hashes de los 71
archivos de corrida existentes antes de crear ese mismo informe, incluida cada
respuesta/registro de intento y archivo de caso. No hay hashes autorreferenciales.

| Artefacto | SHA-256 |
| --- | --- |
| nacho-outputs.json | c9181bee95769a0d13928d768a3490c83de2377ba93aa9f60eb4252d14479fa4 |
| plan.json | fd527ca3b4991caea7de3ed01b17eccf93f58d8379aa476560de6115776c8d6c |
| autorización fuente | c54bdb24eee5986e228dbd1357802621fa4ca03636ff753b52f97e593339daff |
| authorization.json de corrida | 59d2f87e4da59c924599f88b5bc148afec165ce976328bd826f0a3c43ebba78d |
| ledger SQLite | 7a81c5d4d8da667b9d396b3ed5a62b573bb5c97de0f80fb8a6560d3080614457 |
| freeze original | 1484dab560f898c71a857c40d3fe9ee3312981cbafdfa2eb4936b1e093fbfb39 |

TTL local intacto, 24 horas por intento. Primer vencimiento:
`2026-10-15T20:59:49.280297+00:00`; último:
`2026-10-15T21:04:30.612437+00:00`. No se purgó contenido ni se extendió retención.
No volver a cargar contenido expirado eludiendo el lector; cualquier futura
limpieza requiere autorización específica, preservando hashes/ledger/metadata.

## Validaciones y límites

- pytest completo: 705 aprobados, 81,36 s, con transporte de tests simulado.
- validate_data.py: 905 revisiones, 811 artículos, cero hashes inválidos, linaje
  faltante o duplicados; cuatro snapshots válidos; features/targets separados.
- compileall src/scripts/tools/evaluation: correcto.
- SHA-256 antes/después: cero cambios en 3.563 archivos existentes inspeccionados,
  incluyendo freeze, referencias, textos/fingerprints originales, históricos
  Phase 3/4A/4B/4C, producción, prompts, perfil, instrumentos y tests. Solo se
  excluyen el nuevo directorio de corrida/autorización/informe y bytecode.

No se ejecutó comparación con las referencias ChatGPT reales. Los tests de
comparación usan únicamente fixtures fabricadas, no este conjunto. No se abrió
TEST oficial, se descargó Finnhub, se ajustaron modelos/algoritmos/prompts ni se
modificaron contratos de producción. Las referencias conservan su clasificación
chatgpt_assisted_exploratory_review, no ground truth humano independiente.

Esta corrida acredita ejecución/custodia/contabilidad técnica, no calidad
semántica, generalización, causalidad o exposición confirmada. Primero revisar
juntos los rechazos y la única interpretación aceptada; una comparación futura
requiere tarea separada. No iniciar Phase 4C.3 ni consumir estos resultados en
Feature Store, inversiones o interpretaciones operativas.
