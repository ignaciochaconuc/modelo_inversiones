# Phase 4C.2.2 — P1: alineación prompt–evidencia–validador

Estado: `phase4c2_p1_prompt_v4_proposed_pending_review`.
Fecha: 2026-10-19, America/Santiago. Phase 4C.3: `not_started`.

## Alcance y método

Propuesta offline, no activación. Se inspeccionaron conjuntamente
`prepare_economic_request` y los DTOs de economic_attribution.py;
`TRUSTED_INSTRUCTIONS_V2`, selección/resolución de grounding.py;
`validate_payload_evidence` de replay.py; NumericClaim/ExtractedNewsEvent de
schemas.py; runtime_schemas.py y ADR-031/032/034/035. El prompt v3 efectivo
incluye un encabezado económico más las instrucciones heredadas de v2: no es
suficiente revisar solo su primera cadena.

Los 22 `stage_not_supported` históricos son una hipótesis de desalineación,
no 22 falsos positivos demostrados. La metadata conservada no identifica
etapa/cita por caso. El contenido expirado no se abrió, reconstruyó ni releyó;
los resultados y referencias históricos no se adjudican nuevamente. Véase
[diagnóstico limitado por TTL](phase4c2-rejection-diagnosis-ttl-limited.md).
No se usaron anotaciones ChatGPT, respuestas de los smokes ni TEST oficial.

## Matriz de incompatibilidades y límites

Las guardias descritas son las actuales, no una recomendación de explotar sus
límites. Cumplimiento textual es necesario, nunca suficiente para confirmar hechos.

| ID / área | Prompt v3 efectivo | Regla actual / problema verificable | Propuesta v4 y límite pendiente |
| --- | --- | --- | --- |
| P1-A etapas | Distinguir anuncio/cierre sin definir requisitos léxicos | replay.validate_payload_evidence exige `announced`, `proposed`; completed exige `completed`, `closed` o `finalized`, palabras completas sin distinción de caso, en **state_evidence**, no en cualquier evidence | Semántica y literalidad simultáneas; `unknown` si falta una. `acquired` puede sostener un acontecimiento, pero no satisface completed. No reescribir citas. |
| P1-B morfología | No explica variantes excluidas | announces/announcement, proposes/proposal, completes/completion/finalised no equivalen a las palabras exigidas | Mantener unknown/limitación; estudiar equivalencias únicamente mediante otro validador versionado, no implementarlas aquí. |
| P1-C alcance temporal | Distinguir rumor/expectativa/hecho de forma general | La presencia de completed en un cierre esperado o una revisión previa puede pasar la guardia de etapa; el filtro de confirmed no contempla todas las formas futuras | Vincular etapa al acontecimiento y conservar condiciones/tiempo. P1-013/014/039 demuestran aceptación léxica insuficiente, no nuevas etiquetas correctas. |
| P1-D estado | No lista límites del filtro | confirmed se rechaza si la cita contiene rumor/rumour, unconfirmed, may/might, expect/expects/expected u opinion; el filtro no comprende todas las modalidades | No confirmar por ausencia de esas palabras ni recortar calificadores. Un anuncio confirmado no confirma el cierre. |
| P1-E cita única | v2 ya exige literalidad y unicidad | Resolver busca exactamente en el campo del ID, una sola aparición, sin normalizar Unicode/case/espacios; ni siquiera un texto idéntico autoriza cambiar de revisión | Reafirmar cita única y proposición completa; ampliar literalmente solo para desambiguar, nunca por fuzzy matching. Coincidencia no equivale a entailment. |
| P1-F IDs | Dice seleccionar evidence_id, sin delimitar namespaces | SelectedQuote acepta un digest de 64 hex aunque no pertenezca al request; resolver rechaza unknown_evidence_id o wrong_revision aun con contexto elegible | Copiar únicamente IDs de evidence de primary_revision_id; no usar case_id:field, request/revision/registry IDs, IDs inventados o anteriores. Enum por request sería cambio explícito de esquema/transporte futuro, no corrección de prompt ya implementada. |
| P1-G negación | Preservarla sin explicar alcance | La guardia busca not/never/no/denied/denies en toda state_evidence y exige negated=true, sin determinar qué proposición niega | Cita local completa cuando sea posible; no falsear negated ni recortar negación del evento. Si es inseparable, abstenerse. Un validador de alcance necesita diseño y revisión separados. |
| P1-H valores | Preservar cantidades/unidades, sin explicar representación | NumericClaim elimina comas para Decimal, compara value; busca lexema con límites y unidad/escala/período literales en context. Son seis ramas P0 diferentes | Mantener value_text y magnitud sin conversión; null solo cuando justificado. No explotar coma decimal ni omitir escala esencial. Rechazar/abstenerse frente a formato ambiguo. |
| P1-I unidades/escala/período | No delimita precisión literal | Comparación de unidad/período sensible a caso; escala enum one/thousand/million/billion y literal salvo one; `7m` falla ya en límite del número; `Million` no respalda `million` | No expandir USD, Q1, m/bn ni cambiar caso; no usar one para ocultar escala. Futuro parser de locale/abreviaturas requiere contrato nuevo. |
| P1-J puntuación numérica | Sin advertencia | `USD 4.2.` puede fallar por el punto final en la regex del contexto; `1,5` interpretado como 15 puede pasar | Contexto exacto local y fiel puede resolver puntuación, nunca cambiar el lexema. No asumir que un parseo exitoso valida locale. Cambios de límites numéricos requieren tests y revisión específicos. |
| P1-K identidad/tickers | v3 dice never return tickers, pero hereda v2: “Only eligible exact corporate names/aliases support entity_id/ticker assignments.” | La salida económica propone registry_entity_id, no un ticker plano; materialización exige nombre/alias y entrada inequívoca elegible. Producto/plataforma no admite identidad corporativa | Eliminar la instrucción heredada contradictoria en el borrador independiente; separar evidence de mención, identity_evidence y relationship_evidence. Identidad desconocida no impide representar participación textual respaldada. |
| P1-L participación | v3 pide cita específica y ofrece algunos ejemplos | validate_attribution acepta marcos ingleses limitados; direct_participant exige solapamiento de state/relationship en mismo ID; supported_indirect requiere contraparte también directa; identidad sola no demuestra rol | Explicitar roles/marcos/dirección, solapamiento y estados relacionales. No convertir un participante con sintaxis no soportada en contextual para pasar: unknown/limitación o abstención. No añadir aliases. |
| P1-M impacto | Potencial condicional, no causalidad | Potencial exige relación respaldada, estado reported/uncertain, evento no negado, evidencia solapada/nombre y rationale; eso no demuestra impacto causal ni materialidad | not_assessed cuando falte respaldo; sin impacto automático para fabricantes, contexto, ticker, padre o competidor. Nunca exposición confirmada/retornos. |
| P1-N fechas/abstención | v2 sí impone ISO y abstención | Par date/date_evidence null o ISO literal; abstained sin eventos ni claims y con razón permitida; evidencia insuficiente no es stance neutral | Reafirmar sin ampliar política. No convertir fecha textual ni usar publicación; tampoco una fecha ISO incidental prueba la fecha del evento. |

