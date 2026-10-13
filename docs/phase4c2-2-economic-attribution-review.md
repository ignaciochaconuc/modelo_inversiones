# Phase 4C.2.2 — Economic Entity Attribution

Estado: `implemented_pending_external_review`. Phase 4C.3: `not_started`.

## Alcance y revisión inicial

Se revisaron la auditoría del segundo smoke, ADR-027–031, contratos, prompt,
resolver, runtime y protocolo de evaluación 4C.1. La identidad corporativa se
separa de participación económica, relación indirecta y contexto. No se cambia
Phase 4B, el registry, fechas, Feature Store, predicción ni inversiones.
Los dos smokes son evidencia de desarrollo: no se reejecutan, reclasifican,
modifican ni presentan como evaluación independiente.

## Contrato y compatibilidad

| Capa | Histórica | Nueva, exclusivamente opt-in |
| --- | --- | --- |
| Salida del modelo | interpretación v1 / quote selection v2 | `news-economic-selection-v3` |
| Prompt | v1 / v2 | `news-interpretation-prompt-v3` |
| Payload interno | `news-interpretation-v1` | `news-economic-interpretation-v3` |
| Resultado / replay | v1 / grounded v2 | economic v3 |
| Settings / attempt | v1, v2, v3 | v4 |
| Política de atribución | no separada | `news-economic-attribution-v1` |
| Resolver | exact quote v1 | sin cambio de política |
| Transporte / precios | v1 / v2 | v2 sin cambios |

`economic_attribution.py` contiene DTOs, materialización de identidad,
validación y replay puros. El runtime despacha por versión explícita; los lectores
admiten attempts v1–v4 sin migración. No se cambia ningún perfil existente ni el
default. `schemas.py`, `replay.py`, `inputs.py`, ADR históricos y protocolo 4C.1
se conservan. La extracción del resolver común conserva su algoritmo exacto.
La nueva caché incluye versiones de contrato/prompt/validación/configuración:
una respuesta v2 nunca se reutiliza como atribución v3.

Se conserva la salida textual original del proveedor. Las citas resueltas,
offsets, fingerprints, transformación y resultado validado se registran por
separado; el replay recalcula todo y rechaza diferencias. Un fallo no se convierte
silenciosamente en abstención ni en una interpretación válida.

## Semántica y garantías

- `direct_participant`: sujeto del acontecimiento con rol específico y evidencia
  relacional explícita que solapa la evidencia de estado del mismo campo.
- `supported_indirect`: relación textual explícita con un participante directo
  validado del mismo acontecimiento; no se hereda su rol ni su exposición.
- `contextual_mention`: mención conservada sin participación o impacto atribuido.
- `unknown`: relación no establecida; identidad corporativa desconocida cuando
  no puede resolverse. No se inventan tickers ni aliases.

La identidad requiere nombre/alias corporativo exacto del registry elegible,
cita resuelta y entrada única. Una empresa con varias securities candidatas no
se resuelve eligiendo silenciosamente la primera. Los productos y plataformas
conservan identidad desconocida: reconocer una plataforma no prueba que su
fabricante compró, vendió, participó o obtuvo un impacto económico.

La política v1 usa marcos ingleses explícitos para adquisiciones, contratos,
partnerships, financiación, regulación/litigios y relaciones indirectas de
propiedad, competencia, suministro o licencia. Firmar un contrato no determina
por sí solo cuál de las partes es proveedor. Una subsidiaria no hereda ticker
de la matriz. Sintaxis no soportada falla de forma conservadora; no hay fuzzy
matching, proximidad de palabras ni reparación semántica.

Todos los validadores históricos se ejecutan sobre una representación de
validación interna, no una lista pública de tickers afectados. Se añaden reglas
de atribución, estado relacional y potencial impacto. Rumores/negaciones no
pueden convertirse en participación reportada. Las fechas no ISO permanecen
fuera del contrato actual. Las citas pertenecen a la revisión primaria elegible
y al campo declarado; disponibilidad de fuente y resultado siguen separadas.

`EconomicReplayEnvelope.consumer_entities()` reconstruye y valida el envelope
antes de proyectarlo a `ConsumerEntity`. Contexto, desconocidos e indirectos no
producen `reported_participant` ni `economic_ticker`; contexto/desconocidos no
pueden portar impacto potencial. Incluso un participante directo reportado
tiene `confirmed_exposure=false` y `operational=false`. Son restricciones del
contrato, no una integración de inversiones ni una certificación de exposición.
El ticker anidado de identidad nunca debe usarse como feature económica.

