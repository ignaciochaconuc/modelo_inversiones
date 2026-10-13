# Phase 4C.2.2 — Evaluación exploratoria asistida por IA

Estado: `ai_evaluation_prepared_pending_authorization`.
Tipo: **`ai_assisted_exploratory_evaluation`**. Cero referencias generadas, cero
predicciones nuevas, cero inferencias y cero créditos consumidos por esta tarea.
La consulta de documentación oficial no es inferencia ni envío del corpus.

## Alcance y separación

El propietario no dispone de dos humanos independientes. Se añade una alternativa,
sin sustituir ni modificar el protocolo humano original, sus instrumentos, los
32 casos, la tabla neutral, contratos/prompts de Nacho ni producción/configuración.
El protocolo congelado 4C.1 permanece byte-idéntico. Esta alternativa no satisface
su gate de ground truth humano independiente; no se cambia ese gate silenciosamente.

Se usan exclusivamente los 32 casos ficticios ya congelados. Finnhub sigue
bloqueado para revisión externa por derechos; los 24 candidatos reales no se
incluyen en inputs, outputs o costes de este plan. Tampoco los smokes, el corpus
de desarrollo o TEST oficial. No se integra Feature Store ni se inicia 4C.3.

Familia distinta reduce potencialmente sesgos compartidos, pero no convierte al
evaluador en una fuente de verdad independiente. Referencias IA pueden omitir,
confundir o inventar relaciones. Autoría del corpus por el agente implementador,
muestra pequeña/enriquecida e inglés artificial siguen limitando las conclusiones.
Las pautas de OpenAI Docs motivan separar dimensiones y revisar limitaciones de
evaluadores automáticos, no equiparar sus decisiones con verdad humana:
[Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices).

## Opciones de evaluador y presupuesto

Documentación consultada el **13 de octubre de 2026**, America/Santiago. Son
opciones propuestas, no selección autorizada ni verificación de acceso de cuenta.

| Candidato, API estándar de texto | Entrada USD/M tokens | Salida USD/M tokens | Escenario nominal, 32 casos |
| --- | ---: | ---: | ---: |
| `claude-sonnet-4-6`, Anthropic | 3,00 | 15,00 | 1,68 USD |
| `gemini-2.5-flash`, Google | 0,30 | 2,50 | 0,264 USD |