## Borrador separado y compatibilidad

Artefactos nuevos:

- [Prompt v4, draft1](../evaluation/phase4c2_p1_prompt_v4/news-interpretation-prompt-v4.draft1.txt).
- [Manifiesto de propuesta y hashes](../evaluation/phase4c2_p1_prompt_v4/proposal.json).
- [40 probes declarativos nuevos](../evaluation/phase4c2_p1_prompt_v4/fixtures.json).
- [Tests offline](../tests/integration/test_economic_prompt_v4_proposal.py).

Versión propuesta: `news-interpretation-prompt-v4`, revisión `draft1`.
Objetivo de esquema, **sin modificarlo**: `news-economic-selection-v3`.
Resolver `news-exact-quote-resolver-v1`, validación económica v3 y atribución v1
permanecen intactos. El manifiesto fija SHA-256 del borrador, fixtures y seis
fuentes de producción para comprobar la base exacta revisada.

**No es un prompt ejecutable soportado por el runtime actual.** EconomicResult y
EconomicRuntimeSettings fijan literalmente prompt-v3. Antes de una futura
activación hacen falta versiones explícitas para runtime/result/proveniencia,
preparación del wire, replay y cache identity, además de perfil vigente, nuevo
plan y autorización. No se debe modificar una cadena y persistir el resultado
como si hubiera usado v3. Cambiar solo la versión del prompt no obliga por sí
solo a rediseñar el dominio, pero sí a representar honestamente la versión en
los contratos que hoy la fijan. ADR-036 queda **Proposed**, no aceptado/activado.

Los tests evalúan respuestas **escritas a mano** contra el validador v3, no
respuestas de un modelo ni resultados v4. Una prueba construye un espécimen
textual del borrador con el mismo esquema, pero nunca un cliente o invocación.
Todos los resultados de validación se identifican correctamente como v3.

## Fixtures y alcance de la evaluación offline

40 escenarios declarativos con IDs P1-001–040, más ocho variantes nuevas de
atribución corporativa. Las empresas y textos ficticios son nuevos, disjuntos
de los originales congelados; la comprobación de disjunción solo usa textos/IDs
sintéticos originales, nunca sus anotaciones. Algunas parejas repiten el texto
y cambian la propuesta deliberadamente: no son 40 noticias independientes.