Un impacto `potential` requiere evidencia relacional, cita propia y rationale
condicional; no se permiten señales de trading o estimaciones numéricas de
retorno. Compartir una cita no demuestra causalidad económica ni materialidad
financiera. Ninguna clasificación es una estimación de retornos.

## Configuración y operación

`config/news_interpretation.economic.example.yaml` es una plantilla incompleta
deliberadamente bloqueada, sin API keys ni precios/capacidades inventados. No
habilita operaciones reales. Para una evaluación futura autorizada se deberá
completar con información vigente, autorización de almacenamiento, presupuestos
y fuentes temporales explícitas; primero usar `--validate-only` con un perfil
válido. Este modo no carga `.env`, persiste registros ni llama a proveedores.
No se ha preparado ni ejecutado aquí un tercer smoke.

Persisten los controles originales de autorización, reservas por solicitud y
corrida, un intento configurado, telemetría y coste desconocido conservador,
retención/TTL y limpieza explícita. No se amplía la retención de los smokes.
Los diagnósticos nuevos contienen únicamente etapa, ruta de campos permitidos
y código de regla; no artículos, respuestas, secretos ni mensajes del proveedor.

## Tests y revisión técnica

38 pruebas nuevas sintéticas cubren identidades/productos/plataformas, compañías
incidentales, proveedores y signatarios, competidores, subsidiarias, relaciones
indirectas, ambigüedad de securities, atribución sin evidencia, impacto fabricado,
rumores/negaciones, fechas, citas inexistentes/de otra revisión, PIT, abstención,
replay/tampering, caché/coste/retención y preflight sin credenciales/proveedor.
Las pruebas históricas del resolver cubren Unicode, repeticiones y offsets.
Los consumidores tipados rechazan contexto con ticker/participación/impacto y
exposición confirmada o salida operativa para cualquier clasificación.

La revisión técnica verifica que la política es adicional y opt-in, no una
relajación de validación ni una aceptación retrospectiva del segundo smoke.
El contrato admite identidad desconocida y participantes privados sin inventar
securities. Los marcos de relaciones son una política explícita y limitada,
no un clasificador semántico exhaustivo. Rechazo/abstención y bajo recall son
costes aceptados provisionalmente, sujetos a revisión externa.

## Riesgos y evaluación recomendada

No existe todavía validación externa suficiente de precisión/recall de roles
económicos. Faltan construcciones complejas, idiomas, coreferencia, cambios
corporativos, cotizaciones compartidas y cobertura de entidades privadas.
Negaciones, hipótesis y citas indirectas pueden requerir contexto más amplio
que un marco literal. La evidencia textual tampoco demuestra magnitud, signo,
causalidad de impacto o retornos; revisar manualmente rationales de materialidad.
Código que eluda el consumidor validado puede malinterpretar identidades.

Antes del cierre, congelar estas versiones y adjudicar casos nuevos a ciegas,
separando identidad, rol, relación, estado y respaldo de impacto. Incluir positivos
reales, negativos de producto/plataforma y relaciones parciales; reportar también
rechazos, desconocidos y abstenciones, sin seleccionar solo salidas aceptadas.
Separar evaluación sintética, desarrollo y externa; declarar asistencia de IA y
proveniencia de adjudicación. Los smokes anteriores no son holdout. No afirmar
calidad poblacional ni alpha a partir de estas regresiones.

## Validaciones de entrega

Validaciones ejecutadas:

- `python -m pytest`: 586 passed (38 pruebas nuevas), 39,90 s.
- `python scripts/validate_data.py`: correcto; 905 capturas/payloads/revisiones,
  811 artículos, cero hashes inválidos, linaje faltante o duplicados; cuatro
  snapshots originales de enrichment válidos.
- Integridad adicional de Phase 4B v1.1: dos snapshots locales válidos contra
  las revisiones y evidencias originales, sin regenerarlos.
- `python -m compileall -q src scripts`: correcto.
- `python scripts/validate_phase3e1_holdout_protocol.py`: 44 controles correctos,
  fingerprints congelados de protocolo y snapshot preservados. Es validación
  del protocolo histórico, no ejecución/reapertura de TEST; su estado previo
  a la apertura no reemplaza el resultado histórico Phase 3E.2.
- Ambos smokes reconstruidos exactamente con `ATTEMPT_ADAPTER`, record IDs y
  SHA-256 originales coincidentes: primero `invalid_response`, segundo
  `interpreted`. TTL vigente al comprobarlos, sin extensión ni modificación.
  No se les aplica el nuevo contrato como una inferencia o reclasificación.

No se ejecuta TEST oficial ni se modifican prompts/algoritmos históricos.
Decisión: ADR-032. El cierre técnico requiere revisión externa; 4C.3 no iniciado.