Sonnet 4.6 es el candidato preferido por diversidad de familia y orientación a
razonamiento; su capacidad relativa **en este corpus no está demostrada**. Figura
como disponible legacy; registrar el nombre/versionado realmente devuelto, no
inventar un snapshot inmutable. Haiku 4.5 no es el candidato principal por su
ciclo legacy cercano a la primera fecha posible de retiro. Tarifas y ciclo:
[Claude Sonnet 4.6](https://platform.claude.com/docs/en/models/sonnet-4-6/overview),
[Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing).

Gemini es alternativa de menor coste. Su tarifa de salida incluye thinking
tokens; no tratar razonamiento facturable como gratuito. No habilitar búsqueda,
grounding, herramientas ni almacenamiento explícito de caché:
[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).

Escenario nominal: 2.500 tokens de entrada y 3.000 de salida por caso, un intento,
sin descuentos de caché/batch ni costes de herramientas. Fórmula:
`32 × (2500 × input_rate + 3000 × output_rate) / 1_000_000`.
Los paquetes completos suman un escenario conservador basado en bytes UTF-8 +
512 de framing por caso, con 4.096 tokens de salida: **2,569617 USD Sonnet** o
**0,388034 USD Gemini**. Esto no es tokenización oficial ni garantía de factura.
Texto generado/reasoning facturable debe entrar en el límite real del proveedor.

Propuesta: reservar **3,50 USD para un evaluador**, sin reintentos automáticos;
Nacho requiere autorización separada y hasta **1,60 USD** si se mantiene un máximo
de 0,05 USD por cada uno de 32 casos. Total propuesto: **5,10 USD**, no gastado ni
autorizado; el coste de Nacho aún no está estimado por tokens/precios vigentes.
Un segundo evaluador, una repetición o una reparación requieren autorización y
presupuesto nuevos; no están incluidos. Sus resultados no se fusionan por mayoría
silenciosa. No comparar opciones y escoger retrospectivamente la más concordante.

Antes de pagar: seleccionar y congelar modelo, endpoint/servicio, versión,
parámetros (temperatura, salida máxima, thinking real, response format), tarifas
vigentes y política de retención. Deshabilitar tools/search y caché explícita;
verificar comportamiento/cache automático y contabilizar cualquier categoría
facturable. No copiar `reasoning.effort` de OpenAI a otro proveedor. Hoy los
parámetros reales son null: no se afirma compatibilidad de una llamada no preparada.
Presupuesto/limites deben implementarse en el ejecutor autorizado: el preparador
offline estima, no reserva fondos ni impone límites remotos.

## Inputs ciegos y anotación

`evaluation/phase4c2_attribution_ai_v1/prepared/evaluator/annotation_inputs.json`
contiene 32 paquetes allow-listed: solo instrucciones nuevas de anotación, texto
sintético con IDs/fingerprints y tabla neutral de identidad. No contiene outputs,
strata, código, validadores, prompts de Nacho, smokes o resultados de desarrollo.
`ANNOTATION_INSTRUCTIONS.md` es un instrumento de anotación, **no** un cambio al
prompt de producción. Usar una sesión/request limpio por caso; no conectar repo,
memoria previa, navegación, fuentes externas ni herramientas.

El evaluador descompone acontecimientos y menciones antes de observar Nacho.
Anota corporate_identity, participation, role, relationship, ticker_link,
event_state, event_stage e impact_support de forma separada, con evidencia,
rationale breve y estatus conclusive/uncertain/insufficient/not_applicable.
Mantiene rumor/negación, anuncio/cierre, contraparte, desconocidos y potencial
frente a exposición demostrada. No fuerza conclusiones; no solicita chain-of-thought.
La tabla de identidad es ficticia, no registry/configuración de producción, con
cutoff virtual y entradas ambiguas/futuras. La evidencia neutral no demuestra
participación económica por sí sola.

## Procedencia, freeze y orden obligatorio

1. Autorizar solamente la fase del evaluador, identificando documento/ID de
   autorización, responsable, presupuesto, modelo/versión, parámetros y retención.
   No autorizar Nacho implícitamente. Conservar hash de plan/instrucciones/inputs.
2. Ejecutar 32 casos mediante un entorno autorizado del evaluador. Guardar output
   original y respuesta normalizada por separado; registrar provider/model real,
   snapshot o desconocimiento documentado de versión, parámetros efectivos,
   timestamps UTC-aware, tokens entrada/cache/escritura/salida/thinking, coste,
   estado técnico, truncamiento/error y SHA-256. No inferir ceros por telemetría
   faltante: registrar null/unknown. Retener también errores y abstenciones.
3. Importar el archivo de referencias asistidas por IA, nunca asignar identidades
   humanas ficticias. Toda conversión tiene provenance; el output original no se
   reescribe. La normalización/custodia verifica citas y coteja telemetría con los
   originales. No aplicar marcos de aceptación de Nacho al ground truth candidato:
   una referencia puede ser válida semánticamente aunque Nacho no soporte su sintaxis.
4. Congelar los 32 casos, incluidos fallos/no concluyentes, antes de ejecutar o
   revelar Nacho. El sellador verifica bindings, proveniencia declarada, cronología
   y estructura; **no certifica que un proveedor haya ejecutado realmente**, que
   la autorización sea auténtica ni que la conclusión sea verdadera. El propietario
   debe comprobar evidencias/custodia. Declarar que el evaluador no vio outputs.
5. Sellar una sola vez con SHA-256/frozen_at; rerun idéntico no cambia el tiempo.
   Cambios posteriores se archivan aparte, no reemplazan referencias. Autorizar
   Nacho por separado después del freeze; no generar anotaciones a partir de sus
   salidas ni hacer nuevas consultas al evaluador tras revelarlas.
6. Congelar exportación de Nacho y alineación manual por evento/mención. La salida
   del sistema conserva registros originales/contrato vigente, hashes, fuente y
   tiempos reales; la proyección de evaluación no altera el resultado persistido.

Actualmente existe solo una plantilla vacía de referencias IA. `freeze-references`
la rechaza, no la eleva a evaluación completa ni a ground truth.

## Comparación y revisión focalizada del propietario

El instrumento alternativo de comparación no cambia el comparador humano. Lee
valores de las referencias IA selladas, no valores de referencia copiados a mano
después de ver predicciones. Alineación `{matches:[{case_id,reference_unit_id,
system_unit_id}]}` se vincula a SHA-256 de freeze y archivo de sistema; conserva
omisiones y unidades extra, sin fuzzy matching o primeras coincidencias.
El export de evaluación de Nacho tiene los 32 casos y `units` con `unit_id` y
`dimensions` (valores normalizados de salida, nunca referencias). Cada ejecución
conserva attempt_started_at, generated_at cuando exista, record_id y
output_fingerprint; no se acepta un intento iniciado antes del freeze. Un error
de transporte no requiere inventar un timestamp de generación. No fabricar
unidades para abstenciones/rechazos.

Se contabilizan por caso interpreted, abstained, rejected/invalid_response,
transport_error, unresolved y not_run. Por dimensión: comparaciones concluyentes,
acuerdo/desacuerdo literal, no concluyentes, omisiones y estado técnico. Roles
en texto libre pueden discrepar léxicamente siendo equivalentes: revisar esa
distinción manualmente, sin cambiar las referencias para aumentar concordancia.
Reportar también fallos del propio evaluador y referencias insuficientes. La
cola del propietario conserva los 32 casos, priorizando desacuerdos/omisiones,
no concluyentes y casos críticos de producto/plataforma, contraparte, subsidiaria,
ticker/PIT, exposición, anuncio/cierre y negaciones. No descartar resultados
difíciles para mejorar una tasa.

La revisión usa `owner/focused_review.template.json`: identidad real, timestamps,
freeze/input/output fingerprints, selección, lo observado, explicación y decisión
por discrepancia. El propietario puede concluir fallo de Nacho, fallo del
evaluador, equivalencia léxica, ambigüedad o información insuficiente. Si vio
predicciones, declarar `observed_system_predictions=true`; su revisión es **del
propietario, no humana independiente ni ciega**. Resoluciones manuales quedan en
un estrato separado y no sustituyen los conteos iniciales contra referencias IA.

## Criterios de interpretación

- Acuerdo con IA no es precisión contra verdad humana. No afirmar recall,
  generalización, causalidad, retornos ni métricas poblacionales.
- Mantener panel sintético separado de fuentes reales, smokes, desarrollo y
  revisión humana futura. No llamar a este procedimiento independent holdout.
- Toda atribución sin respaldo, ticker inventado, contexto convertido en exposición,
  futuro/PIT o anuncio promovido a cierre requiere revisión crítica y puede impedir
  una recomendación de cierre; verificar primero si falla Nacho o la referencia IA.
- Alto acuerdo no habilita inversión ni 4C.3. Se puede recomendar únicamente cierre
  técnico limitado, declarando ausencia de evaluación humana independiente, tras
  revisar evidencia técnica y todos los casos críticos; no autorización automática.
- Si estos casos guían una corrección, reclasificarlos como desarrollo; repetirlos
  sirve solo como regresión. Obtener casos nuevos antes de conclusiones posteriores.

## Comandos y limitación de ejecución

Disponibles ahora, completamente offline:

```powershell
python tools/evaluation/prepare_ai_attribution_review.py prepare
python tools/evaluation/prepare_ai_attribution_review.py verify
```

Después de autorización y de obtener respuestas reales del evaluador, importar
metadatos completos en una copia de `references/ai_references.template.json`,
guardada bajo `data/cache/news_attribution_review/ai-v1/` (ignorado por Git):

```powershell
python tools/evaluation/prepare_ai_attribution_review.py freeze-references --submitted data/cache/news_attribution_review/ai-v1/ai-references.json --destination data/cache/news_attribution_review/ai-v1/references-frozen.json
```

Después del freeze, de autorización separada y de obtener/exportar Nacho:

```powershell
python tools/evaluation/prepare_ai_attribution_review.py compare --reference-freeze data/cache/news_attribution_review/ai-v1/references-frozen.json --system-file data/cache/news_attribution_review/ai-v1/nacho-outputs.json --alignment data/cache/news_attribution_review/ai-v1/alignment.json --destination data/cache/news_attribution_review/ai-v1/comparison.json
```

No se proporciona un comando que haga llamadas pagadas: el repo no dispone aquí
de un ejecutor autorizado multi-caso/multi-proveedor para este panel sintético.
El smoke CLI de noticias reales no sirve para inventar revisiones sintéticas.
No fingir que existe ese runner ni usarlo con contenido Finnhub. Tras autorización,
puede usarse una sesión limpia del proveedor con los inputs preparados y captura
de provenance; cualquier ejecución automatizada debe pasar por router/abstracción
común y requerirá implementación/autorización separada, sin alterar producción
en esta tarea. El paso de Nacho también necesita ese ejecutor antes de ser operativo.

Revalidar precios/parámetros/retención antes de esos pasos. Conservar secretos
fuera de paquetes/logs; no cargar `.env` en preparación/verificación/importación.
Las respuestas y metadatos originales permanecen en almacenamiento restringido,
con retención aprobada y cleanup explícito de copias de trabajo, sin borrar
históricos protegidos. No hay paquete externo real hasta resolver derechos.

## Validaciones

- Suite completa: 611 pruebas aprobadas; ocho pruebas nuevas mecánicas, sin
  generar referencias semánticas para el corpus. Se repite la suite tras el
  endurecimiento final del sellador.
- `validate_data.py`: correcto; 905 revisiones, 811 artículos, cero hashes
  inválidos/linaje faltante/duplicados; cuatro snapshots históricos válidos.
- `compileall -q src scripts tools/evaluation`: correcto.
- Preparación repetida de forma idéntica y verificador del paquete: 32 casos,
  cero llamadas. Plantillas de referencias y predicciones siguen sin ejecutar.
- Integridad antes/después: 3.383 archivos protegidos, cero cambios. Incluye
  producción/configuración, protocolo/paquete humano, 32 originales, smokes,
  ledger, datos/reportes históricos y comparador humano original.

OpenAI Docs orientó las cautelas sobre evaluadores automáticos y separación de
dimensiones; no se usa el evaluador como árbitro de verdad ni se integran servicios
de evaluación a producción. Phase 4C.3: `not_started`.