Cobertura: anunciado/cerrado/propuesto, acquired sin literal de cierre,
morfología, intención/rumor/futuro, calificadores, negación verdadera e incidental,
IDs válidos/desconocidos/contextuales, campo equivocado, repetición y Unicode;
seis ramas numéricas, unidad/escala/período/case/locale/puntuación, fecha textual;
identidad contextual, identidad sola, participante no resuelto, producto/fabricante,
sintaxis relacional no admitida, evidencia no solapada e impacto contextual indebido.
Se prueban abstención, causalidad PIT y reconstrucción determinista de fixtures.

Casos P1-013/014/019/033/039 están marcados semantic_warning: el validador acepta
la propuesta, pero eso deja abierta o muestra una falsa conclusión. Se preserva
esa aceptación como evidencia del límite, no como etiqueta semántica deseable.
También se conservan rechazos de sintaxis semánticamente plausible: no se cambia
el test para aparentar más calidad. Los ejemplos son desarrollo asistido por IA,
no referencias humanas, holdout independiente, ni evidencia de generalización.
**Pasar estos tests no demuestra que un LLM seguirá el nuevo prompt**, ni permite
estimar tasas de error, precisión, recall o mejora frente a v3.

## Riesgos y recomendación priorizada

1. Revisar primero las instrucciones v4: corregir ambigüedad, namespaces,
   evidencia por campo, negación, números y separación identidad/participación.
   Mantener unknown/abstención honesta. No activar todavía ni entrenar con el
   conjunto congelado; reservar material nuevo para una evaluación futura.
2. Diseñar **por separado**, antes de cualquier implementación, alcance de
   etapa/negación/modalidad vinculado a una proposición. El problema no se
   resuelve exhaustivamente con instrucciones: palabras presentes pueden estar
   negadas, esperadas o referirse a otra acción. Exigir nuevos contratos,
   pruebas adversariales y revisión, sin relajar reglas para la corrida antigua.
3. Investigar en versiones posteriores límites numéricos/locales/abreviaturas y
   marcos relacionales. No añadir sin revisión stemming, regex de proximidad,
   sinónimos globales, normalización financiera o parser de fechas ampliado.
4. Considerar enums dinámicos de IDs por request solo como propuesta de esquema
   versionado con compatibilidad, costes y replay comprobados. El prompt reduce
   confusión, pero no garantiza selección correcta de ID o evidencia relevante.
5. Descartar: forzar completed desde acquired; añadir tokens a citas; recortar
   negaciones/modalidad; negated=true para salvar un texto incidental; inferir
   tickers de productos/subsidiarias; pasar a contextual solo para obtener un
   resultado válido; convertir cifras/escalas o fabricar fechas; aceptar todos
   los rechazos históricos; optimizar la aceptación como objetivo semántico.

El borrador más largo también eleva contexto, riesgo de instrucciones en
competencia y coste potencial. Una activación futura requiere regenerar wires,
reservas y autorización mediante el runner con P0, no reutilizar las 32 llamadas,
el plan anterior ni el perfil vencido. El presupuesto no se renueva aquí.
Mantener la incertidumbre explícita puede aumentar abstenciones u omisiones;
esas pérdidas deben medirse separadamente de falsas confirmaciones.

## Comandos offline

```powershell
python -m pytest tests/integration/test_economic_prompt_v4_proposal.py
python -m pytest
python scripts/validate_data.py
python -m compileall -q src scripts
```

No hay comando de inferencia para el borrador: deliberadamente no está conectado
a router, CLI, perfil o agente. El perfil vencido no se modifica ni renueva.

## Validaciones de entrega

- `python -m pytest`: **822 aprobados**, 197,98 segundos; los 770 anteriores
  y 52 tests nuevos (40 probes, ocho variantes de atribución y cuatro controles).
- Suite específica: **52 aprobados**. Son respuestas manuales sintéticas, no
  resultados de un LLM ni medida de adherencia a v4.
- `validate_data.py`: separación features/targets correcta; 905 revisiones,
  811 artículos, cero hashes inválidos/linaje faltante/duplicados y cuatro
  snapshots de enriquecimiento válidos.
- `python -m compileall -q src scripts`: correcto.
- SHA-256 antes/después: **3.464 archivos existentes** de src/config/data/evaluation
  sin cambios; solo tres artefactos nuevos en la carpeta de propuesta. Prompts,
  contratos, validadores, perfiles, fuentes sintéticas originales, referencias,
  ledger y respuestas históricas se conservaron. Los hashes de artefactos y
  fuentes revisadas están en proposal.json.
- Freeze conservado:
  `1484dab560f898c71a857c40d3fe9ee3312981cbafdfa2eb4936b1e093fbfb39`.
- No se creó árbol real de sidecars ni se ejecutaron proveedores, inferencias,
  comparaciones con ChatGPT o lectura de contenido histórico expirado. Los
  archivos históricos se comprobaron únicamente como bytes opacos para hashing.
- ADR-036 sigue Proposed; estado final de P1
  `phase4c2_p1_prompt_v4_proposed_pending_review`. Phase 4C.3 sigue `not_started`.
